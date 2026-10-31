import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import core
from scripts import db_io, download_orca_profiles, import_orca_profiles
from tests.support import ROOT, small_db


def profile():
    return {"nozzle_temperature_range_low": ["200"], "nozzle_temperature_range_high": ["230"],
            "filament_density": ["1.24"], "filament_diameter": ["1.75"],
            "filament_type": ["PLA"], "hot_plate_temp": ["60"]}


class OrcaTests(unittest.TestCase):
    def test_all_bundled_profiles_are_valid(self):
        files = list((ROOT / "orca_profiles").glob("*.json"))
        self.assertGreaterEqual(len(files), 48)
        for path in files:
            with self.subTest(path=path.name):
                core._validate_physical(core.load_orca_temps(str(path)))

    def test_missing_scalar_nonfinite_and_fractional_fields_are_rejected(self):
        bad_profiles = [{}, {"nozzle_temperature_range_low": "215"}]
        for key, value in (("nozzle_temperature_range_low", "215"),
                           ("nozzle_temperature_range_low", ["215.5"]),
                           ("filament_density", ["nan"]), ("filament_diameter", ["0"]),
                           ("hot_plate_temp", [True]), ("nozzle_temperature_range_high", ["100"])):
            bad_profiles.append(dict(profile(), **{key: value}))
        for p in bad_profiles:
            with self.subTest(profile=p), self.assertRaises(db_io.DatabaseError):
                db_io.orca_values(p)

    def test_download_rejects_invalid_profile_and_reports_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            preset = {"brand": "Snapmaker", "model": "U1", "slicer": "OrcaSlicer", "material": "Audit PLA", "path": "preset.json"}
            with patch.object(download_orca_profiles, "ORCA_DIR", directory), patch("sys.argv", ["audit"]), \
                 patch.object(download_orca_profiles, "fetch_json", return_value={"presets": [preset]}), \
                 patch.object(download_orca_profiles, "fetch_bytes", return_value=b"{}"):
                with self.assertRaises(ValueError), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    download_orca_profiles.main()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_download_names_cannot_escape_directory(self):
        for value in ("../outside", "folder\\file", "", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                download_orca_profiles.local_filename(value)

    def test_import_preserves_local_physical_corrections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "db.json"
            db = small_db()
            db["_products"]["Audit PLA"]["min_temp"] = 205
            db_io.save_db(db, path)
            (root / "Audit PLA @Snapmaker U1 - OrcaSlicer.json").write_text(json.dumps(profile()))
            with patch.object(import_orca_profiles, "DB_FILE", str(path)), \
                 patch.object(import_orca_profiles, "ORCA_DIR", str(root)), patch("sys.argv", ["audit"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    import_orca_profiles.main()
            self.assertEqual(db_io.load_db(path)["_products"]["Audit PLA"]["min_temp"], 205)
