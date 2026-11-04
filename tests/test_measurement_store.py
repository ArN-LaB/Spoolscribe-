"""Registry: atomic writes, revisions, backups, restoration, links; never the catalogue."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from scripts import db_io
from spoolscribe import colour_measurements as cm, core, measurement_store as ms
from tests.support import small_db


def measurement(name="m", **conditions):
    return cm.new_measurement(cm.parse_manual("CIELAB", {"L": "50", "a": "0", "b": "0"}), name=name, conditions=conditions)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data" / "colour_measurements.json"

    def test_default_path_follows_the_patched_catalogue_path(self):
        with patch.object(core, "DB_PATH", str(Path(self.tmp.name) / "data" / "db.json")):
            self.assertEqual(ms.default_path(), Path(self.tmp.name) / "data" / "colour_measurements.json")

    def test_opening_an_absent_registry_creates_nothing(self):
        registry = ms.MeasurementRegistry(self.path)
        self.assertEqual(registry.load()["measurements"], {})
        self.assertFalse(self.path.exists()); self.assertFalse(self.path.parent.exists())

    def test_create_rename_link_detach_delete_each_write_once_with_backup(self):
        registry = ms.MeasurementRegistry(self.path)
        identifier = registry.create(measurement("first"))
        self.assertTrue(identifier.startswith("MEAS-")); self.assertTrue(self.path.exists())
        first_bytes = self.path.read_bytes()
        registry.rename(identifier, "renamed")
        self.assertEqual(Path(str(self.path) + ".bak").read_bytes(), first_bytes)
        stored = json.loads(self.path.read_text())["measurements"][identifier]
        self.assertEqual(stored["name"], "renamed")
        self.assertEqual(stored["original"]["components"], {"L": 50.0, "a": 0.0, "b": 0.0})  # values immutable
        registry.associate(identifier, "PB05001")
        self.assertEqual(registry.get(identifier)["association"], {"sku": "PB05001"})
        self.assertEqual(registry.get(identifier)["original"]["components"]["L"], 50.0)
        registry.detach(identifier)
        self.assertIsNone(registry.get(identifier)["association"])
        before_delete = self.path.read_bytes()
        registry.delete(identifier)
        self.assertEqual(registry.measurements, {})
        self.assertEqual(Path(str(self.path) + ".bak").read_bytes(), before_delete)
        with self.assertRaises(ms.RegistryError):
            registry.rename("MEAS-missing", "x")

    def test_changing_values_creates_a_new_measurement_and_keeps_the_old(self):
        registry = ms.MeasurementRegistry(self.path)
        old = registry.create(measurement("v1"))
        new = registry.replace_values(old, cm.parse_manual("CIELAB", {"L": "51", "a": "0", "b": "0"}))
        self.assertNotEqual(old, new)
        self.assertEqual(registry.get(old)["original"]["components"]["L"], 50.0)
        self.assertEqual(registry.get(new)["original"]["components"]["L"], 51.0)
        self.assertEqual(registry.get(new)["name"], "v1")

    def test_batch_is_atomic_and_two_equal_measurements_keep_distinct_ids(self):
        registry = ms.MeasurementRegistry(self.path)
        ids = registry.create_many([measurement("a"), measurement("a")])
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(registry.get(ids[0])["content_digest"], registry.get(ids[1])["content_digest"])
        snapshot = self.path.read_bytes()
        with self.assertRaises(cm.MeasurementError):
            registry.create_many([measurement("ok"), dict(measurement("bad"), name="")])
        self.assertEqual(self.path.read_bytes(), snapshot)
        self.assertEqual(len(registry.measurements), 2)

    def test_registry_bounds_leave_no_partial_write(self):
        registry = ms.MeasurementRegistry(self.path)
        registry.create(measurement("one"))
        snapshot = self.path.read_bytes()
        with patch.dict(cm.LIMITS, {"registry_count": 2}):
            with self.assertRaises(ms.RegistryError):
                registry.create_many([measurement("two"), measurement("three")])
        self.assertEqual(self.path.read_bytes(), snapshot)
        with patch.dict(cm.LIMITS, {"registry_bytes": 200}):
            with self.assertRaises(db_io.DatabaseError):
                registry.create(measurement("too big for the bound"))
        self.assertEqual(self.path.read_bytes(), snapshot)
        self.assertEqual(len(registry.measurements), 1)

    def test_corrupt_unknown_version_or_oversize_file_is_reported_not_reset(self):
        self.path.parent.mkdir(parents=True)
        for content in (b"{not json", json.dumps({"schema": cm.SCHEMA, "version": 9, "measurements": {}}).encode(),
                        json.dumps({"schema": "x"}).encode(), b"[]"):
            self.path.write_bytes(content)
            registry = ms.MeasurementRegistry(self.path)
            with self.assertRaises(db_io.DatabaseError):
                registry.load()
            self.assertEqual(self.path.read_bytes(), content)
            with self.assertRaises(db_io.DatabaseError):
                registry.create(measurement("x"))
            self.assertEqual(self.path.read_bytes(), content)

    def test_concurrent_change_is_preserved_and_refused(self):
        registry = ms.MeasurementRegistry(self.path)
        registry.create(measurement("mine"))
        other = ms.MeasurementRegistry(self.path); other.load()
        other.create(measurement("theirs"))
        with self.assertRaises(db_io.DatabaseError):
            registry.create(measurement("stale"))
        copies = list(self.path.parent.glob("colour_measurements.json.concurrent-*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), self.path.read_bytes())
        self.assertIn("theirs", self.path.read_text())
        self.assertNotIn("stale", self.path.read_text())

    def test_two_creations_after_opening_an_absent_file_do_not_overwrite_each_other(self):
        first, second = ms.MeasurementRegistry(self.path), ms.MeasurementRegistry(self.path)
        first.load(); second.load()
        first.create(measurement("first"))
        with self.assertRaises(db_io.DatabaseError):
            second.create(measurement("second"))
        self.assertEqual([m["name"] for m in json.loads(self.path.read_text())["measurements"].values()], ["first"])

    def test_final_check_before_replace_detects_a_writer_ignoring_the_lock(self):
        registry = ms.MeasurementRegistry(self.path)
        registry.create(measurement("one"))
        original_write = db_io.atomic_write

        def racing_write(path, data, *, before_replace=None):
            if Path(path) == self.path and before_replace is not None:
                Path(path).write_bytes(b'{"schema": "spoolscribe-colour-measurements", "version": 1, "measurements": {}}')
            return original_write(path, data, before_replace=before_replace)
        with patch("scripts.db_io.atomic_write", side_effect=racing_write):
            with self.assertRaises(db_io.DatabaseError):
                registry.rename(next(iter(registry.measurements)), "later")
        self.assertTrue(list(self.path.parent.glob("colour_measurements.json.concurrent-*")))

    def test_restore_is_explicit_exact_and_keeps_the_replaced_file(self):
        registry = ms.MeasurementRegistry(self.path)
        identifier = registry.create(measurement("keep"))
        kept = self.path.read_bytes()
        registry.rename(identifier, "changed")
        self.path.write_bytes(b"corrupt {")   # the live file breaks afterwards
        broken = ms.MeasurementRegistry(self.path)
        with self.assertRaises(db_io.DatabaseError):
            broken.load()
        # The product captured the revision of the unusable bytes itself; nothing is injected here.
        self.assertEqual(broken.revision, hashlib.sha256(b"corrupt {").hexdigest()); self.assertIsNotNone(broken.load_error); self.assertFalse(broken.loaded)
        restored = broken.restore()
        self.assertIsNone(broken.load_error); self.assertTrue(broken.loaded)
        self.assertEqual(self.path.read_bytes(), kept)
        self.assertEqual(restored["measurements"][identifier]["name"], "keep")
        preserved = list(self.path.parent.glob("colour_measurements.json.before-restore-*"))
        self.assertEqual(preserved[0].read_bytes(), b"corrupt {")
        # A revision that changed between preview and action is refused.
        stale = ms.MeasurementRegistry(self.path); stale.load()
        Path(str(self.path) + ".bak").write_bytes(kept)
        self.path.write_bytes(kept + b"\n")
        with self.assertRaises(db_io.DatabaseError):
            stale.restore()
        with self.assertRaises(ms.RegistryError):
            ms.MeasurementRegistry(Path(self.tmp.name) / "none.json").restore()
        bad_backup = Path(self.tmp.name) / "bad.bak"; bad_backup.write_bytes(b"[]")
        fresh = ms.MeasurementRegistry(self.path); fresh.load()
        with self.assertRaises(db_io.DatabaseError):
            fresh.restore(bad_backup)

    def test_links_resolve_against_the_catalogue_without_rewriting_it(self):
        db = small_db()
        registry = ms.MeasurementRegistry(self.path)
        identifier = registry.create(measurement("linked"))
        registry.associate(identifier, "LOCAL")
        context = registry.resolve_association(registry.get(identifier), db)
        self.assertEqual((context["state"], context["sku"]), ("resolved", "LOCAL"))
        self.assertIn("Red", context["label"])
        del db["_skus"]["LOCAL"]
        context = registry.resolve_association(registry.get(identifier), db)
        self.assertEqual((context["state"], context["sku"]), ("unresolved", "LOCAL"))
        self.assertEqual(registry.get(identifier)["association"], {"sku": "LOCAL"})   # never re-attributed
        self.assertEqual(registry.linked_to("LOCAL"), [identifier])
        self.assertEqual(small_db(), {"_products": small_db()["_products"], "_skus": small_db()["_skus"], "_brands": {}})

    def test_catalogue_and_registry_are_independent_files(self):
        db_path = Path(self.tmp.name) / "data" / "db.json"
        db_io.save_db(small_db(), db_path)
        catalogue_bytes = db_path.read_bytes()
        registry = ms.MeasurementRegistry(self.path)
        identifier = registry.create(measurement("m")); registry.associate(identifier, "LOCAL")
        self.assertEqual(db_path.read_bytes(), catalogue_bytes)
        registry_bytes = self.path.read_bytes()
        db_io.restore_db(db_path, db_path)   # restoring the catalogue leaves the registry alone
        self.assertEqual(self.path.read_bytes(), registry_bytes)
        config = json.loads(Path(self.tmp.name, "config.json").read_text()) if Path(self.tmp.name, "config.json").exists() else {}
        self.assertNotIn("measurements", json.dumps(config))

    def test_items_are_newest_first_and_sizes_are_measured(self):
        registry = ms.MeasurementRegistry(self.path)
        a = registry.create(cm.new_measurement(measurement("a")["original"], name="a", created_at="2026-01-01T00:00:00Z"))
        b = registry.create(cm.new_measurement(measurement("b")["original"], name="b", created_at="2026-02-01T00:00:00Z"))
        self.assertEqual([key for key, _ in registry.items()], [b, a])
        self.assertGreater(registry.serialized_size(), 100)


if __name__ == "__main__":
    unittest.main()


class CorrectionTests(unittest.TestCase):
    """R4: explicit restoration after an unusable file, bounded reads, final revision check on restore."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data" / "colour_measurements.json"

    def seeded(self):
        registry = ms.MeasurementRegistry(self.path)
        identifier = registry.create(measurement("keep")); kept = self.path.read_bytes()
        registry.rename(identifier, "changed")   # the backup now holds the "keep" version
        return registry, identifier, kept

    def test_oversize_registry_is_refused_before_parse_and_still_restorable(self):
        _, identifier, kept = self.seeded()
        padded = json.dumps(cm.empty_registry()).encode() + b" " * (cm.LIMITS["registry_bytes"] + 1 - len(json.dumps(cm.empty_registry())))
        self.path.write_bytes(padded)
        self.assertEqual(self.path.stat().st_size, cm.LIMITS["registry_bytes"] + 1)
        registry = ms.MeasurementRegistry(self.path)
        with patch("scripts.db_io.parse_json", side_effect=AssertionError("must not parse an oversized file")):
            with self.assertRaises(db_io.DatabaseError) as refused:
                registry.load()
        self.assertIn("non chargé", str(refused.exception)); self.assertEqual(registry.revision, hashlib.sha256(padded).hexdigest())
        self.assertEqual(self.path.read_bytes(), padded)   # never reset
        Path(str(self.path) + ".bak").write_bytes(kept)
        restored = registry.restore()
        self.assertEqual(self.path.read_bytes(), kept); self.assertEqual(restored["measurements"][identifier]["name"], "keep")
        preserved = list(self.path.parent.glob("colour_measurements.json.before-restore-*"))
        self.assertEqual(preserved[0].stat().st_size, len(padded))   # the replaced oversized file is kept whole
        oversize_backup = Path(self.tmp.name) / "big.bak"; oversize_backup.write_bytes(padded)
        with self.assertRaises(db_io.DatabaseError):
            registry.restore(oversize_backup)
        self.assertEqual(self.path.read_bytes(), kept)

    def test_restore_refuses_a_file_changed_between_preview_and_action(self):
        registry, identifier, kept = self.seeded()
        self.path.write_bytes(b"corrupt {")
        broken = ms.MeasurementRegistry(self.path)
        with self.assertRaises(db_io.DatabaseError):
            broken.load()
        self.path.write_bytes(b'{"schema": "spoolscribe-colour-measurements", "version": 1, "measurements": {}}\n')   # someone else wrote meanwhile
        with self.assertRaises(db_io.DatabaseError) as refused:
            broken.restore()
        self.assertIn("a changé", str(refused.exception))
        self.assertTrue(self.path.read_bytes().startswith(b'{"schema"'))   # untouched
        self.assertEqual(len(list(self.path.parent.glob("colour_measurements.json.concurrent-*"))), 1)
        self.assertEqual(list(self.path.parent.glob("colour_measurements.json.before-restore-*")), [])

    def test_restore_checks_the_revision_again_immediately_before_replacing(self):
        registry, identifier, kept = self.seeded()
        foreign = json.dumps(cm.empty_registry()).encode() + b"\n"
        original_write = db_io.atomic_write
        seen = {}

        def racing_write(path, data, *, before_replace=None):
            if Path(path) == self.path:
                Path(path).write_bytes(foreign); seen["callback"] = before_replace is not None
            return original_write(path, data, before_replace=before_replace)
        with patch("scripts.db_io.atomic_write", side_effect=racing_write):
            with self.assertRaises(db_io.DatabaseError) as refused:
                registry.restore()
        self.assertTrue(seen["callback"]); self.assertIn("a changé", str(refused.exception))
        self.assertEqual(self.path.read_bytes(), foreign)   # the concurrent bytes stay in place and in a copy
        copies = list(self.path.parent.glob("colour_measurements.json.concurrent-*"))
        self.assertEqual(copies[0].read_bytes(), foreign)
        self.assertEqual(len(list(self.path.parent.glob("colour_measurements.json.before-restore-*"))), 1)

    def test_invalid_or_missing_backup_changes_nothing(self):
        registry, identifier, kept = self.seeded()
        current = self.path.read_bytes()
        bad = Path(self.tmp.name) / "bad.bak"; bad.write_bytes(b"[]")
        with self.assertRaises(db_io.DatabaseError) as refused:
            registry.restore(bad)
        self.assertIn("Sauvegarde invalide", str(refused.exception)); self.assertEqual(self.path.read_bytes(), current)
        with self.assertRaises(ms.RegistryError):
            registry.restore(Path(self.tmp.name) / "absent.bak")
        self.assertEqual(self.path.read_bytes(), current)
        self.assertEqual(list(self.path.parent.glob("colour_measurements.json.before-restore-*")), [])

    def test_registry_errors_are_translatable(self):
        registry = ms.MeasurementRegistry(self.path)
        with self.assertRaises(ms.RegistryError) as raised:
            registry.rename("MEAS-missing", "x")
        self.assertIsInstance(raised.exception, cm.MeasurementError); self.assertEqual(raised.exception.template, "Mesure introuvable.")
        self.path.parent.mkdir(parents=True); self.path.write_bytes(b"{not json")
        with self.assertRaises(db_io.DatabaseError) as invalid:
            registry.load()
        self.assertEqual(invalid.exception.template, "{v0} : JSON invalide : {v1}")
        self.assertEqual(cm.error_text(invalid.exception, lambda t, **v: "EN " + t.format(**v))[:3], "EN ")
