"""Visual reading order without losing source truth, filtering or edit safety."""
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_gui as fixture
from spoolscribe import core


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class VisualReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_one_filter_control_contains_active_criteria_and_fold_actions(self):
        w=self.window;w.show();w._choose_family('PETG')
        self.assertIs(w.filter_summary,w.sections_menu)
        labels=[a.text() for a in w.sections_menu.menu().actions()]
        self.assertIn('Matière : PETG',labels);self.assertIn('Tout replier',labels);self.assertIn('Tout déplier',labels)
        w.reset_filters.click();w.app.processEvents()
        self.assertTrue(w.sections_menu.isVisible());self.assertEqual(w.sections_menu.text(),'Filtres')
        self.assertNotIn('Matière : PETG',[a.text() for a in w.sections_menu.menu().actions()])

    def test_visual_printer_categories_apply_the_same_search_and_compatibility_rules(self):
        from spoolscribe.ui_widgets import PrinterBrowser,PrinterCategoryDialog
        from PySide6.QtWidgets import QDialog
        from PySide6.QtCore import Qt
        browser=PrinterBrowser(self.window.printer,self.window);self.addCleanup(browser.close)
        browser.search.setText('prusa')
        self.assertEqual(browser._category_counts()['usb'],0)
        self.assertGreater(browser._category_counts()['network'],0)
        browser.search.setText('flashforge');before=self.window.firmware.currentData()
        def choose(dialog):
            self.assertEqual(set(dialog.tiles),{'all','compatible','usb','network','stock','modified','rfid','none'})
            self.assertGreater(dialog.tiles['usb'].model_count,0)
            self.assertTrue(dialog.tiles['usb'].accessibleDescription())
            dialog.tiles['usb'].click();return QDialog.Accepted
        with patch.object(PrinterCategoryDialog,'exec',choose):browser.category.showPopup()
        self.assertEqual(browser.category.currentData(),'usb')
        items=[browser.list.item(i) for i in range(browser.list.count()) if not browser.list.item(i).isHidden()]
        self.assertTrue(items)
        self.assertTrue(all('usb' in item.data(Qt.UserRole+2) and 'flashforge' in item.data(Qt.UserRole+1) for item in items))
        self.assertEqual(self.window.firmware.currentData(),before)

    def test_parameter_cards_group_ranges_and_keep_source_values_available(self):
        w=self.window;w.show();w._show_detail('PB05001');raw=Path(core.DB_PATH).read_bytes()
        w.provenance_toggle.setChecked(True);w.app.processEvents()
        self.assertEqual(len(w.parameter_cards),5)
        self.assertEqual(set(w.comparison_cells),{'min_temp','max_temp','bed_min_temp','bed_max_temp','diameter','density','hex'})
        self.assertFalse(w.comparison_sources_toggle.isChecked())
        self.assertGreater(w.comparison_heads[4].width(),30)
        self.assertFalse(w.hardware_body.isVisible())
        expected=w._comparison()
        for row in expected['rows']:
            labels=w.comparison_cells[row['key']]
            self.assertIn(str(row['reference']['value']) if row['key']!='hex' else '#070908',labels[1].text())
            self.assertTrue(labels[1].accessibleDescription())
        w.comparison_sources_toggle.click();w.app.processEvents()
        self.assertTrue(w.parameter_cards[0].sources.isVisible())
        self.assertEqual(Path(core.DB_PATH).read_bytes(),raw)

    def test_grouped_parameters_reflow_without_clipped_values(self):
        from PySide6.QtCore import QPoint,QRect
        w=self.window;w.show();w._show_detail('PB05001');w.provenance_toggle.setChecked(True)
        for width,right in ((1100,300),(1500,700),(1100,300)):
            w.resize(width,850);w.splitter.setSizes([250,400,right])
            for _ in range(5):w.app.processEvents()
            for card in w.parameter_cards:
                for label in card.values:
                    rect=QRect(label.mapTo(card,QPoint()),label.size())
                    self.assertTrue(card.rect().contains(rect))
                    self.assertGreaterEqual(label.height(),label.heightForWidth(label.width()))
        self.assertTrue(w.comparison_summary.text())

    def test_configure_label_fits_after_native_font_metrics_change(self):
        w=self.window;w.show();w._show_detail('PB05001')
        for button in (w.hardware_change,w.export_details_button):
            font=button.font();font.setPointSizeF(font.pointSizeF()+3);button.setFont(font)
        w._apply_theme();w.app.processEvents()
        self.assertEqual(w.hardware_change.width(),w.export_details_button.width())
        for button in (w.hardware_change,w.export_details_button):
            self.assertGreaterEqual(button.width(),button.fontMetrics().horizontalAdvance(button.text())+24)
