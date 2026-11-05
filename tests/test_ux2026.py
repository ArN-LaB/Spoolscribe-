"""SPOOLSCRIBE-UX-2026-001: collapsible filters, in-card draft, value comparison,
export state, CIEDE2000 proximity and card hierarchy. Offline, temporary data only."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core, colour_distance as cd
from scripts import db_io
from tests.support import ROOT, catalogue, small_db
from tests import test_gui as fixture

ORCA_PROFILE = {"nozzle_temperature_range_low": ["200"], "nozzle_temperature_range_high": ["230"],
                "filament_density": ["1.24"], "filament_diameter": ["1.75"], "hot_plate_temp": ["60"]}

# Sharma, Wu & Dalal (2005), "The CIEDE2000 color-difference formula: implementation notes,
# supplementary test data and mathematical observations", Table 1 (34 pairs, ΔE00 to 4 decimals).
SHARMA = [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425), ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
          ((50, 2.8361, -74.02), (50, 0, -82.7485), 3.4412), ((50, -1.3802, -84.2814), (50, 0, -82.7485), 1.0),
          ((50, -1.1848, -84.8006), (50, 0, -82.7485), 1.0), ((50, -0.9009, -85.5211), (50, 0, -82.7485), 1.0),
          ((50, 0, 0), (50, -1, 2), 2.3669), ((50, -1, 2), (50, 0, 0), 2.3669),
          ((50, 2.49, -0.001), (50, -2.49, 0.0009), 7.1792), ((50, 2.49, -0.001), (50, -2.49, 0.001), 7.1792),
          ((50, 2.49, -0.001), (50, -2.49, 0.0011), 7.2195), ((50, 2.49, -0.001), (50, -2.49, 0.0012), 7.2195),
          ((50, -0.001, 2.49), (50, 0.0009, -2.49), 4.8045), ((50, -0.001, 2.49), (50, 0.001, -2.49), 4.8045),
          ((50, -0.001, 2.49), (50, 0.0011, -2.49), 4.7461), ((50, 2.5, 0), (50, 0, -2.5), 4.3065),
          ((50, 2.5, 0), (73, 25, -18), 27.1492), ((50, 2.5, 0), (61, -5, 29), 22.8977),
          ((50, 2.5, 0), (56, -27, -3), 31.903), ((50, 2.5, 0), (58, 24, 15), 19.4535),
          ((50, 2.5, 0), (50, 3.1736, 0.5854), 1.0), ((50, 2.5, 0), (50, 3.2972, 0), 1.0),
          ((50, 2.5, 0), (50, 1.8634, 0.5757), 1.0), ((50, 2.5, 0), (50, 3.2592, 0.335), 1.0),
          ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
          ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.263),
          ((61.2901, 3.7196, -5.3901), (61.4292, 2.248, -4.962), 1.8731),
          ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
          ((22.7233, 20.0904, -46.694), (23.0331, 14.973, -42.5619), 2.0373),
          ((36.4612, 47.858, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
          ((90.8027, -2.0831, 1.441), (91.1528, -1.6435, 0.0447), 1.4441),
          ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
          ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
          ((2.0776, 0.0795, -1.135), (0.9033, -0.0636, -0.5514), 0.9082)]
# sRGB (D65, 2°) to CIELAB references as tabulated by B. Lindbloom / EasyRGB.
LAB = {"FFFFFF": (100, 0, 0), "000000": (0, 0, 0), "FF0000": (53.2408, 80.0925, 67.2032),
       "00FF00": (87.7347, -86.1827, 83.1793), "0000FF": (32.2970, 79.1875, -107.8602), "808080": (53.5850, 0, 0)}


def row(sku, hex_value, brand="B", product="P", color="C", **extra):
    return dict(sku=sku, hex=hex_value, brand=brand, product=product, color_name=color, **extra)


class ColourDistanceTests(unittest.TestCase):
    def test_published_ciede2000_pairs_and_symmetry(self):
        for i, (a, b, expected) in enumerate(SHARMA, 1):
            with self.subTest(pair=i):
                self.assertAlmostEqual(cd.ciede2000(a, b), expected, delta=1e-4)
                self.assertAlmostEqual(cd.ciede2000(b, a), expected, delta=1e-4)

    def test_srgb_to_lab_reference_values_identity_and_neutral_greys(self):
        for hex_value, expected in LAB.items():
            for got, want in zip(cd.hex_to_lab(hex_value), expected):
                self.assertAlmostEqual(got, want, delta=1e-3, msg=hex_value)
        for grey in ("111111", "808080", "EEEEEE"):
            _, a, b = cd.hex_to_lab(grey)
            self.assertLess(abs(a) + abs(b), 1e-4)  # matrix rounding only, far below ΔE 0.01
            self.assertEqual(cd.delta_e00(grey, "#" + grey.lower()), 0.0)
        # Hue angles on both sides of 0°/360° stay small for near-identical colours.
        self.assertLess(cd.delta_e00("FF0001", "FF0100"), 1.0)

    def test_invalid_hex_is_refused_without_inventing_a_colour(self):
        for value in (None, "", "12345", "GGGGGG", "#1234567", "12345678", 123456):
            self.assertIsNone(cd.parse_hex(value))
        with self.assertRaises(ValueError):
            cd.rank("zzz", [row("A", "FFFFFF")])

    def test_rank_is_deterministic_ties_are_stable_and_rows_untouched(self):
        rows = [row("S3", "FF0000", brand="b"), row("S1", "FF0000", brand="A"), row("S2", "FF0000", brand="A", product="Z"),
                row("S4", "FE0000"), row("S5", "00FF00")]
        before = copy.deepcopy(rows)
        result = cd.rank("FF0000", rows)
        self.assertEqual([i["row"]["sku"] for i in result["items"]], ["S1", "S2", "S3", "S4", "S5"])
        self.assertEqual(result["items"][0]["delta"], 0.0)
        for _ in range(5):
            shuffled = rows[:]; random.Random(_).shuffle(shuffled)
            self.assertEqual([i["row"]["sku"] for i in cd.rank("FF0000", shuffled)["items"]], ["S1", "S2", "S3", "S4", "S5"])
        self.assertEqual(rows, before)
        deltas = [i["delta"] for i in result["items"]]
        self.assertEqual(deltas, sorted(deltas))

    def test_exclusions_are_explicit_and_effects_are_flagged(self):
        rows = [row("unknown", None), row("conflict", "112233", hex_variants=2), row("multi", "112233", source_colors=["112233", "445566"]),
                row("alpha", "112233", alpha="80"), row("clear", "112233", color="Transparent Blue"),
                row("silk", "112233", product="PLA Silk"), row("plain", "112233")]
        result = cd.rank("112233", rows)
        self.assertEqual(result["excluded"], {"unknown": 1, "conflict": 1, "multicolour": 1, "translucent": 2})
        self.assertEqual([(i["row"]["sku"], i["effect"]) for i in result["items"]], [("plain", False), ("silk", True)])

    def test_cache_reuses_distances_for_the_same_target(self):
        cache = {}
        rows = [row(f"S{i}", f"{i:06X}") for i in range(50)]
        cd.rank("123456", rows, cache=cache)
        self.assertEqual(len(cache), 50)
        with patch.object(cd, "ciede2000", side_effect=AssertionError("recomputed")):
            cd.rank("123456", rows, cache=cache)


class ComparisonTests(unittest.TestCase):
    def orca(self, directory, product="Polymaker PETG"):
        path = Path(directory) / "orca"; path.mkdir(exist_ok=True)
        (path / f"{product} @Snapmaker U1 - OrcaSlicer.json").write_text(json.dumps(ORCA_PROFILE))
        return patch.object(core, "ORCA_DIR", str(path))

    def test_effective_values_equal_both_encoders_with_orca_on_and_off(self):
        db = catalogue(); entry = dict(db["_skus"]["PB05001"], sku="PB05001"); product = db["_products"][entry["product"]]
        with tempfile.TemporaryDirectory() as directory, self.orca(directory):
            for override in (False, True):
                data = core.value_comparison(db, "PB05001", use_orca_overrides=override)
                payload = core.build_openspool(entry, product, use_orca_overrides=override)
                fields = core.opentag_fields(entry, product, {}, use_orca_overrides=override)
                opentag = core.value_comparison(db, "PB05001", use_orca_overrides=override, nfc_format="opentag3d", opentag_settings={})
                for r, o in zip(data["rows"], opentag["rows"]):
                    key = r["key"]
                    self.assertEqual(r["effective"]["value"], payload["color_hex" if key == "hex" else key], key)
                    other = {"hex": fields["color_1"][:6], **{k: fields[v] for k, v in core._OPENTAG_BOUNDS.items()},
                             "diameter": fields["diameter"], "density": fields["density"]}[key]
                    self.assertEqual(o["effective"]["value"], other, key)
            on = {r["key"]: r for r in core.value_comparison(db, "PB05001", use_orca_overrides=True)["rows"]}
            off = {r["key"]: r for r in core.value_comparison(db, "PB05001")["rows"]}
        # The audit's reproduced case: the card showed 240–260 while the export used 200–230.
        self.assertEqual((on["min_temp"]["reference"]["value"], on["min_temp"]["effective"]["value"]), (240, 200))
        self.assertEqual((on["max_temp"]["effective"]["value"], on["max_temp"]["effective"]["origin"]), (230, "orca"))
        self.assertTrue(on["min_temp"]["differs"]); self.assertFalse(off["min_temp"]["differs"])
        self.assertEqual(off["min_temp"]["orca"], {"value": 200, "applied": False})

    def test_extracted_orca_rule_keeps_encoder_results(self):
        db = catalogue(); entry = dict(db["_skus"]["PB05001"], sku="PB05001"); product = db["_products"][entry["product"]]
        with tempfile.TemporaryDirectory() as directory, self.orca(directory):
            payload = core.build_openspool(entry, product, use_orca_overrides=True)
            partial = dict(product, density=None)
            filled = core.build_openspool(entry, partial)
        expected = dict(min_temp=200, max_temp=230, bed_min_temp=60, bed_max_temp=60, density=1.24, diameter=1.75)
        self.assertEqual({k: payload[k] for k in expected}, expected)
        # Without the override, Orca only fills unknown values.
        self.assertEqual((filled["density"], filled["min_temp"]), (1.24, 240))

    def test_provenance_is_never_upgraded_to_manufacturer(self):
        db = small_db(); product = db["_products"]["Audit PLA"]
        product["_field_sources"] = {"min_temp": dict(source="Polymaker officiel", rank=100, value=190),
                                     "max_temp": dict(source="Open Filament Database", rank=10, value=230)}
        rows = {r["key"]: r for r in core.value_comparison(db, "LOCAL")["rows"]}
        self.assertEqual(rows["min_temp"]["reference"]["kind"], "manufacturer")
        self.assertEqual((rows["max_temp"]["reference"]["kind"], rows["max_temp"]["reference"]["source"]), ("source", "Open Filament Database"))
        self.assertEqual(rows["density"]["reference"]["kind"], "unknown")
        self.assertEqual(rows["hex"]["reference"]["kind"], "unknown")

    def test_personal_copy_compares_to_current_origin_and_never_claims_orca(self):
        with tempfile.TemporaryDirectory() as directory, self.orca(directory):
            path = Path(directory) / "db.json"; db = catalogue(); db_io.save_db(db, path)
            sku = core.save_personal_filament(db, "PB05001", {"min_temp": 235}, "U1", path=str(path))
            data = core.value_comparison(db, sku, use_orca_overrides=True)
            rows = {r["key"]: r for r in data["rows"]}
            self.assertEqual(data["orca"]["status"], "origin_only")
            self.assertFalse(any(r["orca"] and r["orca"]["applied"] for r in data["rows"]))
            self.assertEqual((rows["min_temp"]["reference"]["value"], rows["min_temp"]["personal"]["kind"]), (240, "user"))
            self.assertEqual(rows["max_temp"]["personal"]["kind"], "copy")
            self.assertEqual(rows["min_temp"]["effective"], {"value": 235, "origin": "personal"})
            payload = core.build_openspool(dict(db["_skus"][sku], sku=sku), core.get_sku_view(db, sku).product_data, use_orca_overrides=True)
            self.assertEqual(payload["min_temp"], 235)
            del db["_skus"]["PB05001"]
            missing = core.value_comparison(db, sku)
            self.assertTrue(missing["origin_missing"])
            self.assertEqual(missing["rows"][0]["reference"], {"value": None, "kind": "absent", "source": None, "suspect": False})

    def test_opentag_explicit_settings_are_the_effective_bounds_without_targets_invented(self):
        db = catalogue()
        settings = {"min_print_temp": 245, "max_print_temp": 255, "print_temp": 250}
        data = core.value_comparison(db, "PB05001", nfc_format="opentag3d", opentag_settings=settings)
        rows = {r["key"]: r for r in data["rows"]}
        fields = core.opentag_fields(db["_skus"]["PB05001"], db["_products"]["Polymaker PETG"], settings)
        self.assertEqual(rows["min_temp"]["effective"], {"value": fields["min_print_temp"], "origin": "opentag_settings"})
        self.assertEqual(data["targets"], {"print_temp": 250, "bed_temp": None, "chamber_temp": None})

    def test_personal_hex_is_limited_validated_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"; db = small_db(); db["_skus"]["LOCAL"].update(color_name="White", hex="000000")
            db_io.save_db(db, path); source = copy.deepcopy(db["_skus"]["LOCAL"])
            for bad in ("12345", "", None, "#GG0000"):
                before = path.read_bytes()
                with self.assertRaises(core.ExportValidationError):
                    core.save_personal_filament(db, "LOCAL", {"hex": bad}, "U1", path=str(path))
                self.assertEqual(path.read_bytes(), before)
            sku = core.save_personal_filament(db, "LOCAL", {"hex": "#fafafa"}, "U1", path=str(path))
            self.assertEqual(db["_skus"]["LOCAL"], source)
            self.assertEqual(db["_skus"][sku]["hex"], "FAFAFA")
            self.assertEqual(db["_skus"][sku]["_field_sources"]["hex"]["source"], db_io.USER_SOURCE)
            self.assertIsNone(db_io.implausible_color(db["_skus"][sku]))
            # Physical values were not part of the edit: they remain frozen copies.
            product = core.get_sku_view(db, sku).product_data
            self.assertEqual(product["_field_sources"]["min_temp"]["source"], "Copie personnelle")


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class UxGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self)
        # Cleanups run last-in first-out: discard any open draft before the
        # fixture closes the window, otherwise its close guard would ask.
        self.addCleanup(lambda: self.window._close_draft())

    def big_catalogue(self):
        extension = db_io.load_db(ROOT / "tests/fixtures/catalogues/catalogue_ofd.json")
        self.window.db.update(db_io.merge_bundled_db(self.window.db, extension)[0])
        self.window._reload_table(); self.window.brand_filter.setCurrentIndex(0)

    def state(self):
        w = self.window
        return (w._page, w.current_sku, w.sort1.currentData(), w.sort2.currentData(), len(w._filtered_rows),
                [i.row() for i in w.table.selectionModel().selectedRows()], w.brand_filter.currentData(),
                w.material_filter.currentData(), w.quality_filter.currentData())

    # UX-01 ────────────────────────────────────────────────────────────
    def test_folding_keeps_criteria_page_sort_and_selection(self):
        w = self.window; self.big_catalogue(); w._change_page(1)
        self.assertEqual(w._page, 1); w.table.selectRow(3); w._choose_state("incomplete")
        before = self.state()
        for key in ("brands", "materials", "states"):
            for expanded in (False, True, False):
                w._sections[key]["toggle"].setChecked(expanded)
                self.assertEqual(self.state(), before, key)
        self.assertTrue(all(not s["body"].isVisible() and not s["toggle"].isChecked() for s in w._sections.values()))

    def test_closed_sections_name_their_filter_and_summary_lists_all_criteria(self):
        w = self.window; w.show()
        w._choose_family("PETG"); w._choose_state("ready"); w.search.setText("Black"); w._apply_filter()
        for section in w._sections.values(): section["toggle"].setChecked(False)
        texts = {k: s["toggle"].text() for k, s in w._sections.items()}
        self.assertIn("Polymaker", texts["brands"]); self.assertIn("PETG", texts["materials"]); self.assertIn("Prêtes à exporter", texts["states"])
        self.assertIn("Filtre actif : PETG", w._sections["materials"]["toggle"].accessibleDescription())
        self.assertTrue(w.filter_summary.isVisible())
        for part in ("Fabricant : Polymaker", "Matière : PETG", "Recherche : « Black »"): self.assertIn(part, w.filter_summary.toolTip())
        w.search.setText("zzzz-aucun"); w._apply_filter()
        self.assertEqual(len(w._filtered_rows), 0); self.assertIn("zzzz-aucun", w.filter_summary.toolTip())

    def test_cross_filters_still_apply_in_both_directions_when_folded(self):
        w = self.window; self.big_catalogue()
        for section in w._sections.values(): section["toggle"].setChecked(False)
        w._choose_family("PETG")
        brands = {w.brand_list.item(i).data(0x0100) for i in range(w.brand_list.count())}
        self.assertTrue(brands and all(r["family"] == "PETG" for r in w._filtered_rows))
        w._choose_family(""); w._choose_brand("Polymaker", remember=False)
        families = {w.family_list.item(i).data(0x0100) for i in range(1, w.family_list.count())}
        self.assertEqual(families, {r["family"] for r in w._all_rows if r["brand"] == "Polymaker" and r["family"]})
        self.assertTrue(all(r["brand"] == "Polymaker" for r in w._filtered_rows))

    def test_keyboard_folding_returns_focus_and_reset_keeps_favorites_and_folding(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        w = self.window; w.show(); w.activateWindow(); w.app.processEvents()
        w._toggle_brand_favorite("Polymaker"); w.current_sku = "PB05001"; w._toggle_filament_favorite("PB05001")
        favorites = (core.load_config()["favorite_brands"], core.load_config()["favorite_filaments"])
        w.brand_search.setFocus(); w.app.processEvents()
        toggle = w._sections["brands"]["toggle"]
        toggle.setChecked(False)
        self.assertIs(w.focusWidget(), toggle)
        QTest.keyClick(toggle, Qt.Key_Space); self.assertTrue(toggle.isChecked())
        QTest.keyClick(toggle, Qt.Key_Space); self.assertFalse(toggle.isChecked())
        w.favorites_only.setChecked(True); w._choose_family("PETG"); w._reset_filters()
        self.assertEqual((core.load_config()["favorite_brands"], core.load_config()["favorite_filaments"]), favorites)
        self.assertFalse(toggle.isChecked()); self.assertTrue(w.filter_summary.isVisible()); self.assertEqual(w.filter_summary.text(), "Filtres")
        self.assertEqual((w.material_filter.currentData(), w.favorites_only.isChecked()), ("", False))

    def test_folding_preferences_are_saved_restored_and_old_settings_stay_valid(self):
        from spoolscribe import app_gui
        w = self.window; w._sections["materials"]["toggle"].setChecked(False); w._save_ui_preferences()
        self.assertEqual(core.load_config()["ui"]["collapsed"], {"brands": False, "materials": True, "colours": True, "states": False})
        w.close(); second = app_gui.MainWindow(); self.addCleanup(second.close)
        self.assertFalse(second._sections["materials"]["toggle"].isChecked())
        self.assertTrue(second._sections["brands"]["toggle"].isChecked())
        for legacy in (None, "invalid", {"brands": "yes"}):
            cfg = core.load_config(); cfg["ui"] = dict(cfg["ui"]); cfg["ui"].pop("collapsed", None)
            if legacy is not None: cfg["ui"]["collapsed"] = legacy
            core.save_config(cfg); window = app_gui.MainWindow(); self.addCleanup(window.close)
            self.assertTrue(all(window._sections[k]["toggle"].isChecked() for k in ('brands', 'materials', 'states')), legacy)
            self.assertFalse(window._sections['colours']['toggle'].isChecked(), legacy)

    # UX-02 / UX-03 ────────────────────────────────────────────────────
    def edit(self, sku="PB05001", **changes):
        w = self.window; w.current_sku = sku; w._show_detail(sku); w._edit_physical()
        for key, value in changes.items():
            field = w.draft_fields[key]; field.setText(value); field.textEdited.emit(value)
        return w

    def test_draft_keeps_identity_and_cancel_writes_nothing(self):
        w = self.window; w.table.selectRow(0); sku = w.current_sku; title = w.title.text()
        raw = Path(core.DB_PATH).read_bytes(); db = copy.deepcopy(w.db)
        w._edit_physical(); w.draft_fields["min_temp"].setText("199"); w.draft_fields["min_temp"].textEdited.emit("199")
        self.assertTrue(w.draft_editor.isVisible() or not w.isVisible())
        self.assertEqual((w.current_sku, w.title.text()), (sku, title))
        self.assertEqual([i.row() for i in w.table.selectionModel().selectedRows()], [0])
        self.assertNotEqual(w._field_widgets["Nozzle"].text(), "199–" + str(w.db["_products"][w.db["_skus"][sku]["product"]]["max_temp"]) + " °C")
        self.assertIn("1 modification", w.draft_badge.text()); self.assertTrue(w.draft_fields["min_temp"].property("draftChanged"))
        w.draft_cancel.click()
        self.assertIsNone(w._draft); self.assertTrue(w.draft_editor.isHidden())
        self.assertEqual(Path(core.DB_PATH).read_bytes(), raw); self.assertEqual(w.db, db)

    def test_save_sends_only_edited_fields_and_keeps_the_source_bytes(self):
        w = self.edit(min_temp="235", density=""); source = copy.deepcopy(w.db["_products"]["Polymaker PETG"])
        w.draft_suffix.setText("U1"); w.draft_save.click()
        self.assertTrue(w.current_sku.startswith("USER-")); self.assertIsNone(w._draft)
        product = core.get_sku_view(w.db, w.current_sku).product_data
        self.assertEqual((product["min_temp"], product["density"]), (235, None))
        self.assertEqual(product["_field_sources"]["min_temp"]["source"], db_io.USER_SOURCE)
        self.assertEqual(product["_field_sources"]["density"], db_io.user_correction(None))
        self.assertEqual(product["_field_sources"]["max_temp"]["source"], "Copie personnelle")
        self.assertEqual(core.load_db()["_products"]["Polymaker PETG"], source)
        # Same origin and suffix updates the existing copy.
        copy_sku = w.current_sku; self.edit(copy_sku, max_temp="255"); w.draft_save.click()
        self.assertEqual(w.current_sku, copy_sku); self.assertEqual(core.get_sku_view(w.db, copy_sku).product_data["max_temp"], 255)

    def test_invalid_drafts_and_failed_writes_keep_the_draft_without_writing(self):
        w = self.edit(); raw = Path(core.DB_PATH).read_bytes(); db = copy.deepcopy(w.db)
        for changes, suffix in (({"min_temp": "270"}, "U1"), ({"bed_min_temp": "abc"}, "U1"), ({"min_temp": "235"}, "../x"),
                                ({"hex": "12"}, "U1"), ({"min_temp": "235.5"}, "U1")):
            w._close_draft(); self.edit(**changes); w.draft_suffix.setText(suffix)
            self.assertFalse(w._save_draft(), changes)
            self.assertIsNotNone(w._draft); self.assertFalse(w.draft_error.isHidden()); self.assertTrue(w.draft_error.text())
            self.assertEqual(Path(core.DB_PATH).read_bytes(), raw); self.assertEqual(w.db, db)
        w._close_draft(); self.edit(min_temp="235")
        with patch("spoolscribe.core.save_db", side_effect=OSError("disque plein")):
            self.assertFalse(w._save_draft())
        self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertIn("disque plein", w.draft_error.text())
        self.assertEqual(Path(core.DB_PATH).read_bytes(), raw); self.assertEqual(w.db, db)

    def other_row(self, sku="PB05001"):
        return next(i for i, r in enumerate(self.window._rows) if r["sku"] != sku and not any(v["sku"] == sku for v in r.get("variants", [])))

    def test_transitions_ask_before_losing_a_draft_and_keep_choice_explicit(self):
        w = self.edit(min_temp="235"); raw = Path(core.DB_PATH).read_bytes(); other = self.other_row()
        with patch.object(w, "_ask_draft_decision", return_value="keep") as ask:
            w.table.selectRow(other)
            self.assertEqual(w.current_sku, "PB05001"); self.assertIsNotNone(w._draft)
            w._clear_filament(); self.assertEqual(w.current_sku, "PB05001")
            w._choose_family("PETG"); w._reset_filters(); self.assertEqual(w.material_filter.currentData(), "PETG")
            # Opening Sources loses nothing; the decision is taken when a refresh would start.
            with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_network_consent", return_value=True):
                w._start_update(manual=True); worker.assert_not_called()
            with patch("spoolscribe.ui_catalogue.QFileDialog.getOpenFileName") as picker:
                w._import_settings(); picker.assert_not_called()
            from PySide6.QtGui import QCloseEvent
            event = QCloseEvent(); w.closeEvent(event); self.assertFalse(event.isAccepted())
            self.assertGreaterEqual(ask.call_count, 6)
        self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)
        with patch.object(w, "_ask_draft_decision", return_value="discard"):
            w.table.selectRow(other)
        self.assertIsNone(w._draft); self.assertNotEqual(w.current_sku, "PB05001"); self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)
        self.edit(min_temp="236")
        with patch.object(w, "_ask_draft_decision", return_value="save"):
            w._clear_filament()
        self.assertIn("USER-", "".join(core.load_db()["_skus"]))

    def test_variant_change_and_pagination_with_a_modified_draft(self):
        w = self.edit(min_temp="235"); raw = Path(core.DB_PATH).read_bytes()
        others = [w.variant_choice.itemData(i) for i in range(w.variant_choice.count()) if w.variant_choice.itemData(i) not in (None, "PB05001")]
        self.assertTrue(others, "PB05001 belongs to a multi-package group in the fixture")
        with patch.object(w, "_ask_draft_decision", return_value="keep"):
            w.variant_choice.setCurrentIndex(w.variant_choice.findData(others[0]))
        self.assertEqual((w.current_sku, w.variant_choice.currentData()), ("PB05001", "PB05001"))
        self.assertEqual(w.draft_fields["min_temp"].text(), "235")
        with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("pagination keeps the card")):
            w._change_page(1); w._change_page(1)
        self.assertEqual(w.current_sku, "PB05001"); self.assertEqual(w.stack.currentIndex(), 1); self.assertIsNotNone(w._draft)
        with patch.object(w, "_ask_draft_decision", return_value="discard"):
            w.variant_choice.setCurrentIndex(w.variant_choice.findData(others[0]))
        self.assertEqual(w.current_sku, others[0]); self.assertIsNone(w._draft)
        self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)

    def test_harmless_transitions_keep_the_draft_without_asking(self):
        w = self.edit(min_temp="235")
        with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("unexpected prompt")):
            w._set_view_mode("grid"); w._set_view_mode("list")
            w.search.setText("aucun-resultat-xyz"); w._apply_filter()
            self.assertEqual(w.current_sku, "PB05001"); self.assertEqual(w.stack.currentIndex(), 1)
            w.search.clear(); w._apply_filter(); w._toggle_filament_favorite("PB05001")
        self.assertEqual(w.draft_fields["min_temp"].text(), "235")
        w._close_draft(); self.edit()  # an unchanged draft never prompts
        with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("unexpected prompt")):
            w.table.selectRow(self.other_row())
        self.assertIsNone(w._draft)

    def test_export_and_inspection_never_mix_draft_and_saved_values(self):
        w = self.edit(min_temp="235")
        self.assertFalse(w.btn_generate.isEnabled()); self.assertFalse(w.btn_inspect.isEnabled())
        with patch("spoolscribe.app_gui.QMessageBox.information") as message:
            w._generate(); w._generate(mode="archive"); w._toggle_inspect()
        message.assert_not_called(); self.assertFalse(Path(core.OUTPUT_DIR).exists()); self.assertFalse(w.inspector.isVisible())

    def test_comparison_shows_orca_effect_and_restores_reference_into_the_copy(self):
        w = self.window
        with tempfile.TemporaryDirectory() as directory:
            orca = Path(directory); (orca / "Polymaker PETG @Snapmaker U1 - OrcaSlicer.json").write_text(json.dumps(ORCA_PROFILE))
            with patch.object(core, "ORCA_DIR", str(orca)):
                cfg = core.load_config(); cfg["orca_overrides"] = True; core.save_config(cfg)
                w.provenance_toggle.setChecked(True); w.current_sku = "PB05001"; w._show_detail("PB05001")
                cells = w.comparison_cells["min_temp"]
                self.assertTrue(w.comparison_card.isVisibleTo(w)); self.assertTrue(cells[1].text().startswith("240"))
                self.assertIn("provenance inconnue", cells[1].accessibleDescription()); self.assertTrue(cells[4].text().startswith("≠ 200"))
                self.assertIn("Orca", cells[4].accessibleDescription()); self.assertIn("appliqué", cells[2].text())
                self.assertEqual(w._build_payload()["min_temp"], 200)
        w.provenance_toggle.setChecked(False)
        self.edit(min_temp="230"); w.draft_suffix.setText("Atelier"); w.draft_save.click(); copy_sku = w.current_sku
        source = copy.deepcopy(w.db["_products"]["Polymaker PETG"])
        self.edit(copy_sku, hex="#ABCDEF"); w.draft_save.click()
        self.assertEqual(w.db["_skus"][copy_sku]["hex"], "ABCDEF")
        w._edit_physical()
        self.assertTrue(w.draft_restore["min_temp"].isEnabled()); self.assertTrue(w.draft_restore["hex"].isEnabled())
        w.draft_restore["min_temp"].click(); w.draft_restore["hex"].click()
        self.assertEqual((w.draft_fields["min_temp"].text(), w.draft_fields["hex"].text()), ("240", "070908"))
        w.draft_save.click()
        self.assertEqual(core.get_sku_view(w.db, copy_sku).product_data["min_temp"], 240)
        self.assertEqual(w.db["_skus"][copy_sku]["hex"], "070908")
        self.assertEqual(w.db["_skus"][copy_sku]["_field_sources"]["hex"]["source"], db_io.USER_SOURCE)
        self.assertEqual(w.db["_products"]["Polymaker PETG"], source); self.assertEqual(w.db["_skus"]["PB05001"]["hex"], "070908")

    def test_suspect_reference_colour_cannot_be_restored_as_confirmed(self):
        # A standalone reference: changing a grouped one would only create a shade conflict.
        w = self.window; w.db["_skus"]["CA02011"].update(color_name="White", hex="000000")
        w._reload_table(); self.edit("CA02011", hex="FAFAFA")
        self.assertFalse(w.draft_restore["hex"].isEnabled())
        self.assertIn("à vérifier", w.comparison_cells["hex"][1].accessibleDescription()); self.assertIn("À vérifier", w.parameter_cards[-1].badge.text())

    # UX-04 ────────────────────────────────────────────────────────────
    def test_primary_action_follows_the_blocking_reason(self):
        w = self.window
        w.db["_products"]["Polymaker PETG"]["density"] = None; w.current_sku = "PB05001"; w._show_detail("PB05001")
        self.assertEqual((w._primary_kind, w.btn_generate.text(), w.btn_generate.isEnabled()), ("correct_physical", "Corriger les caractéristiques…", True))
        self.assertIn("Champ à corriger : Densité g/cm³", w.nfc_capacity.text()); self.assertIn("density", w.nfc_capacity.toolTip())
        w.btn_generate.click(); self.assertIsNotNone(w._draft); self.assertIs(w.focusWidget() if w.isVisible() else w.draft_fields["density"], w.draft_fields["density"])
        self.assertFalse(Path(core.OUTPUT_DIR).exists())
        w._close_draft(); w.db["_products"]["Polymaker PETG"]["density"] = 1.3
        w.current_sku = "FB04001"; w._show_detail("FB04001")
        self.assertEqual((w._primary_kind, w.btn_generate.text()), ("missing_colour", "Préciser la couleur…"))
        colour = dict(w.db["_skus"]["CA02011"]); w.db["_skus"]["CA02011"].update(color_name="White", hex="000000"); w._reload_table()
        w.current_sku = "CA02011"; w._show_detail("CA02011")
        self.assertEqual(w._primary_kind, "confirm_colour"); w.btn_generate.click()
        self.assertIsNotNone(w._draft); self.assertIs(w.focusWidget() if w.isVisible() else w.draft_fields["hex"], w.draft_fields["hex"])
        w._close_draft(); w.db["_skus"]["CA02011"].update(colour); w._reload_table()
        w.current_sku = "PB05001"; w._show_detail("PB05001")
        self.assertEqual((w._primary_kind, w.btn_generate.text(), w.btn_generate.isEnabled()), ("export", "Exporter pour NFC", True))
        w.firmware.setCurrentIndex(w.firmware.findData("unknown")); self.assertFalse(w.btn_generate.isEnabled())

    def test_openspool_state_uses_engine_sizes_reserve_and_capacity_limit(self):
        w = self.window; w.current_sku = "PB05001"; w._show_detail("PB05001"); w._open_export_explanation()
        for tag, reserve in (("NTAG216", 0), ("NTAG215", 32)):
            w.tag_type.setCurrentIndex(w.tag_type.findData(tag)); w.nfc_reserve.setValue(reserve)
            options = w._nfc_options(); size = core.nfc_size(core.serialize_openspool(w._build_payload(), **options), tag_type=tag, reserved_bytes=reserve)
            expected = dict(payload=size.utf8_bytes, ndef=size.ndef_bytes, occupied=size.type2_bytes,
                            reserved=reserve, remaining=size.remaining_bytes, capacity=size.capacity_bytes)
            self.assertIn(tag, w.export_details.tag_tile.value.text())
            self.assertIn("OpenSpool 1.0", w.export_details.profile.text())
            for key, value in expected.items():
                self.assertEqual(w.export_details.metrics[key].value.text(), f"{value} octets", key)
            self.assertIn("Espace restant", w.nfc_capacity.toolTip())
        w.nfc_reserve.setValue(core.NFC_CAPACITIES["NTAG215"])
        self.assertEqual(w._primary_kind, "hardware"); self.assertIn("Export bloqué", w.nfc_capacity.text())
        self.assertEqual(w.export_details.metrics['remaining'].value.text(), '—')


    def test_opentag_state_reports_binary_budget_not_writer_json_length(self):
        from tests.test_opentag3d import OpenTagGuiTests
        w = OpenTagGuiTests.select_reader(self); w.current_sku = "PB05001"; w._show_detail("PB05001")
        self.assertEqual((w._primary_kind, w.btn_generate.text()), ("opentag_settings", "Préparer l’étiquette…"))
        p = core.get_sku_view(w.db, "PB05001").product_data
        core.save_opentag_settings("PB05001", dict(print_temp=p["min_temp"], bed_temp=p["bed_min_temp"], chamber_temp=0, weight=1000))
        outputs = [w.opentag_output.itemData(i) for i in range(w.opentag_output.count())]
        self.assertEqual(len(outputs), 3); w._open_export_explanation()
        for output in outputs:
            w.opentag_output.setCurrentIndex(w.opentag_output.findData(output))
            for tag, remaining in (("NTAG216", 621), ("NTAG215", 245)):
                w.tag_type.setCurrentIndex(w.tag_type.findData(tag)); w.nfc_reserve.setValue(0); w._refresh_nfc_capacity()
                self.assertEqual(w._primary_kind, "export", w.nfc_capacity.text())
                self.assertIn("OpenTag3D 2.004", w.export_details.profile.text())
                self.assertEqual(w.export_details.tag_tile.value.text(), tag)
                for key, expected in dict(payload=224, ndef=248, occupied=251, remaining=remaining, reserved=0, capacity=core.NFC_CAPACITIES[tag]).items():
                    self.assertEqual(w.export_details.metrics[key].value.text(), f"{expected} octets", (output, tag, key))
                if output != "ndef":
                    self.assertNotEqual(w.export_details.metrics['occupied'].value.text(), f"{len(w._prepare_opentag().data)} octets")
            w.nfc_reserve.setValue(10); self.assertEqual(w.export_details.metrics['reserved'].value.text(), "10 octets")


    def test_export_summary_is_readable_and_details_keep_the_exact_budget(self):
        w = self.window; w.show(); w._show_detail('PB05001'); w.app.processEvents()
        self.assertIn('Le fichier tient sur votre NTAG216', w.nfc_capacity.text())
        self.assertNotIn('NDEF', w.nfc_capacity.text()); self.assertFalse(w.export_details.isVisible())
        self.assertTrue(w.capacity_meter.isVisible())
        size = core.nfc_size(core.serialize_openspool(w._build_payload(), **w._nfc_options()))
        self.assertEqual((w.capacity_meter.value(), w.capacity_meter.maximum()), (size.remaining_bytes, size.capacity_bytes))
        before = w.size(); w.export_details_button.click(); self.assertTrue(w.export_details.isVisible()); self.assertEqual(w.size(), before)
        self.assertEqual(w.export_details.metrics['ndef'].value.text(), f'{size.ndef_bytes} octets')
        w.nfc_reserve.setValue(core.NFC_CAPACITIES['NTAG216'])
        self.assertFalse(w.capacity_meter.isVisible()); self.assertNotIn('Le fichier tient', w.nfc_capacity.text())
        with self.assertRaises(core.NfcCapacityError) as failure:w._nfc_options()
        self.assertEqual(str(failure.exception), w.export_details.diagnostic.text())


    def test_colour_summary_explains_the_limit_without_expert_terms(self):
        from PySide6.QtWidgets import QLabel
        cfg=core.load_config();cfg['colour_delta_max']=None;core.save_config(cfg)  # this scenario documents the unrestricted catalogue counts
        w = self.window; w.show(); w._start_colour_search('74CAC5'); w.app.processEvents()
        self.assertIn('couleurs comparables', w.results_label.text())
        self.assertNotIn('ΔE00', w.colour_info.text()); self.assertNotIn('HEX', w.colour_info.text())
        self.assertIsNone(w.colour_guidance); w.colour_details_button.click(); dialog = w.colour_guidance
        self.assertTrue(dialog.isVisible()); self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.assertEqual(dialog.comparable.value.text(), '365'); self.assertEqual(dialog.excluded.value.text(), '232')
        self.assertEqual(sum(int(t.value.text()) for t in dialog.reasons.values()), 232)
        self.assertNotIn('CIEDE2000', ' '.join(l.text() for l in dialog.tabs.widget(0).findChildren(QLabel)))
        self.assertIn('CIEDE2000', ' '.join(l.text() for l in dialog.tabs.widget(1).findChildren(QLabel)))


    def test_last_file_is_only_offered_after_a_real_write_and_tracks_context(self):
        w = self.window; w.current_sku = "PB05001"; w._show_detail("PB05001")
        self.assertFalse(w.btn_open_out.isEnabled()); self.assertTrue(w.last_export_label.isHidden())
        with patch("subprocess.Popen") as popen:
            w._open_output(); popen.assert_not_called()
        self.assertFalse(Path(core.OUTPUT_DIR).exists())
        with patch("spoolscribe.app_gui.QFileDialog.getExistingDirectory", return_value=""), patch("spoolscribe.app_gui.QMessageBox.information"):
            w._generate()
        self.assertIsNone(getattr(w, "_last_export", None))
        Path(core.OUTPUT_DIR).mkdir()
        with patch("spoolscribe.app_gui.QMessageBox.information"):
            w._generate()
        path = w._last_export["path"]; self.assertTrue(Path(path).is_file())
        self.assertIn("identique à l’export actuel", w.last_export_label.text()); self.assertTrue(w.btn_open_out.isEnabled())
        # Linux opens the containing folder; Finder/Explorer can select the
        # actual file. Exercise all three commands without opening anything.
        import os
        for platform, command in (
                ("linux", ["xdg-open", str(Path(path).parent)]),
                ("darwin", ["open", "-R", path]),
                ("win32", ["explorer", "/select,", os.path.normpath(path)])):
            with self.subTest(platform=platform), patch("spoolscribe.ui_detail.sys.platform", platform), patch("subprocess.Popen") as popen:
                w._open_output()
                popen.assert_called_once_with(command)
        w.nfc_profile.setCurrentIndex(w.nfc_profile.findData("full"))
        self.assertIn("autre fiche ou réglages différents", w.last_export_label.text())
        w.nfc_profile.setCurrentIndex(w.nfc_profile.findData("auto")); self.assertIn("identique", w.last_export_label.text())
        w.current_sku = "FB04001"; w._show_detail("FB04001"); self.assertIn("autre fiche", w.last_export_label.text())
        Path(path).unlink(); w._refresh_last_export()
        self.assertIn("introuvable", w.last_export_label.text()); self.assertFalse(w.btn_open_out.isEnabled())
        with patch("subprocess.Popen") as popen:
            w._open_output(); popen.assert_not_called()

    # UX-05 ────────────────────────────────────────────────────────────
    def test_colour_proximity_ranks_locally_without_changing_data(self):
        cfg=core.load_config();cfg["colour_delta_max"]=None;core.save_config(cfg)  # exercise the full ordering, including far colours after reload
        w = self.window; self.big_catalogue(); before = copy.deepcopy(w.db); raw = Path(core.DB_PATH).read_bytes()
        w.current_sku = "PB05001"; w._show_detail("PB05001"); w._open_colour_search()
        self.assertTrue(w.colour_panel.isVisibleTo(w)); self.assertEqual(w.colour_hex.text(), "#070908")
        deltas = [w._colour_deltas[r["sku"]]["delta"] for r in w._filtered_rows]
        self.assertEqual(deltas, sorted(deltas)); self.assertEqual(deltas[0], 0.0)
        self.assertFalse(w.table.isColumnHidden(w._delta_column)); self.assertEqual(w.table.item(0, w._delta_column).text(), "0.00"); self.assertEqual(w._colour_report["total"], len(w._filtered_rows))
        self.assertIn("Teintes proches de #070908", w.filter_summary.toolTip())
        order = [r["sku"] for r in w._filtered_rows]; w._apply_filter(); self.assertEqual([r["sku"] for r in w._filtered_rows], order)
        w._choose_brand("Polymaker", remember=False)
        self.assertTrue(all(r["brand"] == "Polymaker" for r in w._filtered_rows))
        self.assertFalse(w._start_colour_search("#12"))
        self.assertIn("Code couleur invalide", w.colour_info.text()); self.assertEqual(w._colour_query["hex"], "070908")
        self.assertTrue(w._start_colour_search("ff0000")); self.assertEqual(w._colour_query["hex"], "FF0000")
        # A corrected HEX after a reload is ranked from the new value (index rebuilt).
        index_before = w._colour_index[0]; moved = w._filtered_rows[0]["sku"]; w.db["_skus"][moved]["hex"] = "00FF00"
        w._reload_table(); self.assertIsNot(w._colour_index[0], index_before)
        self.assertEqual(w._colour_deltas[moved]["row"]["hex"], "00FF00")
        self.assertAlmostEqual(w._colour_deltas[moved]["delta"], cd.delta_e00("FF0000", "00FF00"), places=5)
        w.db = before; w._reload_table()
        w._stop_colour_search(); self.assertIsNone(w._colour_query); self.assertNotIn("ΔE", w.table.item(0, 3).text())
        w._open_colour_search(); w._reset_filters(); self.assertIsNone(w._colour_query); self.assertEqual(w.colour_hex.text(), ""); self.assertIsNone(w._colour_report)
        self.assertEqual(w.db, before); self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)

    # UX-06 ────────────────────────────────────────────────────────────
    def test_cards_render_colour_first_states_and_focus_without_losing_identity(self):
        from PySide6.QtCore import Qt, QSize, QRect
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
        w = self.window; w._set_view_mode("grid"); delegate = w.grid.itemDelegate()
        index = w.grid.model().index(0, 0); sku = index.data(Qt.UserRole)
        self.assertEqual(sku, w.table.item(0, 1).data(Qt.UserRole))
        self.assertIn(w._rows[0]["color_name"] or "Couleur", index.data(Qt.AccessibleTextRole))
        long_row = dict(delegate.rows[sku], color_name="Very Long Colour Name " * 6, product="P" * 200, hex=None, ready=False,
                        quality="Couleur à vérifier (x)", hex_variants=2)
        for state in (QStyle.State_Selected, QStyle.State_HasFocus, QStyle.State_MouseOver, QStyle.State_None):
            for row in (delegate.rows[sku], long_row):
                delegate.rows[sku] = row; image = QImage(QSize(190, 220), QImage.Format_ARGB32); image.fill(0)
                option = QStyleOptionViewItem(); option.rect = QRect(0, 0, 180, 208); option.state = state | QStyle.State_Enabled
                painter = QPainter(image); delegate.paint(painter, option, index); painter.end()
                self.assertFalse(image.isNull())
        w.grid.setCurrentRow(0); w._set_view_mode("list")
        self.assertEqual([i.row() for i in w.table.selectionModel().selectedRows()], [0])
        with patch.object(w, "_show_detail") as shown:
            w.grid.favoriteRequested.emit(sku); shown.assert_not_called()
