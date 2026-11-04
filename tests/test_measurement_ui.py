"""Measurement window inside the real application window (offscreen, offline, isolated files)."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import db_io
from spoolscribe import colour_measurements as cm, core, i18n
from tests import test_gui as fixture
from tests.support import ROOT

if fixture.HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QLabel, QMessageBox
    from spoolscribe import app_gui


@unittest.skipUnless(fixture.HAS_QT, "PySide6 non installé")
class MeasurementUiTests(unittest.TestCase):
    setUpClass = classmethod(fixture.GuiTests.setUpClass.__func__)

    def setUp(self):
        timer = patch("spoolscribe.app_gui.QTimer.singleShot"); timer.start(); self.addCleanup(timer.stop)
        fixture.GuiTests.setUp(self)
        self.addCleanup(i18n.set_language, "fr")
        self.window.show(); self.app.processEvents()
        self.registry_path = Path(core.DB_PATH).with_name("colour_measurements.json")

    def open_window(self):
        dialog = self.window._open_measurements()
        self.app.processEvents()
        return dialog

    def snapshot(self):
        return (Path(core.DB_PATH).read_bytes(), Path(core.CONFIG_PATH).read_bytes() if Path(core.CONFIG_PATH).exists() else b"")

    def test_entry_point_lives_in_the_colours_section_and_opening_writes_nothing(self):
        w = self.window
        self.assertTrue(w.colour_panel.isAncestorOf(w.colour_measure_btn))
        before = self.snapshot()
        dialog = self.open_window()
        self.assertIsInstance(dialog, QDialog)
        self.assertEqual(dialog.registry.path, self.registry_path)
        self.assertFalse(self.registry_path.exists())
        self.assertEqual([dialog.tabs.tabText(i) for i in range(dialog.tabs.count())], ["Saisir", "Coller", "Importer", "Enregistrées"])
        self.assertFalse(dialog.btn_save.isEnabled()); self.assertFalse(dialog.btn_search.isEnabled())
        dialog.reject(); self.app.processEvents()
        self.assertFalse(self.registry_path.exists()); self.assertEqual(self.snapshot(), before)

    def test_hex_entry_searches_through_the_historical_path_and_keeps_filters(self):
        w = self.window; dialog = self.open_window()
        w._choose_brand("Polymaker", remember=False)
        dialog.space.setCurrentIndex(dialog.space.findData("sRGB_HEX")); dialog.hex_edit.setText("#74CABF")
        self.assertEqual(dialog.level_tile.value.text(), "Proximité indicative")
        self.assertTrue(dialog.btn_search.isEnabled())
        dialog.btn_search.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["kind"], "measurement"); self.assertEqual(w._colour_query["hex"], "74CABF")
        self.assertEqual(w.brand_filter.currentData(), "Polymaker")
        self.assertTrue(all(r["brand"] == "Polymaker" for r in w._filtered_rows))
        self.assertEqual(w._filtered_rows[0]["hex"], "74CABF")
        self.assertIn("74CABF", w._active_section_values()["colours"])
        self.assertFalse(self.registry_path.exists())   # searching is not saving
        # The HEX field now starts a classic query again; the measurement query is replaced.
        w._start_colour_search("070908")
        self.assertEqual(w._colour_query["kind"], "hex")

    def test_lab_d65_entry_ranks_directly_and_the_card_explains_the_basis(self):
        w = self.window; dialog = self.open_window()
        dialog.space.setCurrentIndex(dialog.space.findData("CIELAB"))
        for key, text in (("L", "73,2"), ("a", "-25,6"), ("b", "-12,4")):
            dialog.lab_edits[key].setText(text)
        self.assertEqual(dialog.level_tile.value.text(), "Conditions insuffisantes"); self.assertFalse(dialog.btn_search.isEnabled())
        self.assertTrue(dialog.btn_save.isEnabled())   # storable even when blocked
        dialog.illuminant.setCurrentIndex(dialog.illuminant.findData("D65")); dialog.observer.setCurrentIndex(dialog.observer.findData(2))
        self.assertEqual(dialog.level_tile.value.text(), "Proximité indicative"); self.assertTrue(dialog.btn_search.isEnabled())
        with patch("spoolscribe.colour_distance.rank") as hex_rank:
            dialog.btn_search.click(); self.app.processEvents()
        hex_rank.assert_not_called()
        self.assertEqual(w._colour_query["lab"], (73.2, -25.6, -12.4)); self.assertNotIn("hex", w._colour_query)
        self.assertEqual(w.colour_hex.text(), "")
        self.assertIn("L* 73,2", w._active_section_values()["colours"])
        self.assertIsNone(w._colour_report["target"]); self.assertIn("D65/2°", w._colour_report["basis"])
        w._open_colour_explanation(); self.app.processEvents()
        self.assertIn("Mesure comparée", w.colour_guidance.target.text()); self.assertFalse(w.colour_guidance.swatch.isVisible())
        w.colour_guidance.close()

    def test_blocked_conditions_store_but_never_rank(self):
        dialog = self.open_window()
        dialog.space.setCurrentIndex(dialog.space.findData("CIELAB"))
        for key, text in (("L", "60"), ("a", "10"), ("b", "-3")):
            dialog.lab_edits[key].setText(text)
        dialog.illuminant.setCurrentIndex(dialog.illuminant.findData("D50")); dialog.observer.setCurrentIndex(dialog.observer.findData(2))
        self.assertEqual(dialog.level_tile.value.text(), "Conditions insuffisantes"); self.assertIn("D50", dialog.level_tile.note.text())
        self.assertFalse(dialog.btn_search.isEnabled())
        with patch("spoolscribe.colour_distance.ciede2000") as delta:
            dialog.btn_save.click(); self.app.processEvents()
        delta.assert_not_called()
        self.assertTrue(self.registry_path.exists())
        stored = json.loads(self.registry_path.read_text())["measurements"]
        self.assertEqual(len(stored), 1)
        measurement = next(iter(stored.values()))
        self.assertEqual(measurement["conditions"]["illuminant"], "D50"); self.assertEqual(measurement["original"]["lexemes"]["L"], "60")
        self.assertIsNone(measurement["measured_at"])
        self.assertEqual(dialog.saved_list.count(), 1); self.assertEqual(dialog.tabs.currentIndex(), 0)

    def test_paste_conflict_requires_a_choice_then_saves_alternatives(self):
        w = self.window; dialog = self.open_window(); dialog.tabs.setCurrentIndex(1)
        dialog.paste_edit.setPlainText((ROOT / "tests/fixtures/measurements/synthetic_paste_conflicts.txt").read_text(encoding="utf-8"))
        dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 3)
        self.assertIn("ne correspondent pas", dialog.paste_errors.toPlainText() if hasattr(dialog.paste_errors, "toPlainText") else dialog.paste_errors.text())
        self.assertFalse(dialog.btn_search.isEnabled())
        self.assertEqual(dialog.paste_illuminant.currentData(), "D50"); self.assertEqual(dialog.paste_observer.currentData(), 10)
        dialog.paste_candidates.setCurrentRow(2)   # the Lab set, with D50/10° → blocked
        self.assertEqual(dialog.level_tile.value.text(), "Conditions insuffisantes")
        dialog.paste_candidates.setCurrentRow(0)   # the HEX set → indicative
        self.assertEqual(dialog.level_tile.value.text(), "Proximité indicative")
        dialog.btn_save.click(); self.app.processEvents()
        stored = next(iter(json.loads(self.registry_path.read_text())["measurements"].values()))
        self.assertEqual(stored["original"]["space"], "sRGB_HEX")
        self.assertEqual({a["space"] for a in stored["original"]["alternatives"]}, {"sRGB_RGB8", "CIELAB"})
        self.assertIn("HEX #74CABF", stored["original"]["raw_text"])
        self.assertEqual(stored["provenance"]["method"], "paste")
        self.assertIsNone(w._colour_query)

    def test_csv_import_with_decimal_commas_reports_partial_and_writes_once(self):
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(2)
        path = str(ROOT / "tests/fixtures/measurements/synthetic_lab_semicolon_fr.csv")
        before = Path(path).read_bytes()
        with patch("spoolscribe.ui_colour_measurements.QFileDialog.getOpenFileName", return_value=(path, "")):
            dialog.btn_file.click(); self.app.processEvents()
        self.assertEqual(dialog.delimiter.currentData(), ";"); self.assertEqual(dialog.decimal.currentData(), ",")
        self.assertEqual(dialog.preview.rowCount(), 5); self.assertEqual(dialog.preview.columnCount(), 7)
        self.assertEqual(dialog.mapping_combos["L"].currentData(), 1); self.assertEqual(dialog.mapping_combos["name"].currentData(), 0)
        self.assertFalse(dialog.btn_import.isEnabled())
        dialog.btn_check.click(); self.app.processEvents()
        self.assertEqual(dialog.import_summary.text(), "4 valides / 1 à corriger / 1 doublons potentiels")
        self.assertTrue(dialog.partial_confirm.isVisible()); self.assertFalse(dialog.btn_import.isEnabled())
        dialog.partial_confirm.setChecked(True); self.assertTrue(dialog.btn_import.isEnabled())
        dialog.btn_import.click(); self.app.processEvents()
        stored = json.loads(self.registry_path.read_text())["measurements"]
        self.assertEqual(len(stored), 4); self.assertEqual(dialog.tabs.currentIndex(), 3); self.assertEqual(dialog.saved_list.count(), 4)
        self.assertEqual(Path(path).read_bytes(), before)
        names = sorted(m["name"] for m in stored.values())
        self.assertEqual(names, ["Cible rouge", "Cible rouge", "Cible verte", "D50 bloquée"])   # duplicates kept, distinct ids
        # Re-checking the same file reports the exact re-import.
        dialog.tabs.setCurrentIndex(2); dialog.btn_check.click(); self.app.processEvents()
        self.assertIn("Déjà importé", dialog.import_errors.toPlainText())
        # 1 in-batch repetition + 3 distinct digests already stored + 4 exact file/record re-imports
        self.assertEqual(dialog.import_summary.text(), "4 valides / 1 à corriger / 8 doublons potentiels")

    def test_non_utf8_file_waits_for_an_explicit_encoding(self):
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(2)
        path = str(ROOT / "tests/fixtures/measurements/synthetic_latin1.csv")
        with patch("spoolscribe.ui_colour_measurements.QFileDialog.getOpenFileName", return_value=(path, "")):
            dialog.btn_file.click(); self.app.processEvents()
        self.assertIn("UTF-8", dialog.import_note.text()); self.assertEqual(dialog.preview.columnCount(), 0)
        dialog.encoding.setCurrentIndex(dialog.encoding.findData("latin-1")); self.app.processEvents()
        self.assertEqual(dialog.preview.columnCount(), 4)
        dialog.delimiter.setCurrentIndex(dialog.delimiter.findData(";")); dialog.decimal.setCurrentIndex(dialog.decimal.findData(","))
        dialog.btn_check.click(); self.app.processEvents()
        self.assertEqual(dialog.import_summary.text(), "1 valides / 0 à corriger / 0 doublons potentiels")

    def test_saved_measurements_link_rename_detach_delete_and_restore_only_the_registry(self):
        w = self.window; dialog = self.open_window()
        catalogue_before = Path(core.DB_PATH).read_bytes(); config_before = Path(core.CONFIG_PATH).read_bytes()
        dialog.space.setCurrentIndex(dialog.space.findData("sRGB_HEX")); dialog.hex_edit.setText("112233")
        dialog.btn_save.click(); self.app.processEvents()
        identifier = dialog.draft_identifier; self.assertTrue(identifier.startswith("MEAS-"))
        dialog.tabs.setCurrentIndex(3); self.assertEqual(dialog.saved_list.currentItem().data(Qt.UserRole), identifier)
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_link.click(); self.app.processEvents()
        self.assertIn("Sélectionnez d’abord", dialog.feedback.text())
        w.current_sku = "PB05001"; w._show_detail("PB05001")
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes) as question:
            dialog.btn_link.click(); self.app.processEvents()
        self.assertIn("PB05001", question.call_args.args[2])
        self.assertEqual(dialog.registry.get(identifier)["association"], {"sku": "PB05001"})
        self.assertIn("lié à PB05001", dialog.saved_list.currentItem().text())
        self.assertEqual(Path(core.DB_PATH).read_bytes(), catalogue_before)
        self.assertEqual(w.db["_skus"]["PB05001"]["hex"], json.loads(catalogue_before.decode())["_skus"]["PB05001"]["hex"])
        with patch("spoolscribe.ui_colour_measurements.QInputDialog.getText", return_value=("Renommée", True)):
            dialog.btn_rename.click(); self.app.processEvents()
        self.assertEqual(dialog.registry.get(identifier)["name"], "Renommée")
        self.assertEqual(dialog.registry.get(identifier)["original"]["components"]["hex"], "112233")
        dialog.btn_detach.click(); self.app.processEvents()
        self.assertIsNone(dialog.registry.get(identifier)["association"])
        # Use as target, then delete it: the active query is withdrawn, filters untouched.
        w._choose_brand("Polymaker", remember=False)
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(3); dialog.saved_list.setCurrentRow(0)
        dialog.btn_use.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["id"], identifier)
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(3); dialog.saved_list.setCurrentRow(0)
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_delete.click(); self.app.processEvents()
        self.assertIsNone(w._colour_query); self.assertEqual(w.brand_filter.currentData(), "Polymaker")
        self.assertEqual(dialog.registry.measurements, {})
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_restore.click(); self.app.processEvents()
        self.assertEqual(dialog.registry.get(identifier)["name"], "Renommée")
        self.assertEqual(Path(core.DB_PATH).read_bytes(), catalogue_before)
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), config_before)
        self.assertFalse(any("MEAS-" in line for line in Path(core.CONFIG_PATH).read_text().splitlines()))

    def test_window_fits_every_language_and_theme_with_keyboard_focus(self):
        for language in ("fr", "en", "es", "zh_CN"):
            i18n.set_language(language)
            for dark in (False, True):
                with patch("spoolscribe.app_gui.is_dark_theme", return_value=dark):
                    self.window._apply_theme()
                    from spoolscribe.ui_colour_measurements import MeasurementWindow
                    dialog = MeasurementWindow(self.window, registry=self.window.measurement_window.registry if self.window.measurement_window else None)
                    dialog.show(); self.app.processEvents()
                    screen = dialog.screen().availableGeometry()
                    self.assertLessEqual(dialog.height(), screen.height()); self.assertLessEqual(dialog.width(), screen.width())
                    self.assertTrue(dialog.tabs.tabText(0)); self.assertTrue(dialog.btn_close.text())
                    dialog.hex_edit.setFocus(Qt.TabFocusReason); self.assertTrue(dialog.hex_edit.hasFocus() or not dialog.isActiveWindow())
                    dialog.close()


    # ── corrections after the independent QA (R1, R3, R4, R6) ─────────────
    def test_each_entry_keeps_its_own_draft_and_importer_has_none(self):
        w = self.window; dialog = self.open_window()
        dialog.space.setCurrentIndex(dialog.space.findData("sRGB_HEX")); dialog.hex_edit.setText("74CABF")
        dialog.tabs.setCurrentIndex(1); dialog.paste_edit.setPlainText("HEX #112233"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(cm.hex_of(dialog._draft_measurement()), "112233")
        dialog.tabs.setCurrentIndex(0); self.app.processEvents()
        self.assertEqual(dialog.hex_edit.text(), "74CABF"); self.assertEqual(cm.hex_of(dialog._draft_measurement()), "74CABF")
        self.assertTrue(dialog.btn_save.isEnabled()); self.assertTrue(dialog.btn_search.isEnabled())
        dialog.tabs.setCurrentIndex(2); self.app.processEvents()
        self.assertIsNone(dialog.draft); self.assertIsNone(dialog._draft_measurement())
        self.assertFalse(dialog.btn_save.isEnabled()); self.assertFalse(dialog.btn_search.isEnabled())
        dialog.tabs.setCurrentIndex(3); self.app.processEvents()
        self.assertIsNone(dialog.draft); self.assertFalse(dialog.btn_save.isEnabled())
        dialog.tabs.setCurrentIndex(1); self.app.processEvents()
        self.assertEqual(cm.hex_of(dialog._draft_measurement()), "112233")
        dialog.tabs.setCurrentIndex(0); self.app.processEvents()
        dialog.btn_search.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["hex"], "74CABF"); self.assertFalse(self.registry_path.exists())

    def test_editing_the_pasted_text_withdraws_the_proposal_until_reinterpreted(self):
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(1)
        dialog.paste_edit.setPlainText("HEX #112233"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertTrue(dialog.btn_save.isEnabled())
        dialog.paste_edit.setPlainText("HEX #FF0000"); self.app.processEvents()
        self.assertIsNone(dialog.draft); self.assertFalse(dialog.btn_save.isEnabled()); self.assertFalse(dialog.btn_search.isEnabled())
        self.assertEqual(dialog.paste_candidates.count(), 0); self.assertIn("Texte modifié", dialog.paste_conditions.text())
        dialog.paste_observer.setCurrentIndex(dialog.paste_observer.findData(2)); self.app.processEvents()
        self.assertIsNone(dialog.draft)   # changing a condition never resurrects old components
        dialog.btn_interpret.click(); self.app.processEvents()
        self.assertIsNone(dialog.paste_observer.currentData())   # a new proposal starts from the conditions of the new text
        dialog.paste_observer.setCurrentIndex(dialog.paste_observer.findData(2)); self.app.processEvents()
        measurement = dialog._draft_measurement()
        self.assertEqual((measurement["original"]["components"]["hex"], measurement["original"]["raw_text"]), ("FF0000", "HEX #FF0000"))
        self.assertEqual(measurement["conditions"]["observer"], 2)   # declared context kept with an sRGB principal
        dialog.btn_save.click(); self.app.processEvents()
        stored = next(iter(json.loads(self.registry_path.read_text())["measurements"].values()))
        self.assertEqual((stored["original"]["components"], stored["original"]["raw_text"]), ({"hex": "FF0000"}, "HEX #FF0000"))
        self.assertEqual(cm.comparison_policy(stored)["reason"], "srgb_declared")

    def test_unbalanced_paste_requires_an_explicit_choice(self):
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(1)
        dialog.paste_edit.setPlainText("L*=50 a*=1 b*=2 L*=80 D65 2°"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 1); self.assertIsNone(dialog.draft); self.assertFalse(dialog.btn_save.isEnabled())
        self.assertIn("incomplètes", dialog.paste_errors.text()); self.assertIn("décision", dialog.paste_errors.text())
        dialog.paste_candidates.setCurrentRow(0); self.app.processEvents()
        self.assertEqual(dialog._draft_measurement()["original"]["components"]["L"], 50.0); self.assertTrue(dialog.btn_search.isEnabled())
        dialog.paste_edit.setPlainText("Adobe RGB 116 202 191"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 0); self.assertIn("non pris en charge", dialog.paste_errors.text())

    def test_search_uses_the_selected_acquisition_identity_not_its_colour(self):
        w = self.window; dialog = self.open_window()
        a = dialog.registry.create(cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="Acquisition A"))
        b = dialog.registry.create(cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="Acquisition B"))

        def use(identifier):
            d = self.open_window(); d.tabs.setCurrentIndex(3); d._refresh_saved()
            for i in range(d.saved_list.count()):
                if d.saved_list.item(i).data(Qt.UserRole) == identifier:
                    d.saved_list.setCurrentRow(i)
            d.btn_use.click(); self.app.processEvents(); return d
        use(a)
        self.assertEqual((w._colour_query["id"], w._colour_query["name"]), (a, "Acquisition A"))
        cache = w._colour_query["cache"]; self.assertTrue(cache)   # distances were computed for A
        use(b)
        self.assertEqual((w._colour_query["id"], w._colour_query["name"]), (b, "Acquisition B"))
        self.assertIs(w._colour_query["cache"], cache)   # same values: distances reused, identity not
        self.assertIn("Acquisition B", w.colour_info.text())
        dialog = use(a); dialog = self.open_window(); dialog.tabs.setCurrentIndex(3)
        with patch("spoolscribe.ui_colour_measurements.QInputDialog.getText", return_value=("B renommée", True)):
            for i in range(dialog.saved_list.count()):
                if dialog.saved_list.item(i).data(Qt.UserRole) == b:
                    dialog.saved_list.setCurrentRow(i)
            dialog.btn_rename.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["id"], a)   # renaming B leaves A's query alone
        use(b); self.assertEqual(w._colour_query["name"], "B renommée")
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(3)
        for i in range(dialog.saved_list.count()):
            if dialog.saved_list.item(i).data(Qt.UserRole) == a:
                dialog.saved_list.setCurrentRow(i)
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_delete.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["id"], b)   # deleting A while B is the target keeps B
        for i in range(dialog.saved_list.count()):
            if dialog.saved_list.item(i).data(Qt.UserRole) == b:
                dialog.saved_list.setCurrentRow(i)
        with patch("spoolscribe.ui_colour_measurements.QInputDialog.getText", return_value=("B encore", True)):
            dialog.btn_rename.click(); self.app.processEvents()
        self.assertEqual(w._colour_query["name"], "B encore")   # the active target follows its own explicit changes
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_delete.click(); self.app.processEvents()
        self.assertIsNone(w._colour_query)

    def test_csv_principal_set_is_an_explicit_choice(self):
        import tempfile
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "two_spaces.csv"; path.write_text("Sample,L*,a*,b*,HEX\nred,50,1,2,FF0000\nblue,30,0,-40,0000FF\n", encoding="utf-8")
            with patch("spoolscribe.ui_colour_measurements.QFileDialog.getOpenFileName", return_value=(str(path), "")):
                dialog.btn_file.click(); self.app.processEvents()
            self.assertTrue(dialog.principal.isVisible()); self.assertIsNone(dialog.principal.currentData())
            dialog.btn_check.click(); self.app.processEvents()
            self.assertIn("jeu principal", dialog.import_summary.text()); self.assertIsNone(dialog.import_report); self.assertFalse(dialog.btn_import.isEnabled())
            dialog.principal.setCurrentIndex(dialog.principal.findData("sRGB_HEX")); dialog.btn_check.click(); self.app.processEvents()
            self.assertEqual(dialog.import_summary.text(), "2 valides / 0 à corriger / 0 doublons potentiels")
            self.assertIn("Jeu principal : HEX", dialog.import_errors.toPlainText())
            dialog.btn_import.click(); self.app.processEvents()
            stored = list(json.loads(self.registry_path.read_text())["measurements"].values())
            self.assertEqual({m["original"]["space"] for m in stored}, {"sRGB_HEX"})
            self.assertEqual({a["space"] for m in stored for a in m["original"]["alternatives"]}, {"CIELAB"})
            dialog.mapping_combos["hex"].setCurrentIndex(0); self.app.processEvents()   # one space left: the choice disappears
            self.assertFalse(dialog.principal.isVisible())

    def test_documented_conditions_and_sample_details_are_saved_and_shown(self):
        dialog = self.open_window()
        dialog.space.setCurrentIndex(dialog.space.findData("CIELAB"))
        for key, text in (("L", "50"), ("a", "1"), ("b", "2")):
            dialog.lab_edits[key].setText(text)
        dialog.illuminant.setCurrentIndex(dialog.illuminant.findData("D65")); dialog.observer.setCurrentIndex(dialog.observer.findData(2))
        self.assertFalse(dialog.swatch.isVisible())   # never a preview of a Lab value
        dialog.manual_conditions.advanced_toggle.setChecked(True); self.app.processEvents()
        dialog.geometry.setText("45/0"); dialog.specular.setCurrentIndex(dialog.specular.findData("SCE")); dialog.aperture.setText("8 mm")
        dialog.details_toggle.setChecked(True); self.app.processEvents()
        dialog.sample_material.setText("PLA"); dialog.sample_finish.setText("mat"); dialog.sample_thickness.setText("2 mm")
        dialog.sample_backing.setText("fond blanc"); dialog.sample_surface_note.setText("poncé")
        self.assertEqual(dialog.level_tile.value.text(), "Proximité indicative")
        dialog.btn_save.click(); self.app.processEvents()
        stored = next(iter(json.loads(self.registry_path.read_text())["measurements"].values()))
        self.assertEqual({k: stored["conditions"][k] for k in ("geometry", "specular", "aperture")}, {"geometry": "45/0", "specular": "SCE", "aperture": "8 mm"})
        self.assertEqual({k: stored["sample"][k] for k in ("material", "finish", "thickness", "backing", "surface_note")},
                         {"material": "PLA", "finish": "mat", "thickness": "2 mm", "backing": "fond blanc", "surface_note": "poncé"})
        dialog.tabs.setCurrentIndex(3); dialog.saved_list.setCurrentRow(0); self.app.processEvents()
        for text in ("45/0", "SCE", "PLA", "fond blanc", "saisie manuelle"):
            self.assertIn(text, dialog.saved_detail.text())
        dialog.tabs.setCurrentIndex(0); dialog.space.setCurrentIndex(dialog.space.findData("sRGB_HEX")); dialog.hex_edit.setText("74CABF"); self.app.processEvents()
        self.assertTrue(dialog.swatch.isVisible()); self.assertIn("#74CABF", dialog.swatch.styleSheet())

    def test_errors_and_labels_are_translated_in_english(self):
        i18n.set_language("en")
        dialog = self.open_window()
        labels = [label.text() for label in dialog.findChildren(QLabel)]
        self.assertIn("Value format", labels); self.assertNotIn("Packaging", labels)
        dialog.space.setCurrentIndex(dialog.space.findData("CIELAB"))
        for key, text in (("L", "150"), ("a", "0"), ("b", "0")):
            dialog.lab_edits[key].setText(text)
        self.assertEqual(dialog.manual_error.text(), "L* must be between 0 and 100.")
        dialog.tabs.setCurrentIndex(1); dialog.paste_edit.setPlainText("RGB 116 202 191.5"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertIn("refused", dialog.paste_errors.text()); self.assertNotIn("refusé", dialog.paste_errors.text())
        dialog.tabs.setCurrentIndex(2)
        path = str(ROOT / "tests/fixtures/measurements/synthetic_lab_semicolon_fr.csv")
        with patch("spoolscribe.ui_colour_measurements.QFileDialog.getOpenFileName", return_value=(path, "")):
            dialog.btn_file.click(); self.app.processEvents()
        dialog.btn_check.click(); self.app.processEvents()
        self.assertIn("Record 5: Invalid number", dialog.import_errors.toPlainText())
        dialog.tabs.setCurrentIndex(3); self.app.processEvents()
        dialog.registry.create(cm.new_measurement(cm.parse_manual("CIELAB", {"L": "1", "a": "2", "b": "3"}), name="x", conditions={"illuminant": "D50", "observer": 10}))
        dialog._refresh_saved(); dialog.saved_list.setCurrentRow(0)
        self.assertIn("D50 / 10°", dialog.saved_list.item(0).text()); self.assertIn("Method: manual entry", dialog.saved_detail.text())

    def test_restore_after_an_unreadable_registry_is_a_real_action_that_keeps_the_file(self):
        from spoolscribe import measurement_store as ms
        registry = ms.MeasurementRegistry(self.registry_path)
        identifier = registry.create(cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="avant"))
        registry.rename(identifier, "après")   # the backup holds "avant"
        self.registry_path.write_bytes(b"corrupt {")
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(3); self.app.processEvents()
        self.assertIn("Registre illisible", dialog.feedback.text()); self.assertTrue(dialog.registry_problem.isVisible())
        self.assertIn("Restaurer", dialog.registry_problem.text()); self.assertTrue(dialog.btn_restore.isEnabled())
        self.assertEqual(dialog.saved_list.count(), 0); self.assertFalse(dialog.btn_save.isEnabled())
        self.assertEqual(self.registry_path.read_bytes(), b"corrupt {")   # nothing reset
        with patch("spoolscribe.ui_colour_measurements.QMessageBox.question", return_value=QMessageBox.Yes):
            dialog.btn_restore.click(); self.app.processEvents()
        self.assertIn("restauré", dialog.feedback.text()); self.assertIsNone(dialog.registry.load_error)
        self.assertEqual(dialog.saved_list.count(), 1); self.assertEqual(dialog.registry.get(identifier)["name"], "avant")
        self.assertFalse(dialog.registry_problem.isVisible())
        preserved = list(self.registry_path.parent.glob("colour_measurements.json.before-restore-*"))
        self.assertEqual(preserved[0].read_bytes(), b"corrupt {")
        self.assertNotIn("Traceback", dialog.feedback.text())

    def test_oversize_csv_is_refused_before_being_read(self):
        import tempfile
        dialog = self.open_window(); dialog.tabs.setCurrentIndex(2)
        with tempfile.TemporaryDirectory() as tmp:
            big = Path(tmp) / "big.csv"
            with open(big, "wb") as stream:
                stream.truncate(cm.LIMITS["file_bytes"] + 1)
            with patch("spoolscribe.ui_colour_measurements.QFileDialog.getOpenFileName", return_value=(str(big), "")):
                dialog.btn_file.click(); self.app.processEvents()
            self.assertIn("volumineux", dialog.import_note.text()); self.assertIsNone(dialog._import_state)
            self.assertEqual(dialog.file_label.text(), "Aucun fichier choisi")

    # ── R2 after the re-QA 09: a decimal comma in an RGB channel ───────────
    def test_decimal_comma_rgb_paste_is_refused_and_nothing_is_saved_or_searched(self):
        w = self.window; dialog = self.open_window()
        existing = dialog.registry.create(cm.new_measurement(cm.parse_manual("sRGB_HEX", {"hex": "112233"}), name="existante"))
        before = self.snapshot(); registry_before = self.registry_path.read_bytes()
        dialog.tabs.setCurrentIndex(1)
        dialog.paste_edit.setPlainText("RGB 116 202 191,5"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 0)
        self.assertIsNone(dialog.draft); self.assertIsNone(dialog._draft_measurement())
        self.assertFalse(dialog.btn_save.isEnabled()); self.assertFalse(dialog.btn_search.isEnabled())
        self.assertTrue(dialog.paste_errors.isVisible())
        self.assertIn("RGB « 116 202 191,5 » refusé : trois entiers 0–255 sans décimale sont requis.", dialog.paste_errors.text())
        self.assertIn("Une décision est nécessaire", dialog.paste_errors.text())
        self.assertEqual(dialog.paste_edit.toPlainText(), "RGB 116 202 191,5")   # kept as typed, for an explicit correction
        dialog.btn_save.click(); dialog.btn_search.click(); self.app.processEvents()
        dialog._save_draft(); dialog._search_draft(); self.app.processEvents()   # even forced: nothing to store or search
        self.assertIsNone(w._colour_query)
        self.assertEqual(self.registry_path.read_bytes(), registry_before); self.assertEqual(list(dialog.registry.measurements), [existing])
        self.assertEqual(self.snapshot(), before)
        # Next to a valid HEX the refused RGB set is reported and nothing is chosen automatically.
        dialog.paste_edit.setPlainText("HEX #74CABF RGB 116 202 191,5"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 1); self.assertIsNone(dialog.draft); self.assertFalse(dialog.btn_save.isEnabled())
        self.assertIn("191,5", dialog.paste_errors.text())
        # The documented notation, once written by the user, is proposed and stored exactly as typed.
        dialog.paste_edit.setPlainText("RGB 116, 202, 191"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 1); self.assertTrue(dialog.btn_save.isEnabled())
        dialog.btn_save.click(); self.app.processEvents()
        stored = [m for i, m in json.loads(self.registry_path.read_text())["measurements"].items() if i != existing]
        self.assertEqual(len(stored), 1)
        original = stored[0]["original"]
        self.assertEqual((original["space"], original["components"], original["lexemes"], original["raw_text"], original["alternatives"]),
                         ("sRGB_RGB8", {"r": 116, "g": 202, "b": 191}, {"r": "116", "g": "202", "b": "191"}, "RGB 116, 202, 191", []))
        self.assertIsNone(w._colour_query); self.assertEqual(Path(core.DB_PATH).read_bytes(), before[0])

    def test_decimal_comma_rgb_refusal_is_translated(self):
        i18n.set_language("en")
        w = self.window; dialog = self.open_window(); dialog.tabs.setCurrentIndex(1)
        dialog.paste_edit.setPlainText("RGB 116 202 191,5"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertIn("RGB “116 202 191,5” refused: three integers 0–255 without decimals are required.", dialog.paste_errors.text())
        self.assertNotIn("refusé", dialog.paste_errors.text())
        self.assertEqual(dialog.paste_candidates.count(), 0); self.assertFalse(dialog.btn_save.isEnabled())
        dialog._save_draft(); dialog._search_draft(); self.app.processEvents()
        self.assertFalse(self.registry_path.exists()); self.assertIsNone(w._colour_query)

    # ── R2-SEP-SPACE (re-QA 12): blanks around the same separator ──────────
    def test_same_separator_with_varying_spaces_is_saved_exactly_as_typed(self):
        w = self.window; dialog = self.open_window(); dialog.tabs.setCurrentIndex(1)
        before = self.snapshot()
        # The same separator with or without a blank is still a decimal remnant when a channel is fractional.
        dialog.paste_edit.setPlainText("RGB 116,202, 191,5"); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 0); self.assertIsNone(dialog._draft_measurement())
        self.assertIn("RGB « 116,202, 191,5 » refusé", dialog.paste_errors.text())
        dialog.btn_save.click(); dialog._save_draft(); dialog._search_draft(); self.app.processEvents()
        self.assertFalse(self.registry_path.exists()); self.assertIsNone(w._colour_query)
        # Paste → Interpret → Save: one comma kind, irregular blanks, three whole channels.
        text = "RGB 116,202, 191"
        dialog.paste_edit.setPlainText(text); dialog.btn_interpret.click(); self.app.processEvents()
        self.assertEqual(dialog.paste_candidates.count(), 1)
        self.assertFalse(dialog.paste_errors.isVisible())
        self.assertTrue(dialog.btn_save.isEnabled()); self.assertTrue(dialog.btn_search.isEnabled())
        dialog.btn_save.click(); self.app.processEvents()
        stored = list(json.loads(self.registry_path.read_text())["measurements"].values())
        self.assertEqual(len(stored), 1)
        original = stored[0]["original"]
        self.assertEqual((original["space"], original["components"], original["lexemes"], original["raw_text"], original["alternatives"]),
                         ("sRGB_RGB8", {"r": 116, "g": 202, "b": 191}, {"r": "116", "g": "202", "b": "191"}, text, []))
        self.assertIsNone(w._colour_query); self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
