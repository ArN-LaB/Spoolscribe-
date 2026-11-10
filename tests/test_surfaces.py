"""Readable surfaces, restrained colour score and content-aware windows, offline."""
import json
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


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class SemanticAccentTests(unittest.TestCase):
    """B14 D: same meaning, same style; « ready » is never drawn as a hardware qualification."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_accents_follow_documented_meanings_in_both_themes(self):
        from spoolscribe.ui_widgets import CARD_RADIUS,TILE_RADIUS
        w=self.window
        for dark in (False,True):
            with self.subTest(dark=dark):
                with patch('spoolscribe.app_gui.is_dark_theme',return_value=dark):w._apply_theme()
                qss=w.styleSheet()
                self.assertNotIn('tone=ready',qss)                      # no green rule on the printer card
                self.assertIn('QFrame#exportJourney[tone=attention]',qss) # something to do before exporting
                self.assertNotIn('dashed',qss.split('QFrame#draftEditor {')[1].split('}')[0])
                self.assertIn(f"border:1px solid {w._tok['accent']}",qss.split('QFrame#draftEditor {')[1].split('}')[0])
                for name in ('QFrame#exportJourney {','QFrame#draftEditor, QFrame#comparisonCard {'):
                    self.assertIn(f'border-radius:{CARD_RADIUS}px',qss.split(name)[1].split('}')[0])
                self.assertIn(f'border-radius:{TILE_RADIUS}px',qss.split('QFrame#guidanceTile {')[1].split('}')[0])

    def test_ready_export_card_has_no_coloured_rule_and_blocked_one_keeps_attention(self):
        w=self.window;w.show();w.current_sku='PB05001';w._show_detail('PB05001');w.app.processEvents()
        self.assertEqual(w.export_journey.property('tone'),'ready')
        image=w.export_journey.grab().toImage();left=image.pixelColor(1,image.height()//2)
        right=image.pixelColor(image.width()-2,image.height()//2)
        self.assertEqual(left.name(),right.name())   # left edge drawn like the right one: plain border
        w.firmware.setCurrentIndex(w.firmware.findData('unknown'));w.app.processEvents()
        self.assertNotEqual(w.export_journey.property('tone'),'ready')


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class DialogFitterLifetimeTests(unittest.TestCase):
    """B14 G: the reproduced SIGSEGV path. Real modal dialogs (Paramètres, export options) are opened,
    cancelled and reopened; Qt must never call a dialog fitter whose Python state is gone."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_export_preferences_journey_never_reaches_a_stateless_fitter(self):
        import collections, gc, sys, time
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialogButtonBox, QPushButton, QTabWidget
        from spoolscribe import ui_surfaces
        w=self.window;w.show();target=Path(self.tmp.name)/'prefs.json'
        # Before the fix this journey called eventFilter on collected fitters (AttributeError
        # 'fitting', then calls into freed memory) and crashed with SIGSEGV. Overrides are not
        # patched here: PySide keeps the override it resolved, so a restored patch would itself
        # leave a dangling callable behind.
        # B18/33: the full collections below examine only what this journey creates (its dialogs and
        # fitters, all built after the freeze). Unfrozen, they walked the whole heap left by the
        # preceding tests (~3 M objects), seconds per pass on a slow CI Mac, and ran out the bound.
        gc.freeze();self.addCleanup(gc.unfreeze)
        errors=[]
        hook=sys.excepthook;sys.excepthook=lambda *a:errors.append(a[1]);self.addCleanup(setattr,sys,'excepthook',hook)
        # Each action runs once, only when the dialog it expects is shown and its fitter has settled:
        # no fixed pace, and never on another modal window an earlier test may have left visible.
        def shown(child_type,name):
            d=QApplication.activeModalWidget()
            return d if d is not None and d.isVisible() and d.findChild(child_type,name) is not None else None
        def ready(child_type,name):
            d=shown(child_type,name);fitter=getattr(d,'_content_fitter',None)
            return d if fitter is not None and not fitter.pending else None
        settings=lambda:ready(QPushButton,'exportPreferences');options=lambda:ready(QCheckBox,'includeLayout')
        depth=[0]   # Paramètres requested and not yet returned (export options and the file write happen inside)
        def idle():return depth[0]==0 and shown(QPushButton,'exportPreferences') is None and shown(QCheckBox,'includeLayout') is None
        def open_settings():
            def run():
                try:w._open_settings()
                finally:depth[0]-=1
            depth[0]+=1;QTimer.singleShot(0,run)
        def export_click():
            d=settings();tabs=d.findChild(QTabWidget);tabs.setCurrentIndex(tabs.count()-1)
            language=d.findChild(QComboBox,'interface_language');language.setCurrentIndex(language.findData('es'))
            d.findChild(QPushButton,'exportPreferences').click()
        def press(button):return lambda:options().findChild(QDialogButtonBox).button(button).click()
        steps=collections.deque();done=[]
        for _ in range(2):
            steps.extend([('open',idle,open_settings),('export',settings,export_click),('cancel',options,press(QDialogButtonBox.Cancel)),
                          ('open',idle,open_settings),('export',settings,export_click),('ok',options,press(QDialogButtonBox.Ok)),('gc',idle,gc.collect),
                          ('open',idle,open_settings),('reject',settings,lambda:settings().reject()),('gc',idle,gc.collect)])
        steps.append(('done',idle,lambda:done.append(True)))
        deadline=time.monotonic()+20;stop={}
        def advance():
            if done:return
            if errors or time.monotonic()>deadline:
                # First failure is reported as is; open journey dialogs are closed so the test returns.
                stop.setdefault('at',(steps[0][0],len(steps),'error' if errors else 'deadline'))
                d=shown(QCheckBox,'includeLayout') or shown(QPushButton,'exportPreferences')
                if d is not None:d.reject()
                if d is not None or depth[0]:QTimer.singleShot(0,advance)
                return
            name,expected,action=steps[0]
            if expected():
                steps.popleft()
                try:action()
                except Exception as exc:errors.append(exc)
            QTimer.singleShot(0,advance)
        with patch('spoolscribe.ui_catalogue.QFileDialog.getSaveFileName',return_value=(str(target),'JSON')):
            QTimer.singleShot(0,advance)
            while not done and not stop and time.monotonic()<deadline:w.app.processEvents()
        if not done:
            step,left,why=stop.get('at',(steps[0][0],len(steps),'deadline'))
            self.fail(f'journey did not finish: stopped before {step!r} ({left} steps left, {why}), '
                      f'active modal {QApplication.activeModalWidget()!r}, errors {errors!r}')
        self.assertEqual(errors,[])
        gc.collect()
        for fitter in list(ui_surfaces._FITTERS.values()):   # every live fitter keeps its state
            self.assertIn('fitting',fitter.__dict__);self.assertIsNotNone(fitter.dialog)
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['settings']['language'],'fr')
