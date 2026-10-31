import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import core
from scripts import catalogue_sources as source, db_io, sync_universal_catalogue as worker
from tests.support import ROOT, entry, product, small_db


def source_fixture():
    brand = {"uuid": "00000000-0000-4000-8000-000000000001", "name": "Test Brand", "website": "example.invalid"}
    filament = {"uuid": "00000000-0000-4000-8000-000000000002", "name": "PLA Pro", "density": 1.24,
                "min_print_temperature": 190, "max_print_temperature": 230,
                "min_bed_temperature": 40, "max_bed_temperature": 60}
    variant = {"uuid": "00000000-0000-4000-8000-000000000003", "name": "Rouge", "color_hex": "#aabbcc"}
    sizes = [{"uuid": "00000000-0000-4000-8000-000000000004", "diameter": 1.75, "filament_weight": 1000,
              "article_number": "REAL-SKU", "spool_refill": True}]
    return {k: json.dumps(v).encode() for k, v in {
        "data/test/brand.json": brand, "data/test/PLA/material.json": {"material": "PLA"},
        "data/test/PLA/pro/filament.json": filament, "data/test/PLA/pro/red/variant.json": variant,
        "data/test/PLA/pro/red/sizes.json": sizes}.items()} | {"LICENSE": b"MIT"}


def change(files, path, **values):
    row = json.loads(files[path]); row.update(values); files[path] = json.dumps(row).encode()


