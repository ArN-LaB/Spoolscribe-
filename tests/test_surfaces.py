"""Readable surfaces, restrained colour score and content-aware windows, offline."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tests import test_gui as fixture
from spoolscribe import core


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class SurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_tabs_have_mirrored_overflow_and_readable_scroll_buttons(self):
        from spoolscribe.ui_surfaces import ReadingTabs
        from PySide6.QtWidgets import QWidget,QToolButton
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        tabs=ReadingTabs();self.addCleanup(tabs.close)
        for name in ('Catalogue','Bobines','Export','Interface','Teintes'):tabs.addTab(QWidget(),name)
        tabs.resize(310,200);tabs.show()
        for _ in range(4):self.window.app.processEvents()
        bar=tabs.tabBar();left,right=bar.overflow_edges()
        self.assertFalse(left);self.assertTrue(right)
        buttons={b.property('scrollDirection'):b for b in bar.findChildren(QToolButton)}
        self.assertEqual(set(buttons),{'left','right'})
        self.assertFalse(buttons['right'].icon().isNull());start=bar.tabRect(0).x()
        QTest.mouseClick(buttons['right'],Qt.LeftButton);self.window.app.processEvents()
        self.assertLess(bar.tabRect(0).x(),start);self.assertTrue(bar.overflow_edges()[0])
        bar.setCurrentIndex(bar.count()-1);self.window.app.processEvents()
        self.assertFalse(bar.overflow_edges()[1]);self.assertTrue(bar.overflow_edges()[0])
        tabs.resize(900,200);self.window.app.processEvents();self.assertEqual(bar.overflow_edges(),(False,False))

    def test_dialog_size_uses_content_and_available_screen_without_empty_tail(self):
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel
        from PySide6.QtCore import QRect
        dialog=QDialog(self.window);self.addCleanup(dialog.close);box=QVBoxLayout(dialog);box.addWidget(QLabel('Short explanation'));box.addStretch(1)
        short=fit_dialog(dialog,preferred_width=540,available=QRect(0,0,1200,850))
        self.assertLess(short.height(),250);self.assertGreaterEqual(short.width(),540)
        for i in range(35):box.insertWidget(i,QLabel('Row '+str(i)))
        tall=fit_dialog(dialog,preferred_width=640,available=QRect(1200,0,1200,850))
        self.assertGreater(tall.height(),short.height()+200);self.assertLessEqual(tall.height(),770)
        self.assertGreaterEqual(dialog.x(),1200)

    def test_settings_fit_all_tabs_when_space_exists_and_still_scroll_on_small_screen(self):
        from PySide6.QtWidgets import QDialog,QTabWidget,QScrollArea
        from spoolscribe.ui_surfaces import fit_dialog
        from PySide6.QtCore import QRect
        def inspect(dialog):
            tabs=dialog.findChild(QTabWidget);dialog.show()
            fit_dialog(dialog,preferred_width=640,available=QRect(0,0,1400,1000))
            for _ in range(4):self.window.app.processEvents()
            self.assertEqual(tabs.tabBar().overflow_edges(),(False,False))
            self.assertIsInstance(tabs.currentWidget(),QScrollArea)
            self.assertLess(dialog.height(),600)
            font=dialog.font();font.setPointSizeF(font.pointSizeF()+3);dialog.setFont(font)
            fit_dialog(dialog,preferred_width=640,available=QRect(0,0,1400,1000))
            for _ in range(4):self.window.app.processEvents()
            self.assertEqual(tabs.tabBar().overflow_edges(),(False,False))
            fit_dialog(dialog,preferred_width=640,available=QRect(0,0,600,400))
            for _ in range(4):self.window.app.processEvents()
            self.assertLessEqual(dialog.height(),320);self.assertLessEqual(dialog.width(),552)
            self.assertTrue(tabs.currentWidget().verticalScrollBar().isVisible())
            dialog.hide();return QDialog.Rejected
        with patch('spoolscribe.app_gui.QDialog.exec',inspect):self.window._open_settings(colour_tab=True)

    def test_score_footer_shares_a_row_without_dominating_the_colour_title(self):
        w=self.window;w.show();w._start_colour_search('070908');w._set_view_mode('grid');w.app.processEvents()
        delegate=w.grid.itemDelegate()
        from PySide6.QtCore import QRectF
        meta,badge=delegate.footer_rects(QRectF(0,0,170,198),w.grid.font(),15.1)
        self.assertLess(badge.width(),85);self.assertLess(badge.height(),23)
        self.assertFalse(meta.intersects(badge));self.assertAlmostEqual(meta.center().y(),badge.center().y(),delta=1)
        self.assertEqual(w.grid.gridSize().height(),232)
        w._stop_colour_search();self.assertEqual(w.grid.gridSize().height(),216)

    def test_brand_halo_only_changes_rendering_in_dark_mode(self):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        w=self.window;w.show();w._show_detail('PB05001');before=Path(core.DB_PATH).read_bytes()
        with patch('spoolscribe.app_gui.is_dark_theme',return_value=True):w._apply_theme();w._refresh_logo('Snapmaker')
        halo=w.logo.graphicsEffect();self.assertIsInstance(halo,QGraphicsDropShadowEffect)
        self.assertTrue(halo.isEnabled());self.assertEqual(halo.offset().x(),0);self.assertEqual(halo.offset().y(),0)
        self.assertGreater(halo.blurRadius(),4)
        # The rendered halo must improve luminance, not merely exist as an effect.
        w.app.processEvents();halo.setEnabled(False);w.app.processEvents();plain=w.hero.grab().toImage()
        original=w.logo.pixmap().toImage();halo.setEnabled(True);w.app.processEvents();lit=w.hero.grab().toImage()
        changed=sum(lit.pixelColor(x,y).lightness()>plain.pixelColor(x,y).lightness()+3
                    for y in range(min(55,lit.height())) for x in range(min(150,lit.width())))
        self.assertGreater(changed,20)
        self.assertEqual(original,w.logo.pixmap().toImage())

        with patch('spoolscribe.app_gui.is_dark_theme',return_value=False):w._apply_theme();w._refresh_logo('Snapmaker')
        self.assertFalse(halo.isEnabled());self.assertEqual(Path(core.DB_PATH).read_bytes(),before)
