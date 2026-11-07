"""Backup / restore: archive contract, refusals, journaled restoration, crash recovery, startup bootstrap.

Offline, without Qt. Every test works in temporary folders with explicit
``backup.Paths``; both SPOOLSCRIBE_DATA_HOME and SPOOLSCRIBE_CONFIG_PATH point
to a temporary folder as well, so the real user data is never touched.
"""
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from unittest.mock import patch

import tests.support  # noqa: F401  (offline audit hook)
from tests.support import ROOT, catalogue

from scripts import db_io
from spoolscribe import backup, colour_measurements as cm, device_profiles, recovery

PRINTERS_BYTES = (ROOT / "data" / "printers.json").read_bytes()
PRESET_ID = "0123456789abcdef0123456789abcdef"
ORCA_NAME = "Audit PLA @Snapmaker U1 - OrcaSlicer.json"
OPENTAG = {"material": "PLA", "manufacturer": "Polymaker", "color_name": "Rouge", "print_temp": 210,
           "bed_temp": 60, "min_print_temp": 190, "max_print_temp": 230, "weight": 1000}


def tree(home: Path, config: Path | None = None) -> dict:
    """Bytes of every active file (our private transaction folder and lock files excluded)."""
    files = {}
    for path in sorted(home.rglob("*")):
        rel = path.relative_to(home)
        if rel.parts[0] == recovery.TX_ROOT_NAME or path.name.endswith(".lock") or not path.is_file():
            continue
        files[rel.as_posix()] = path.read_bytes()
    if config is not None and config.exists() and home not in config.parents:
        files["<config>"] = config.read_bytes()
    return files


def build_source(home: Path, config: Path) -> dict:
    """Catalogue + personal copy + intentional null correction + linked measurement + preset + Orca + printers + config."""
    db = catalogue()
    db["_products"]["Audit PLA"] = {"type": "PLA", "brand": "Polymaker", "min_temp": 190, "max_temp": 230,
                                    "bed_min_temp": 60, "bed_max_temp": None, "diameter": 1.75, "density": 1.24,
                                    "_field_sources": {"bed_max_temp": db_io.user_correction(None)}}
    db["_skus"]["LOCAL"] = {"sku": "LOCAL", "product": "Audit PLA", "color_name": "Red", "hex": "FF0000",
                            "_field_sources": {"hex": db_io.user_correction("FF0000")}}
    db["_products"]["Audit PLA @Mine"] = dict(db["_products"]["Audit PLA"], display_name="Audit PLA @Mine",
                                              _personal=True, _personal_base_name="Audit PLA")
    db["_skus"]["LOCAL@Mine"] = {"sku": "LOCAL@Mine", "product": "Audit PLA @Mine", "color_name": "Red",
                                 "hex": "FF0000", "source": "Personnalisation locale", "_personal": True,
                                 "_personal_suffix": "Mine", "_personal_origin": "LOCAL"}
    data = home / "data"
    data.mkdir(parents=True)
    (data / "polymaker_db.json").write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
    measurement = cm.new_measurement(cm.parse_manual("CIELAB", {"L": "50", "a": "10", "b": "-5"}), name="Rouge mesuré")
    measurement["association"] = {"sku": "LOCAL"}
    registry = cm.validate_registry({"schema": cm.SCHEMA, "version": 1, "measurements": {cm.new_id(): measurement}})
    (data / "colour_measurements.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    presets = device_profiles.validate({"schema": "spoolscribe-device-presets", "version": 1, "default": PRESET_ID,
                                        "profiles": {PRESET_ID: {"name": "Mon spectro", "manufacturer": "X",
                                                                 "model": "Y", "conditions": {"illuminant": "D65",
                                                                                              "observer": 2}}}})
    (data / "colour_device_profiles.json").write_text(json.dumps(presets), encoding="utf-8")
    (data / "printers.json").write_bytes(PRINTERS_BYTES)
    # Excluded categories and an unknown file.
    (data / "polymaker_db.json.bak").write_text("{}")
    (data / "catalogue_ofd.json").write_text("{}")
    (data / "catalogue_ofd_audit.json").write_text("{}")
    (data / "polymaker_logo.svg").write_text("<svg/>")
    (data / "mes-notes.txt").write_text("à ne pas perdre")
    orca = home / "orca_profiles"
    orca.mkdir()
    (orca / ORCA_NAME).write_text(json.dumps({"nozzle_temperature_range_low": ["190"],
                                              "nozzle_temperature_range_high": ["230"]}))
    (home / "output").mkdir()
    (home / "output" / "LOCAL.json").write_text('{"protocol": "openspool"}')
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({
        "language": "fr", "network_consent": True, "network_sources_revision": 2,
        "last_update": "2026-01-02T03:04:05", "last_update_attempt": "2026-01-02T03:04:05",
        "last_update_status": "complete", "update_interval_days": 7, "auto_update": False,
        "opentag3d_settings": {"LOCAL": OPENTAG}, "favorite_filaments": ["LOCAL"], "ui": {"view": "grid"},
        "export_directory": str(home.parent / "ailleurs"), "qr_label": {"preset": "custom", "custom": {
            "width_mm": 40, "height_mm": 30, "margins_mm": [2, 2, 2, 2], "dpi": 300, "orientation": "portrait"}},
    }, indent=2), encoding="utf-8")
    return db


class Fixture(unittest.TestCase):
    def setUp(self):
        # Process-wide state touched by these tests (recovery.bootstrap() stores its status for the GUI;
        # an in-process restore marks the catalogue path in core): saved here, restored even on failure.
        self.addCleanup(setattr, recovery, "STARTUP_STATUS", recovery.STARTUP_STATUS)
        core = sys.modules.get("spoolscribe.core")
        marks = getattr(core, "_RESTORED_DB_PATHS", None)
        if isinstance(marks, set):
            self.addCleanup(lambda saved=set(marks): (marks.clear(), marks.update(saved)))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        env = patch.dict(os.environ, {"SPOOLSCRIBE_DATA_HOME": str(self.root / "env-home"),
                                      "SPOOLSCRIBE_CONFIG_PATH": str(self.root / "env-home" / "config.json")})
        env.start()
        self.addCleanup(env.stop)
        self.src = self.root / "source"
        self.src_config = self.root / "source-config" / "config.json"
        self.db = build_source(self.src, self.src_config)
        self.src_paths = backup.Paths.for_home(self.src, self.src_config)
        self.dst = self.root / "destination"
        self.dst_config = self.root / "destination-config" / "config.json"   # config on another folder
        self.dst_paths = backup.Paths.for_home(self.dst, self.dst_config)
        self.archive = self.root / "out" / "sauvegarde.zip"
        self.archive.parent.mkdir()

    def make(self, options=None, paths=None, archive=None, **kwargs):
        return backup.create_backup(archive or self.archive, paths or self.src_paths,
                                    options or backup.Options(), **kwargs)

    def seed_destination(self):
        """An existing destination with different data (and its own consent)."""
        data = self.dst / "data"
        data.mkdir(parents=True)
        db = {"_products": {"Old": {"type": "PLA"}}, "_skus": {"OLD": {"product": "Old", "color_name": "Blue"}},
              "_brands": {}}
        (data / "polymaker_db.json").write_text(json.dumps(db), encoding="utf-8")
        (data / "colour_device_profiles.json").write_text(json.dumps(device_profiles.empty()), encoding="utf-8")
        (self.dst / "orca_profiles").mkdir()
        (self.dst / "orca_profiles" / "Mine only.json").write_text("{}")
        self.dst_config.parent.mkdir(parents=True)
        self.dst_config.write_text(json.dumps({"language": "en", "network_consent": False, "ui": {"view": "list"},
                                               "export_directory": "", "update_interval_days": 1}))

    def assertCode(self, code, function, *args, **kwargs):
        with self.assertRaises(backup.BackupError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code, str(caught.exception))
        return caught.exception


