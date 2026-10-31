import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import core
from tests.support import product, entry


class OpenSpoolTests(unittest.TestCase):
    def test_no_silent_color_or_brand_defaults(self):
        for value in (None, "", "NOTHEX", 123, False):
            with self.subTest(value=value), self.assertRaises(core.ExportValidationError):
                core.build_openspool(dict(entry(), hex=value), product())
        p = product()
        del p["brand"]
        with self.assertRaises(core.ExportValidationError):
            core.build_openspool(entry(), p)

    def test_invalid_physical_values_and_reversed_ranges(self):
        for field in ("min_temp", "max_temp", "bed_min_temp", "bed_max_temp", "diameter", "density"):
            for value in (None, True, "215", float("nan"), float("inf"), -1):
                with self.subTest(field=field, value=value), self.assertRaises(core.ExportValidationError):
                    core.build_openspool(entry(), dict(product(), **{field: value}))
        for changes in ({"min_temp": 250, "max_temp": 200}, {"bed_min_temp": 80, "bed_max_temp": 60},
                        {"diameter": 0}, {"density": 0}, {"min_temp": 190.5}):
            with self.subTest(changes=changes), self.assertRaises(core.ExportValidationError):
                core.build_openspool(entry(), dict(product(), **changes))

    def test_transparency_multicolor_and_brand_metadata_are_retained(self):
        e = dict(entry(), hex="#aabbcc", alpha="00", additional_color_hexes=["FFFFFF", "000000"])
        meta = {"name": "Polymaker", "website": "https://example.invalid", "origin": "CN",
                "logo_url": "https://example.invalid/logo.svg", "logo_path": "data/logo.svg"}
        p = core.build_openspool(e, product(), meta)
        self.assertEqual(p["color_hex"], "AABBCC")
        self.assertEqual(p["alpha"], "00")
        self.assertEqual(p["additional_color_hexes"], e["additional_color_hexes"])
        self.assertEqual(p["brand_meta"], meta)
        self.assertEqual(p["image"], meta["logo_url"])
        for bad in ({"alpha": None}, {"alpha": 0}, {"additional_color_hexes": "FFFFFF"},
                    {"additional_color_hexes": ["GGGGGG"]}, {"additional_color_hexes": ["FFFFFF"] * 5}):
            with self.subTest(bad=bad), self.assertRaises(core.ExportValidationError):
                core.build_openspool(dict(entry(), **bad), product())

    def test_protocol_and_json_validation(self):
        valid = core.build_openspool(entry(), product())
        for change in ({"protocol": "other"}, {"version": 1}, {"version": "2.0"},
                       {"subtype": 123}, {"brand_meta": {"name": False}}):
            with self.subTest(change=change), self.assertRaises(core.ExportValidationError):
                core.serialize_openspool(dict(valid, **change))

    def test_write_and_preview_are_identical_and_archive_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            e, p = entry(), product()
            preview = core.serialize_openspool(core.build_openspool(e, p))
            out = core.write_openspool(e["sku"], e, p, directory)
            archive = core.write_openspool(e["sku"], e, p, directory, mode="archive")
            self.assertEqual(Path(out).read_text(), preview)
            self.assertNotEqual(out, archive)
            self.assertEqual(json.loads(Path(archive).read_text()), json.loads(preview))
            self.assertIn("\n", Path(archive).read_text())

    def test_capacity_failure_does_not_create_or_overwrite_an_export(self):
        e = dict(entry(), color_name="é" * 1000)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(core.NfcCapacityError):
                core.write_openspool("LOCAL", e, product(), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])
            out = core.write_openspool("LOCAL", e, product(), directory, mode="archive")
            self.assertTrue(Path(out).is_file())

    def test_sku_path_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as directory:
            out = core.write_openspool("../../escape", entry(), product(), directory)
            self.assertEqual(Path(out).parent, Path(directory).resolve())
            self.assertNotIn("..", Path(out).name)

    def test_bad_orca_is_not_silently_ignored(self):
        with patch("core.find_orca_profile", return_value="bad"), patch("core.load_orca_temps", side_effect=ValueError("bad profile")):
            with self.assertRaisesRegex(core.ExportValidationError, "Orca"):
                core.build_openspool(entry(), product())

    def test_existing_orca_overrides_are_applied(self):
        with patch("core.find_orca_profile", return_value="profile"), patch("core.load_orca_temps", return_value={"min_temp": 200, "density": 1.3}):
            p = core.build_openspool(entry(), product(), use_orca_overrides=True)
            self.assertEqual((p["min_temp"], p["density"]), (200, 1.3))

    def test_orca_cannot_silently_replace_a_local_correction(self):
        with patch("core.find_orca_profile", return_value="profile"), patch("core.load_orca_temps", return_value={"min_temp": 200, "density": 1.3}):
            p = core.build_openspool(entry(), product())
            self.assertEqual((p["min_temp"], p["density"]), (190, 1.24))
            missing = dict(product(), min_temp=None)
            self.assertEqual(core.build_openspool(entry(), missing)["min_temp"], 200)
