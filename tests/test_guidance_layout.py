"""Readable colour filters and printer/tag guidance, isolated offline fixtures."""
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_gui as fixture
from spoolscribe import core


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class GuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        self.addCleanup(lambda: self.window._close_draft())

    def test_colours_are_a_sidebar_filter_below_materials_and_survive_folding(self):
        w = self.window; w.show(); w.app.processEvents()
        self.assertEqual(list(w._sections), ['brands', 'materials', 'colours', 'states'])
        self.assertTrue(w.sidebar.isAncestorOf(w.colour_panel))
        self.assertFalse(w._sections['colours']['toggle'].isChecked())
        w._show_detail('PB05001'); w.btn_similar.click(); w.app.processEvents()
        self.assertTrue(w._sections['colours']['toggle'].isChecked())
        query = w._colour_query['hex']; rows = [r['sku'] for r in w._filtered_rows]
        w._set_section_expanded('colours', False)
        self.assertEqual(w._colour_query['hex'], query)
        self.assertEqual([r['sku'] for r in w._filtered_rows], rows)
        self.assertIn('#' + query, w._sections['colours']['toggle'].text())

    def test_colour_picker_and_reset_never_write_catalogue_or_remove_favourites(self):
        from PySide6.QtGui import QColor
        w = self.window; raw = Path(core.DB_PATH).read_bytes()
        cfg = core.load_config(); cfg.update(favorite_brands=['Polymaker'], favorite_filaments=['PB05001']); core.save_config(cfg)
        with patch('spoolscribe.ui_detail.QColorDialog.getColor', return_value=QColor('red')):
            w.colour_swatch.click()
        self.assertEqual(w._colour_query['hex'], 'FF0000')
        with patch('spoolscribe.ui_detail.QColorDialog.getColor', return_value=QColor()):
            w.colour_swatch.click()
        self.assertEqual(w._colour_query['hex'], 'FF0000')
        w._reset_filters()
        self.assertIsNone(w._colour_query); self.assertEqual(w.colour_hex.text(), '')
        self.assertTrue(w._sections['colours']['toggle'].isChecked())
        self.assertEqual(core.load_config()['favorite_brands'], ['Polymaker'])
        self.assertEqual(core.load_config()['favorite_filaments'], ['PB05001'])
        self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)

    def test_filter_categories_share_a_card_and_active_criteria_are_not_a_paragraph(self):
        from PySide6.QtWidgets import QFrame, QToolButton
        w = self.window; w._choose_brand('Polymaker'); w._choose_family('PETG')
        for section in w._sections.values():
            self.assertIsInstance(section['toggle'].parentWidget(), QFrame)
            self.assertEqual(section['toggle'].parentWidget().objectName(), 'filterSection')
            self.assertIs(section['body'].parentWidget(), section['toggle'].parentWidget())
        self.assertIsInstance(w.filter_summary, QToolButton)
        self.assertIn('2', w.filter_summary.text())
        self.assertIn('Fabricant : Polymaker', w.filter_summary.toolTip())
        self.assertIn('Matière : PETG', w.filter_summary.toolTip())

    def test_remove_is_disabled_when_empty_and_really_clears_only_colour(self):
        w = self.window; w.show(); w._set_section_expanded('colours', True)
        self.assertFalse(w.colour_exit_btn.isEnabled())
        self.assertNotIn('22F4D3', w.colour_hex.placeholderText())
        w._choose_family('PETG'); base = [r['sku'] for r in w._filtered_rows]
        w.colour_hex.setText('#22F4D3'); self.assertTrue(w.colour_exit_btn.isEnabled())
        w.colour_exit_btn.click(); self.assertEqual(w.colour_hex.text(), '')
        w._start_colour_search('070908'); self.assertTrue(w.colour_exit_btn.isEnabled())
        w._open_colour_explanation(); w.colour_exit_btn.click(); w.app.processEvents()
        self.assertIsNone(w._colour_query); self.assertFalse(w.colour_guidance.isVisible())
        self.assertEqual(w.colour_hex.text(), ''); self.assertFalse(w.colour_exit_btn.isEnabled())
        self.assertEqual(w.material_filter.currentData(), 'PETG')
        self.assertEqual([r['sku'] for r in w._filtered_rows], base)
        self.assertNotIn('Teintes proches', w.filter_summary.toolTip())

    def test_opentag_settings_live_in_details_not_twice_in_the_filament_card(self):
        from PySide6.QtWidgets import QPushButton
        from tests.test_opentag3d import OpenTagGuiTests
        w = OpenTagGuiTests.select_reader(self); w.show(); w._show_detail('PB05001'); w.app.processEvents()
        prepare = [b for b in w.findChildren(QPushButton) if b.isVisible() and 'Préparer l’étiquette' in b.text()]
        self.assertEqual(prepare, [w.btn_generate])
        self.assertFalse(w.btn_opentag_settings.isVisible())
        w.export_details_button.click(); w.app.processEvents()
        self.assertTrue(w.export_details.isAncestorOf(w.btn_opentag_settings))
        self.assertTrue(w.btn_opentag_settings.isVisible())
        with patch.object(w, '_complete_opentag_settings') as edit:
            w.btn_generate.click()
        edit.assert_called_once()

    def test_every_printer_has_a_visible_visual_without_claiming_a_photo(self):
        from spoolscribe import printer_profiles, i18n
        from spoolscribe.printer_presentations import presentation
        w = self.window; w.show(); w._show_detail('PB05001')
        for key in printer_profiles.PROFILES:
            w.printer.setCurrentIndex(w.printer.findData(key)); w.app.processEvents()
            self.assertFalse(w.hardware_photo.isHidden(), key)
            self.assertFalse(w.hardware_photo.pixmap().isNull(), key)
            self.assertFalse(w.printer_card.photo.isHidden(), key)
            self.assertFalse(w.printer_card.photo.pixmap().isNull(), key)
        w.printer.setCurrentIndex(w.printer.findData('flashforge_creator5'))
        self.assertIn('Flashforge Creator 5', w.hardware_photo.toolTip())
        w.printer.setCurrentIndex(w.printer.findData('no_reader'))
        self.assertIn('générique', w.hardware_photo.toolTip())
        # "Imprimante sans lecteur" is still a printer; translated names never
        # select a different type of artwork or change firmware compatibility.
        for language in ('en', 'fr', 'es', 'zh_CN'):
            i18n.set_language(language)
            self.assertEqual(presentation(printer_profiles.PROFILES['no_reader'])['visual_kind'], 'enclosed')
            self.assertEqual(presentation(printer_profiles.PROFILES['opentag3d'])['visual_kind'], 'reader')
        i18n.set_language('fr')

    def test_compact_colour_controls_are_fully_inside_their_section(self):
        from PySide6.QtCore import QPoint, QRect
        w = self.window; w.resize(1100, 760); w.show(); w._start_colour_search('22F4D3')
        for _ in range(4):w.app.processEvents()
        body = w._sections['colours']['body']
        for widget in (w.colour_swatch, w.colour_hex, w.colour_rank_btn, w.colour_exit_btn, w.colour_details_button):
            bounds = QRect(widget.mapTo(body, QPoint()), widget.size())
            self.assertTrue(body.rect().contains(bounds), (widget.objectName(), bounds, body.rect()))
        for button in (w.colour_rank_btn, w.colour_exit_btn, w.colour_details_button):
            self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text())+18)
        self.assertGreaterEqual(w.colour_rank_btn.mapTo(body, QPoint()).y(),
                                w.colour_hex.mapTo(body, QPoint()).y() + w.colour_hex.height())

    def test_help_without_a_colour_teaches_the_method_without_fake_results(self):
        w = self.window; raw = Path(core.DB_PATH).read_bytes(); w._open_colour_explanation()
        self.assertEqual(w.colour_guidance.tabs.currentIndex(), 1)
        self.assertFalse(w.colour_guidance.tabs.isTabEnabled(0))
        w._start_colour_search('22F4D3')
        self.assertTrue(w.colour_guidance.tabs.isTabEnabled(0))
        self.assertEqual(int(w.colour_guidance.comparable.value.text()), len(w._filtered_rows))
        self.assertEqual(Path(core.DB_PATH).read_bytes(), raw)

    def test_colour_help_shows_counts_as_tiles_and_updates_after_refiltering(self):
        w = self.window; w._start_colour_search('74CAC5'); w._open_colour_explanation()
        dialog = w.colour_guidance
        self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.assertEqual(int(dialog.excluded.value.text()), sum(int(t.value.text()) for t in dialog.reasons.values()))
        w._choose_family('PETG')
        self.assertEqual(int(dialog.comparable.value.text()), len(w._filtered_rows))
        previous = dialog.target.text(); w._start_colour_search('not-a-colour')
        self.assertEqual(dialog.target.text(), previous)  # failed input never relabels the actual query
        w._stop_colour_search(); self.assertFalse(dialog.isVisible())

    def test_missing_opentag_temperature_is_explained_before_technical_diagnostic(self):
        from PySide6.QtWidgets import QLabel
        from tests.test_opentag3d import OpenTagGuiTests
        w = OpenTagGuiTests.select_reader(self); w._show_detail('PB05001'); w._open_export_explanation()
        self.assertEqual(w._primary_kind, 'opentag_settings')
        self.assertIn('température de buse', w.nfc_capacity.text())
        self.assertNotIn('print_temp', w.nfc_capacity.text())
        overview = ' '.join(label.text() for label in w.export_details.tabs.widget(0).findChildren(QLabel))
        self.assertNotIn('print_temp', overview); self.assertNotIn('NDEF', overview)
        self.assertIn('print_temp', w.export_details.diagnostic.text())
        self.assertNotIn('transmises', w.hardware_summary.text())

    def test_capacity_dialog_clears_old_numbers_when_the_tag_no_longer_fits(self):
        w = self.window; w._show_detail('PB05001'); w._open_export_explanation()
        self.assertEqual(w.export_journey.property('tone'), 'ready')
        self.assertNotEqual(w.export_details.metrics['remaining'].value.text(), '—')
        w.nfc_reserve.setValue(core.NFC_CAPACITIES['NTAG216'])
        self.assertEqual(w.export_journey.property('tone'), 'attention')
        self.assertFalse(w.capacity_meter.isVisible())
        self.assertEqual(w.export_details.metrics['remaining'].value.text(), '—')
        self.assertIn('trop volumineux', w.export_details.readiness.value.text())
        self.assertEqual(w._primary_kind, 'hardware')

    def test_explanation_windows_keep_main_geometry_and_close_action_accessible(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QDialogButtonBox
        w = self.window; w.resize(1100, 760); w.show(); w._show_detail('PB05001'); w.app.processEvents()
        before = w.size(); w.export_details_button.click()
        for dialog in [w.export_details]:
            dialog.resize(440, 420); w.app.processEvents(); w.app.processEvents()
            close = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Close)
            self.assertTrue(dialog.rect().contains(close.mapTo(dialog, QPoint(close.width()//2, close.height()//2))))
            self.assertEqual(dialog.tabs.widget(0).horizontalScrollBar().maximum(), 0)
            dialog.close()
        self.assertEqual(w.size(), before)
