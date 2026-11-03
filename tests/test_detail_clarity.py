"""Actual feedback: independent editing, compact truth and inclusive colour limits."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tests import test_gui as fixture
from spoolscribe import core,colour_distance


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class DetailClarityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self);self.addCleanup(lambda:self.window._close_draft())

    def test_edit_and_details_are_exclusive_and_keep_dirty_draft_safe(self):
        w=self.window;w.show();w._show_detail('PB05001');raw=Path(core.DB_PATH).read_bytes()
        w.provenance_toggle.click();self.assertTrue(w.comparison_card.isVisible())
        w._edit_physical();self.assertFalse(w.comparison_card.isVisible());self.assertFalse(w.provenance_toggle.isChecked())
        self.assertFalse(w.provenance_box.isVisible());self.assertTrue(w.draft_editor.isVisible());self.assertFalse(w.card.isVisible())
        w.draft_fields['min_temp'].setText('235');w._draft_edited()
        with patch.object(w,'_ask_draft_decision',return_value='keep'):w.provenance_toggle.click()
        self.assertFalse(w.provenance_toggle.isChecked());self.assertTrue(w.draft_editor.isVisible())
        with patch.object(w,'_ask_draft_decision',return_value='discard'):w.provenance_toggle.click()
        self.assertIsNone(w._draft);self.assertFalse(w.draft_editor.isVisible());self.assertTrue(w.comparison_card.isVisible())
        self.assertEqual(Path(core.DB_PATH).read_bytes(),raw)

    def test_identical_reference_values_are_not_repeated_in_sources(self):
        w=self.window;w.show();w._show_detail('PB05001');w.provenance_toggle.click();w.comparison_sources_toggle.click();w.app.processEvents()
        for card in w.parameter_cards:
            for key in card.keys:
                self.assertFalse(card.source_rows[key][1].isVisible())
        self.assertLess(w.parameter_cards[0].height(),100)
        self.assertTrue(w.comparison_cells['min_temp'][1].text())
        self.assertTrue(w.comparison_cells['min_temp'][4].accessibleDescription())

    def test_shown_score_does_not_hide_a_threshold_exceedance(self):
        delta=round(colour_distance.ciede2000(colour_distance.hex_to_lab('C8E6A0'),colour_distance.hex_to_lab('D8EEA3')),6)
        self.assertEqual(delta,3.035999);self.assertEqual(colour_distance.display_delta(delta),'3.04')
        for score,expected in ((0,'0.00'),(3,'3.00'),(3.000001,'3.01'),(2.999999,'3.00'),(10.000001,'10.01')):
            self.assertEqual(colour_distance.display_delta(score),expected)
            for threshold in (3,10,20):self.assertEqual(score<=threshold,float(colour_distance.display_delta(score))<=threshold)
        w=self.window;w._colour_query=dict(hex='C8E6A0',cache={})
        items=[dict(row={'sku':'same'},delta=0,effect=False),dict(row={'sku':'next'},delta=delta,effect=False)]
        cfg=core.load_config();cfg['colour_delta_max']=3;core.save_config(cfg)
        with patch('spoolscribe.colour_distance.rank',return_value=dict(items=items,total=2,excluded={})):
            self.assertEqual([r['sku'] for r in w._rank_by_colour([])],['same'])
        self.assertIn('≤',w.colour_limit_button.text())

    def test_visible_settings_page_grows_until_scrolling_is_unnecessary(self):
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtWidgets import QDialog,QTabWidget
        from PySide6.QtCore import QRect
        def inspect(d):
            d.show();tabs=d.findChild(QTabWidget);font=d.font();font.setPointSizeF(font.pointSizeF()+4);d.setFont(font)
            for index in (4,0,2,0):
                tabs.setCurrentIndex(index);fit_dialog(d,preferred_width=700,available=QRect(0,0,1400,1000))
                for _ in range(8):self.window.app.processEvents()
                page=tabs.currentWidget()
                self.assertEqual(page.verticalScrollBar().maximum(),0,(index,d.size(),page.verticalScrollBar().maximum()))
                self.assertLessEqual(d.height(),920)
            d.hide();return QDialog.Rejected
        with patch('spoolscribe.app_gui.QDialog.exec',inspect):self.window._open_settings(colour_tab=True)

    def test_delta_footer_has_air_above_and_below(self):
        from PySide6.QtCore import QRectF
        w=self.window;w.show();w._start_colour_search('070908');w._set_view_mode('grid');w.app.processEvents()
        box=QRectF(w.grid.visualItemRect(w.grid.item(0))).adjusted(5,5,-5,-5)
        meta,badge=w.grid.itemDelegate().footer_rects(box,w.grid.font(),5.3)
        self.assertGreaterEqual(badge.top()-(box.top()+155+18),8)
        self.assertGreaterEqual(box.bottom()-badge.bottom(),10)
        self.assertFalse(meta.intersects(badge))

    def test_late_page_layout_can_use_free_screen_space_after_opening(self):
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtWidgets import QDialog,QTabWidget
        from PySide6.QtCore import QRect
        def inspect(d):
            d.show();tabs=d.findChild(QTabWidget);fit_dialog(d,preferred_width=700,available=QRect(0,0,1400,1000))
            for _ in range(4):self.window.app.processEvents()
            old=d.height();page=tabs.currentWidget();intro=page.widget().layout().itemAt(0).widget();intro.setMinimumHeight(240)
            for _ in range(10):self.window.app.processEvents()
            self.assertGreater(d.height(),old+100);self.assertEqual(page.verticalScrollBar().maximum(),0)
            d.hide();return QDialog.Rejected
        with patch('spoolscribe.app_gui.QDialog.exec',inspect):self.window._open_settings()