class RoundTripTests(Fixture):
    def test_nominal_round_trip_restores_exact_data_into_another_home(self):
        manifest = self.make()
        self.seed_destination()
        analysis = backup.analyze_backup(self.archive, self.dst_paths)
        actions = {e["type"]: e["action"] for e in analysis.entries}
        self.assertEqual(actions, {"catalogue": "replace", "registry": "create", "presets": "replace",
                                   "printers": "create", "orca": "create", "config": "replace"})
        self.assertEqual(analysis.counts["personal"], 1)
        self.assertEqual(analysis.counts["linked"], 1)
        self.assertEqual(analysis.counts["config_opentag3d"], 1)
        self.assertIn({"type": "orca", "target": str(self.dst / "orca_profiles"), "count": 1}, analysis.kept)
        self.assertEqual(analysis.config["machine_state_kept"][0], "network_consent")
        result = backup.restore_backup(analysis)
        self.assertEqual(len(result.published), 6)
        # Exact catalogue: ids, values, personal copies, provenances and intentional null.
        restored = json.loads((self.dst / "data/polymaker_db.json").read_text(encoding="utf-8"))
        self.assertEqual(restored, self.db)
        self.assertEqual((self.dst / "data/polymaker_db.json").read_bytes(),
                         (self.src / "data/polymaker_db.json").read_bytes())
        self.assertIsNone(restored["_products"]["Audit PLA"]["bed_max_temp"])
        self.assertEqual(restored["_products"]["Audit PLA"]["_field_sources"]["bed_max_temp"]["source"], "Utilisateur")
        self.assertTrue(restored["_skus"]["LOCAL@Mine"]["_personal"])
        for name in ("colour_measurements.json", "colour_device_profiles.json", "printers.json"):
            self.assertEqual((self.dst / "data" / name).read_bytes(), (self.src / "data" / name).read_bytes())
        registry = json.loads((self.dst / "data/colour_measurements.json").read_text())
        self.assertEqual([m["association"] for m in registry["measurements"].values()], [{"sku": "LOCAL"}])
        self.assertEqual((self.dst / "orca_profiles" / ORCA_NAME).read_bytes(),
                         (self.src / "orca_profiles" / ORCA_NAME).read_bytes())
        self.assertEqual((self.dst / "orca_profiles" / "Mine only.json").read_text(), "{}")   # kept, never deleted
        self.assertFalse((self.dst / "output").exists())                                     # exports not included
        config = json.loads(self.dst_config.read_text())
        self.assertEqual(config["opentag3d_settings"], {"LOCAL": OPENTAG})
        self.assertEqual(config["language"], "fr")
        self.assertEqual(config["update_interval_days"], 7)
        self.assertIs(config["network_consent"], False)               # local consent kept, never imported
        self.assertEqual(config["ui"], {"view": "list"})               # layout not included: local kept
        self.assertEqual(config["export_directory"], "")
        self.assertNotIn("last_update", config)
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))
        self.assertFalse(recovery.pointer_path(self.dst_config).exists())
        self.assertEqual(len(manifest["entries"]), 6)

    def test_absent_registry_is_announced_and_destination_file_is_kept(self):
        (self.src / "data" / "colour_measurements.json").unlink()
        manifest = self.make(backup.Options(include_config=False))
        self.assertIn("registry", manifest["absent"])
        self.assertIn("config", manifest["excluded"])
        self.seed_destination()
        kept = json.dumps(cm.empty_registry()).encode()
        (self.dst / "data" / "colour_measurements.json").write_bytes(kept)
        before_config = self.dst_config.read_bytes()
        analysis = backup.analyze_backup(self.archive, self.dst_paths)
        self.assertIn("registry", analysis.absent)
        self.assertIn("registry", [k["type"] for k in analysis.kept])
        self.assertIn("config", [k["type"] for k in analysis.kept])
        backup.restore_backup(analysis)
        self.assertEqual((self.dst / "data" / "colour_measurements.json").read_bytes(), kept)
        self.assertEqual(self.dst_config.read_bytes(), before_config)

    def test_manifest_is_strict_and_private_and_preferences_are_filtered(self):
        manifest = self.make()
        with zipfile.ZipFile(self.archive) as archive:
            text = archive.read("manifest.json").decode()
            prefs = json.loads(archive.read("config/preferences.json"))["settings"]
            names = archive.namelist()
        for secret in (str(self.root), os.path.expanduser("~"), "network_consent", "last_update"):
            self.assertNotIn(secret, text)
        self.assertEqual(set(manifest), {"format", "version", "app", "created_utc", "options", "entries",
                                         "absent", "excluded"})
        self.assertIs(type(manifest["version"]), int)
        for key in ("network_consent", "network_sources_revision", "last_update", "last_update_attempt",
                    "last_update_status", "ui", "export_directory"):
            self.assertNotIn(key, prefs)
        self.assertEqual(prefs["opentag3d_settings"], {"LOCAL": OPENTAG})
        self.assertNotIn("output/LOCAL.json", names)
        for entry in manifest["entries"]:
            self.assertFalse(os.path.isabs(entry["path"]))
        self.assertTrue({"internal_backups", "sources", "audits", "resources", "unknown", "export",
                         "external_exports"} <= set(manifest["excluded"]))

    def test_layout_export_path_and_exports_are_options(self):
        self.make(backup.Options(include_layout=True, include_export_path=True, include_exports=True))
        with zipfile.ZipFile(self.archive) as archive:
            prefs = json.loads(archive.read("config/preferences.json"))["settings"]
            self.assertIn("output/LOCAL.json", archive.namelist())
        self.assertEqual(prefs["ui"], {"view": "grid"})
        self.assertEqual(prefs["export_directory"], str(self.root / "ailleurs"))
        self.seed_destination()
        analysis = backup.analyze_backup(self.archive, self.dst_paths)
        self.assertTrue(analysis.config["layout"])
        backup.restore_backup(analysis)
        self.assertEqual((self.dst / "output" / "LOCAL.json").read_text(), '{"protocol": "openspool"}')
        self.assertEqual(json.loads(self.dst_config.read_text())["ui"], {"view": "grid"})

    def test_plan_reports_categories_absences_and_unknown_files_without_writing(self):
        before = tree(self.src, self.src_config)
        plan = backup.plan_backup(self.src_paths, backup.Options())
        self.assertTrue(plan.ok)
        self.assertEqual(plan.unknown, ["data/mes-notes.txt"])
        self.assertEqual(plan.categories["unknown"]["count"], 1)
        for category in ("internal_backups", "sources", "audits", "resources"):
            self.assertEqual(plan.categories[category]["state"], "excluded", category)
        self.assertEqual(plan.categories["export"]["reason"], "option_off")
        self.assertEqual(plan.categories["external_exports"]["reason"], "external")
        self.assertEqual(plan.categories["catalogue"]["state"], "included")
        self.assertEqual(plan.counts["orca_profiles"], 1)
        self.assertEqual(tree(self.src, self.src_config), before)
        self.assertFalse((self.src / recovery.TX_ROOT_NAME).exists())

    def test_diagnostics_sessions_are_technical_never_archived_nor_unknown(self):
        session = self.src / "diagnostics" / "20261107T120000Z-42"
        session.mkdir(parents=True)
        (session / "events.log").write_text("QA_DIAGNOSTICS_MARKER")
        plan = backup.plan_backup(self.src_paths, backup.Options(include_exports=True))
        self.assertEqual(plan.unknown, ["data/mes-notes.txt"])
        self.assertEqual(plan.categories["technical"]["state"], "excluded")
        self.make(options=backup.Options(include_exports=True))
        with zipfile.ZipFile(self.archive) as archive:
            self.assertFalse([n for n in archive.namelist() if "diagnostics" in n])
            self.assertFalse(any(b"QA_DIAGNOSTICS_MARKER" in archive.read(n) for n in archive.namelist()))

    def test_existing_archive_needs_explicit_overwrite_and_cancel_publishes_nothing(self):
        self.archive.write_bytes(b"ancienne")
        self.assertCode("destination_exists", self.make)
        self.assertEqual(self.archive.read_bytes(), b"ancienne")
        self.make(overwrite=True)
        self.assertTrue(zipfile.is_zipfile(self.archive))
        other = self.root / "out" / "annulee.zip"
        self.assertCode("cancelled", self.make, archive=other, cancel=lambda: True)
        self.assertFalse(other.exists())
        self.assertEqual(sorted(p.name for p in self.archive.parent.iterdir()), ["sauvegarde.zip"])

    def test_invalid_or_missing_sources_and_concurrent_change_refuse_creation(self):
        db = self.src / "data" / "polymaker_db.json"
        original = db.read_bytes()
        db.write_text('{"_skus": {"X": {"product": "P", "hex": "nothex"}}}')
        self.assertCode("source_invalid", self.make)
        db.unlink()
        self.assertCode("catalogue_missing", self.make)
        db.write_bytes(original)
        calls = []

        def cancel():   # a non-cooperating writer changes the catalogue while the archive is written
            calls.append(1)
            if len(calls) == 3:
                db.write_bytes(original + b"\n")
            return False
        self.assertCode("source_changed", self.make, cancel=cancel)
        self.assertFalse(self.archive.exists())
        self.assertEqual(list(self.archive.parent.iterdir()), [])

    def test_writer_lock_is_honoured(self):
        self.make()
        self.seed_destination()
        analysis = backup.analyze_backup(self.archive, self.dst_paths)
        with db_io._writer_lock(Path(self.dst_paths.db_path)):
            self.assertCode("writer_busy", backup.restore_backup, analysis)
            self.assertCode("writer_busy", self.make, paths=self.dst_paths, archive=self.root / "out" / "x.zip")

    def test_paths_current_follows_core_and_limits_match_existing_ones(self):
        from spoolscribe import core, printer_profiles
        with patch.object(core, "DATA_HOME", str(self.src)), \
                patch.object(core, "DB_PATH", str(self.src / "data" / "polymaker_db.json")), \
                patch.object(core, "ORCA_DIR", str(self.src / "orca_profiles")), \
                patch.object(core, "OUTPUT_DIR", str(self.src / "output")), \
                patch.object(core, "CONFIG_PATH", str(self.src_config)), \
                patch.dict(os.environ, {"SPOOLSCRIBE_DATA_HOME": str(self.src)}):
            self.assertEqual(backup.Paths.current(), self.src_paths)
        self.assertEqual(backup.LIMITS["config"], core.SETTINGS_FILE_LIMIT)
        self.assertEqual(backup.LIMITS["printers"], printer_profiles.MAX_CATALOGUE_BYTES)
        self.assertEqual(backup.LIMITS["registry"], cm.LIMITS["registry_bytes"])
        # One rule set: the backup uses core's portable keys and validator, no private copy.
        self.assertEqual(backup._portable_keys(), tuple(core.PORTABLE_SETTINGS_KEYS))
        self.assertFalse(hasattr(backup, "_FALLBACK_PORTABLE_KEYS"))

    def test_every_error_code_has_a_french_template(self):
        for code, template in backup.MESSAGES.items():
            self.assertIsInstance(template, str)
            error = backup.BackupError(code, **{f"v{i}": "x" for i in range(3)})
            self.assertEqual(error.template, template)
            self.assertNotIn("{", str(error))


# ── Archive refusals ──────────────────────────────────────────────────────
def rewrite(source: Path, target: Path, *, replace=None, drop=(), add=(), manifest=None, fix=True):
    """Copy an archive with changes; ``fix`` recomputes manifest sizes/digests of listed members."""
    with zipfile.ZipFile(source) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
    document = json.loads(dict((i.filename, d) for i, d in members)["manifest.json"])
    out = []
    for info, data in members:
        if info.filename in drop or info.filename == "manifest.json":
            continue
        out.append((info.filename, (replace or {}).get(info.filename, data)))
    out += list(add)
    if fix:
        contents = {(n.filename if isinstance(n, zipfile.ZipInfo) else n): d for n, d in out}
        for entry in document["entries"]:
            if entry["path"] in contents:
                entry["bytes"] = len(contents[entry["path"]])
                entry["sha256"] = hashlib.sha256(contents[entry["path"]]).hexdigest()
    if manifest is not None:
        manifest(document)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name, data in out:
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(document))
    return target


