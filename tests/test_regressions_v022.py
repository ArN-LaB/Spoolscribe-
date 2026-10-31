"""Offline reproductions of the final v0.2.2 review findings R1 and R3."""
import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import core
from scripts import (
    db_io, scrape_spoolman_hex as spool_poly,
    scrape_spoolman_multibrand_hex as spool_multi,
    scrape_thefilamentdb_hex as filament_poly,
    scrape_thefilamentdb_multibrand_hex as filament_multi,
    seed_prusament, seed_rosa3d, sync_multibrand_assets as assets,
)
from tests.support import small_db


class SourceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "data/db.json"
        self.dump = self.root / "source.jsonl.gz"
        db = small_db()
        db["_last_updated"] = "2020-01-01T00:00:00"
        db_io.save_db(db, self.db_path)
        self.write_dump([])

    def write_dump(self, rows):
        with gzip.open(self.dump, "wt", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")

    def run_source(self, module, data=None, sides=None):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(module, "DB_FILE", str(self.db_path)))
            stack.enter_context(patch("sys.argv", ["offline-review"]))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            if module is spool_poly:
                stack.enter_context(patch.object(module, "fetch_spoolman", return_value=data))
            elif module is spool_multi:
                stack.enter_context(patch.object(module, "fetch_brand", **(
                    {"side_effect": sides} if sides is not None else {"return_value": data})))
            else:
                stack.enter_context(patch.object(module, "THEFILE", str(self.dump)))
            return db_io._execute_step(module.main, str(self.db_path))

    def test_spoolman_empty_or_unusable_sources_are_not_successful(self):
        for module in (spool_poly, spool_multi):
            for data in ({}, {"filaments": []}, {"filaments": [{"name": "PLA", "material": "PLA", "colors": []}]},
                         {"filaments": [{"name": "PLA", "material": "PLA", "colors": [{"name": "Red", "hex": "ZZZZZZ"}]}]}):
                with self.subTest(module=module.__name__, data=data):
                    before = self.db_path.read_bytes()
                    record, code = self.run_source(module, data)
                    self.assertEqual((record["status"], code), ("unavailable", 2))
                    self.assertEqual(self.db_path.read_bytes(), before)

    def test_thefilamentdb_empty_or_irrelevant_dump_is_not_successful(self):
        for rows in ([], [{"brand": "Other", "name": "PLA", "colorName": "Red", "colorHex": "FF0000"}],
                     [{"brand": b, "name": "PLA", "colorName": "Red", "colorHex": "ZZZZZZ"}
                      for b in ("Polymaker", "Prusament", "ROSA3D")]):
            self.write_dump(rows)
            for module in (filament_poly, filament_multi):
                with self.subTest(module=module.__name__, rows=rows):
                    record, code = self.run_source(module)
                    self.assertEqual((record["status"], code), ("unavailable", 2))

    def test_valid_sources_with_no_matching_change_are_successful(self):
        data = {"filaments": [{"name": "Other PLA", "material": "PLA", "colors": [{"name": "Other Red", "hex": "FF0000"}]}]}
        self.write_dump([{"brand": b, "name": "PLA", "colorName": "Other Red", "colorHex": "FF0000"}
                         for b in ("Polymaker", "Prusament", "ROSA3D")])
        for module in (spool_poly, spool_multi, filament_poly, filament_multi):
            with self.subTest(module=module.__name__):
                record, code = self.run_source(module, data)
                self.assertEqual((record["status"], code), ("unchanged", 0))

    def test_multibrand_partial_sources_keep_useful_color_and_report_partial(self):
        db = db_io.load_db(self.db_path)
        db["_products"]["Audit PLA"]["brand"] = "Prusament"
        db["_skus"]["LOCAL"]["hex"] = None
        db_io.save_db(db, self.db_path)
        data = {"filaments": [{"material": "PLA", "colors": [{"name": "Red", "hex": "FF0000"}]}]}
        record, code = self.run_source(spool_multi, sides=[data, {"filaments": []}])
        self.assertEqual((record["status"], code), ("partial", 3))
        self.assertEqual(db_io.load_db(self.db_path)["_skus"]["LOCAL"]["hex"], "FF0000")
        db = db_io.load_db(self.db_path)
        db["_skus"]["LOCAL"]["hex"] = None
        db_io.save_db(db, self.db_path)
        self.write_dump([{"brand": "Prusament", "name": "PLA", "colorName": "Red", "colorHex": "FF0000"}])
        record, code = self.run_source(filament_multi)
        self.assertEqual((record["status"], code), ("partial", 3))
        self.assertEqual(db_io.load_db(self.db_path)["_skus"]["LOCAL"]["hex"], "FF0000")

    def test_empty_required_step_cannot_advance_refresh_date(self):
        for module in (spool_poly, spool_multi, filament_poly, filament_multi):
            with self.subTest(module=module.__name__):
                record, code = self.run_source(module, {"filaments": []})
                failed = subprocess.CompletedProcess([], code, stdout=db_io.STEP_PREFIX + json.dumps(record), stderr="")
                good = subprocess.CompletedProcess([], 0, stdout=db_io.STEP_PREFIX + '{"status":"unchanged"}', stderr="")
                with patch.multiple(core, DB_PATH=str(self.db_path), DATA_HOME=str(self.root)), \
                     patch("core.subprocess.run", side_effect=[failed] + [good] * (len(core.UPDATE_PIPELINE) - 1)):
                    results = core.run_update_pipeline(consent=True)
                self.assertEqual(core.update_status(results), "partial")
                self.assertEqual(db_io.load_db(self.db_path)["_last_updated"], "2020-01-01T00:00:00")

    def test_asset_sources_total_failure_partial_and_valid(self):
        for _, _, filename, _ in assets.BRANDS:
            (self.root / filename).write_bytes(b"existing logo")
        for responses, expected in (([OSError("offline"), OSError("offline")], ("unavailable", 2)),
                                    ([{}, {}], ("unavailable", 2)),
                                    ([{"name": "Prusament"}, OSError("offline")], ("partial", 3)),
                                    ([{"name": "Prusament"}, {"name": "ROSA3D"}], ("changed", 0)),
                                    ([{"name": "Prusament"}, {"name": "ROSA3D"}], ("unchanged", 0))):
            with self.subTest(expected=expected), patch.multiple(assets, DB_FILE=str(self.db_path), DATA_DIR=str(self.root)), \
                 patch.object(assets, "_fetch_json", side_effect=responses), patch("sys.argv", ["offline-review"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                record, code = db_io._execute_step(assets.main, str(self.db_path))
                self.assertEqual((record["status"], code), expected)


class SeedColorRegressionTests(unittest.TestCase):
    def test_both_seeds_preserve_intentional_unknown_and_existing_colors(self):
        for module, sku in ((seed_prusament, "PM-PLA-JETBLACK"), (seed_rosa3d, "R3-PETG-BLACK")):
            products, entries = module.build_entries()
            for changes in ({"hex": None, "alpha": "00"},
                            {"hex": None, "additional_color_hexes": ["FF0000", "0000FF"]},
                            {"hex": None, "color_name": "Transparent local"},
                            {"hex": "ABCDEF", "alpha": "80"}):
                with self.subTest(module=module.__name__, changes=changes), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "db.json"
                    entry = dict(copy.deepcopy(entries[sku]), **changes, user_note="local correction")
                    db = {"_products": products, "_skus": {sku: entry}, "_brands": {}, "_notes": "local"}
                    db_io.save_db(db, path)
                    with patch.object(module, "DB_FILE", str(path)), patch("sys.argv", ["offline-review"]), \
                         contextlib.redirect_stdout(io.StringIO()):
                        record, code = db_io._execute_step(module.main, str(path))
                    self.assertEqual(code, 0, record)
                    stored = db_io.load_db(path)
                    self.assertEqual(stored["_skus"][sku], entry)
                    self.assertEqual(stored["_notes"], "local")
                    if entry["hex"] is None:
                        with self.assertRaises(core.MissingColorError):
                            core.build_openspool(stored["_skus"][sku], products[entry["product"]])
