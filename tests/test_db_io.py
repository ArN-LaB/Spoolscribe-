import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core
from scripts import db_io
from tests.support import small_db


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data/db.json"
        db_io.save_db(small_db(), self.path)

    def test_atomic_save_keeps_previous_valid_bytes(self):
        original = self.path.read_bytes()
        db = db_io.load_db(self.path)
        db["_skus"]["LOCAL"]["hex"] = "ABCDEF"
        db_io.save_db(db, self.path)
        self.assertEqual(Path(str(self.path) + ".bak").read_bytes(), original)
        self.assertEqual(db_io.load_db(self.path)["_skus"]["LOCAL"]["hex"], "ABCDEF")

    def test_interruption_before_publish_preserves_original(self):
        before = self.path.read_bytes()
        db = db_io.load_db(self.path)
        db["_skus"]["LOCAL"]["hex"] = "ABCDEF"
        replace = db_io.os.replace

        def fail_publish(source, destination):
            if Path(destination) == self.path:
                raise OSError("injected publish failure")
            return replace(source, destination)

        with patch("scripts.db_io.os.replace", side_effect=fail_publish):
            with self.assertRaises(OSError):
                db_io.save_db(db, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(Path(str(self.path) + ".bak").read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob("*.lock")))
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_flush_failure_never_truncates_original(self):
        before = self.path.read_bytes()
        with patch("scripts.db_io.os.fsync", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                db_io.atomic_write(self.path, b"replacement")
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_and_wrongly_shaped_databases_are_reported(self):
        for text in ("{broken", "[]", '{"_skus": []}', '{"_products": null}',
                     '{"_skus":{},"_skus":{}}', '{"x":NaN}', '{"_skus":{"x":null}}'):
            with self.subTest(text=text):
                self.path.write_text(text)
                with self.assertRaises(db_io.DatabaseError):
                    db_io.load_db(self.path)
                with self.assertRaises(db_io.DatabaseError):
                    db_io.save_db(small_db(), self.path)
                self.assertEqual(self.path.read_text(), text)

    def test_invalid_new_data_is_rejected_before_writing(self):
        before = self.path.read_bytes()
        db = small_db()
        db["_products"]["Audit PLA"]["density"] = float("nan")
        with self.assertRaises(db_io.DatabaseError):
            db_io.save_db(db, self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_an_update_cannot_introduce_an_orphan_product_reference(self):
        before = self.path.read_bytes()
        db = db_io.load_db(self.path)
        db["_skus"]["NEW"] = {"product": "not present", "color_name": "Red", "hex": "FF0000"}
        with self.assertRaisesRegex(db_io.DatabaseError, "sans produit"):
            db_io.save_db(db, self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_an_update_cannot_silently_drop_local_entries(self):
        before = self.path.read_bytes()
        db = db_io.load_db(self.path)
        db["_skus"].clear()
        with self.assertRaisesRegex(db_io.DatabaseError, "Suppression"):
            db_io.save_db(db, self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_stale_writer_cannot_overwrite_new_correction(self):
        first, stale = db_io.load_db(self.path), db_io.load_db(self.path)
        first["_skus"]["LOCAL"]["hex"] = "ABCDEF"
        db_io.save_db(first, self.path)
        stale["_skus"]["LOCAL"]["hex"] = "000000"
        with self.assertRaisesRegex(db_io.DatabaseError, "changé"):
            db_io.save_db(stale, self.path)
        self.assertEqual(db_io.load_db(self.path)["_skus"]["LOCAL"]["hex"], "ABCDEF")

    def test_foreign_lock_is_never_removed(self):
        lock = Path(str(self.path) + ".lock")
        lock.write_bytes(b"other writer")
        with self.assertRaises(db_io.DatabaseError):
            db_io.save_db(small_db(), self.path)
        self.assertEqual(lock.read_bytes(), b"other writer")

    def test_concurrent_external_edit_during_backup_or_staging_is_preserved(self):
        for timing in ("backup", "staging"):
            with self.subTest(timing=timing):
                db = db_io.load_db(self.path)
                db["_skus"]["LOCAL"]["hex"] = "111111"
                external = small_db()
                external["_skus"]["LOCAL"]["hex"] = "ABCDEF"
                # Raw bytes, including invalid JSON, must be retained without parsing.
                concurrent = json.dumps(external).encode() if timing == "backup" else b'{unfinished external edit'
                original_atomic, original_fsync = db_io.atomic_write, db_io.os.fsync
                calls = 0

                def atomic(path, raw, **kwargs):
                    original_atomic(path, raw, **kwargs)
                    if Path(path) == Path(str(self.path) + ".bak") and timing == "backup":
                        self.path.write_bytes(concurrent)

                def fsync(fd):
                    nonlocal calls
                    calls += 1
                    original_fsync(fd)
                    if timing == "staging" and calls == 2:
                        self.path.write_bytes(concurrent)

                with patch("scripts.db_io.atomic_write", side_effect=atomic), patch("scripts.db_io.os.fsync", side_effect=fsync):
                    with self.assertRaisesRegex(db_io.DatabaseError, "changé"):
                        db_io.save_db(db, self.path)
                self.assertEqual(self.path.read_bytes(), concurrent)
                self.assertTrue(any(p.read_bytes() == concurrent for p in self.path.parent.glob("db.json.concurrent-*")))
                self.assertFalse(list(self.path.parent.glob("*.lock")))
                self.assertFalse(list(self.path.parent.glob("*.tmp")))
                self.path.write_bytes(json.dumps(small_db()).encode())

    def test_stale_revision_preserves_detected_external_bytes(self):
        db = db_io.load_db(self.path)
        external = json.dumps(dict(small_db(), _notes="external edit")).encode()
        self.path.write_bytes(external)
        with self.assertRaisesRegex(db_io.DatabaseError, "changé"):
            db_io.save_db(db, self.path)
        self.assertTrue(any(p.read_bytes() == external for p in self.path.parent.glob("db.json.concurrent-*")))

    def test_explicit_restore_preserves_corrupt_file_and_backup(self):
        old = self.path.read_bytes()
        backup = db_io.backup_db(self.path)
        self.path.write_bytes(b"corrupt interrupted update")
        db_io.restore_db(self.path, backup)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(backup.read_bytes(), old)
        preserved = list(self.path.parent.glob("db.json.before-restore-*"))
        self.assertEqual(len(preserved), 1)
        self.assertEqual(preserved[0].read_bytes(), b"corrupt interrupted update")

    def test_invalid_restore_source_does_not_touch_current_data(self):
        before = self.path.read_bytes()
        bad = self.path.parent / "bad-backup"
        bad.write_text("broken")
        with self.assertRaises(db_io.DatabaseError):
            db_io.restore_db(self.path, bad)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_is_distinct_from_corrupt(self):
        absent = self.path.parent / "absent.json"
        with self.assertRaises(db_io.DatabaseError):
            db_io.load_db(absent)
        self.assertEqual(db_io.load_db(absent, missing_ok=True)["_skus"], {})

    def test_failed_color_save_restores_in_memory_value(self):
        db = small_db()
        with patch("spoolscribe.core.save_db", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                core.set_sku_hex(db, "LOCAL", "ABCDEF", alpha="00")
        self.assertEqual(db["_skus"]["LOCAL"]["hex"], "FF0000")
        self.assertNotIn("alpha", db["_skus"]["LOCAL"])


class BundleTests(unittest.TestCase):
    def test_new_unresolved_bundle_entries_are_reported_without_inventing_products(self):
        bundle = small_db()
        bundle["_skus"]["ORPHAN"] = {"product": "unknown", "hex": None}
        merged, conflicts = db_io.merge_bundled_db(small_db(), bundle)
        self.assertNotIn("ORPHAN", merged["_skus"])
        self.assertIn("_skus.ORPHAN (produit absent, ajout ignoré)", conflicts)

    def test_conservative_merge_preserves_local_fields_and_intentional_nulls(self):
        local, bundled = small_db(), small_db()
        local["_skus"]["LOCAL"]["hex"] = None
        local["_products"]["Audit PLA"]["min_temp"] = 205
        local["_skus"]["MY_OWN"] = dict(local["_skus"]["LOCAL"])
        bundled["_skus"]["NEW"] = dict(bundled["_skus"]["LOCAL"])
        merged, conflicts = db_io.merge_bundled_db(local, bundled)
        self.assertIsNone(merged["_skus"]["LOCAL"]["hex"])
        self.assertEqual(merged["_products"]["Audit PLA"]["min_temp"], 205)
        self.assertIn("MY_OWN", merged["_skus"])
        self.assertIn("NEW", merged["_skus"])
        self.assertIn("_skus.LOCAL.hex", conflicts)
        self.assertEqual(local["_skus"].keys(), {"LOCAL", "MY_OWN"})

    def test_packaged_first_install_and_upgrade_use_temporary_user_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, user = root / "bundle", root / "user"
            (bundle / "data").mkdir(parents=True)
            (bundle / "orca_profiles").mkdir()
            source = bundle / "data/polymaker_db.json"
            source.write_text(json.dumps(small_db()))
            (bundle / "data/logo.svg").write_text("bundled logo")
            target = user / "tests/fixtures/catalogues/polymaker_db.json"
            with patch.multiple(core, _FROZEN=True, RESOURCE_DIR=str(bundle), DATA_DIR=str(user / "data"),
                                DB_PATH=str(target), ORCA_DIR=str(user / "orca_profiles")):
                core.load_db()
                local = db_io.load_db(target)
                local["_skus"]["LOCAL"]["hex"] = "ABCDEF"
                db_io.save_db(local, target)
                (user / "data/logo.svg").write_text("my logo")
                new = small_db()
                new["_skus"]["NEW"] = dict(new["_skus"]["LOCAL"])
                source.write_text(json.dumps(new))
                upgraded = core.load_db()
                self.assertEqual(upgraded["_skus"]["LOCAL"]["hex"], "ABCDEF")
                self.assertIn("NEW", upgraded["_skus"])
                self.assertIn("_skus.LOCAL.hex", upgraded["_bundle_conflicts"])
                self.assertEqual((user / "data/logo.svg").read_text(), "my logo")
                self.assertEqual(source.read_text(), json.dumps(new))
                before = target.read_bytes()
                core.load_db()
                self.assertEqual(target.read_bytes(), before)
