"""SPOOLSCRIBE-UX-2026-001, phase D: reproductions of QA findings R1–R8 (05-CODEX-QA.md).

Real controls, dialogs and Qt events; offline fixtures, temporary data, inert workers.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from spoolscribe import core, colour_distance as cd, i18n
from scripts import db_io
from tests.support import small_db
from tests import test_gui as fixture

if fixture.HAS_QT:
    from PySide6.QtCore import Qt, QPoint, QItemSelectionModel
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QPushButton


def db_bytes():
    return Path(core.DB_PATH).read_bytes()


class MulticolourProjectionTests(unittest.TestCase):
    """R5: integration from a validated database, not a hand-made row."""

    def catalogue(self):
        db = small_db()
        base = dict(product="Audit PLA", color_name="Red", hex="FF0000")
        db["_skus"] = {
            "PLAIN": dict(base, sku="PLAIN", color_name="Plain red"),
            "MULTI": dict(base, sku="MULTI", color_name="Red Green", additional_color_hexes=["00FF00"]),
            "SOURCE": dict(base, sku="SOURCE", color_name="Red Blue", source_colors=["FF0000", "0000FF"]),
            "DUP": dict(base, sku="DUP", color_name="Red twice", additional_color_hexes=["FF0000"]),
            "G1": dict(base, sku="G1", color_name="Blue", hex="0000AA", weight=1000),
            "G2": dict(base, sku="G2", color_name="Blue", hex="0000AA", weight=750, additional_color_hexes=["00AA00"]),
        }
        db_io.validate_db(db)
        return db

    def test_every_supported_multicolour_representation_is_excluded(self):
        db = self.catalogue(); before = copy.deepcopy(db)
        rows = core.group_filaments(core.list_skus(db))
        group = next(r for r in rows if r.get("variant_count", 1) == 2)
        self.assertEqual({v["sku"] for v in group["variants"]}, {"G1", "G2"})
        result = cd.rank("FF0000", rows, index=cd.build_index(rows))
        ranked = {i["row"]["sku"] for i in result["items"]}
        self.assertEqual(ranked, {"PLAIN", "DUP"})  # a duplicated main colour is not a second colour
        self.assertEqual(result["excluded"], {"multicolour": 3})
        self.assertEqual(db, before)
        # The export still carries every colour: the search changed nothing.
        payload = core.build_openspool(dict(db["_skus"]["MULTI"], sku="MULTI"), db["_products"]["Audit PLA"])
        self.assertEqual(payload["additional_color_hexes"], ["00FF00"])

    def test_personal_copy_of_a_multicolour_reference_stays_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db.json"; db = self.catalogue(); db_io.save_db(db, path)
            sku = core.save_personal_filament(db, "MULTI", {"min_temp": 200}, "U1", path=str(path))
            raw = path.read_bytes()
            rows = core.group_filaments(core.list_skus(db))
            classes = {r["sku"]: cd.classify(r) for r in rows}
            self.assertEqual(classes[sku], "multicolour")
            self.assertEqual(path.read_bytes(), raw)


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class CorrectionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        self.addCleanup(lambda: self.window._close_draft())

    def edit(self, sku="PB05001", **changes):
        w = self.window; w.current_sku = sku; w._show_detail(sku); w._edit_physical()
        for key, value in changes.items():
            field = w.draft_fields[key]; field.setText(value); field.textEdited.emit(value)
        return w

    def select_row(self, sku, view="list"):
        w = self.window
        row = next(i for i, r in enumerate(w._rows) if r["sku"] == sku or any(v["sku"] == sku for v in r.get("variants", [])))
        (w.table.selectRow(row) if view == "list" else w.grid.setCurrentRow(row))
        return row

    # R1 ───────────────────────────────────────────────────────────────
    def sources_dialog(self, button_text):
        def run(dialog):
            button = next(b for b in dialog.findChildren(QPushButton) if b.text() == button_text)
            button.click(); return dialog.result()
        return patch.object(QDialog, "exec", run)

    def test_r1_every_refresh_route_asks_once_before_starting(self):
        w = self.window
        for decision, starts in (("keep", 0), ("save", 1), ("discard", 1)):
            with self.subTest(decision=decision):
                w._close_draft(); w.worker = None
                self.edit(min_temp="235"); raw = db_bytes()
                with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_network_consent", return_value=True), \
                     patch.object(w, "_ask_draft_decision", return_value=decision) as ask, self.sources_dialog("Actualiser maintenant"):
                    w._choose_sources()
                self.assertEqual(ask.call_count, 1); self.assertEqual(worker.call_count, starts)
                if decision == "keep":
                    self.assertEqual((w.current_sku, w.draft_fields["min_temp"].text()), ("PB05001", "235"))
                    self.assertTrue(w.draft_save.isEnabled()); self.assertEqual(db_bytes(), raw)
                elif decision == "save":
                    self.assertIsNone(w._draft); self.assertTrue(any(k.startswith("USER-") for k in core.load_db()["_skus"]))
                else:
                    self.assertIsNone(w._draft); self.assertEqual(db_bytes(), raw)
                w.worker = None; w._finish_update_ui()  # the inert worker never finishes by itself
        # Main button with consent: still a single question.
        w._close_draft(); self.edit(min_temp="236"); self.assertTrue(w.update_btn.isEnabled())
        with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_network_consent", return_value=True), \
             patch.object(core, "has_network_consent", return_value=True), patch.object(w, "_ask_draft_decision", return_value="keep") as ask:
            w.update_btn.click()
        self.assertEqual((ask.call_count, worker.call_count), (1, 0))

    def test_r1_failed_save_saving_sources_only_and_automatic_refresh_start_nothing(self):
        w = self.edit(min_temp="235"); raw = db_bytes()
        with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_network_consent", return_value=True), \
             patch.object(w, "_ask_draft_decision", return_value="save"), patch("spoolscribe.core.save_db", side_effect=OSError("disque plein")), \
             self.sources_dialog("Actualiser maintenant"):
            w._choose_sources()
        worker.assert_not_called(); self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertIn("disque plein", w.draft_error.text())
        with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_draft_decision") as ask, \
             self.sources_dialog("Enregistrer seulement"):
            w._choose_sources()
        ask.assert_not_called(); worker.assert_not_called()
        with patch("spoolscribe.app_gui.UpdateWorker") as worker, patch.object(w, "_ask_draft_decision") as ask, \
             patch.object(w, "isVisible", return_value=True), patch.object(core, "has_network_consent", return_value=True), \
             patch.object(core, "update_due", return_value=True):
            w._maybe_auto_update(); w._start_update()
        ask.assert_not_called(); worker.assert_not_called()
        self.assertEqual(db_bytes(), raw); self.assertIsNotNone(w._draft)

    # R2 ───────────────────────────────────────────────────────────────
    def dual_format_reader(self):
        w = self.window
        w.printer.setCurrentIndex(w.printer.findData("u1")); w.firmware.setCurrentIndex(w.firmware.findData("paxx12_openrfid"))
        self.assertEqual({w.nfc_format.itemData(i) for i in range(w.nfc_format.count())}, {"openspool", "opentag3d"})
        return w

    def shown_min(self):
        return float(self.window.comparison_cells["min_temp"][4].text().split("\n")[0].removeprefix("≠ "))

    def test_r2_comparison_follows_format_settings_dialog_orca_and_import(self):
        from spoolscribe import opentag3d
        w = self.dual_format_reader(); w.provenance_toggle.setChecked(True)
        w.current_sku = "PB05001"; w._show_detail("PB05001")
        w.format_buttons.buttons["openspool"].click()
        self.assertIn("OpenSpool", w.comparison_heads[4].text()); self.assertEqual(self.shown_min(), 240)
        core.save_opentag_settings("PB05001", dict(min_print_temp=245, max_print_temp=255, print_temp=250, bed_temp=60, chamber_temp=0, weight=1000))
        w.format_buttons.buttons["opentag3d"].click()
        decoded = opentag3d.decode(w._prepare_opentag().payload)
        self.assertIn("OpenTag3D", w.comparison_heads[4].text()); self.assertEqual(self.shown_min(), decoded["min_print_temp"])
        self.assertEqual(decoded["min_print_temp"], 245)
        # The real OpenTag3D dialog changes the explicit bounds.
        def fill(dialog):
            for key, value in (("min_print_temp", "250"), ("max_print_temp", "260")):
                dialog.findChild(QLineEdit, "opentag_" + key).setText(value)
            next(b for b in dialog.findChildren(QPushButton) if b.text() == "Enregistrer").click(); return dialog.result()
        with patch.object(QDialog, "exec", fill):
            w.btn_opentag_settings.click()
        self.assertEqual(opentag3d.decode(w._prepare_opentag().payload)["min_print_temp"], 250); self.assertEqual(self.shown_min(), 250)
        # Back to OpenSpool, then the Orca priority through the real settings dialog.
        w.format_buttons.buttons["openspool"].click()
        self.assertIn("OpenSpool", w.comparison_heads[4].text()); self.assertEqual(self.shown_min(), 240)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "Polymaker PETG @Snapmaker U1 - OrcaSlicer.json").write_text(json.dumps(
                {"nozzle_temperature_range_low": ["200"], "nozzle_temperature_range_high": ["230"], "filament_density": ["1.24"],
                 "filament_diameter": ["1.75"], "hot_plate_temp": ["60"]}))
            with patch.object(core, "ORCA_DIR", directory):
                def tick(dialog):
                    box = next(c for c in dialog.findChildren(__import__("PySide6.QtWidgets", fromlist=["QCheckBox"]).QCheckBox)
                               if c.text() == "Préférer les valeurs Orca à l’export")
                    box.setChecked(True); dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click(); return dialog.result()
                with patch.object(QDialog, "exec", tick):
                    w._open_settings()
                self.assertEqual((self.shown_min(), w._build_payload()["min_temp"]), (200, 200))
                Path(directory, "Polymaker PETG @Snapmaker U1 - OrcaSlicer.json").write_text("{invalid")
                w.format_buttons.buttons["opentag3d"].click(); w.format_buttons.buttons["openspool"].click()
                self.assertIn("Profil Orca inutilisable", w.comparison_note.text())
        # Imported settings that select OpenTag3D refresh the comparison too.
        target = Path(self.tmp.name) / "settings.json"; core.export_settings(target)
        document = json.loads(target.read_text()); document["settings"].update(nfc_format="opentag3d", orca_overrides=False)
        target.write_text(json.dumps(document))
        with patch("spoolscribe.ui_catalogue.QFileDialog.getOpenFileName", return_value=(str(target), "")):
            w._import_settings()
        self.assertEqual(w.nfc_format.currentData(), "opentag3d"); self.assertIn("OpenTag3D", w.comparison_heads[4].text())
        self.assertEqual(self.shown_min(), opentag3d.decode(w._prepare_opentag().payload)["min_print_temp"])

    def test_r2_draft_reminders_follow_the_format_without_touching_typed_values(self):
        w = self.dual_format_reader(); w.format_buttons.buttons["openspool"].click()
        core.save_opentag_settings("PB05001", dict(min_print_temp=None, max_print_temp=255, print_temp=250, bed_temp=60, chamber_temp=0, weight=1000))
        self.edit(min_temp="235", max_temp="250")
        self.assertIn("export 260", w.draft_hints["max_temp"].text())
        w.format_buttons.buttons["opentag3d"].click()
        self.assertIn("export 255", w.draft_hints["max_temp"].text())
        self.assertIn("export —", w.draft_hints["min_temp"].text())  # explicit None is not filled in
        self.assertEqual((w.draft_fields["min_temp"].text(), w.draft_fields["max_temp"].text()), ("235", "250"))
        self.assertIn("2 modification", w.draft_badge.text())

    # R3 ───────────────────────────────────────────────────────────────
    def test_r3_one_decision_per_deselection_intent_with_real_events(self):
        w = self.window; w.resize(1280, 800); w.show(); w.app.processEvents()
        w.search.setText("PB0500"); w._apply_filter()
        for view in ("list", "grid"):
            for gesture in ("reclick", "empty", "escape", "escape_in_field"):
                with self.subTest(view=view, gesture=gesture):
                    w._close_draft(); w._set_view_mode(view); w.app.processEvents()
                    row = self.select_row("PB05001", view); w.app.processEvents()
                    sku = w.current_sku; self.edit(sku, min_temp="235"); raw = db_bytes(); w.app.processEvents()
                    widget = w.table if view == "list" else w.grid
                    with patch.object(w, "_ask_draft_decision", return_value="keep") as ask:
                        if gesture == "reclick":
                            rect = w.table.visualRect(w.table.model().index(row, 2)) if view == "list" else w.grid.visualItemRect(w.grid.item(row))
                            QTest.mouseClick(widget.viewport(), Qt.LeftButton, pos=QPoint(rect.left() + 20, rect.center().y()))
                        elif gesture == "empty":
                            QTest.mouseClick(widget.viewport(), Qt.LeftButton, pos=QPoint(widget.viewport().width() - 5, widget.viewport().height() - 5))
                        elif gesture == "escape":
                            widget.setFocus(); QTest.keyClick(widget, Qt.Key_Escape)
                        else:
                            w.draft_fields["min_temp"].setFocus(); QTest.keyClick(w.draft_fields["min_temp"], Qt.Key_Escape)
                        w.app.processEvents()
                    self.assertEqual(ask.call_count, 1)
                    self.assertEqual(w.current_sku, sku); self.assertEqual(w.draft_fields["min_temp"].text(), "235")
                    selected = [i.row() for i in w.table.selectionModel().selectedRows()] if view == "list" else [w.grid.row(i) for i in w.grid.selectedItems()]
                    self.assertEqual(selected, [row]); self.assertEqual(db_bytes(), raw)
        # Discard: one question, deselection happens, nothing written.
        w._close_draft(); w._set_view_mode("list"); row = self.select_row("PB05001"); self.edit(w.current_sku, min_temp="235"); raw = db_bytes()
        rect = w.table.visualRect(w.table.model().index(row, 2))
        with patch.object(w, "_ask_draft_decision", return_value="discard") as ask:
            QTest.mouseClick(w.table.viewport(), Qt.LeftButton, pos=QPoint(rect.left() + 20, rect.center().y()))
        self.assertEqual(ask.call_count, 1); self.assertIsNone(w.current_sku); self.assertEqual(db_bytes(), raw)

    # R4 ───────────────────────────────────────────────────────────────
    def suspect(self, alpha=None):
        w = self.window; entry = w.db["_skus"]["CA02011"]; entry.update(color_name="White", hex="000000")
        if alpha: entry["alpha"] = alpha
        core.save_db(w.db); w._reload_table(); w.current_sku = "CA02011"; w._show_detail("CA02011")
        return w

    def test_r4_explicit_confirmation_of_an_unchanged_suspect_hex(self):
        w = self.suspect(alpha="80"); source = copy.deepcopy(core.load_db()["_skus"]["CA02011"])
        self.assertEqual(w._primary_kind, "confirm_colour"); w.btn_generate.click()
        self.assertFalse(w.draft_confirm_hex.isHidden()); self.assertFalse(w.draft_confirm_hex.isChecked())
        self.assertFalse(w.draft_save.isEnabled())  # opening alone confirms nothing
        w.draft_confirm_hex.click(); self.assertTrue(w.draft_save.isEnabled()); self.assertIn("1 modification", w.draft_badge.text())
        w.draft_suffix.setText("Blanc"); w.draft_save.click()
        copy_sku = w.current_sku; entry = core.load_db()["_skus"][copy_sku]
        self.assertTrue(copy_sku.startswith("USER-")); self.assertEqual((entry["hex"], entry["alpha"]), ("000000", "80"))
        self.assertEqual(entry["_field_sources"]["hex"]["source"], db_io.USER_SOURCE)
        self.assertEqual(core.get_sku_view(core.load_db(), copy_sku).product_data["_field_sources"]["min_temp"]["source"], "Copie personnelle")
        self.assertEqual(core.load_db()["_skus"]["CA02011"], source)
        self.assertEqual(w._primary_kind, "export")  # the copy is exportable, the source still is not
        w.current_sku = "CA02011"; w._show_detail("CA02011"); self.assertEqual(w._primary_kind, "confirm_colour")

    def test_r4_cancel_invalid_entry_failed_write_and_plausible_colour(self):
        w = self.suspect(); raw = db_bytes(); w.btn_generate.click()
        w.draft_confirm_hex.click(); w.draft_cancel.click(); self.assertEqual(db_bytes(), raw); self.assertIsNone(w._draft)
        w.btn_generate.click(); self.assertFalse(w.draft_confirm_hex.isChecked())
        w.draft_confirm_hex.click(); field = w.draft_fields["hex"]; field.setText("zz"); field.textEdited.emit("zz")
        self.assertFalse(w._save_draft()); self.assertIn("HEX", w.draft_error.text()); self.assertEqual(db_bytes(), raw)
        field.setText("000000"); field.textEdited.emit("000000")
        with patch("spoolscribe.core.save_db", side_effect=OSError("disque plein")):
            self.assertFalse(w._save_draft())
        self.assertTrue(w.draft_confirm_hex.isChecked()); self.assertEqual(db_bytes(), raw)
        w._close_draft(); w.current_sku = "PB05001"; w._show_detail("PB05001"); w._edit_physical()
        self.assertTrue(w.draft_confirm_hex.isHidden())  # only offered for a suspect colour

    # R5 (GUI path) ────────────────────────────────────────────────────
    def test_r5_search_excludes_multicolour_and_rebuilds_after_reload(self):
        w = self.window; w.db["_skus"]["CA02011"]["additional_color_hexes"] = ["123456"]; core.save_db(w.db); w._reload_table()
        raw = db_bytes(); w.brand_filter.setCurrentIndex(0)
        w._open_colour_search(); w._start_colour_search(w.db["_skus"]["CA02011"]["hex"])
        self.assertNotIn("CA02011", w._colour_deltas); self.assertGreater(w._colour_report["excluded"].get("multicolour", 0), 0)
        del w.db["_skus"]["CA02011"]["additional_color_hexes"]; w._reload_table()
        self.assertEqual(w._colour_deltas["CA02011"]["delta"], 0.0); self.assertEqual(db_bytes(), raw)

    # R6 ───────────────────────────────────────────────────────────────
    def test_r6_free_hex_entry_without_selection_or_with_unknown_colour(self):
        w = self.window; w.show(); w.app.processEvents(); raw = db_bytes()
        for start in ("none", "FB04001"):
            with self.subTest(start=start):
                w._stop_colour_search(); w._clear_filament()
                if start != "none":
                    w.current_sku = start; w._show_detail(start); self.assertFalse(w.btn_similar.isEnabled())
                button = w._sections['colours']['toggle']
                w._set_section_expanded('colours', False)
                self.assertTrue(button.isVisible() and button.isEnabled()); self.assertTrue(button.accessibleName())
                button.setFocus(); QTest.keyClick(button, Qt.Key_Space); w.app.processEvents()
                self.assertTrue(w.colour_panel.isVisible()); self.assertEqual(w.colour_hex.text(), "")
                QTest.keyClicks(w.colour_hex, "#zz"); QTest.keyClick(w.colour_hex, Qt.Key_Return)
                self.assertIn("Code couleur invalide", w.colour_info.text()); self.assertIsNone(w._colour_query)
                w.colour_hex.clear(); QTest.keyClicks(w.colour_hex, "#3366cc"); QTest.keyClick(w.colour_hex, Qt.Key_Return)
                self.assertEqual(w._colour_query["hex"], "3366CC"); self.assertTrue(w._filtered_rows)
                self.assertIsNone(w.db["_skus"]["FB04001"]["hex"])
        w.colour_exit_btn.click(); self.assertIsNone(w._colour_query)
        w._sections['colours']['toggle'].click(); w._start_colour_search("FF0000"); w.reset_filters.click(); self.assertIsNone(w._colour_query)
        self.assertEqual(db_bytes(), raw)
        for language in ("en", "es", "zh_CN"):
            i18n.set_language(language)
            self.assertNotEqual(i18n.tr("TEINTES"), "TEINTES"); self.assertNotEqual(i18n.tr("Choisir une couleur"), "Choisir une couleur")
        i18n.set_language("fr")

    # R7 ───────────────────────────────────────────────────────────────
    def test_r7_favourite_click_keeps_distance_metadata_order_and_selection(self):
        w = self.window; w.resize(1280, 800); w.show(); w._set_view_mode("grid")
        w.current_sku = "PB05001"; w._show_detail("PB05001"); w._open_colour_search(); w.app.processEvents()
        self.edit(w.current_sku, min_temp="235")
        delegate = w.grid.itemDelegate(); order = [r["sku"] for r in w._rows]
        before = {sku: row["_distance"] for sku, row in delegate.rows.items()}
        self.assertTrue(all(before.values()))
        other = w._rows[1]["sku"]; selected = [w.grid.row(i) for i in w.grid.selectedItems()]
        rect = w.grid.visualItemRect(w.grid.item(1))
        QTest.mouseClick(w.grid.viewport(), Qt.LeftButton, pos=QPoint(rect.right() - 15, rect.top() + 15))  # star
        self.assertTrue(delegate.rows[other]["_favorite"])
        w.grid.favoriteRequested.emit(other); self.assertFalse(delegate.rows[other]["_favorite"])
        self.assertEqual({sku: row["_distance"] for sku, row in delegate.rows.items()}, before)
        self.assertEqual([r["sku"] for r in w._rows], order); self.assertEqual([w.grid.row(i) for i in w.grid.selectedItems()], selected)
        self.assertEqual(w.draft_fields["min_temp"].text(), "235")
        w.grid.favoriteRequested.emit(other); w.favorites_only.setChecked(True)
        self.assertTrue(all(delegate.rows[r["sku"]]["_distance"] for r in w._rows))
        w._set_view_mode("list"); self.assertIn("ΔE", w.table.item(0, 3).text())

    # R8 ───────────────────────────────────────────────────────────────
    def test_r8_opentag_capacity_routes_to_tag_settings_at_the_exact_limit(self):
        from tests.test_opentag3d import OpenTagGuiTests
        w = OpenTagGuiTests.select_reader(self); w.current_sku = "PB05001"; w._show_detail("PB05001")
        self.assertEqual(w._primary_kind, "opentag_settings")  # missing explicit targets stay a tag-preparation issue
        p = core.get_sku_view(w.db, "PB05001").product_data
        core.save_opentag_settings("PB05001", dict(print_temp=p["min_temp"], bed_temp=p["bed_min_temp"], chamber_temp=0, weight=1000))
        outputs = [w.opentag_output.itemData(i) for i in range(w.opentag_output.count())]
        for output in outputs:
            w.opentag_output.setCurrentIndex(w.opentag_output.findData(output))
            for tag, free in (("NTAG215", 245), ("NTAG216", 621)):
                with self.subTest(output=output, tag=tag):
                    w.tag_type.setCurrentIndex(w.tag_type.findData(tag))
                    w.nfc_reserve.setValue(free); self.assertEqual(w._primary_kind, "export"); self.assertEqual(w._export_context["budget"]["remaining"], 0)
                    w.nfc_reserve.setValue(free + 1)
                    self.assertEqual((w._primary_kind, w.btn_generate.text()), ("hardware", "Ajuster l’étiquette…"))
                    self.assertIn("capacité NFC insuffisante", w._export_context["diagnostic"])
        with patch.object(w, "_open_hardware") as hardware:
            w.btn_generate.click()
        hardware.assert_called_once(); self.assertFalse(Path(core.OUTPUT_DIR).exists())
        w.nfc_reserve.setValue(0); w.db["_products"]["Polymaker PETG"]["density"] = 3000; w._show_detail("PB05001")
        self.assertEqual(w._primary_kind, "correct_physical")


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class KeyboardNavigationTests(unittest.TestCase):
    """R3 after re-QA E: one decision per keyboard move leaving a modified draft (11-CLAUDE-CORRECTIF-R3.md)."""

    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        self.addCleanup(lambda: self.window._close_draft())
        w = self.window; w.resize(1280, 800); w.show(); w.search.setText("PB0500"); w._apply_filter(); w.app.processEvents()
        self.assertGreaterEqual(len(w._rows), 3)

    def start(self, view, row=1, edit=True):
        w = self.window; w._close_draft(); w._set_view_mode(view)
        (w.table.selectRow(row) if view == "list" else w.grid.setCurrentRow(row)); w.app.processEvents()
        widget = w.table if view == "list" else w.grid
        sku = w.current_sku
        if edit:
            w._edit_physical(); field = w.draft_fields["min_temp"]; field.setText("235"); field.textEdited.emit("235")
        widget.setFocus(); w.app.processEvents()
        return widget, sku

    @staticmethod
    def target(widget, key):
        """Row Qt would move to, computed by the test itself (no application helper)."""
        from PySide6.QtWidgets import QAbstractItemView
        action = {Qt.Key_Down: QAbstractItemView.MoveDown, Qt.Key_Up: QAbstractItemView.MoveUp}[key]
        row = widget.moveCursor(action, Qt.NoModifier).row()
        item = widget.item(row, 1) if hasattr(widget, "selectRow") else widget.item(row)
        return row, item.data(Qt.UserRole)

    def selected(self, view):
        w = self.window
        return [i.row() for i in w.table.selectionModel().selectedRows()] if view == "list" else [w.grid.row(i) for i in w.grid.selectedItems()]

    def test_arrow_keys_ask_once_and_respect_each_decision(self):
        w = self.window
        for view in ("list", "grid"):
            # Up starts where Down lands (in the grid, Down moves one card row).
            widget, _ = self.start(view, edit=False)
            below, _ = self.target(widget, Qt.Key_Down)
            for key, start in ((Qt.Key_Down, 1), (Qt.Key_Up, below)):
                for decision in ("keep", "discard", "save", "save_failure"):
                    with self.subTest(view=view, key=key, decision=decision):
                        widget, sku = self.start(view, row=start)
                        _, target_sku = self.target(widget, key)
                        self.assertNotEqual(w._group_for_sku(target_sku)["sku"], w._group_for_sku(sku)["sku"])
                        raw = db_bytes(); before_rows = self.selected(view)
                        answer = "save" if decision == "save_failure" else decision
                        failing = patch("spoolscribe.core.save_db", side_effect=OSError("disque plein")) if decision == "save_failure" else patch("builtins.id", id)
                        with patch.object(w, "_ask_draft_decision", return_value=answer) as ask, failing:
                            QTest.keyClick(widget, key); w.app.processEvents()
                        self.assertEqual(ask.call_count, 1)
                        if decision in ("keep", "save_failure"):
                            self.assertEqual((w.current_sku, self.selected(view)), (sku, before_rows))
                            self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertIsNotNone(w._draft)
                            self.assertEqual(db_bytes(), raw)
                        elif decision == "discard":
                            self.assertIsNone(w._draft); self.assertEqual(db_bytes(), raw)
                            self.assertIs(w._group_for_sku(w.current_sku), w._group_for_sku(target_sku))
                        else:
                            self.assertIsNone(w._draft)
                            saved = core.load_db()
                            personal = [k for k, e in saved["_skus"].items() if e.get("_personal_origin") == sku and e.get("_personal_suffix") == "Personnel"]
                            self.assertEqual(len(personal), 1)
                            self.assertEqual(core.get_sku_view(saved, personal[0]).product_data["min_temp"], 235)
                            self.assertIs(w._group_for_sku(w.current_sku), w._group_for_sku(target_sku))
                        w._close_draft()

    def test_navigation_without_a_modified_draft_is_unchanged(self):
        w = self.window
        for view in ("list", "grid"):
            for edit in (False, True):
                widget, sku = self.start(view, edit=False)
                if edit: w._edit_physical()  # opened but unchanged: never asks
                with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("unexpected prompt")):
                    QTest.keyClick(widget, Qt.Key_Down); w.app.processEvents()
                self.assertNotEqual(w.current_sku, sku); self.assertIsNone(w._draft)
                # Left/Right inside the table stay on the same row: no prompt either.
                if view == "list":
                    self.start(view)
                    with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("unexpected prompt")):
                        QTest.keyClick(w.table, Qt.Key_Right); w.app.processEvents()
                    self.assertIsNotNone(w._draft)

    def test_keyboard_search_letter_asks_at_most_once(self):
        w = self.window
        for view in ("list", "grid"):
            widget, sku = self.start(view, row=0)
            raw = db_bytes()
            with patch.object(w, "_ask_draft_decision", return_value="keep") as ask:
                QTest.keyClicks(widget, "pol"); w.app.processEvents()
            self.assertLessEqual(ask.call_count, 1)
            self.assertEqual(w.current_sku, sku); self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertEqual(db_bytes(), raw)


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class KeyboardSelectionCommandTests(unittest.TestCase):
    """R3-A / R3-B after re-QA 13 (15-CLAUDE-CORRECTIFS-R3-AB.md): modifier deselection and targets on another page.

    R3-C after re-QA 17 (19-CLAUDE-CORRECTIF-R3-C.md): keyboard context after a saved deselection.
    """

    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        self.addCleanup(lambda: self.window._close_draft())

    def place(self, view, search, page, row):
        """Normal configuration (hidden columns, 250 rows per page), real widgets.

        The search is applied explicitly, so the deferred refresh queued by typing is a duplicate:
        stopped here (test mount only) so that it cannot repopulate the views in the middle of a test.
        """
        w = self.window; w._close_draft(); w.resize(1280, 800); w.show()
        w.search.setText(search); w._apply_filter(); w._search_timer.stop(); w._page = page; w._show_page(); w._set_view_mode(view); w.app.processEvents()
        widget = w.table if view == "list" else w.grid
        if view == "list":
            widget.setCurrentCell(row, 2); widget.selectRow(row)
        else:
            widget.setCurrentRow(row)
        widget.setFocus(); w.app.processEvents()
        return widget

    def modified(self, key="min_temp", value="235"):
        w = self.window; w._edit_physical(); field = w.draft_fields[key]; field.setText(value); field.textEdited.emit(value)
        (w.table if w.view_mode == "list" else w.grid).setFocus(); w.app.processEvents()

    def test_r3a_ctrl_right_on_the_selected_row_asks_once(self):
        w = self.window
        self.assertTrue(w.table.isColumnHidden(1))  # normal configuration: hidden reference column
        # Oracle without draft: the modifier turns this move into a deselection.
        self.place("list", "PETG", 0, 8); QTest.keyClick(w.table, Qt.Key_Right, Qt.ControlModifier); w.app.processEvents()
        self.assertIsNone(w.current_sku)
        for decision in ("keep", "save_failure", "save", "discard"):
            with self.subTest(decision=decision):
                self.place("list", "PETG", 0, 8); sku = w.current_sku; self.modified()
                raw = db_bytes(); answer = "save" if decision == "save_failure" else decision
                failing = patch("spoolscribe.core.save_db", side_effect=OSError("disque plein")) if decision == "save_failure" else patch("builtins.id", id)
                with patch.object(w, "_ask_draft_decision", return_value=answer) as ask, failing:
                    QTest.keyClick(w.table, Qt.Key_Right, Qt.ControlModifier); w.app.processEvents()
                self.assertEqual(ask.call_count, 1)
                if decision in ("keep", "save_failure"):
                    self.assertEqual((w.current_sku, [i.row() for i in w.table.selectionModel().selectedRows()]), (sku, [8]))
                    self.assertEqual(w.draft_fields["min_temp"].text(), "235"); self.assertTrue(w._draft_dirty()); self.assertEqual(db_bytes(), raw)
                    if decision == "save_failure": self.assertIn("disque plein", w.draft_error.text())
                else:
                    self.assertIsNone(w.current_sku); self.assertIsNone(w._draft)
                    copies = [k for k, e in core.load_db()["_skus"].items() if e.get("_personal_origin") == sku]
                    if decision == "save":
                        self.assertEqual(core.get_sku_view(core.load_db(), copies[0]).product_data["min_temp"], 235)
                    else:
                        self.assertEqual(db_bytes(), raw)

    def test_r3a_modifier_without_movement_never_asks(self):
        w = self.window
        # Ctrl+Left on the first visible column: Qt does not move, so nothing to decide.
        for key in (Qt.Key_Left,):
            with self.subTest(key=key):
                self.place("list", "PETG", 0, 8); w.table.setCurrentCell(8, 0); w.table.selectRow(8); w.app.processEvents()
                sku = w.current_sku; self.modified(); raw = db_bytes()
                with patch.object(w, "_ask_draft_decision", side_effect=AssertionError("unexpected prompt")):
                    QTest.keyClick(w.table, key, Qt.ControlModifier); w.app.processEvents()
                self.assertEqual((w.current_sku, w.draft_fields["min_temp"].text()), (sku, "235")); self.assertEqual(db_bytes(), raw)

    def test_r3b_saved_draft_reaches_a_target_moved_to_another_page(self):
        w = self.window
        # Oracle: the real End move without any draft.
        self.place("grid", "", 1, 1); source = w.current_sku
        QTest.keyClick(w.grid, Qt.Key_End); w.app.processEvents(); target = w.current_sku
        self.assertNotEqual(target, source)
        self.place("grid", "", 1, 1); self.assertEqual(w.current_sku, source)
        original = copy.deepcopy(core.load_db()["_skus"][source]); self.modified("density", "1.27")
        with patch.object(w, "_ask_draft_decision", return_value="save") as ask:
            QTest.keyClick(w.grid, Qt.Key_End); w.app.processEvents()
        self.assertEqual(ask.call_count, 1); self.assertIsNone(w._draft)
        self.assertIs(w._group_for_sku(w.current_sku), w._group_for_sku(target))
        index = next(i for i, r in enumerate(w._filtered_rows) if r["sku"] == target or any(v["sku"] == target for v in r.get("variants", [])))
        self.assertEqual(w._page, index // w._page_size)
        self.assertEqual([w.grid.row(i) for i in w.grid.selectedItems()], [index % w._page_size])
        saved = core.load_db(); copies = [k for k, e in saved["_skus"].items() if e.get("_personal_origin") == source]
        self.assertEqual(len(copies), 1); self.assertEqual(core.get_sku_view(saved, copies[0]).product_data["density"], 1.27)
        self.assertEqual(saved["_skus"][source], original)

    def test_r3b_target_outside_the_results_keeps_the_saved_copy(self):
        w = self.window; self.place("list", "PETG", 0, 8); self.modified(); w._save_draft(); copy_sku = w.current_sku
        page, rows = w._page, [i.row() for i in w.table.selectionModel().selectedRows()]
        self.assertFalse(w._select_result("NO-SUCH-REFERENCE"))
        self.assertEqual((w.current_sku, w._page, [i.row() for i in w.table.selectionModel().selectedRows()]), (copy_sku, page, rows))

    def cursor(self, row, column):
        """Selected row with the current index on a visible column, as after clicks or moves."""
        table = self.window.table
        table.selectRow(row); table.selectionModel().setCurrentIndex(table.model().index(row, column), QItemSelectionModel.NoUpdate)
        table.setFocus(); self.window.app.processEvents()

    def context(self):
        """Keyboard context by identity: fiche, selection, cursor reference and column, page."""
        w = self.window; index = w.table.currentIndex()
        return dict(fiche=w.current_sku, selected=[i.row() for i in w.table.selectionModel().selectedRows()],
                    cursor=w._view_row_sku(w.table, index.row()), column=index.column(), page=w._page)

    def test_r3c_saved_deselection_keeps_the_cursor_context(self):
        w = self.window; ctrl = Qt.ControlModifier
        with self.subTest(view="grid"):
            # The grid never deselects with a modifier: no R3-C route there.
            for key in (Qt.Key_Right, Qt.Key_Left, Qt.Key_Home, Qt.Key_End):
                self.place("grid", "PETG", 0, 8); QTest.keyClick(w.grid, key, ctrl); w.app.processEvents()
                self.assertIsNotNone(w.current_sku)
        # Table moves that deselect without a draft, from the first, a middle and the last visible column.
        cases = (("Ctrl+Right", 8, 0, Qt.Key_Right, ctrl), ("Ctrl+Left", 8, 3, Qt.Key_Left, ctrl),
                 ("Ctrl+Shift+Right", 8, 3, Qt.Key_Right, ctrl | Qt.ShiftModifier), ("Ctrl+Left last column", 8, 8, Qt.Key_Left, ctrl),
                 ("Ctrl+Home", 0, 3, Qt.Key_Home, ctrl), ("Ctrl+End", -1, 0, Qt.Key_End, ctrl))
        for name, row, column, key, modifiers in cases:
            with self.subTest(key=name):
                self.place("list", "PETG", 0, 0); row %= w.table.rowCount(); self.cursor(row, column); source = w.current_sku
                QTest.keyClick(w.table, key, modifiers); w.app.processEvents(); intent = self.context()
                self.assertEqual((intent["fiche"], intent["selected"], intent["cursor"]), (None, [], source))
                self.place("list", "PETG", 0, 0); self.cursor(row, column); self.assertEqual(w.current_sku, source)
                original = copy.deepcopy(core.load_db()["_skus"][source]); self.modified()
                with patch.object(w, "_ask_draft_decision", return_value="save") as ask:
                    QTest.keyClick(w.table, key, modifiers); w.app.processEvents()
                self.assertEqual(ask.call_count, 1); self.assertIsNone(w._draft)
                self.assertEqual(self.context(), intent)
                saved = core.load_db(); copies = [k for k, e in saved["_skus"].items() if e.get("_personal_origin") == source]
                self.assertEqual(len(copies), 1); self.assertEqual(core.get_sku_view(saved, copies[0]).product_data["min_temp"], 235)
                self.assertEqual(saved["_skus"][source], original)
                raw = db_bytes(); QTest.keyClick(w.table, Qt.Key_Down); w.app.processEvents(); reached = w.current_sku
                # Ctrl+End aims at the last row, which the saved copy may now be: the oracle on the
                # saved bytes would then be another move, so this case is checked against the intent only.
                if key != Qt.Key_End:
                    # Oracle on the same saved bytes, copy included: the same move without a draft.
                    self.cursor(next(i for i, r in enumerate(w._rows) if r["sku"] == source), column)
                    QTest.keyClick(w.table, key, modifiers); w.app.processEvents(); self.assertEqual(self.context(), intent)
                    QTest.keyClick(w.table, Qt.Key_Down); w.app.processEvents()
                    self.assertEqual(w.current_sku, reached); self.assertEqual(db_bytes(), raw)

    def test_r3c_cursor_follows_the_source_to_its_page_or_stays_safe(self):
        """Projection changed after the save, simulated in the in-memory results only."""
        w = self.window
        self.place("list", "", 0, 8); QTest.keyClick(w.table, Qt.Key_Right, Qt.ControlModifier); w.app.processEvents()
        column = w.table.currentIndex().column()
        for moved in (True, False):
            with self.subTest(moved=moved):
                self.place("list", "", 0, 8); source = w.current_sku; self.modified(); save = w._save_draft
                self.assertGreater(len(w._filtered_rows), w._page_size + 1)

                def reordered():
                    ok = save()
                    group = next(r for r in w._filtered_rows if r["sku"] == source); w._filtered_rows.remove(group)
                    if moved:
                        w._filtered_rows.insert(w._page_size, group)
                    return ok
                with patch.object(w, "_save_draft", side_effect=reordered), patch.object(w, "_ask_draft_decision", return_value="save") as ask:
                    QTest.keyClick(w.table, Qt.Key_Right, Qt.ControlModifier); w.app.processEvents()
                state = self.context(); self.assertEqual(ask.call_count, 1)
                self.assertEqual((state["fiche"], state["selected"], w.search.text()), (None, [], ""))
                self.assertTrue(any(e.get("_personal_origin") == source for e in core.load_db()["_skus"].values()))
                if moved:
                    self.assertEqual((state["cursor"], state["column"], state["page"]), (source, column, 1))
                else:
                    self.assertNotEqual(state["cursor"], source)  # nothing else is selected; the cursor stays put