def entry_for(path, data, kind="orca"):
    return {"path": path, "type": kind, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def patch_declared_size(path: Path, name: str, size: int, *, local=False):
    """Change the uncompressed size declared for ``name`` in the central directory (and local header)."""
    raw = bytearray(path.read_bytes())
    encoded = name.encode()
    position = 0
    while True:
        position = raw.find(b"PK\x01\x02", position)
        assert position >= 0
        length = struct.unpack_from("<H", raw, position + 28)[0]
        if bytes(raw[position + 46:position + 46 + length]) == encoded:
            struct.pack_into("<I", raw, position + 24, size)
            offset = struct.unpack_from("<I", raw, position + 42)[0]
            if local:
                struct.pack_into("<I", raw, offset + 22, size)
            break
        position += 4
    path.write_bytes(bytes(raw))


class RefusalTests(Fixture):
    def setUp(self):
        super().setUp()
        self.make()
        self.seed_destination()
        self.before = tree(self.dst, self.dst_config)
        self.bad = self.root / "out" / "bad.zip"

    def refused(self, code, archive=None):
        error = self.assertCode(code, backup.analyze_backup, archive or self.bad, self.dst_paths)
        self.assertEqual(tree(self.dst, self.dst_config), self.before)
        self.assertFalse((self.dst / recovery.TX_ROOT_NAME).exists())
        return error

    def orca_member(self):
        return "orca_profiles/" + ORCA_NAME

    def test_digest_size_and_schema(self):
        member = self.orca_member()
        with zipfile.ZipFile(self.archive) as archive:
            data = archive.read(member)
        rewrite(self.archive, self.bad, replace={member: data.replace(b"190", b"191")}, fix=False)
        self.refused("digest_mismatch")
        rewrite(self.archive, self.bad, replace={member: data + b" "}, fix=False)
        self.refused("size_mismatch")
        rewrite(self.archive, self.bad, replace={"data/polymaker_db.json":
                                                 b'{"_skus": {"X": {"product": "P", "hex": "zz"}}}'})
        self.assertIn("HEX", str(self.refused("member_invalid")))
        rewrite(self.archive, self.bad, replace={"data/colour_measurements.json": b"[]"})
        self.refused("member_invalid")
        rewrite(self.archive, self.bad, replace={"data/printers.json": b'{"format": 1}'})
        self.refused("member_invalid")
        rewrite(self.archive, self.bad, replace={member: b"[1, 2]"})
        self.refused("member_invalid")
        rewrite(self.archive, self.bad, replace={"data/polymaker_db.json": b'{"a": 1, "a": 2}'})
        self.refused("member_invalid")

    def test_missing_unexpected_and_duplicate_members(self):
        rewrite(self.archive, self.bad, drop=("data/colour_measurements.json",))
        self.refused("missing_member")
        rewrite(self.archive, self.bad, add=[("orca_profiles/extra.json", b"{}")])
        self.refused("unexpected_member")
        member = self.orca_member()
        with zipfile.ZipFile(self.archive) as archive:
            data = archive.read(member)
        rewrite(self.archive, self.bad, add=[(member, data)])
        self.refused("duplicate_member")
        rewrite(self.archive, self.bad, add=[("manifest.json", b"{}")])
        self.refused("manifest_duplicate")
        rewrite(self.archive, self.bad, manifest=lambda m: m["entries"].append(dict(m["entries"][0])))
        self.refused("duplicate_member")
        with zipfile.ZipFile(self.bad, "w") as archive:
            archive.writestr("data/polymaker_db.json", b"{}")
        self.refused("manifest_missing")

    def test_traversal_absolute_drive_backslash_and_collisions(self):
        for name in ("../evil.json", "/abs.json", "C:/evil.json", "orca_profiles/..\\evil.json",
                     "orca_profiles/./x.json", "orca_profiles//x.json", "orca_profiles/CON.json",
                     "orca_profiles/x\x01.json", "orca_profiles/e\u0301.json"):
            with self.subTest(name=name):
                rewrite(self.archive, self.bad, add=[(name, b"{}")],
                        manifest=lambda m, name=name: m["entries"].append(entry_for(name, b"{}")))
                self.refused("unsafe_path")
        rewrite(self.archive, self.bad, add=[("orca_profiles/A.json", b"{}"), ("orca_profiles/a.json", b"{}")],
                manifest=lambda m: m["entries"].extend([entry_for("orca_profiles/A.json", b"{}"),
                                                       entry_for("orca_profiles/a.json", b"{}")]))
        self.refused("duplicate_member")
        rewrite(self.archive, self.bad, add=[("orca_profiles/\u00e9.json", b"{}"), ("orca_profiles/\u00c9.json", b"{}")],
                manifest=lambda m: m["entries"].extend([entry_for("orca_profiles/\u00e9.json", b"{}"),
                                                       entry_for("orca_profiles/\u00c9.json", b"{}")]))
        self.refused("duplicate_member")

    def test_links_directories_and_encrypted_members(self):
        link = zipfile.ZipInfo("orca_profiles/link.json")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        rewrite(self.archive, self.bad, add=[(link, b"/etc/passwd")],
                manifest=lambda m: m["entries"].append(entry_for("orca_profiles/link.json", b"/etc/passwd")))
        self.refused("link_member")
        folder = zipfile.ZipInfo("orca_profiles/folder/")
        rewrite(self.archive, self.bad, add=[(folder, b"")])
        self.refused("not_regular")
        fifo = zipfile.ZipInfo("orca_profiles/fifo.json")
        fifo.create_system = 3
        fifo.external_attr = (stat.S_IFIFO | 0o600) << 16
        rewrite(self.archive, self.bad, add=[(fifo, b"{}")],
                manifest=lambda m: m["entries"].append(entry_for("orca_profiles/fifo.json", b"{}")))
        self.refused("not_regular")
        rewrite(self.archive, self.bad)
        raw = bytearray(self.bad.read_bytes())
        position = raw.find(b"PK\x01\x02")
        struct.pack_into("<H", raw, position + 8, struct.unpack_from("<H", raw, position + 8)[0] | 1)
        self.bad.write_bytes(bytes(raw))
        self.refused("encrypted_member")

    def test_decompression_bombs_and_bounds(self):
        member = self.orca_member()
        rewrite(self.archive, self.bad)
        patch_declared_size(self.bad, member, 600 * 1024 * 1024)
        self.refused("total_too_large")
        rewrite(self.archive, self.bad)
        patch_declared_size(self.bad, member, 9 * 1024 * 1024)
        self.refused("size_mismatch")
        # Header claims fewer bytes than the stream holds: never read beyond, refused.
        bomb = b'{"x": "' + b"a" * 200000 + b'"}'
        rewrite(self.archive, self.bad, replace={member: bomb})
        with zipfile.ZipFile(self.bad) as archive:
            self.assertLess(archive.getinfo(member).compress_size, 5000)
        patch_declared_size(self.bad, member, 100, local=True)
        rewrite_manifest = json.loads(zipfile.ZipFile(self.bad).read("manifest.json"))
        self.assertTrue(any(e["path"] == member for e in rewrite_manifest["entries"]))
        self.refused("size_mismatch")
        with patch.dict(backup.LIMITS, {"orca": 1000}):
            rewrite(self.archive, self.bad, replace={member: bomb})
            self.refused("member_too_large")
        with patch.dict(backup.LIMITS, {"total_bytes": 1000}):
            self.refused("total_too_large", self.archive)
        with patch.dict(backup.LIMITS, {"members": 3}):
            self.refused("too_many_members", self.archive)
        with patch.dict(backup.LIMITS, {"archive_bytes": 100}):
            self.refused("archive_too_large", self.archive)

    def test_streaming_bound_ignores_declared_sizes(self):
        member = self.orca_member()
        payload = b'{"x": "' + b"a" * 5000 + b'"}'
        rewrite(self.archive, self.bad, replace={member: payload})
        with zipfile.ZipFile(self.bad) as archive:
            info = archive.getinfo(member)
            info.file_size = 10          # a lying header: the reader stops at limit + 1
            with self.assertRaises(backup.BackupError) as caught:
                backup._stream_member(archive, info, 100)
        self.assertIn(caught.exception.code, ("member_corrupt", "size_mismatch", "member_too_large"))
        with zipfile.ZipFile(self.bad) as archive:
            info = archive.getinfo(member)
            info.file_size = 50
            with self.assertRaises(backup.BackupError) as caught:
                backup._stream_member(archive, info, 60)
        self.assertIn(caught.exception.code, ("member_corrupt", "size_mismatch", "member_too_large"))

    def test_versions_format_and_options(self):
        for version in (2, True, 1.0, "1", None):
            with self.subTest(version=version):
                rewrite(self.archive, self.bad, manifest=lambda m, v=version: m.update(version=v))
                self.refused("unsupported_version")
        rewrite(self.archive, self.bad, manifest=lambda m: m.update(format="autre"))
        self.refused("not_a_backup")
        self.bad.write_bytes(b"pas une archive")
        self.refused("not_a_backup")
        rewrite(self.archive, self.bad, manifest=lambda m: m.update(extra=1))
        self.refused("manifest_invalid")
        rewrite(self.archive, self.bad, manifest=lambda m: m["options"].update(include_config=False))
        self.refused("options_mismatch")
        rewrite(self.archive, self.bad, manifest=lambda m: m["options"].update(include_exports=True))
        self.refused("options_mismatch")
        rewrite(self.archive, self.bad, manifest=lambda m: m["options"].update(include_layout=1))
        self.refused("manifest_invalid")
        prefs = {"format": "spoolscribe-settings", "version": 1, "settings": {"ui": {"view": "x"}}}
        rewrite(self.archive, self.bad, replace={"config/preferences.json": json.dumps(prefs).encode()})
        self.refused("options_mismatch")
        prefs["settings"] = {"network_consent": True}
        rewrite(self.archive, self.bad, replace={"config/preferences.json": json.dumps(prefs).encode()})
        self.refused("member_invalid")
        prefs["settings"] = {"update_interval_days": True}
        rewrite(self.archive, self.bad, replace={"config/preferences.json": json.dumps(prefs).encode()})
        self.refused("member_invalid")
        prefs.update(version=True, settings={})
        rewrite(self.archive, self.bad, replace={"config/preferences.json": json.dumps(prefs).encode()})
        self.refused("member_invalid")

    def test_unsafe_destinations_are_refused(self):
        if not hasattr(os, "symlink"):
            self.skipTest("liens symboliques indisponibles")
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        target = self.dst / "orca_profiles" / ORCA_NAME
        try:
            os.symlink(elsewhere / "victim.json", target)
        except OSError:
            self.skipTest("liens symboliques non autorisés")
        self.before = tree(self.dst, self.dst_config)
        self.refused("unsafe_target", self.archive)
        self.assertFalse((elsewhere / "victim.json").exists())


# ── Restoration transaction ───────────────────────────────────────────────
class TransactionTests(Fixture):
    def setUp(self):
        super().setUp()
        self.make()
        self.seed_destination()
        self.before = tree(self.dst, self.dst_config)

    def analysis(self):
        return backup.analyze_backup(self.archive, self.dst_paths)

    def assertUntouched(self):
        self.assertEqual(tree(self.dst, self.dst_config), self.before)
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))
        self.assertFalse(recovery.pointer_path(self.dst_config).exists())

    def test_concurrent_change_between_analysis_and_restore_is_refused(self):
        analysis = self.analysis()
        db = self.dst / "data" / "polymaker_db.json"
        db.write_bytes(db.read_bytes() + b" ")
        changed = tree(self.dst, self.dst_config)
        self.assertCode("changed_since_analysis", backup.restore_backup, analysis)
        self.assertEqual(tree(self.dst, self.dst_config), changed)
        self.assertEqual(list((self.dst / recovery.TX_ROOT_NAME).glob("tx-*")), [])
        analysis = self.analysis()
        (self.dst / "data" / "colour_measurements.json").write_text("{}")   # a file appears meanwhile
        self.assertCode("changed_since_analysis", backup.restore_backup, analysis)
        analysis = self.analysis()
        with self.archive.open("ab") as stream:
            stream.write(b"\0")
        self.assertCode("archive_changed", backup.restore_backup, analysis)

    def test_cancel_before_publication_writes_nothing(self):
        analysis = self.analysis()
        self.assertCode("cancelled", backup.restore_backup, analysis, cancel=lambda: True)
        self.assertUntouched()

    def test_each_publication_boundary_rolls_back_in_process(self):
        labels = self.boundaries()
        for label in labels:
            with self.subTest(label=label):
                analysis = self.analysis()

                def hook(seen, label=label):
                    if seen == label:
                        raise OSError(errno.EIO, "panne simulée")
                with patch.object(backup, "_FAULT_HOOK", hook):
                    error = self.assertCode("restore_failed" if label != "staged" else "staging_failed",
                                            backup.restore_backup, analysis)
                self.assertIn("panne simulée", str(error))
                self.assertUntouched()

    def boundaries(self):
        count = len([e for e in self.analysis().entries if e["action"] != "unchanged"])
        return ["staged", "journal"] + [label for i in range(count) for label in (f"proof:{i}", f"published:{i}")] \
            + ["before_commit"]

    def test_disk_full_at_each_write_rolls_back(self):
        count = len([e for e in self.analysis().entries if e["action"] != "unchanged"])
        real = recovery._stage_temporary                      # every publication stages its object through it
        for failing in range(1, count + 1):
            with self.subTest(write=failing):
                calls = []

                def full(path, data):
                    calls.append(path)
                    if len(calls) == failing:
                        raise OSError(errno.ENOSPC, "No space left on device")
                    return real(path, data)
                analysis = self.analysis()
                with patch.object(recovery, "_stage_temporary", full):
                    error = self.assertCode("restore_failed", backup.restore_backup, analysis)
                self.assertEqual(error.details["errors"], [])
                self.assertUntouched()

    @unittest.skipIf(os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0, "droits POSIX requis")
    def test_write_refused_in_a_read_only_folder_rolls_back(self):
        orca = self.dst / "orca_profiles"
        orca.chmod(0o555)
        self.addCleanup(orca.chmod, 0o755)
        analysis = self.analysis()
        error = self.assertCode("restore_failed", backup.restore_backup, analysis)
        self.assertTrue(error.details["rolled_back"])       # data/ files were published, then restored
        self.assertUntouched()

    def test_third_party_file_appearing_during_publication_is_never_deleted(self):
        presets = self.dst / "data" / "colour_device_profiles.json"
        presets.unlink()
        self.before = tree(self.dst, self.dst_config)
        analysis = self.analysis()

        def hook(label):
            if label == "published:0":                     # printers published; presets not yet
                presets.write_text("tiers")
        with patch.object(backup, "_FAULT_HOOK", hook):
            error = self.assertCode("restore_failed", backup.restore_backup, analysis)
        self.assertIn("modifié par un autre programme", str(error))
        self.assertEqual(presets.read_text(), "tiers")
        presets.unlink()
        self.assertUntouched()

    # ── Ownership: a third-party object is never deleted on byte equality alone ──
    @staticmethod
    def foreign_create(path: Path, data: bytes) -> dict:
        """An independent writer creates ``path`` exclusively; returns its identity for the oracle."""
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        st = path.stat()
        return {"ino": st.st_ino, "dev": st.st_dev, "size": st.st_size, "sha256": hashlib.sha256(data).hexdigest()}

    def member_bytes(self, member: str) -> bytes:
        with zipfile.ZipFile(self.archive) as archive:
            return archive.read(member)

    def assertForeignIntact(self, path: Path, identity: dict, data: bytes):
        self.assertTrue(path.exists(), f"{path.name} a été supprimé")
        self.assertEqual(path.read_bytes(), data)
        st = path.stat()
        self.assertEqual((st.st_dev, st.st_ino), (identity["dev"], identity["ino"]), "identité (inode) changée")

    def test_foreign_identical_before_any_publication_is_preserved(self):
        """05 cas A: identical bytes created by a third party after the journal, before any publication."""
        printers = self.dst / "data" / "printers.json"
        self.assertFalse(printers.exists())
        expected = self.member_bytes("data/printers.json")
        analysis = self.analysis()
        self.assertEqual(next(e["action"] for e in analysis.entries if e["type"] == "printers"), "create")
        seen, foreign = [], {}

        def hook(label):
            seen.append(label)
            if label == "journal":
                foreign.update(self.foreign_create(printers, expected))
                raise OSError(errno.EIO, "panne simulée avant toute publication")
        with patch.object(backup, "_FAULT_HOOK", hook), self.assertRaises(backup.BackupError) as caught:
            backup.restore_backup(analysis)
        self.assertFalse([s for s in seen if s.startswith("published:")], seen)     # no publication of any item
        self.assertForeignIntact(printers, foreign, expected)                      # never deleted on byte equality
        error = caught.exception
        self.assertEqual(error.code, "restore_recoverable", str(error))             # ambiguity kept, no false success
        ambiguous = [c for c in error.details["conflicts"] if c["type"] == "printers"]
        self.assertEqual([c["state"] for c in ambiguous], ["ambiguous"], error.details)
        pending = backup.pending_recovery(str(self.dst), str(self.dst_config))
        self.assertEqual(pending["phase"], "rollback_incomplete")
        self.assertEqual([c["type"] for c in pending["conflicts"]], ["printers"])
        # Startup recovery does not delete it either; dismissing keeps it and clears the state.
        self.assertEqual(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"], "recoverable")
        self.assertForeignIntact(printers, foreign, expected)
        backup.dismiss_recovery(str(self.dst), pending["txid"])
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))
        self.assertForeignIntact(printers, foreign, expected)
        printers.unlink()
        self.assertUntouched()

    def test_foreign_identical_after_first_publication_is_preserved(self):
        """05 cas B: after our first publication, a third party creates the second target with identical bytes."""
        printers = self.dst / "data" / "printers.json"
        presets = self.dst / "data" / "colour_device_profiles.json"
        presets.unlink()
        self.before = tree(self.dst, self.dst_config)
        expected = self.member_bytes("data/colour_device_profiles.json")
        analysis = self.analysis()
        order = [e["type"] for e in analysis.entries if e["action"] != "unchanged"]
        self.assertEqual(order[:2], ["printers", "presets"])
        seen, foreign = [], {}

        def hook(label):
            seen.append(label)
            if label == "published:0":
                foreign.update(self.foreign_create(presets, expected))
        with patch.object(backup, "_FAULT_HOOK", hook), self.assertRaises(backup.BackupError) as caught:
            backup.restore_backup(analysis)
        self.assertIn("published:0", seen)
        self.assertNotIn("published:1", seen)                      # the second item was never published by us
        self.assertForeignIntact(presets, foreign, expected)
        error = caught.exception
        self.assertEqual(error.code, "restore_recoverable", str(error))
        self.assertEqual([r["type"] for r in error.details["rolled_back"]], ["printers"])   # ours: removed
        self.assertFalse(printers.exists())
        self.assertEqual([(c["type"], c["state"]) for c in error.details["conflicts"]], [("presets", "ambiguous")])
        pending = backup.pending_recovery(str(self.dst), str(self.dst_config))
        self.assertEqual(pending["phase"], "rollback_incomplete")
        backup.dismiss_recovery(str(self.dst), pending["txid"])
        self.assertForeignIntact(presets, foreign, expected)
        presets.unlink()
        self.assertUntouched()

    @staticmethod
    def replace_identity(path: Path) -> dict:
        """A third party replaces ``path`` by a new object with the same bytes (other inode)."""
        data = path.read_bytes()
        temporary = path.with_name(path.name + ".tiers")
        temporary.write_bytes(data)
        os.replace(temporary, path)
        st = path.stat()
        return {"ino": st.st_ino, "dev": st.st_dev, "size": st.st_size, "sha256": hashlib.sha256(data).hexdigest()}

    def test_last_moment_appearance_before_creating_an_absent_target_is_never_replaced(self):
        """The proof is written, then (before the link) a third party creates the target: never overwritten."""
        printers = self.dst / "data" / "printers.json"
        expected = self.member_bytes("data/printers.json")
        for data, code, state in ((b"tiers", "restore_failed", "foreign"), (expected, "restore_recoverable", "ambiguous")):
            with self.subTest(bytes="identical" if data == expected else "different"):
                analysis = self.analysis()
                foreign = {}

                def hook(label):
                    if label == "proof:0":
                        foreign.update(self.foreign_create(printers, data))
                with patch.object(backup, "_FAULT_HOOK", hook):
                    error = self.assertCode(code, backup.restore_backup, analysis)
                self.assertForeignIntact(printers, foreign, data)
                self.assertEqual([(c["type"], c["state"]) for c in error.details["conflicts"] + error.details["foreign"]],
                                 [("printers", state)])
                if code == "restore_recoverable":
                    backup.dismiss_recovery(str(self.dst), error.details["txid"])
                printers.unlink()
                self.assertUntouched()

    def test_identical_bytes_with_a_different_identity_are_never_rolled_back(self):
        """After our publication, a third party replaces the object with the same bytes: not ours any more."""
        printers = self.dst / "data" / "printers.json"
        presets = self.dst / "data" / "colour_device_profiles.json"
        for position, target in ((0, printers), (1, presets)):      # a created target, then a replaced one
            with self.subTest(target=target.name):
                analysis = self.analysis()
                order = [e["type"] for e in analysis.entries if e["action"] != "unchanged"]
                foreign = {}

                def hook(label, position=position, target=target):
                    if label == f"published:{position}":
                        foreign.update(self.replace_identity(target))
                        raise OSError(errno.EIO, "panne après remplacement tiers")
                with patch.object(backup, "_FAULT_HOOK", hook):
                    error = self.assertCode("restore_recoverable", backup.restore_backup, analysis)
                self.assertForeignIntact(target, foreign, target.read_bytes())
                self.assertEqual([(c["type"], c["state"]) for c in error.details["conflicts"]],
                                 [(order[position], "ambiguous")])
                pending = backup.pending_recovery(str(self.dst), str(self.dst_config))
                self.assertEqual(pending["phase"], "rollback_incomplete")
                backup.dismiss_recovery(str(self.dst), pending["txid"])
                self.assertForeignIntact(target, foreign, target.read_bytes())
                # Put the exact previous state back by hand for the next sub-test.
                if position == 0:
                    target.unlink()
                else:
                    target.write_bytes(self.before["data/colour_device_profiles.json"])
                self.assertEqual(tree(self.dst, self.dst_config), self.before)

    def test_unsupported_no_replace_primitive_blocks_before_any_write(self):
        analysis = self.analysis()

        def no_link(src, dst, *args, **kwargs):
            raise OSError(errno.ENOTSUP, "Operation not supported")
        with patch.object(os, "link", no_link):
            error = self.assertCode("staging_failed", backup.restore_backup, analysis)
        self.assertIn("sans remplacement", str(error))
        self.assertEqual(list((self.dst / recovery.TX_ROOT_NAME).glob("tx-*")), [])
        self.assertUntouched()

    def test_rollback_proofs_are_durable_identities_not_empty_markers(self):
        analysis = self.analysis()
        seen = {}

        def hook(label):
            if label == "published:1":
                txdir = next((self.dst / recovery.TX_ROOT_NAME).glob("tx-*"))
                journal = recovery.read_journal(txdir)
                for item in journal["items"][:2]:
                    seen[item["type"]] = recovery.read_proof(txdir, item)
                self.assertIsNone(recovery.read_proof(txdir, journal["items"][2]))   # not attempted yet
                raise OSError(errno.EIO, "panne")
        with patch.object(backup, "_FAULT_HOOK", hook):
            self.assertCode("restore_failed", backup.restore_backup, analysis)
        self.assertEqual(set(seen), {"printers", "presets"})
        for identity in seen.values():
            self.assertTrue(recovery.valid_identity(identity), identity)
        self.assertUntouched()

    # ── Temporaries and probe names: ownership of the object, never of the name (B01/09 F1.1–F1.3) ──
    def find_temporary(self, target: Path, identity: dict) -> Path:
        """The staged object of ``target``, located by identity in the only synthetic data folder."""
        for candidate in target.parent.iterdir():
            if candidate.name.startswith(f".{target.name}.") and candidate.name.endswith(".tmp"):
                st = candidate.lstat()
                if (st.st_dev, st.st_ino) == (identity["dev"], identity["ino"]):
                    return candidate
        self.fail(f"objet temporaire de {target.name} introuvable par identité")

    def proof_identity(self, index: int = 0) -> dict:
        txdir = next((self.dst / recovery.TX_ROOT_NAME).glob("tx-*"))
        return json.loads((txdir / "done" / str(index)).read_text(encoding="utf-8"))["identity"]

    def substitute_source(self, target: Path, retained_dir: Path, data: bytes) -> dict:
        """Third-party writer: move the attested temporary to a retention name (object kept alive, no inode
        reuse) and create, exclusively, another object at the old name."""
        temporary = self.find_temporary(target, self.proof_identity(0))
        retained = retained_dir / temporary.name
        os.rename(temporary, retained)
        return {"retained": retained, "name": temporary, "foreign": self.foreign_create(temporary, data)}

    def test_foreign_probe_destination_is_preserved(self):
        """F1.1: a third party occupies the probe's link name just before the real os.link (EEXIST)."""
        probe_dir = self.root / "probe"
        probe_dir.mkdir()
        real_link, calls, occupant = os.link, [], {}

        def wrapped(src, dst, *args, **kwargs):
            calls.append({"src": str(src), "dst": str(dst)})
            if len(calls) == 1:
                occupant.update(self.foreign_create(Path(dst), b"occupant tiers"), path=Path(dst))
            try:
                real_link(src, dst, *args, **kwargs)        # the real syscall, traced
                calls[-1]["result"] = "created"
            except OSError as exc:
                calls[-1]["result"] = exc.__class__.__name__
                raise
        with patch.object(os, "link", wrapped):
            supported = recovery.link_supported(probe_dir)
        self.assertEqual(calls[0]["result"], "FileExistsError", calls)
        self.assertForeignIntact(occupant["path"], occupant, b"occupant tiers")
        self.assertEqual([p.name for p in probe_dir.iterdir() if p != occupant["path"]], [],
                         "objets de sonde laissés ou occupant remplacé")
        if supported:   # only after a real successful probe with owned names, never from EEXIST alone
            created = [c for c in calls if c.get("result") == "created"]
            self.assertTrue(created, calls)
            self.assertNotEqual(created[-1]["dst"], str(occupant["path"]))

    def test_staged_source_replaced_after_proof_with_different_bytes_is_safe(self):
        """F1.2a: after the proof, the staged temporary is replaced by a third-party object (other bytes)."""
        self._staged_source_replaced_after_proof(b"octets tiers, pas ceux de l'archive")

    def test_staged_source_replaced_after_proof_with_identical_bytes_is_safe(self):
        """F1.2b: same substitution with the archive's exact bytes: identical SHA proves nothing."""
        self._staged_source_replaced_after_proof(self.member_bytes("data/printers.json"))

    def _staged_source_replaced_after_proof(self, foreign_bytes: bytes):
        printers = self.dst / "data" / "printers.json"
        expected = self.member_bytes("data/printers.json")
        retained_dir = self.root / "retained"
        retained_dir.mkdir()
        analysis = self.analysis()
        state, links, real_link = {}, [], os.link

        def hook(label):
            if label == "proof:0":
                state.update(self.substitute_source(printers, retained_dir, foreign_bytes))

        def traced_link(src, dst, *args, **kwargs):
            entry = {"src": str(src), "dst": str(dst)}
            links.append(entry)
            try:
                real_link(src, dst, *args, **kwargs)
                entry["result"] = "created"
            except OSError as exc:
                entry["result"] = exc.__class__.__name__
                raise
        with patch.object(backup, "_FAULT_HOOK", hook), patch.object(os, "link", traced_link):
            try:
                outcome = ("success", backup.restore_backup(analysis))
            except backup.BackupError as exc:
                outcome = ("error", exc)
        self.assertIn("foreign", state, "le hook proof:0 n'a pas été atteint")
        # The third-party source and the retained attested object are both alive and intact.
        self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        self.assertEqual(state["retained"].read_bytes(), expected)
        retained_st = state["retained"].stat()
        phases = [recovery._quick_phase(d) for d in (self.dst / recovery.TX_ROOT_NAME).glob("tx-*")]
        if outcome[0] == "success":
            # Acceptable only if the published target IS the attested object, with the exact bytes.
            st = printers.stat()
            self.assertEqual((st.st_dev, st.st_ino), (retained_st.st_dev, retained_st.st_ino), "objet publié non attesté")
            self.assertEqual(printers.read_bytes(), expected)
        else:
            self.assertIn(outcome[1].code, ("restore_failed", "restore_recoverable"), str(outcome[1]))
            self.assertNotIn("committed", phases)
            if printers.exists():
                st = printers.stat()
                self.assertNotEqual((st.st_dev, st.st_ino), (state["foreign"]["dev"], state["foreign"]["ino"]),
                                    "l'objet tiers a été publié")
                self.assertEqual(printers.read_bytes(), expected, "octets étrangers publiés")
        self.assertTrue(all("result" in link for link in links), links)       # every real syscall traced
        state["name"].unlink()   # the fixture's own third-party object, removed after the observations

    def test_foreign_source_after_link_is_preserved(self):
        """F1.3: the real link succeeds, then the source name is taken by a new third-party object before cleanup."""
        printers = self.dst / "data" / "printers.json"
        expected = self.member_bytes("data/printers.json")
        retained_dir = self.root / "retained"
        retained_dir.mkdir()
        analysis = self.analysis()
        state, real_link = {}, os.link

        def wrapped(src, dst, *args, **kwargs):
            real_link(src, dst, *args, **kwargs)              # the real syscall succeeds first
            if Path(dst) == printers and "foreign" not in state:
                retained = retained_dir / Path(src).name
                os.rename(src, retained)                      # the attested object stays alive (and linked at the target)
                state.update(retained=retained, name=Path(src),
                             foreign=self.foreign_create(Path(src), b"nouveau tiers au nom source"))
        with patch.object(os, "link", wrapped):
            try:
                outcome = ("success", backup.restore_backup(analysis))
            except backup.BackupError as exc:
                outcome = ("error", exc)
        self.assertIn("foreign", state, "le lien réel vers printers.json n'a pas été observé")
        self.assertForeignIntact(state["name"], state["foreign"], b"nouveau tiers au nom source")
        retained_st = state["retained"].stat()
        self.assertEqual(state["retained"].read_bytes(), expected)
        if outcome[0] == "success":
            st = printers.stat()
            self.assertEqual((st.st_dev, st.st_ino), (retained_st.st_dev, retained_st.st_ino))
            self.assertEqual(printers.read_bytes(), expected)
        else:
            self.assertIn(outcome[1].code, ("restore_failed", "restore_recoverable"), str(outcome[1]))
            if printers.exists():
                st = printers.stat()
                self.assertEqual((st.st_dev, st.st_ino), (retained_st.st_dev, retained_st.st_ino))
        state["name"].unlink()

    def test_failure_between_publication_and_cleanup_rolls_back_without_residue(self):
        """A fault right after os.link / os.replace (before the staged name is cleaned): exact previous state."""
        work = [e for e in self.analysis().entries if e["action"] != "unchanged"]
        for entry in work:
            label = ("linked:" if entry["current"] is None else "replaced:") + Path(entry["target"]).name
            with self.subTest(label=label):
                analysis = self.analysis()
                armed = [True]

                def hook(seen, label=label):
                    if seen == label and armed:            # once: the rollback's own rewrite must not be faulted
                        armed.clear()
                        raise OSError(errno.EIO, "panne après publication")
                with patch.object(recovery, "_PUBLISH_HOOK", hook):
                    error = self.assertCode("restore_failed", backup.restore_backup, analysis)
                self.assertEqual(error.details["conflicts"], [])
                self.assertUntouched()                        # includes: no orphan temporary left in data folders

    # ── Staging write errors: the temporary's name may have been taken by a third party (B02/05) ──
    def stage_write_scenario(self, foreign_bytes=None, fail=True):
        """Real restore; the first write on the staged temporary of printers.json is a real 1-byte partial write.

        Optionally (``foreign_bytes``), before the next write a fixture writer moves the original to a retention
        name outside the active tree (kept alive) and creates a third party exclusively at the freed name; the
        next write on the same descriptor then fails once with an injected ENOSPC (``fail``).
        """
        printers = self.dst / "data" / "printers.json"
        retained_dir = self.root / "retained"
        retained_dir.mkdir(exist_ok=True)
        analysis = self.analysis()
        real_write, state = os.write, {"calls": []}

        def staged_name(fd):
            st = os.fstat(fd)
            for candidate in printers.parent.iterdir():
                if candidate.name.startswith(".printers.json.") and candidate.name.endswith(".tmp"):
                    cs = candidate.lstat()
                    if (cs.st_dev, cs.st_ino) == (st.st_dev, st.st_ino):
                        return candidate
            return None

        def wrapped(fd, data):
            if "fd" not in state:
                name = staged_name(fd)
                if name is None:
                    return real_write(fd, data)
                state.update(fd=fd, name=name)
                written = real_write(fd, bytes(data[:1]))            # real partial write, partial count returned
                state["calls"].append(("partial", written))
                if foreign_bytes is not None:
                    retained = retained_dir / name.name
                    os.rename(name, retained)                         # original kept alive: no inode reuse
                    state.update(retained=retained, foreign=self.foreign_create(name, foreign_bytes))
                return written
            if fd == state["fd"] and fail and not state.get("failed"):
                state["failed"] = True
                state["calls"].append(("ENOSPC", 0))
                raise OSError(errno.ENOSPC, "No space left on device (injecté)")
            if fd == state["fd"]:
                state["calls"].append(("write", len(data)))
            return real_write(fd, data)
        with patch.object(os, "write", wrapped):
            try:
                outcome = ("success", backup.restore_backup(analysis))
            except backup.BackupError as exc:
                outcome = ("error", exc)
        self.assertIn("name", state, "écriture du temporaire de printers.json non observée")
        return printers, state, outcome

    def leftover_temporaries(self):
        return sorted(p.relative_to(self.dst).as_posix() for p in self.dst.rglob("*.tmp")
                      if recovery.TX_ROOT_NAME not in p.parts)

    def _stage_write_error_with_foreign(self, foreign_bytes, expected_state):
        expected = self.member_bytes("data/printers.json")
        printers, state, outcome = self.stage_write_scenario(foreign_bytes)
        self.assertEqual([c[0] for c in state["calls"]], ["partial", "ENOSPC"])
        # The third party is present, same identity, same bytes; the original is kept without loss.
        self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        self.assertEqual(state["retained"].read_bytes(), expected[:1])
        self.assertEqual(outcome[0], "error")
        error = outcome[1]
        self.assertEqual(error.code, "restore_recoverable", str(error))          # never complete, never success
        self.assertFalse(error.details["complete"])
        self.assertEqual([(c["type"], c["state"]) for c in error.details["conflicts"]], [("printers", expected_state)])
        self.assertFalse(printers.exists())
        pending = backup.pending_recovery(str(self.dst), str(self.dst_config))
        self.assertEqual(pending["phase"], "rollback_incomplete")
        self.assertEqual([c["type"] for c in pending["conflicts"]], ["printers"])
        # Startup recovery keeps it recoverable and never deletes it; dismissing keeps it too.
        self.assertEqual(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"], "recoverable")
        self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        backup.dismiss_recovery(str(self.dst), pending["txid"])
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))
        self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        state["name"].unlink()                                   # the fixture's own third party, after observations
        self.assertUntouched()

    def test_stage_write_error_foreign_different_bytes_is_preserved(self):
        self._stage_write_error_with_foreign(b"octets tiers, pas ceux de l'archive", "foreign")

    def test_stage_write_error_foreign_identical_bytes_is_preserved(self):
        self._stage_write_error_with_foreign(self.member_bytes("data/printers.json"), "ambiguous")

    def test_stage_residue_is_reported_until_its_owner_removes_it(self):
        """The recorded leftover keeps the restore recoverable; it is never removed by us. Once the third
        party removes its own object, the next recovery completes (data files already exact)."""
        printers, state, outcome = self.stage_write_scenario(b"objet tiers temporaire")
        self.assertEqual(outcome[1].code, "restore_recoverable")
        self.assertEqual(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"], "recoverable")
        self.assertTrue(state["name"].exists())
        state["name"].unlink()                                     # the third party removes its own object
        self.assertEqual(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"], "recovered")
        self.assertUntouched()

    def test_stage_write_error_without_substitution_cleans_owned_temporary(self):
        printers, state, outcome = self.stage_write_scenario(None)
        self.assertEqual([c[0] for c in state["calls"]], ["partial", "ENOSPC"])
        self.assertEqual(outcome[0], "error")
        self.assertEqual(outcome[1].code, "restore_failed", str(outcome[1]))
        self.assertTrue(outcome[1].details["complete"])
        self.assertEqual(outcome[1].details["conflicts"], [])
        self.assertFalse(state["name"].exists())                   # our own temporary, removed
        self.assertEqual(self.leftover_temporaries(), [])
        self.assertUntouched()

    def test_stage_partial_write_without_failure_restores_exactly(self):
        printers, state, outcome = self.stage_write_scenario(None, fail=False)
        self.assertEqual(state["calls"][0], ("partial", 1))
        self.assertTrue(any(c[0] == "write" for c in state["calls"][1:]), state["calls"])
        self.assertEqual(outcome[0], "success", outcome[1] if outcome[0] == "error" else None)
        self.assertEqual(printers.read_bytes(), self.member_bytes("data/printers.json"))
        self.assertEqual(self.leftover_temporaries(), [])
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))

    # ── Staging residue born during a rollback or revert: kept in the journal until resolved (B03/05) ──
    FRESH_BOOTSTRAP = textwrap.dedent("""
        import json, sys
        root, home, config = sys.argv[1:4]
        sys.path[:0] = [root + "/src", root]
        from spoolscribe import recovery
        status = recovery.bootstrap(home, config)
        pending = recovery.pending_recovery(home, config)
        residues = recovery.read_journal(__import__("pathlib").Path(pending["dir"]))["residues"] if pending else None
        print(json.dumps({"state": status["state"], "code": status["code"], "pending": pending is not None,
                          "phase": pending and pending["phase"], "residues": residues,
                          "conflicts": pending and pending["conflicts"]}))
    """)

    def fresh_bootstrap(self) -> dict:
        """recovery.bootstrap() in a new process, no injection, both isolation variables on this destination."""
        env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(self.dst), SPOOLSCRIBE_CONFIG_PATH=str(self.dst_config),
                   PYTHONDONTWRITEBYTECODE="1")
        run = subprocess.run([sys.executable, "-I", "-B", "-c", self.FRESH_BOOTSTRAP, str(ROOT), str(self.dst),
                              str(self.dst_config)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def rollback_stage_failure(self, foreign_bytes, operation):
        """While ``operation()`` rolls back the catalogue (``publish_replace`` of its snapshot), the real staging of
        the temporary gets a real 1-byte partial write; the original is moved to a retention name outside the
        active tree (kept alive), a third party is created exclusively at the freed name, then ENOSPC once."""
        catalogue = self.dst / "data" / "polymaker_db.json"
        retained_dir = self.root / "retained"
        retained_dir.mkdir(exist_ok=True)
        real_write, state = os.write, {"calls": []}

        def staged_name(fd):
            st = os.fstat(fd)
            for candidate in catalogue.parent.iterdir():
                if candidate.name.startswith(".polymaker_db.json.") and candidate.name.endswith(".tmp"):
                    cs = candidate.lstat()
                    if (cs.st_dev, cs.st_ino) == (st.st_dev, st.st_ino):
                        return candidate
            return None

        def wrapped(fd, data):
            if not state.get("armed"):
                return real_write(fd, data)
            if "fd" not in state:
                name = staged_name(fd)
                if name is None:
                    return real_write(fd, data)
                state.update(fd=fd, name=name)
                written = real_write(fd, bytes(data[:1]))
                state["calls"].append(("partial", written))
                retained = retained_dir / name.name
                os.rename(name, retained)
                state.update(retained=retained, foreign=self.foreign_create(name, foreign_bytes))
                return written
            if fd == state["fd"] and not state.get("failed"):
                state["failed"] = True
                state["calls"].append(("ENOSPC", 0))
                raise OSError(errno.ENOSPC, "No space left on device (injecté)")
            return real_write(fd, data)
        with patch.object(os, "write", wrapped):
            outcome = operation(state)
        self.assertEqual([c[0] for c in state["calls"]], ["partial", "ENOSPC"], "staging du rollback non observé")
        return catalogue, state, outcome

    def restore_then_rollback_stage_failure(self, foreign_bytes):
        analysis = self.analysis()

        def operation(state):
            def hook(label):
                if label == "before_commit":                 # all six publications done; one EIO, no commit
                    state["armed"] = True
                    raise OSError(errno.EIO, "panne simulée avant commit")
            with patch.object(backup, "_FAULT_HOOK", hook), self.assertRaises(backup.BackupError) as caught:
                backup.restore_backup(analysis)
            return caught.exception
        return self.rollback_stage_failure(foreign_bytes, operation)

    def assertResidueKept(self, state, foreign_bytes, error, expected_state):
        self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        self.assertEqual(len(state["retained"].read_bytes()), 1)            # the original, kept alive, untouched
        self.assertEqual(error.code, "restore_recoverable", str(error))
        self.assertFalse(error.details["complete"])
        residues = [c for c in error.details["conflicts"] if c.get("temporary") == str(state["name"])]
        self.assertEqual([(c["type"], c["state"]) for c in residues], [("catalogue", expected_state)])
        txdir = Path(error.details["dir"])
        journal = recovery.read_journal(txdir)                               # durable, not only in memory
        self.assertEqual(journal["phase"], "rollback_incomplete")
        self.assertEqual([(r["temporary"], r["state"]) for r in journal["residues"]], [(str(state["name"]), expected_state)])
        self.assertFalse([d for d in (self.dst / recovery.TX_ROOT_NAME).glob("tx-*")
                          if recovery._quick_phase(d) == "committed"])

    def assertFreshBootstrapKeepsResidue(self, state, foreign_bytes, expected_state):
        for attempt in (1, 2):                                               # repeated: kept, never duplicated
            fresh = self.fresh_bootstrap()
            self.assertEqual(fresh["state"], "recoverable", fresh)
            self.assertTrue(fresh["pending"])
            self.assertEqual(fresh["phase"], "rollback_incomplete")
            self.assertEqual([(r["temporary"], r["state"]) for r in fresh["residues"]],
                             [(str(state["name"]), expected_state)], attempt)
            self.assertForeignIntact(state["name"], state["foreign"], foreign_bytes)
        # The business files are back to their previous bytes; the residue alone keeps the state recoverable.
        current = tree(self.dst, self.dst_config)
        current.pop("data/" + state["name"].name)
        self.assertEqual(current, self.before)

    def test_rollback_staging_residue_survives_fresh_bootstrap(self):
        """B03/05 rollback-different: the residue of a staging conflict born in the rollback is never forgotten."""
        foreign = b"objet tiers de 36 octets, pas l'instantane"
        catalogue, state, error = self.restore_then_rollback_stage_failure(foreign)
        self.assertResidueKept(state, foreign, error, "foreign")
        self.assertFreshBootstrapKeepsResidue(state, foreign, "foreign")
        backup.dismiss_recovery(str(self.dst), backup.pending_recovery(str(self.dst), str(self.dst_config))["txid"])
        state["name"].unlink()                                    # the fixture's own third party, after observations
        self.assertUntouched()

    def test_rollback_staging_residue_with_identical_snapshot_bytes_survives_fresh_bootstrap(self):
        """Same, the third party carries the exact bytes of the snapshot being restored: ambiguous, kept."""
        snapshot = self.before["data/polymaker_db.json"]
        catalogue, state, error = self.restore_then_rollback_stage_failure(snapshot)
        self.assertResidueKept(state, snapshot, error, "ambiguous")
        self.assertFreshBootstrapKeepsResidue(state, snapshot, "ambiguous")
        backup.dismiss_recovery(str(self.dst), backup.pending_recovery(str(self.dst), str(self.dst_config))["txid"])
        state["name"].unlink()
        self.assertUntouched()

    def test_rollback_staging_residue_resolved_when_its_owner_removes_it(self):
        foreign = b"objet tiers retire ensuite par son proprietaire"
        catalogue, state, error = self.restore_then_rollback_stage_failure(foreign)
        self.assertFreshBootstrapKeepsResidue(state, foreign, "foreign")
        elsewhere = self.root / "owner-moved" / state["name"].name
        elsewhere.parent.mkdir()
        os.rename(state["name"], elsewhere)                       # the owner really moves its object away
        fresh = self.fresh_bootstrap()
        self.assertEqual(fresh["state"], "recovered", fresh)
        self.assertFalse(fresh["pending"])
        self.assertEqual(elsewhere.read_bytes(), foreign)          # never deleted by the product
        self.assertUntouched()

    def test_rollback_staging_residue_dismissed_explicitly_keeps_object(self):
        foreign = b"objet tiers conserve apres classement"
        catalogue, state, error = self.restore_then_rollback_stage_failure(foreign)
        self.assertFreshBootstrapKeepsResidue(state, foreign, "foreign")
        txid = backup.pending_recovery(str(self.dst), str(self.dst_config))["txid"]
        backup.dismiss_recovery(str(self.dst), txid)
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))
        journal = recovery.read_journal(self.dst / recovery.TX_ROOT_NAME / (recovery.TX_PREFIX + txid))
        self.assertEqual(journal["phase"], "dismissed")
        self.assertNotIn("residues", journal)
        self.assertEqual([r["temporary"] for r in journal["dismissed_residues"]], [str(state["name"])])
        self.assertForeignIntact(state["name"], state["foreign"], foreign)
        self.assertEqual(self.fresh_bootstrap()["state"], "clean")
        state["name"].unlink()
        self.assertUntouched()

    def test_journal_residue_fields_are_optional_and_strictly_validated(self):
        base = {"format": recovery.JOURNAL_FORMAT, "version": recovery.JOURNAL_VERSION, "phase": "rollback_incomplete",
                "items": []}
        recovery.validate_journal(dict(base))                                # v2 without the optional fields
        good = {"target": "/a/b.json", "temporary": "/a/.b.json.x.tmp", "state": "foreign"}
        recovery.validate_journal(dict(base, residues=[good], dismissed_residues=[dict(good, state="ambiguous")]))
        for bad in ({}, dict(good, target="relatif.json"), dict(good, temporary=None), dict(good, state="owned"), "x"):
            for key in ("residues", "dismissed_residues"):
                with self.subTest(key=key, residue=bad), self.assertRaises(ValueError):
                    recovery.validate_journal(dict(base, **{key: [bad]}))
        with self.assertRaises(ValueError):
            recovery.validate_journal(dict(base, residues={"not": "a list"}))
        journal = dict(base)
        recovery.record_residue(journal, good)
        recovery.record_residue(journal, dict(good))                        # same temporary: recorded once
        self.assertEqual(journal["residues"], [good])

    def test_revert_staging_residue_is_kept_recoverable(self):
        """An explicit revert also stages through publish_replace: its residue is kept as well."""
        result = backup.restore_backup(self.analysis())
        foreign = b"objet tiers pendant l'annulation explicite"

        def operation(state):
            state["armed"] = True
            return backup.revert_restore(str(self.dst), result.txid, str(self.dst_config))
        catalogue, state, outcome = self.rollback_stage_failure(foreign, operation)
        self.assertEqual(outcome.state, "recoverable")
        self.assertIn((str(state["name"]), "foreign"), [(c.get("temporary"), c["state"]) for c in outcome.conflicts])
        self.assertForeignIntact(state["name"], state["foreign"], foreign)
        fresh = self.fresh_bootstrap()
        self.assertEqual(fresh["state"], "recoverable", fresh)
        self.assertEqual(fresh["phase"], "reverting")
        self.assertEqual([r["temporary"] for r in fresh["residues"]], [str(state["name"])])
        self.assertForeignIntact(state["name"], state["foreign"], foreign)

    def test_failed_rollback_keeps_journal_then_recovery_finishes(self):
        analysis = self.analysis()

        armed = []

        def hook(label):
            if label == "published:3":
                armed.append(True)
                raise OSError(errno.EIO, "panne")
        real = recovery._stage_temporary

        def unplugged(path, data):               # after the fault, rollback rewrites fail (the journal still works)
            if armed:
                raise OSError(errno.EIO, "disque retiré")
            return real(path, data)
        with patch.object(backup, "_FAULT_HOOK", hook), patch.object(recovery, "_stage_temporary", unplugged):
            error = self.assertCode("restore_recoverable", backup.restore_backup, analysis)
        self.assertTrue(error.details["errors"])
        pending = backup.pending_recovery(str(self.dst), str(self.dst_config))
        self.assertEqual(pending["phase"], "rollback_incomplete")
        self.assertFalse(pending["busy"])
        self.assertTrue(pending["published"])
        self.assertCode("recovery_pending", backup.restore_backup, self.analysis_unchecked())
        status = recovery.bootstrap(str(self.dst), str(self.dst_config))
        self.assertEqual(status["state"], "recovered", status)
        self.assertUntouched()

    def analysis_unchecked(self):
        analysis = self.analysis()
        return analysis

    def test_success_then_explicit_revert_restores_exact_previous_state(self):
        result = backup.restore_backup(self.analysis())
        self.assertNotEqual(tree(self.dst, self.dst_config), self.before)
        kept = backup.committed_restores(str(self.dst))
        self.assertEqual(kept[0]["txid"], result.txid)
        self.assertTrue(Path(result.snapshot_dir).is_dir())
        outcome = backup.revert_restore(str(self.dst), result.txid, str(self.dst_config))
        self.assertEqual(outcome.state, "recovered")
        self.assertEqual(outcome.code, "recovery_reverted")
        self.assertUntouched()                              # created files removed, replaced ones exact
        self.assertCode("not_found", backup.revert_restore, str(self.dst), result.txid)

    def test_revert_never_overwrites_a_later_change(self):
        result = backup.restore_backup(self.analysis())
        db = self.dst / "data" / "polymaker_db.json"
        db.write_bytes(b'{"_products": {}, "_skus": {}, "_brands": {}}')
        outcome = backup.revert_restore(str(self.dst), result.txid, str(self.dst_config))
        self.assertEqual(outcome.state, "recoverable")
        self.assertEqual([c["type"] for c in outcome.conflicts], ["catalogue"])
        self.assertEqual(db.read_bytes(), b'{"_products": {}, "_skus": {}, "_brands": {}}')
        self.assertEqual(backup.pending_recovery(str(self.dst), str(self.dst_config))["phase"], "reverting")
        dismissed = backup.dismiss_recovery(str(self.dst), result.txid)
        self.assertEqual(dismissed.state, "cleaned")
        self.assertIsNone(backup.pending_recovery(str(self.dst), str(self.dst_config)))

    def test_snapshots_are_pruned_to_the_newest_ones(self):
        for _ in range(recovery.KEEP_SNAPSHOTS + 1):
            backup.restore_backup(self.analysis())
            db = self.dst / "data" / "polymaker_db.json"
            data = json.loads(db.read_text())
            data["_brands"]["n%d" % len(data["_brands"])] = {}
            db.write_text(json.dumps(data))
        self.assertEqual(len(backup.committed_restores(str(self.dst))), recovery.KEEP_SNAPSHOTS)

    def test_restore_lock_excludes_a_second_restoration(self):
        analysis = self.analysis()
        with recovery.restore_lock(self.dst):
            self.assertCode("busy", backup.restore_backup, analysis)
        self.assertUntouched()


