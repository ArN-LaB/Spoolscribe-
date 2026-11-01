import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core
from spoolscribe import convert_profile
from scripts import db_io
from tests.support import catalogue


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "db.json"
        self.db.write_text(json.dumps(catalogue()), encoding="utf-8")
        paths = patch.multiple(convert_profile, DB_PATH=str(self.db), OUTPUT_DIR=str(self.root / "output"))
        paths.start()
        self.addCleanup(paths.stop)
        cfg = patch.multiple(core, DB_PATH=str(self.db), CONFIG_PATH=str(self.root / "config.json"))
        cfg.start()
        self.addCleanup(cfg.stop)

    def run_cli(self, answers, args=()):
        out = io.StringIO()
        with patch("sys.argv", ["spoolscribe.convert_profile.py", *args]), patch("builtins.input", side_effect=answers), \
             contextlib.redirect_stdout(out):
            code = convert_profile.main()
        return code, out.getvalue()

    def test_export_and_inspection_use_the_same_valid_payload(self):
        code, output = self.run_cli(["PB05001", "i", "o", "q"])
        files = list((self.root / "output").glob("*.json"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text()
        self.assertIn(text, output)
        self.assertEqual(json.loads(text)["color_hex"], "070908")

    def test_missing_color_cancel_produces_no_black_or_database_change(self):
        before = self.db.read_bytes()
        _, output = self.run_cli(["FB04001", "", "q"])
        self.assertIn("Export annulé", output)
        self.assertFalse((self.root / "output").exists())
        self.assertEqual(before, self.db.read_bytes())

    def test_archive_option_keeps_readable_json(self):
        self.run_cli(["PB05001", "o", "q"], ["--export-format", "archive"])
        files = list((self.root / "output").glob("*_archive.json"))
        self.assertEqual(len(files), 1)
        self.assertIn("\n", files[0].read_text())

    def test_ntag215_essential_preview_matches_file(self):
        _, output = self.run_cli(["PB05001", "i", "o", "q"],
                                 ["--tag-type", "NTAG215", "--nfc-profile", "essential", "--reserve-bytes", "32"])
        target, = (self.root / "output").glob("*ntag215_essential.json")
        self.assertIn(target.read_text(), output)
        self.assertNotIn("brand_meta", json.loads(target.read_text()))
        self.assertTrue(core.nfc_size(target.read_text(), tag_type="NTAG215", reserved_bytes=32).fits)

    def test_saved_nfc_default_is_used_until_overridden(self):
        before = self.db.read_bytes()
        code, output = self.run_cli([], ["--tag-type", "NTAG215", "--reserve-bytes", "16", "--save-nfc-default"])
        self.assertEqual(code, 0)
        self.assertIn("NTAG215", output)
        self.assertEqual(self.db.read_bytes(), before)  # configuration only, no database or export
        self.assertEqual(core.nfc_defaults(), dict(tag_type="NTAG215", profile="auto", reserved_bytes=16))
        self.run_cli(["PB05001", "o", "q"])
        self.assertTrue(list((self.root / "output").glob("*ntag215_essential.json")))
        self.run_cli(["PB05001", "o", "q"], ["--tag-type", "NTAG216"])
        self.assertTrue(list((self.root / "output").glob("*ntag216_essential.json")))
        self.assertEqual(core.nfc_defaults()["tag_type"], "NTAG215")  # an override is not a new default

    def test_filtered_list_exits_without_network_or_writes(self):
        before = self.db.read_bytes()
        with patch("spoolscribe.convert_profile.check_and_update_db", side_effect=AssertionError("List must stay offline")):
            code, output = self.run_cli([], ["--list", "--brand", "Polymaker", "--search", "PETG Black", "--limit", "3"])
        self.assertEqual(code, 0)
        self.assertIn("résultats", output)
        self.assertEqual(self.db.read_bytes(), before)
        self.assertFalse((self.root / "output").exists())

    def test_corruption_is_reported_and_restore_requires_explicit_answer(self):
        backup = db_io.backup_db(self.db)
        self.db.write_text("corrupt")
        code, output = self.run_cli([])
        self.assertEqual(code, 1)
        self.assertIn("ERREUR", output)
        code, _ = self.run_cli(["n"], ["--restore-db", str(backup)])
        self.assertEqual(code, 0)
        self.assertEqual(self.db.read_text(), "corrupt")
        self.run_cli(["o", "q"], ["--restore-db", str(backup)])
        self.assertEqual(db_io.load_db(self.db)["_skus"]["PB05001"]["hex"], "070908")

    def test_restore_keeps_exact_backup_and_auto_preferences_without_startup_update(self):
        db = db_io.load_db(self.db)
        db["_last_updated"] = "2020-01-01T00:00:00"
        db["_skus"]["PB05001"].update(hex="ABCDEF", user_note="local")
        db_io.save_db(db, self.db)
        backup = db_io.backup_db(self.db)
        chosen = backup.read_bytes()
        core.set_network_consent(True, auto_update=True)
        preferences = Path(core.CONFIG_PATH).read_bytes()
        self.db.write_text("corrupt")
        with patch("spoolscribe.convert_profile.run_update_pipeline", return_value=[]) as update:
            code, _ = self.run_cli(["o", "q"], ["--restore-db", str(backup)])
        self.assertIn(code, (None, 0))
        update.assert_not_called()
        self.assertEqual(self.db.read_bytes(), chosen)
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), preferences)
        # Restoration blocks automatic work only; explicit U remains available.
        with patch("spoolscribe.convert_profile.ensure_consent_interactive", return_value=True), \
             patch("spoolscribe.convert_profile.run_update_pipeline", return_value=[]) as update, \
             contextlib.redirect_stdout(io.StringIO()):
            convert_profile.check_and_update_db(force=True)
        update.assert_called_once()
        # A fresh process has no in-memory restoration marker.
        with patch.object(core, "_RESTORED_DB_PATHS", set()), \
             patch("spoolscribe.convert_profile.run_update_pipeline", return_value=[]) as update, \
             contextlib.redirect_stdout(io.StringIO()):
            convert_profile.check_and_update_db()
        update.assert_called_once()