def tar_bytes(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for path, raw in files.items():
            member = tarfile.TarInfo("source/" + path); member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return stream.getvalue()


class SourceAdapterTests(unittest.TestCase):
    def test_spoolman_supplements_only_uncovered_brands_with_exact_units(self):
        rows = [{"id": "new_pla_red_1", "manufacturer": "New Brand", "material": "PLA", "name": "Red",
                 "density": 1.24, "diameter": 1.75, "weight": 1000, "color_hex": "aabbcc00",
                 "extruder_temp_range": [190, 230], "bed_temp": 60},
                {"manufacturer": "eSun", "id": "esun_red", "material": "PLA", "name": "Red"}]
        db, report = source.adapt_spoolman(rows, source_digest="d", covered_brands=["eSUN 3D"])
        self.assertEqual(report["already_covered"], 1)
        self.assertFalse(report["rejected"])
        sku, e = next(iter(db["_skus"].items())); p = db["_products"][e["product"]]
        self.assertTrue(sku.startswith("SMDB-"))
        self.assertEqual(e["source_id"], "new_pla_red_1")
        self.assertEqual((e["hex"], e["alpha"], p["bed_min_temp"], p["bed_max_temp"]), ("AABBCC", "00", 60, 60))
        self.assertEqual((p["min_temp"], p["max_temp"]), (190, 230))
        with self.assertRaises(db_io.SourceUnavailable):
            source.adapt_spoolman([], source_digest="d")
        bad = dict(rows[0], id="bad", extruder_temp_range=[240, 190])
        _, partial = source.adapt_spoolman([rows[0], bad], source_digest="d")
        self.assertEqual(len(partial["rejected"]), 1)

    def test_generic_brand_identity_units_and_colors(self):
        db, report = source.adapt_ofd(source_fixture(), source_digest="digest")
        self.assertEqual(report["references"], 1)
        self.assertFalse(report["rejected"])
        sku, e = next(iter(db["_skus"].items()))
        self.assertTrue(sku.startswith("OFD-"))
        self.assertEqual(e["manufacturer_sku"], "REAL-SKU")
        self.assertEqual(e["hex"], "AABBCC")
        p = db["_products"][e["product"]]
        self.assertEqual((p["brand"], p["diameter"], p["density"], e["weight"]), ("Test Brand", 1.75, 1.24, 1000))
        core.validate_openspool(core.build_openspool(dict(e, sku=sku), p))

    def test_spoolman_worker_preserves_local_edits_and_reports_partial_sources(self):
        from scripts import sync_spoolman_catalogue as spoolman_worker
        row = {"id": "new_pla_red", "manufacturer": "New Brand", "material": "PLA", "name": "Red",
               "density": 1.24, "diameter": 1.75, "color_hex": "aabbcc", "extruder_temp": 220, "bed_temp": 60}
        incoming, _ = source.adapt_spoolman([row], source_digest="original")
        sku = next(iter(incoming["_skus"]))
        incoming["_skus"][sku].update(hex=None, user_note="intentional")
        incoming["_last_updated"] = "2020-01-01"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            db_io.save_db(incoming, path)
            raw = json.dumps([row, dict(row, id="bad", diameter=-1)]).encode()
            with patch.object(spoolman_worker, "DB_FILE", str(path)), patch.object(spoolman_worker, "fetch_catalogue", return_value=raw):
                record, code = db_io._execute_step(spoolman_worker.main, str(path))
            self.assertEqual((record["status"], code), ("partial", 3))
            actual = db_io.load_db(path)
            self.assertEqual(actual["_skus"][sku], incoming["_skus"][sku])
            self.assertEqual(actual["_last_updated"], "2020-01-01")
            before = path.read_bytes()
            with patch.object(spoolman_worker, "DB_FILE", str(path)), patch.object(spoolman_worker, "fetch_catalogue", return_value=b"[]"):
                record, code = db_io._execute_step(spoolman_worker.main, str(path))
            self.assertEqual((record["status"], code), ("unavailable", 2))
            self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(db_io.SourceUnavailable):
            source.adapt_spoolman([{"manufacturer": "Covered"}], source_digest="d", covered_brands=["Covered"])

    def test_unknowns_and_multiple_colors_are_not_invented(self):
        files = source_fixture()
        change(files, "data/test/PLA/pro/filament.json", min_print_temperature=None)
        change(files, "data/test/PLA/pro/red/variant.json", color_hex=["#aa0000", "#00bb00"])
        db, report = source.adapt_ofd(files, source_digest="digest")
        e = next(iter(db["_skus"].values())); p = db["_products"][e["product"]]
        self.assertIsNone(e["hex"])
        self.assertEqual(e["source_colors"], ["AA0000", "00BB00"])
        self.assertIsNone(p["min_temp"])
        self.assertEqual(report["incomplete"], 1)
        with self.assertRaises(core.ExportValidationError):
            core.build_openspool(dict(e, hex="AA0000"), p)

    def test_explicit_alpha_preserved_and_multicolor_not_truncated(self):
        files = source_fixture()
        change(files, "data/test/PLA/pro/red/variant.json", color_hex="#aabbcc00")
        db, _ = source.adapt_ofd(files, source_digest="digest")
        e = next(iter(db["_skus"].values()))
        self.assertEqual((e["hex"], e["alpha"]), ("AABBCC", "00"))
        e = dict(entry(), source_colors=["AA0000", "00BB00"], hex="AA0000")
        self.assertEqual(core.build_openspool(e, product())["additional_color_hexes"], ["00BB00"])
        e["source_colors"] = [f"00000{i}" for i in range(6)]
        with self.assertRaises(core.ExportValidationError):
            core.build_openspool(e, product())

    def test_empty_invalid_and_partial_sources(self):
        with self.assertRaises(db_io.SourceUnavailable):
            source.adapt_ofd({}, source_digest="d")
        valid = source_fixture()
        for key, value in list(valid.items()):
            if "/red/" in key:
                valid[key.replace("/red/", "/bad/")] = value
        change(valid, "data/test/PLA/pro/bad/variant.json", color_hex="not a color")
        db, report = source.adapt_ofd(valid, source_digest="d")
        self.assertEqual(len(db["_skus"]), 1)
        self.assertEqual(len(report["rejected"]), 1)
        self.assertIn("HEX", report["rejected"][0]["reason"])

    def test_duplicate_ids_and_non_finite_json_rejected(self):
        files = source_fixture()
        for key, value in list(files.items()):
            if "/red/" in key:
                files[key.replace("/red/", "/duplicate/")] = value
        db, report = source.adapt_ofd(files, source_digest="d")
        self.assertEqual(len(db["_skus"]), 1)
        self.assertIn("dupliqué", report["rejected"][0]["reason"])
        for raw in (b'{"name":"x","name":"y"}', b'{"density":NaN}'):
            broken = source_fixture(); broken["data/test/PLA/pro/filament.json"] = raw
            with self.assertRaises(db_io.SourceUnavailable):
                source.adapt_ofd(broken, source_digest="d")

    def test_archive_paths_links_and_limits(self):
        files = source_fixture()
        self.assertEqual(source.read_ofd_archive(tar_bytes(files)), files)
        with self.assertRaises(db_io.SourceUnavailable):
            source.read_ofd_archive(tar_bytes({"../escape": b"x", "LICENSE": b"MIT"}))
        with self.assertRaises(db_io.SourceUnavailable):
            source.read_ofd_archive(b"not gzip")
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo("source/data/link"); member.type = tarfile.SYMTYPE; member.linkname = "/etc/passwd"
            archive.addfile(member)
        with self.assertRaises(db_io.SourceUnavailable):
            source.read_ofd_archive(stream.getvalue())

    def test_worker_preserves_local_nulls_and_reports_failures(self):
        incoming, _ = source.adapt_ofd(source_fixture(), source_digest="d")
        sku = next(iter(incoming["_skus"]))
        incoming["_skus"][sku].update(hex=None, user_note="local")
        incoming["_last_updated"] = "2020-01-01"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            db_io.save_db(incoming, path)
            with patch.object(worker, "DB_FILE", str(path)), patch.object(worker, "fetch_archive", return_value=tar_bytes(source_fixture())):
                worker.main()
            actual = db_io.load_db(path)
            self.assertEqual(actual["_skus"][sku], incoming["_skus"][sku])
            self.assertEqual(actual["_last_updated"], "2020-01-01")
            before = path.read_bytes()
            with patch.object(worker, "DB_FILE", str(path)), patch.object(worker, "fetch_archive", side_effect=OSError("offline")):
                record, code = db_io._execute_step(worker.main, str(path))
            self.assertEqual((record["status"], code), ("unavailable", 2))
            self.assertEqual(path.read_bytes(), before)

    def test_extension_is_read_only_and_restore_stays_exact(self):
        extension, _ = source.adapt_ofd(source_fixture(), source_digest="d")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            db_io.save_db(small_db(), path)
            db_io.save_db(extension, path.with_name("catalogue_ofd.json"))
            before = path.read_bytes()
            self.assertEqual(len(core.load_db(str(path))["_skus"]), 2)
            self.assertEqual(path.read_bytes(), before)
            backup = path.with_suffix(".backup"); backup.write_bytes(before)
            core.restore_db(str(path), str(backup))
            self.assertEqual(len(core.load_db(str(path))["_skus"]), 1)
            self.assertEqual(path.read_bytes(), before)


class CatalogueQueryTests(unittest.TestCase):
    def test_physical_edits_validate_and_preserve_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"
            db_io.save_db(small_db(), path)
            db = db_io.load_db(path)
            core.set_product_physical(db, "LOCAL", {"density": 1.31, "min_temp": None}, path=str(path))
            self.assertEqual(db_io.load_db(path)["_products"]["Audit PLA"]["density"], 1.31)
            self.assertIsNone(db["_products"]["Audit PLA"]["min_temp"])
            before = copy.deepcopy(db)
            with self.assertRaises(ValueError):
                core.set_product_physical(db, "LOCAL", {"density": float("nan")}, path=str(path))
            self.assertEqual(db, before)
            concurrent = db_io.load_db(path); concurrent["_skus"]["LOCAL"]["hex"] = "000000"; db_io.save_db(concurrent, path)
            with self.assertRaises(db_io.DatabaseError):
                core.set_product_physical(db, "LOCAL", {"density": 1.4}, path=str(path))
            self.assertEqual(db, before)

    def test_filters_accents_multiword_and_stable_numeric_two_level_sort(self):
        rows = []
        for sku, brand, weight in (("b", "Éclair", 1000), ("a", "Éclair", 500), ("c", "Other", 100), ("d", "Éclair", None)):
            rows.append(dict(sku=sku, brand=brand, material="PLA", product="PLA bleu", color_name="Bleu", hex="0000FF",
                             ready=weight is not None, weight=weight))
        result = core.query_catalogue(rows, text="eclair bleu", material="PLA", sort1="brand", sort2="weight", descending2=True)
        self.assertEqual([r["sku"] for r in result], ["b", "a", "d"])
        self.assertEqual([r["sku"] for r in core.query_catalogue(rows, quality="incomplete")], ["d"])
        self.assertEqual(core.query_catalogue(rows, text="absent"), [])
        with self.assertRaises(ValueError):
            core.query_catalogue(rows, sort1="unknown")

    def test_old_consent_does_not_authorize_new_host(self):
        with patch("core.load_config", return_value={"network_consent": True}):
            self.assertFalse(core.has_network_consent())
            self.assertFalse(core.consent_was_asked())

    def test_logo_paths_cannot_escape_resource_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "outside.svg").write_text("test")
            with patch.multiple(core, DATA_HOME=str(root), RESOURCE_DIR=str(root)):
                self.assertIsNone(core.logo_abs_path({"_brands": {"X": {"logo_path": "outside.svg"}}}, "X"))