CRASH_SCRIPT = textwrap.dedent("""
    import os, sys
    sys.path[:0] = [sys.argv[1] + "/src", sys.argv[1]]
    from spoolscribe import backup
    archive, home, config, label = sys.argv[2:6]
    analysis = backup.analyze_backup(archive, backup.Paths.for_home(home, config))
    def hook(seen):
        if seen == label:
            os._exit(17)          # abrupt stop: no rollback, no cleanup, lock released by the OS
    backup._FAULT_HOOK = hook
    backup.recovery._PUBLISH_HOOK = hook      # "linked:<name>" / "replaced:<name>": after publication, before cleanup
    backup.restore_backup(analysis)
    sys.exit(0)
""")


class CrashRecoveryTests(Fixture):
    """Abrupt termination at each publication boundary, then startup recovery."""

    def setUp(self):
        super().setUp()
        self.make()
        self.seed_destination()
        self.baseline = self.root / "baseline"
        shutil.copytree(self.dst, self.baseline / "home")
        shutil.copytree(self.dst_config.parent, self.baseline / "config")
        self.before = tree(self.dst, self.dst_config)
        self.script = self.root / "crash.py"
        self.script.write_text(CRASH_SCRIPT)

    def reset(self):
        shutil.rmtree(self.dst)
        shutil.rmtree(self.dst_config.parent)
        shutil.copytree(self.baseline / "home", self.dst)
        shutil.copytree(self.baseline / "config", self.dst_config.parent)

    def crash(self, label):
        env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(self.root / "env-home"),
                   SPOOLSCRIBE_CONFIG_PATH=str(self.root / "env-home" / "config.json"), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-I", "-B", str(self.script), str(ROOT), str(self.archive),
                               str(self.dst), str(self.dst_config), label],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_crash_at_each_boundary_is_rolled_back_at_startup(self):
        work = [e for e in backup.analyze_backup(self.archive, self.dst_paths).entries if e["action"] != "unchanged"]
        labels = ["staged", "journal"]
        for i, entry in enumerate(work):      # proof written / published (before cleanup) / published and cleaned
            labels += [f"proof:{i}", ("linked:" if entry["current"] is None else "replaced:") + Path(entry["target"]).name,
                       f"published:{i}"]
        labels += ["before_commit", "committed"]
        self.assertEqual(len(labels), 2 + 3 * len(work) + 2)
        for label in labels:
            with self.subTest(label=label):
                self.reset()
                run = self.crash(label)
                self.assertEqual(run.returncode, 17, run.stderr)
                pending = recovery.pending_recovery(str(self.dst), str(self.dst_config))
                if label == "committed":
                    self.assertIsNone(pending)
                    restored = tree(self.dst, self.dst_config)
                    self.assertEqual(restored["data/polymaker_db.json"], (self.src / "data/polymaker_db.json").read_bytes())
                    # Config lives outside DATA_HOME: its pointer is cleaned at the next start.
                    status = recovery.bootstrap(str(self.dst), str(self.dst_config))
                    self.assertIn(status["state"], ("cleaned", "clean"), status)
                    self.assertFalse(recovery.pointer_path(self.dst_config).exists())
                    self.assertEqual(tree(self.dst, self.dst_config), restored)
                    continue
                self.assertIsNotNone(pending)
                self.assertEqual(pending["phase"], "staging" if label == "staged" else "publishing")
                if label.startswith(("published:", "linked:", "replaced:")):
                    self.assertTrue(pending["published"])
                    self.assertTrue(recovery.pointer_path(self.dst_config).exists())
                status = recovery.bootstrap(str(self.dst), str(self.dst_config))
                self.assertIn(status["state"], ("recovered", "cleaned"), status)
                self.assertEqual(tree(self.dst, self.dst_config), self.before)
                self.assertIsNone(recovery.pending_recovery(str(self.dst), str(self.dst_config)))
                self.assertFalse(recovery.pointer_path(self.dst_config).exists())

    def test_third_party_change_after_crash_is_kept_and_reported_recoverable(self):
        run = self.crash("published:2")
        self.assertEqual(run.returncode, 17, run.stderr)
        pending = recovery.pending_recovery(str(self.dst), str(self.dst_config))
        published = pending["published"][0]
        Path(published["target"]).write_text("modifié par un tiers")
        status = recovery.bootstrap(str(self.dst), str(self.dst_config))
        self.assertEqual(status["state"], "recoverable", status)
        self.assertEqual(status["code"], "recovery_incomplete")
        self.assertEqual(Path(published["target"]).read_text(), "modifié par un tiers")
        self.assertEqual(recovery.pending_recovery(str(self.dst), str(self.dst_config))["phase"],
                         "rollback_incomplete")
        # Every other published file was restored; the journal and snapshots remain.
        current = tree(self.dst, self.dst_config)
        for key, data in self.before.items():
            if not str(Path(published["target"])).endswith(key.replace("<config>", "config.json")):
                self.assertEqual(current.get(key), data, key)
        again = recovery.bootstrap(str(self.dst), str(self.dst_config))
        self.assertEqual(again["state"], "recoverable")
        txid = recovery.pending_recovery(str(self.dst), str(self.dst_config))["txid"]
        recovery.dismiss_recovery(self.dst, txid)
        self.assertEqual(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"], "clean")

    def test_recovery_from_another_data_home_finds_the_config_pointer(self):
        run = self.crash("published:5")        # config (outside DATA_HOME) is published by then
        self.assertEqual(run.returncode, 17, run.stderr)
        self.assertNotEqual(self.dst_config.read_bytes(), self.before["<config>"])
        other_home = self.root / "other-home"
        pending = recovery.pending_recovery(str(other_home), str(self.dst_config))
        self.assertIsNotNone(pending)
        self.assertEqual(recovery.bootstrap(str(other_home), str(self.dst_config))["state"], "recovered")
        self.assertEqual(tree(self.dst, self.dst_config), self.before)
        self.assertFalse(other_home.exists())


# ── Startup bootstrap ─────────────────────────────────────────────────────
PATHS_SCRIPT = textwrap.dedent("""
    import json, sys
    sys.path[:0] = [sys.argv[1] + "/src", sys.argv[1]]
    from spoolscribe import recovery
    computed = [recovery.data_home(), recovery.config_path()]
    assert "spoolscribe.core" not in sys.modules
    from spoolscribe import core
    print(json.dumps({"recovery": computed, "core": [core.DATA_HOME, core.CONFIG_PATH],
                      "user": [recovery.user_data_dir(), core.user_data_dir()]}))
""")

ORDER_SCRIPT = textwrap.dedent("""
    import importlib.abc, json, os, runpy, sys
    root, entry, home, config, report = sys.argv[1:6]
    sys.path[:0] = [root + "/src", root]
    seen = {}

    class Watch(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in ("spoolscribe.core", "spoolscribe.app_gui") and name not in seen:
                from spoolscribe import recovery
                seen[name] = recovery.pending_recovery(home, config) is None
                if name == "spoolscribe.app_gui":
                    raise ImportError("stop: no GUI in this test")
            return None

    sys.meta_path.insert(0, Watch())
    try:
        if entry == "gui_entry":
            runpy.run_path(root + "/packaging/gui_entry.py", run_name="not_main")
        elif entry == "module":
            runpy.run_module("spoolscribe", run_name="__main__")
        else:
            import spoolscribe.convert_profile
    except ImportError as exc:
        if "stop:" not in str(exc):
            raise
    from spoolscribe import recovery
    json.dump({"seen": seen, "status": recovery.STARTUP_STATUS["state"]}, open(report, "w"))
""")


class BootstrapTests(Fixture):
    def run_python(self, script, *args, env=None):
        path = self.root / "script.py"
        path.write_text(script)
        return subprocess.run([sys.executable, "-I", "-B", str(path), str(ROOT), *map(str, args)],
                              env=env, capture_output=True, text=True, timeout=60)

    def test_paths_equal_core_for_every_environment_combination(self):
        fake_home = self.root / "fake-home"
        fake_home.mkdir()
        base = {k: v for k, v in os.environ.items()
                if k not in ("SPOOLSCRIBE_DATA_HOME", "SPOOLSCRIBE_CONFIG_PATH", "XDG_CONFIG_HOME", "APPDATA")}
        base.update(HOME=str(fake_home), USERPROFILE=str(fake_home), PYTHONDONTWRITEBYTECODE="1",
                    SPOOLSCRIBE_RESOURCE_DIR=str(ROOT))
        combos = [
            {"SPOOLSCRIBE_DATA_HOME": str(self.root / "h1"), "SPOOLSCRIBE_CONFIG_PATH": str(self.root / "c1.json")},
            {"SPOOLSCRIBE_DATA_HOME": str(self.root / "h2")},
            {"SPOOLSCRIBE_CONFIG_PATH": str(self.root / "c3.json")},
            {},
            {"SPOOLSCRIBE_DATA_HOME": "", "XDG_CONFIG_HOME": str(self.root / "xdg"), "APPDATA": str(self.root / "ad")},
        ]
        for extra in combos:
            with self.subTest(env=extra):
                run = self.run_python(PATHS_SCRIPT, env=dict(base, **extra))
                self.assertEqual(run.returncode, 0, run.stderr)
                values = json.loads(run.stdout)
                self.assertEqual(values["recovery"], values["core"])
                self.assertEqual(values["user"][0], values["user"][1])
        self.assertEqual(list(fake_home.iterdir()), [])      # importing core created nothing in the fake home
        for extra in ({}, {"XDG_CONFIG_HOME": str(self.root / "x")}, {"APPDATA": str(self.root / "a")}):
            with patch.dict(os.environ, extra):
                from spoolscribe import core
                self.assertEqual(recovery.user_data_dir(), core.user_data_dir())

    def test_bootstrap_without_journal_is_a_cheap_no_op(self):
        home = self.root / "fresh"
        status = recovery.bootstrap(str(home), str(self.root / "fresh-config.json"))
        self.assertEqual(status["state"], "clean")
        self.assertIs(recovery.STARTUP_STATUS, status)
        self.assertFalse(home.exists())
        self.assertIsNone(recovery.pending_recovery(str(home), str(self.root / "fresh-config.json")))
        status = recovery.bootstrap(str(self.src), str(self.src_config))
        self.assertEqual(status["state"], "clean")
        self.assertFalse((self.src / recovery.TX_ROOT_NAME).exists())

    def test_stale_pointer_and_finished_leftovers_are_cleaned_without_creating_folders(self):
        home = self.root / "never-created"
        config = self.root / "cfg" / "config.json"
        config.parent.mkdir()
        recovery.write_pointer(config, self.root / "gone" / recovery.TX_ROOT_NAME / "tx-x")
        status = recovery.bootstrap(str(home), str(config))
        self.assertEqual(status["state"], "cleaned")
        self.assertFalse(recovery.pointer_path(config).exists())
        self.assertFalse(home.exists())
        with recovery.restore_lock(self.src):
            txid, txdir = recovery.new_transaction(self.src)
        recovery.write_journal(txdir, {"format": recovery.JOURNAL_FORMAT, "version": recovery.JOURNAL_VERSION,
                                       "txid": txid, "phase": "rolled_back", "items": []})
        self.assertEqual(recovery.bootstrap(str(self.src), str(self.src_config))["state"], "cleaned")
        self.assertFalse(txdir.exists())

    def test_legacy_v1_journal_without_proofs_is_kept_and_reported_never_replayed(self):
        """A pre-R2 journal (empty markers, digest ownership) must not drive any deletion or rewrite."""
        target = self.src / "data" / "printers.json"
        data = target.read_bytes()
        with recovery.restore_lock(self.src):
            txid, txdir = recovery.new_transaction(self.src)
        after = hashlib.sha256(data).hexdigest()
        recovery.write_journal(txdir, {"format": recovery.JOURNAL_FORMAT, "version": 1, "txid": txid,
                                       "phase": "publishing", "items": [{
                                           "index": 0, "type": "printers", "member": "data/printers.json",
                                           "target": str(target), "before": None, "after": after,
                                           "snapshot": None, "staged": "new/0"}]})
        (txdir / "done" / "0").touch()                       # v1 marker: no identity, no proof of ownership
        identity = target.stat()
        status = recovery.bootstrap(str(self.src), str(self.src_config))
        self.assertEqual(status["state"], "recoverable", status)
        self.assertIn("version 1", json.dumps(status["errors"], ensure_ascii=False))
        self.assertEqual(target.read_bytes(), data)
        self.assertEqual(target.stat().st_ino, identity.st_ino)
        self.assertTrue(txdir.exists())
        pending = backup.pending_recovery(str(self.src), str(self.src_config))
        self.assertEqual(pending["phase"], "invalid")
        self.make()
        self.assertCode("recovery_pending", backup.restore_backup, backup.analyze_backup(self.archive, self.src_paths))

    @unittest.skipIf(os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0, "droits POSIX requis")
    def test_unwritable_data_folder_gives_a_clear_lock_error(self):
        locked = self.root / "locked"
        locked.mkdir()
        locked.chmod(0o555)
        self.addCleanup(locked.chmod, 0o755)
        with self.assertRaises(backup.BackupError) as caught:
            with recovery.restore_lock(locked):
                pass
        self.assertEqual(caught.exception.code, "lock_unavailable")

    def test_legacy_printer_identifier_is_accepted_in_preferences(self):
        config = json.loads(self.src_config.read_text())
        config["printer_profile"] = "u1_stock"
        self.src_config.write_text(json.dumps(config))
        self.assertTrue(backup.plan_backup(self.src_paths).ok)
        config["printer_profile"] = "imprimante-inconnue"
        self.src_config.write_text(json.dumps(config))
        plan = backup.plan_backup(self.src_paths)
        self.assertEqual([e.code for e in plan.blocking], ["source_invalid"])
        self.assertTrue(backup.plan_backup(self.src_paths, backup.Options(include_config=False)).ok)

    def test_bootstrap_never_raises(self):
        with patch.object(recovery, "_transaction_dirs", side_effect=RuntimeError("boom")):
            status = recovery.bootstrap(str(self.src), str(self.src_config))
        self.assertEqual(status["state"], "error")
        self.assertIn("boom", status["message"])

    def test_busy_transaction_of_a_live_process_is_left_alone(self):
        self.make()
        self.seed_destination()
        analysis = backup.analyze_backup(self.archive, self.dst_paths)
        states = []

        def hook(label):
            if label == "published:1":
                states.append(recovery.bootstrap(str(self.dst), str(self.dst_config))["state"])
                states.append(recovery.pending_recovery(str(self.dst), str(self.dst_config))["busy"])
        with patch.object(backup, "_FAULT_HOOK", hook):
            backup.restore_backup(analysis)
        self.assertEqual(states, ["busy", True])
        self.assertIsNone(recovery.pending_recovery(str(self.dst), str(self.dst_config)))

    def interrupted(self):
        """A destination left with a pending journal (crash after the first publication)."""
        self.make(overwrite=True)
        self.seed_destination()
        before = tree(self.dst, self.dst_config)
        script = self.root / "crash.py"
        script.write_text(CRASH_SCRIPT)
        run = subprocess.run([sys.executable, "-I", "-B", str(script), str(ROOT), str(self.archive), str(self.dst),
                              str(self.dst_config), "published:0"], capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(run.returncode, 17, run.stderr)
        self.assertIsNotNone(recovery.pending_recovery(str(self.dst), str(self.dst_config)))
        return before

    def test_bootstrap_runs_before_core_in_a_fresh_interpreter(self):
        before = self.interrupted()
        script = textwrap.dedent("""
            import json, sys
            sys.path[:0] = [sys.argv[1] + "/src", sys.argv[1]]
            from spoolscribe import recovery
            status = recovery.bootstrap()
            print(json.dumps({"state": status["state"], "core": "spoolscribe.core" in sys.modules,
                              "qt": any(m.startswith("PySide6") for m in sys.modules)}))
        """)
        env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(self.dst), SPOOLSCRIBE_CONFIG_PATH=str(self.dst_config))
        run = self.run_python(script, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), {"state": "recovered", "core": False, "qt": False})
        self.assertEqual(tree(self.dst, self.dst_config), before)

    def test_every_entry_point_recovers_before_importing_the_model(self):
        for entry in ("convert_profile", "module", "gui_entry"):
            with self.subTest(entry=entry):
                if self.dst.exists():
                    shutil.rmtree(self.dst)
                    shutil.rmtree(self.dst_config.parent)
                before = self.interrupted()
                report = self.root / f"{entry}.json"
                env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(self.dst), SPOOLSCRIBE_CONFIG_PATH=str(self.dst_config),
                           QT_QPA_PLATFORM="offscreen")
                run = self.run_python(ORDER_SCRIPT, entry, self.dst, self.dst_config, report, env=env)
                self.assertEqual(run.returncode, 0, run.stderr)
                result = json.loads(report.read_text())
                self.assertEqual(result["status"], "recovered")
                expected = {"spoolscribe.core": True} if entry == "convert_profile" else {"spoolscribe.app_gui": True}
                for name, resolved in expected.items():
                    self.assertIs(result["seen"].get(name), resolved, result)
                self.assertEqual(tree(self.dst, self.dst_config), before)

    def test_recovery_module_imports_only_the_standard_library(self):
        source = (ROOT / "src" / "spoolscribe" / "recovery.py").read_text(encoding="utf-8")
        import ast
        modules = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                modules |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "import relatif interdit")
                modules.add(node.module.split(".")[0])
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib:
            self.assertLessEqual(modules - {"__future__"}, set(stdlib))
        self.assertNotIn("spoolscribe", modules)
        self.assertNotIn("scripts", modules)


if __name__ == "__main__":
    unittest.main()
