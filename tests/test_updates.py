import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import core
import convert_profile
from scripts import db_io, scrape_spoolman_hex, scrape_spoolman_multibrand_hex, scrape_wholesale
from tests.support import ROOT, small_db


def result(status="unchanged", code=0):
    return subprocess.CompletedProcess([], code,
        stdout=db_io.STEP_PREFIX + json.dumps({"status": status, "message": ""}), stderr="")


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db_path = root / "data/db.json"
        db = small_db()
        db["_last_updated"] = "2020-01-01T00:00:00"
        db_io.save_db(db, self.db_path)
        self.paths = patch.multiple(core, DB_PATH=str(self.db_path), DATA_HOME=str(root),
                                    CONFIG_PATH=str(root / "config.json"))
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def test_no_consent_runs_no_worker_and_makes_no_backup(self):
        before = self.db_path.read_bytes()
        with patch("core.has_network_consent", return_value=False), patch("core._run_step_process") as run:
            results = core.run_update_pipeline()
        run.assert_not_called()
        self.assertEqual(core.update_status(results), "failed")
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertFalse(Path(str(self.db_path) + ".pre-update.bak").exists())

    def test_partial_update_keeps_previous_full_refresh_date(self):
        count = len(core.UPDATE_PIPELINE)
        responses = [result("changed")] + [result("unavailable", 2)] * (count - 1)
        before = self.db_path.read_bytes()
        with patch("core._run_step_process", side_effect=responses), patch("core.mark_updated") as mark:
            results = core.run_update_pipeline(consent=True)
        self.assertEqual(core.update_status(results), "partial")
        mark.assert_not_called()
        db = db_io.load_db(self.db_path)
        self.assertEqual(db["_last_updated"], "2020-01-01T00:00:00")
        self.assertEqual(db["_update_status"], "partial")
        self.assertEqual(Path(str(self.db_path) + ".pre-update.bak").read_bytes(), before)

    def test_full_verified_check_updates_date_even_without_data_changes(self):
        with patch("core._run_step_process", return_value=result()) as run, patch("core.mark_updated") as mark:
            results = core.run_update_pipeline(consent=True)
        self.assertEqual(core.update_status(results), "complete")
        mark.assert_not_called()
        self.assertNotEqual(db_io.load_db(self.db_path)["_last_updated"], "2020-01-01T00:00:00")
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["SPOOLSCRIBE_DATA_HOME"], str(self.db_path.parent.parent))

    def test_zero_success_or_missing_worker_status_is_not_complete(self):
        for response in (result("error", 1), subprocess.CompletedProcess([], 0, stdout="", stderr="")):
            with self.subTest(response=response), patch("core._run_step_process", return_value=response), patch("core.mark_updated") as mark:
                results = core.run_update_pipeline(consent=True)
                self.assertEqual(core.update_status(results), "failed")
                mark.assert_not_called()

    def test_corrupt_database_prevents_all_workers(self):
        self.db_path.write_text("corrupt")
        with patch("core._run_step_process") as run:
            results = core.run_update_pipeline(consent=True)
        run.assert_not_called()
        self.assertEqual(core.update_status(results), "failed")
        self.assertEqual(self.db_path.read_text(), "corrupt")

    def test_timeout_and_missing_script_are_explicit(self):
        with patch("core._run_step_process", side_effect=subprocess.TimeoutExpired("audit", 1)):
            self.assertEqual(core.update_status(core.run_update_pipeline(consent=True)), "failed")
        with patch("core.os.path.isfile", return_value=False), patch("core._run_step_process") as run:
            self.assertEqual(core.update_status(core.run_update_pipeline(consent=True)), "failed")
            run.assert_not_called()

    def test_real_standalone_offline_worker_reports_status_and_preserves_manual_hex(self):
        # A local seed only: no network worker is launched.
        env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(self.db_path.parent.parent), PYTHONDONTWRITEBYTECODE="1")
        expected_path = self.db_path.parent / "polymaker_db.json"
        original = small_db()
        original["_products"]["Prusament PLA"] = dict(original["_products"]["Audit PLA"], brand="Prusament")
        original["_skus"]["PM-PLA-JETBLACK"] = {"product": "Prusament PLA", "color_name": "Jet Black", "hex": "ABCDEF"}
        db_io.save_db(original, expected_path)
        proc = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/seed_prusament.py")],
                              cwd=self.tmp.name, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(db_io.STEP_PREFIX, proc.stdout)
        self.assertEqual(db_io.load_db(expected_path)["_skus"]["PM-PLA-JETBLACK"]["hex"], "ABCDEF")

    def test_prusament_update_preserves_hex_without_force(self):
        fixture = small_db()
        fixture["_products"]["Audit PLA"]["brand"] = "Prusament"
        fixture["_skus"]["LOCAL"]["hex"] = "ABCDEF"
        fixture["_skus"]["LOCAL"]["color_name"] = "Jet Black"
        db_io.save_db(fixture, self.db_path)
        upstream = {"filaments": [{"material": "PLA", "colors": [{"name": "Jet Black", "hex": "24292A"}]}]}
        with patch.object(scrape_spoolman_multibrand_hex, "DB_FILE", str(self.db_path)), \
             patch.object(scrape_spoolman_multibrand_hex, "fetch_brand", return_value=upstream), \
             patch("sys.argv", ["audit"]), contextlib.redirect_stdout(io.StringIO()):
            scrape_spoolman_multibrand_hex.main()
        self.assertEqual(db_io.load_db(self.db_path)["_skus"]["LOCAL"]["hex"], "ABCDEF")

    def test_transparent_unknown_color_remains_an_explicit_user_choice(self):
        fixture = small_db()
        fixture["_products"]["Audit PLA"]["brand"] = "Prusament"
        fixture["_skus"]["LOCAL"].update(hex=None, color_name="Transparent")
        db_io.save_db(fixture, self.db_path)
        upstream = {"filaments": [{"material": "PLA", "colors": [{"name": "Transparent", "hex": "FFFFFF"}]}]}
        with patch.object(scrape_spoolman_multibrand_hex, "DB_FILE", str(self.db_path)), \
             patch.object(scrape_spoolman_multibrand_hex, "fetch_brand", return_value=upstream), \
             patch("sys.argv", ["audit"]), contextlib.redirect_stdout(io.StringIO()):
            scrape_spoolman_multibrand_hex.main()
        stored = db_io.load_db(self.db_path)["_skus"]["LOCAL"]
        self.assertIsNone(stored["hex"])
        self.assertNotIn("alpha", stored)

    def test_remote_errors_cannot_be_successful_empty_results(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            for fetch in (scrape_spoolman_hex.fetch_spoolman, lambda: scrape_wholesale.fetch_page(1)):
                with self.assertRaises(db_io.SourceUnavailable), contextlib.redirect_stdout(io.StringIO()):
                    fetch()

    def test_step_protocol_reports_source_unavailable(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                db_io.run_step(Mock(side_effect=db_io.SourceUnavailable("offline")))
        self.assertEqual(raised.exception.code, 2)
        record = json.loads(out.getvalue().split(db_io.STEP_PREFIX)[1])
        self.assertEqual(record["status"], "unavailable")

    def test_windowed_worker_reports_even_without_standard_streams(self):
        destination = Path(self.tmp.name) / "step-result.json"
        with patch.dict(os.environ, {"SPOOLSCRIBE_STEP_RESULT_PATH": str(destination)}), \
             patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
            with self.assertRaises(SystemExit) as raised:
                db_io.run_step(Mock(side_effect=db_io.SourceUnavailable("offline")))
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(json.loads(destination.read_text())["status"], "unavailable")

    def test_parent_accepts_private_results_without_console_output(self):
        def worker(command, **kwargs):
            path = Path(kwargs["env"]["SPOOLSCRIBE_STEP_RESULT_PATH"])
            path.write_text(json.dumps({"status": "unchanged", "message": ""}))
            return subprocess.CompletedProcess(command, 0, stdout=None, stderr=None)
        with patch("core._run_step_process", side_effect=worker):
            results = core.run_update_pipeline(consent=True)
        self.assertEqual(core.update_status(results), "complete")

    def test_cli_manual_update_can_reconsider_refusal_or_revoke_permission(self):
        for old, answer, expected in ((False, "o", True), (True, "n", False)):
            with self.subTest(old=old), patch("core.consent_was_asked", return_value=True), \
                 patch("core.has_network_consent", return_value=old), \
                 patch("builtins.input", side_effect=[answer, "n"]), patch("core.set_network_consent") as save, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(convert_profile.ensure_consent_interactive(force=True), expected)
                save.assert_called_once_with(expected, auto_update=False)

    def test_frozen_worker_uses_same_status_entrypoint(self):
        script = ROOT / "scripts/seed_prusament.py"
        db_path = self.db_path.parent / "polymaker_db.json"
        db_io.save_db(small_db(), db_path)
        with patch.dict(os.environ, {"SPOOLSCRIBE_DATA_HOME": str(self.db_path.parent.parent)}), \
             patch.object(sys, "argv", ["app", core.RUN_SCRIPT_FLAG, str(script)]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                core.maybe_run_as_script_worker(sys.argv)
        self.assertEqual(raised.exception.code, 0)
        self.assertIn(db_io.STEP_PREFIX, output.getvalue())