class NfcProfilesTests(unittest.TestCase):
    def test_both_tag_boundaries_and_reserved_space(self):
        for tag, capacity in core.NFC_CAPACITIES.items():
            length = capacity - 27
            self.assertTrue(core.nfc_size("x" * length, tag_type=tag).fits)
            self.assertFalse(core.nfc_size("x" * (length + 1), tag_type=tag).fits)
            self.assertFalse(core.nfc_size("x" * length, tag_type=tag, reserved_bytes=1).fits)
        with self.assertRaises(ValueError):
            core.nfc_size("a", tag_type="NTAG999")

    def test_essential_is_explicit_and_retains_all_printing_and_color_fields(self):
        e = dict(entry(), color_name="é" * 300, alpha="00", additional_color_hexes=["AABBCC"])
        payload = core.build_openspool(e, product())
        with self.assertRaises(core.NfcCapacityError):
            core.serialize_openspool(payload, tag_type="NTAG215")
        essential = json.loads(core.serialize_openspool(payload, tag_type="NTAG215", profile="essential"))
        self.assertEqual(essential, {k:v for k,v in payload.items() if k in core.NFC_ESSENTIAL_FIELDS})
        self.assertEqual(json.loads(core.serialize_openspool(payload, mode="archive", profile="essential")), payload)

    def test_profile_files_are_distinct_and_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            e, p = entry(), product()
            full = core.write_openspool("LOCAL", e, p, directory)
            essential = core.write_openspool("LOCAL", e, p, directory, tag_type="NTAG215", profile="essential")
            self.assertNotEqual(full, essential)
            before = Path(essential).read_bytes()
            with self.assertRaises(core.NfcCapacityError):
                core.write_openspool("LOCAL", e, p, directory, tag_type="NTAG215", profile="essential", reserved_bytes=490)
            self.assertEqual(Path(essential).read_bytes(), before)


