"""Colour comparison visibility and reversible, content-sized dialogs."""
import unittest
from unittest.mock import patch
from tests import test_gui as fixture
from spoolscribe import core, i18n

@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class VisibilityReflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self);i18n.set_language('fr')
    def settle(self):
        from PySide6.QtTest import QTest
        for _ in range(6):self.window.app.processEvents();QTest.qWait(15)

    def test_delta_has_its_own_column_only_during_colour_comparison(self):
        w=self.window;w._start_colour_search('070908');w._set_view_mode('list');self.settle()
        col=w._delta_column
        self.assertFalse(w.table.isColumnHidden(col));self.assertIn('ΔE',w.table.horizontalHeaderItem(col).text())
        self.assertEqual(w.table.item(0,col).text(),'0.00')
        self.assertNotIn('ΔE',w.table.item(0,3).text())
        w._stop_colour_search();self.assertTrue(w.table.isColumnHidden(col))
        w._start_colour_search('070908');self.assertFalse(w.table.isColumnHidden(col))

    def test_card_name_keeps_product_variant_without_repeating_manufacturer(self):
        from spoolscribe.ui_widgets import card_product_label
        self.assertEqual(card_product_label('Snapmaker Matte PLA','Snapmaker'),'Matte PLA')
        self.assertEqual(card_product_label('Polymaker™ PETG','Polymaker'),'PETG')
        self.assertEqual(card_product_label('PolyLite PLA Pro','Polymaker'),'PolyLite PLA Pro')
        self.assertEqual(card_product_label('Bambu Lab Bambu Lab PLA Matte','Bambu Lab'),'PLA Matte')

    def test_folded_dialog_shrinks_without_manual_fit_and_stays_on_screen(self):
        from PySide6.QtWidgets import QDialog,QVBoxLayout,QWidget,QLabel,QToolButton
        from PySide6.QtCore import QRect
        from spoolscribe.ui_surfaces import ReadingTabs,fit_dialog
        d=QDialog(self.window);self.addCleanup(d.close);layout=QVBoxLayout(d);tabs=ReadingTabs();layout.addWidget(tabs)
        page=QWidget();box=QVBoxLayout(page);toggle=QToolButton();toggle.setCheckable(True);box.addWidget(toggle)
        details=QWidget();rows=QVBoxLayout(details)
        for i in range(22):rows.addWidget(QLabel('Additional information '+str(i)))
        details.hide();box.addWidget(details);box.addStretch();toggle.toggled.connect(details.setVisible);tabs.addTab(page,'Details')
        d.show();fit_dialog(d,preferred_width=600,available=QRect(0,0,1400,1200));self.settle();small=d.height()
        toggle.setChecked(True);self.settle();expanded=d.height();self.assertGreater(expanded,small+150)
        toggle.setChecked(False);self.settle();self.assertLess(d.height(),expanded-150);self.assertLessEqual(abs(d.height()-small),8)

    def test_colour_window_describes_the_user_goal_and_refolds(self):
        from spoolscribe.ui_colour_measurements import MeasurementWindow
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtCore import QRect
        d=MeasurementWindow(self.window);self.addCleanup(d.close);d.show()
        fit_dialog(d,preferred_width=820,available=QRect(0,0,1600,1800));self.settle();small=d.height()
        self.assertEqual(d.windowTitle(),'Valeurs couleur : Lab, RGB, fichier')
        d.details_toggle.setChecked(True);self.settle();expanded=d.height();self.assertGreater(expanded,small+200)
        d.details_toggle.setChecked(False);self.settle();self.assertLess(d.height(),expanded-200)

    def test_qr_uses_available_height_and_refolds_details(self):
        from spoolscribe.ui_qr import QrWindow,snapshot
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtCore import QRect
        w=self.window;w.current_sku='PB05001';w._show_detail(w.current_sku)
        qr=QrWindow(snapshot(w),w);qr.setAttribute(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.WA_DeleteOnClose,False);self.addCleanup(qr.close)
        qr.show();fit_dialog(qr,preferred_width=640,available=QRect(0,0,1600,1800));self.settle();small=qr.height()
        self.assertEqual(qr.lower.verticalScrollBar().maximum(),0)
        qr.details_toggle.setChecked(True);self.settle();expanded=qr.height();self.assertGreater(expanded,small+100)
        self.assertEqual(qr.lower.verticalScrollBar().maximum(),0)
        qr.details_toggle.setChecked(False);self.settle();self.assertLess(qr.height(),expanded-100)
        fit_dialog(qr,preferred_width=600,available=QRect(0,0,900,720));self.settle()
        self.assertLessEqual(qr.height(),640);self.assertGreater(qr.lower.verticalScrollBar().maximum(),0)

    def test_transient_score_does_not_allow_hiding_all_normal_columns(self):
        w=self.window;w._start_colour_search('070908')
        for col in range(1,w._delta_column):w._set_column_visible(col,False)
        w._stop_colour_search()
        self.assertTrue(any(not w.table.isColumnHidden(i) for i in range(1,w._delta_column)))

    def test_reflow_settles_instead_of_rescheduling_forever(self):
        from spoolscribe.ui_colour_measurements import MeasurementWindow
        d=MeasurementWindow(self.window);self.addCleanup(d.close);d.show();self.settle()
        fitter=d._content_fitter
        with patch.object(fitter,'settle',wraps=fitter.settle) as settle:
            self.settle();self.settle()
            self.assertLess(settle.call_count,8)
