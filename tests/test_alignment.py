"""Follow-up from installed macOS screenshots, using the actual startup style."""
import unittest
from unittest.mock import patch
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_visible_export_buttons_share_edges_and_remain_inside_small_window(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.resize(1000,720);w.show();w._show_detail('PB05001');w.app.processEvents()
        self.assertTrue(w.btn_inspect.isVisible());self.assertTrue(w.btn_open_out.isVisible())
        left=lambda widget:widget.mapTo(w,QPoint(0,0)).x()
        right=lambda widget:left(widget)+widget.width()
        self.assertEqual(left(w.btn_generate),left(w.btn_inspect))
        self.assertEqual(right(w.btn_generate),right(w.btn_open_out))
        self.assertEqual(w.btn_inspect.height(),w.btn_open_out.height())
        self.assertLessEqual(right(w.btn_open_out),w.width())
        self.assertEqual(left(w.btn_generate),left(w.hero))
        self.assertEqual(right(w.btn_generate),right(w.hero))

    def test_brand_stars_are_not_repeated_in_every_name_and_name_click_selects(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        import core
        w=self.window;w.show();w.app.processEvents()
        self.assertTrue(all('☆' not in w.brand_list.item(i).text() for i in range(w.brand_list.count())))
        target=next(w.brand_list.item(i) for i in range(w.brand_list.count()) if w.brand_list.item(i).data(Qt.UserRole)=='Polymaker')
        w.brand_list.scrollToItem(target);w.app.processEvents();rect=w.brand_list.visualItemRect(target)
        before=core.load_config()['favorite_brands']
        QTest.mouseClick(w.brand_list.viewport(),Qt.LeftButton,pos=QPoint(rect.left()+15,rect.center().y()))
        self.assertEqual(w.brand_filter.currentData(),'Polymaker');self.assertEqual(core.load_config()['favorite_brands'],before)
        QTest.mouseClick(w.brand_list.viewport(),Qt.LeftButton,pos=QPoint(rect.right()-13,rect.center().y()))
        self.assertIn('Polymaker',core.load_config()['favorite_brands'])

    def test_catalogue_toolbar_uses_one_control_height(self):
        w=self.window;w.show();w.app.processEvents()
        self.assertEqual(w.segwrap.height(),w.columns_btn.height())
        self.assertEqual(w.search.height(),w.update_btn.height())
        self.assertEqual(w.update_btn.height(),w.menu_btn.height())

    def test_settings_form_labels_and_fields_are_aligned(self):
        from PySide6.QtWidgets import QDialog,QTabWidget,QComboBox
        from PySide6.QtCore import QPoint
        w=self.window
        def inspect(dialog):
            dialog.show();dialog.resize(540,420);tabs=dialog.findChild(QTabWidget);tabs.setCurrentIndex(1);w.app.processEvents()
            a=dialog.findChild(QComboBox,'preferred_weight_g');b=dialog.findChild(QComboBox,'preferred_packaging')
            self.assertEqual(a.mapTo(dialog,QPoint()).x(),b.mapTo(dialog,QPoint()).x())
            self.assertEqual(a.width(),b.width());self.assertEqual(a.height(),b.height())
            self.assertLessEqual(a.mapTo(dialog,QPoint()).x()+a.width(),dialog.width())
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):w._open_settings()

    def test_startup_configuration_matches_the_app_without_growing_the_font(self):
        import app_gui
        app=self.window.app;size=app.font().pointSizeF()
        app_gui.configure_application(app);app_gui.configure_application(app)
        self.assertEqual(app.style().objectName().lower(),'fusion')
        self.assertEqual(app.font().pointSizeF(),size)

    def test_colour_logo_does_not_get_a_duplicated_halo(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap,QPainter,QColor
        image=QPixmap(24,24);image.fill(Qt.transparent);p=QPainter(image);p.fillRect(6,6,12,12,QColor('#cf2211'));p.end()
        result=self.window._transparent_logo(image).toImage()
        # Rendering pads by two logical pixels, but adds no displaced contour.
        self.assertEqual(result.pixelColor(2+5,2+12).alpha(),0)
        self.assertEqual(result.pixelColor(2+6,2+12).name(),'#cf2211')

    def test_duplicate_manufacturer_name_is_only_cleaned_for_display(self):
        from ui_widgets import product_label
        text='Artillery Artillery Basic PLA'
        self.assertEqual(product_label(text,'Artillery'),'Artillery Basic PLA')
        self.assertEqual(text,'Artillery Artillery Basic PLA')
        self.assertEqual(product_label('PLA+','Artillery'),'PLA+')

    def test_json_button_opens_and_scrolls_to_the_file(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.resize(1000,720);w.show();w._show_detail('PB05001');w.app.processEvents()
        w.btn_inspect.click();w.app.processEvents();w.app.processEvents()
        self.assertTrue(w.inspector.isVisible())
        top=w.inspector.mapTo(w.detail_scroll.viewport(),QPoint())
        self.assertTrue(w.detail_scroll.viewport().rect().contains(top))
        w.btn_inspect.click();self.assertFalse(w.inspector.isVisible())
