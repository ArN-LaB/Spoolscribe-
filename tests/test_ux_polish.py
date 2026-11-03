"""Consolidated regressions for folding, density and aligned action groups."""
import copy
from pathlib import Path
import unittest
from tests import test_gui as fixture
from spoolscribe import core


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class UxPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self): fixture.GuiTests.setUp(self)

    def test_fold_all_preserves_filters_favorites_order_and_selection(self):
        w=self.window;w.show();w._choose_family('PETG');w._show_detail('PB05001')
        before=copy.deepcopy(w.db);rows=[r['sku'] for r in w._filtered_rows];selected=w.current_sku
        cfg=core.load_config();cfg['favorite_brands']=['Polymaker'];core.save_config(cfg)
        w._set_all_sections_expanded(False);w.app.processEvents()
        self.assertTrue(all(not s['toggle'].isChecked() for s in w._sections.values()))
        self.assertIn('PETG',w._sections['materials']['toggle'].text())
        self.assertEqual([r['sku'] for r in w._filtered_rows],rows);self.assertEqual(w.current_sku,selected)
        self.assertEqual(w.db,before);self.assertEqual(core.load_config()['favorite_brands'],['Polymaker'])
        w._set_all_sections_expanded(True);w.app.processEvents()
        self.assertTrue(all(s['toggle'].isChecked() for s in w._sections.values()))
        self.assertTrue(w.sections_menu.menu().actions())
        w._save_ui_preferences();self.assertTrue(all(v is False for v in core.load_config()['ui']['collapsed'].values()))

    def test_sidebar_does_not_stretch_short_lists_to_fill_a_tall_window(self):
        w=self.window;w.resize(1380,1100);w.show();w._choose_brand('ROSA3D');w._choose_family('ASA');w.app.processEvents()
        section=w._sections['materials']
        self.assertLess(section['frame'].height(),290)
        self.assertGreaterEqual(section['toggle'].height(),32)
        # Colour actions use the same palette as the other secondary controls.
        self.assertNotIn('QToolButton#colourAction { color:',w.styleSheet())
        self.assertNotIn('QToolButton#sectionToggle[filterKind=colour]',w.styleSheet())

    def test_sources_or_draft_close_printer_without_automatic_reopening(self):
        w=self.window;w.show();w._show_detail('PB05001');w.app.processEvents()
        for _ in range(4):w.app.processEvents()
        self.assertTrue(w.hardware_body.isVisible());raw=Path(core.DB_PATH).read_bytes()
        height=w.export_journey.height()
        w.provenance_toggle.setChecked(True)
        for _ in range(4):w.app.processEvents()
        self.assertFalse(w.hardware_body.isVisible());self.assertTrue(w.btn_generate.isVisible())
        self.assertLess(w.export_journey.height(),height-40)
        self.assertTrue(w.nfc_capacity.isVisible())
        w._edit_physical();w.provenance_toggle.setChecked(False);w.app.processEvents()
        self.assertFalse(w.hardware_body.isVisible())
        w._cancel_draft();w.app.processEvents();self.assertFalse(w.hardware_body.isVisible())
        w.hardware_fold.click();w.app.processEvents();self.assertTrue(w.hardware_body.isVisible())
        self.assertEqual(Path(core.DB_PATH).read_bytes(),raw)

    def test_manual_printer_fold_survives_temporary_detail_work(self):
        w=self.window;w.show();w._show_detail('PB05001');w.hardware_fold.click();w.app.processEvents()
        self.assertFalse(w.hardware_body.isVisible())
        w.provenance_toggle.setChecked(True);w.provenance_toggle.setChecked(False);w.app.processEvents()
        self.assertFalse(w.hardware_body.isVisible())
        w.hardware_fold.click();w.app.processEvents();self.assertTrue(w.hardware_body.isVisible())

    def test_detail_and_printer_share_edges_and_secondary_action_sizes(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.show();w._show_detail('PB05001')
        for width in (1100,1380,1101):
            w.resize(width,800);w.app.processEvents();w.app.processEvents()
            left=lambda x:x.mapTo(w,QPoint()).x()
            self.assertEqual(left(w.hero),left(w.export_journey))
            self.assertEqual(left(w.hero)+w.hero.width(),left(w.export_journey)+w.export_journey.width())
            self.assertGreaterEqual(w.hardware_name.width(),w.hardware_name.fontMetrics().horizontalAdvance('Snapmaker'))
        self.assertEqual(w.hardware_change.width(),w.export_details_button.width())
        self.assertEqual({b.height() for b in (w.hardware_change,w.export_details_button,w.colour_rank_btn,w.colour_exit_btn,w.colour_details_button)}, {32})
        widths=[b.width() for b in (w.colour_rank_btn,w.colour_exit_btn,w.colour_details_button)]
        self.assertLessEqual(max(widths)-min(widths),1)  # integer layout remainder

    def test_opening_printer_closes_sources_and_respects_a_modified_draft(self):
        from unittest.mock import patch
        w=self.window;w.show();w._show_detail('PB05001')
        w.provenance_toggle.setChecked(True);w.hardware_fold.click();w.app.processEvents()
        self.assertFalse(w.provenance_toggle.isChecked());self.assertTrue(w.hardware_body.isVisible())
        raw=Path(core.DB_PATH).read_bytes();w._edit_physical();w.draft_fields['min_temp'].setText('245');w._draft_edited()
        with patch.object(w,'_ask_draft_decision',return_value='keep'):
            w.hardware_fold.click()
        self.assertIsNotNone(w._draft);self.assertFalse(w.hardware_fold.isChecked());self.assertFalse(w.hardware_body.isVisible())
        with patch.object(w,'_ask_draft_decision',return_value='discard'):
            w.hardware_fold.click()
        self.assertIsNone(w._draft);self.assertFalse(w.provenance_toggle.isChecked());self.assertTrue(w.hardware_body.isVisible())
        self.assertTrue(w.btn_generate.isEnabled())
        self.assertEqual(Path(core.DB_PATH).read_bytes(),raw)

    def test_hardware_dialog_compacts_to_content_and_keeps_actions_visible(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QPushButton
        w=self.window;w._open_hardware();w.app.processEvents();dialog=w.hardware_dialog
        self.assertLessEqual(dialog.height(),dialog.screen().availableGeometry().height()-80)
        self.assertEqual(w.hardware_footer_close.width(),w.btn_update_printers.width())
        for button in (w.hardware_footer_close,w.btn_update_printers):
            self.assertEqual(button.height(),32)
            self.assertTrue(dialog.rect().contains(button.mapTo(dialog,QPoint(button.width()//2,button.height()//2))))
        # Expanding advanced content must still allow reaching it in the scroll area.
        w.setup_details_toggle.setChecked(True);w.app.processEvents()
        self.assertTrue(w.hardware_scroll.verticalScrollBar().isVisible() or w.hardware_page.height()<=w.hardware_scroll.viewport().height())
