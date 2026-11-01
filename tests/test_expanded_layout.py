"""Exercise expanded states and resize sequences from the installed-app feedback."""
import unittest
from unittest.mock import patch
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class ExpandedLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_storage_details_are_bounded_and_leave_close_accessible(self):
        from PySide6.QtWidgets import QDialog,QToolButton,QPlainTextEdit,QPushButton
        w=self.window;w.stats_label.setToolTip('\n'.join(f'_products.very long product name {i}.density' for i in range(100)))
        def inspect(dialog):
            dialog.resize(600,460);dialog.show();w.app.processEvents();before=dialog.size()
            toggle=next(b for b in dialog.findChildren(QToolButton) if b.text()=='Stockage et valeurs conservées');toggle.click();w.app.processEvents()
            self.assertEqual(dialog.size(),before)
            text=dialog.findChild(QPlainTextEdit,'storageDetails');self.assertIsNotNone(text);self.assertTrue(text.isVisible())
            self.assertLessEqual(text.height(),160)
            close=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Fermer')
            from PySide6.QtCore import QPoint
            self.assertTrue(dialog.rect().contains(close.mapTo(dialog,QPoint(close.width()//2,close.height()//2))))
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):w._database_details()

    def test_physical_form_aligns_all_fields_and_uses_french_actions(self):
        from PySide6.QtWidgets import QDialog,QLineEdit,QDialogButtonBox
        from PySide6.QtCore import QPoint
        w=self.window;w._show_detail('PB05001')
        def inspect(dialog):
            dialog.show();w.app.processEvents();fields=dialog.findChildren(QLineEdit)
            self.assertEqual(len({f.mapTo(dialog,QPoint()).x() for f in fields}),1)
            self.assertEqual(len({f.width() for f in fields}),1)
            buttons=dialog.findChild(QDialogButtonBox)
            self.assertEqual(buttons.button(QDialogButtonBox.Save).text(),'Enregistrer')
            self.assertEqual(buttons.button(QDialogButtonBox.Cancel).text(),'Annuler')
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):w._edit_physical()

    def test_favorite_filters_span_the_same_edges_as_manufacturer_search(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.show();w.app.processEvents()
        left=lambda x:x.mapTo(w,QPoint()).x()
        self.assertEqual(left(w.brand_favorites_only),left(w.brand_search))
        self.assertEqual(w.brand_favorites_only.width(),w.favorites_only.width())
        self.assertEqual(left(w.favorites_only)+w.favorites_only.width(),left(w.brand_search)+w.brand_search.width())

    def test_expanded_provenance_is_a_card_with_consistent_value_alignment(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.show();w._show_detail('PB05001');w.provenance_toggle.click();w.app.processEvents()
        self.assertEqual(w.provenance_box.objectName(),'provenanceCard')
        for row in range(w.fields.rowCount()):
            label=w.fields.itemAtPosition(row,0).widget();value=w.fields.itemAtPosition(row,1).widget()
            self.assertEqual(label.mapTo(w,QPoint()).y(),value.mapTo(w,QPoint()).y())

    def test_printer_rows_do_not_grow_after_narrow_wide_narrow_sequence(self):
        from ui_widgets import PrinterBrowser
        browser=PrinterBrowser(self.window.printer,self.window);self.addCleanup(browser.close);browser.show()
        for width in (440,900,440,700,440):
            browser.resize(width,480);self.window.app.processEvents();self.window.app.processEvents()
            rects=[browser.list.visualItemRect(browser.list.item(i)) for i in range(browser.list.count())]
            self.assertTrue(all(80<=r.height()<=160 for r in rects))
            self.assertTrue(all(r.width()<=browser.list.viewport().width() for r in rects))

    def test_printer_card_surface_stays_readable_on_light_theme(self):
        from ui_widgets import PrinterBrowser
        from PySide6.QtCore import Qt
        browser=PrinterBrowser(self.window.printer,self.window);self.addCleanup(browser.close)
        browser.search.setText('prusa');browser.show();self.window.app.processEvents()
        item=next(browser.list.item(i) for i in range(browser.list.count()) if not browser.list.item(i).isHidden())
        rect=browser.list.visualItemRect(item);image=browser.list.viewport().grab().toImage();ratio=image.devicePixelRatio()
        color=image.pixelColor(int((rect.left()+90)*ratio),int((rect.top()+8)*ratio))
        self.assertGreater(color.lightness(),128)