class BundledExtensionTests(unittest.TestCase):
    def test_spoolman_snapshot_has_no_cross_source_brand_duplicates(self):
        supplement = db_io.load_db(ROOT / "data/catalogue_spoolman.json")
        ofd = db_io.load_db(ROOT / "data/catalogue_ofd.json")
        baseline = db_io.load_db(ROOT / "data/polymaker_db.json")
        covered = {source.brand_key(n) for n in set(ofd["_brands"]) | set(baseline["_brands"])}
        self.assertFalse(covered & {source.brand_key(n) for n in supplement["_brands"]})
        audit = db_io.parse_json((ROOT / "data/catalogue_spoolman_audit.json").read_bytes())
        self.assertEqual(len(supplement["_skus"]), audit["references"])
        self.assertFalse(audit["rejected"])
        rows = core.list_skus(supplement)
        for row in rows:
            self.assertTrue(row["sku"].startswith("SMDB-"))
            if row["ready"]:
                view = core.get_sku_view(supplement, row["sku"])
                payload = core.build_openspool(dict(supplement["_skus"][row["sku"]], sku=row["sku"]), view.product_data, view.brand_meta)
                self.assertTrue(core.nfc_size(core.serialize_openspool(payload, tag_type="NTAG215", profile="essential"), tag_type="NTAG215").fits)

    def test_legacy_catalogue_and_1008_compact_exports_are_identical(self):
        from tests.support import catalogue
        contract = db_io.parse_json((ROOT / "tests/fixtures/legacy_catalogue_contract.json").read_bytes())
        self.assertEqual(hashlib.sha256((ROOT / "data/polymaker_db.json").read_bytes()).hexdigest(), contract["base_sha256"])
        db, fingerprints = catalogue(), {}
        for sku, e in db["_skus"].items():
            view = core.get_sku_view(db, sku)
            if view is not None and e.get("hex"):
                text = core.serialize_openspool(core.build_openspool(dict(e, sku=sku), view.product_data, view.brand_meta))
                fingerprints[sku] = hashlib.sha256(text.encode()).hexdigest()
        self.assertEqual(len(fingerprints), contract["exports"])
        digest = hashlib.sha256(json.dumps(fingerprints, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(digest, contract["compact_exports_sha256"])

    def test_every_new_reference_has_valid_data_or_explicit_unknowns(self):
        db = db_io.load_db(ROOT / "data/catalogue_ofd.json")
        audit = db_io.parse_json((ROOT / "data/catalogue_ofd_audit.json").read_bytes())
        self.assertEqual(len(db["_skus"]), audit["references"])
        self.assertEqual(len(db["_brands"]), audit["brands_imported"])
        self.assertFalse(audit["rejected"])
        self.assertTrue({"Bambu Lab", "eSUN 3D", "SUNLU", "Anycubic", "Creality", "ELEGOO"} <= set(db["_brands"]))
        ready = 0
        rows = {r["sku"]: r for r in core.list_skus(db)}
        for sku, e in db["_skus"].items():
            self.assertTrue(sku.startswith("OFD-"))
            self.assertEqual(sku[4:].lower(), e["source_id"])
            self.assertIn(e["product"], db["_products"])
            view = core.get_sku_view(db, sku)
            if rows[sku]["ready"]:
                p = core.build_openspool(dict(e, sku=sku), view.product_data, view.brand_meta)
                text = core.serialize_openspool(p, tag_type="NTAG215", profile="essential")
                self.assertTrue(core.nfc_size(text, tag_type="NTAG215").fits)
                ready += 1
            else:
                self.assertNotEqual(rows[sku]["quality"], "Prêt")
        self.assertGreater(ready, 20000)

    def test_approved_logos_match_manifest_and_rejected_logos_are_not_referenced(self):
        manifest = db_io.parse_json((ROOT / "data/brand_logos/manifest.json").read_bytes())
        db = db_io.load_db(ROOT / "data/catalogue_ofd.json")
        audit = db_io.parse_json((ROOT / "data/catalogue_ofd_audit.json").read_bytes())
        self.assertEqual(len(manifest), audit["logos_approved"])
        rejected = {row["brand"] for row in audit["logos_rejected"]}
        for name, brand in db["_brands"].items():
            if name in rejected:
                self.assertNotIn("logo_path", brand)
            else:
                asset = manifest[brand["source_id"]]
                self.assertEqual(brand["logo_path"], asset["path"])
                self.assertEqual(hashlib.sha256((ROOT / asset["path"]).read_bytes()).hexdigest(), asset["sha256"])
