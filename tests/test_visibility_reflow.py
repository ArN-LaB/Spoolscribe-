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


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class MinimumGeometryTests(unittest.TestCase):
    """B14/07: three panels at the announced minimum width, without overlap or cut actions."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self);i18n.set_language('fr')
        self.window.show();self.window.current_sku='PB05001';self.window._show_detail('PB05001')

    def settle(self):
        # Reflows reach the window through several queued layout passes: wait for a quiet stretch.
        w=self.window;quiet=0
        for _ in range(200):
            state=(w.minimumSize().toTuple(),w.size().toTuple())
            w.app.processEvents()
            stable=not getattr(w,'_minimum_fit_pending',False) and state==(w.minimumSize().toTuple(),w.size().toTuple())
            quiet=quiet+1 if stable else 0
            if quiet>=5:return
        self.fail('layout passes never settled')

    def check(self,step):
        from PySide6.QtCore import QPoint,QRect
        w=self.window;self.settle();s=w.splitter
        rect=lambda x,ref:QRect(x.mapTo(ref,QPoint(0,0)),x.size())
        panels=[s.widget(i) for i in range(s.count())];rects=[rect(p,s) for p in panels]
        diagnostic=(step,w.size().toTuple(),w.minimumWidth(),[(r.x(),r.width()) for r in rects],[p.minimumSizeHint().width() for p in panels])
        for i in range(3):
            self.assertTrue(QRect(0,0,s.width(),s.height()).contains(rects[i]),diagnostic)
            self.assertGreaterEqual(panels[i].width(),max(panels[i].minimumWidth(),panels[i].minimumSizeHint().width()),diagnostic)
            for j in range(i+1,3):self.assertFalse(rects[i].intersects(rects[j]),diagnostic)
        # The announced 860 px stays the minimum whenever the real layout fits in it.
        from spoolscribe import app_gui
        self.assertEqual(w.minimumWidth(),max(app_gui.MIN_WINDOW_WIDTH,w.minimumSizeHint().width()),diagnostic)
        self.assertGreaterEqual(w.width(),w.minimumWidth(),diagnostic)
        viewport=rect(w.detail_scroll.viewport(),w)
        if w.stack.currentIndex()==1:
            for button in (w.btn_similar,w.favorite_btn,w.btn_edit_physical,w.provenance_toggle,w.draft_save,w.draft_cancel):
                if button.isVisibleTo(w):
                    r=rect(button,w);self.assertTrue(viewport.left()<=r.left() and r.right()<=viewport.right(),(step,button.text()))
            for button in (w.btn_generate,w.btn_qr,w.btn_inspect,w.btn_open_out,w.hardware_change,w.export_details_button):
                if button.isVisibleTo(w):
                    self.assertTrue(rect(panels[2],w).contains(rect(button,w)),(step,button.text()))
                    self.assertGreaterEqual(button.width(),max(button.fontMetrics().horizontalAdvance(l) for l in button.text().splitlines())+8,(step,button.text()))
            for label in (w.title,w.hardware_name):
                for word in label.text().split():self.assertLessEqual(label.fontMetrics().horizontalAdvance(word),label.width(),(step,word))
        for button in (w.update_btn,w.columns_btn,w.previous_page,w.next_page):
            self.assertTrue(rect(panels[1],w).contains(rect(button,w)),(step,button.text()))

    def test_sizes_and_round_trip_keep_three_separate_panels(self):
        w=self.window
        for width in (860,1000,1280,1280,860,1000,1280,860):
            w.resize(width,600);self.check(f'selected-{width}')
        w._edit_physical();self.check('draft-860');w._cancel_draft()
        w.provenance_toggle.setChecked(True);self.check('details-860');w.provenance_toggle.setChecked(False)
        w.current_sku=None;w._show_empty();w.resize(860,600);self.check('empty-860')
        w._set_view_mode('grid');self.check('grid-860');w.resize(1280,600);self.check('grid-1280')

    def test_idle_window_stops_scheduling_layout_passes(self):
        """B14/11: once settled, an idle window posts no further layout pass (no CPU loop)."""
        from PySide6.QtCore import QEvent,QEventLoop,QObject,QTimer
        w=self.window
        class Requests(QObject):
            count=0
            def eventFilter(self,watched,event):
                if event.type()==QEvent.LayoutRequest:self.count+=1
                return False
        requests=Requests();w.installEventFilter(requests);self.addCleanup(w.removeEventFilter,requests)
        fits=[];fit=w._fit_window_minimum
        def counted():fits.append(1);fit()
        w._fit_window_minimum=counted;self.addCleanup(delattr,w,'_fit_window_minimum')
        def run(ms):
            loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
        w.resize(860,600)
        # Settle in a real event loop: a 50 ms slice without any layout pass and nothing pending.
        for _ in range(60):
            seen=(requests.count,len(fits));run(50)
            if not w._minimum_fit_pending and (requests.count,len(fits))==seen:break
        else:self.fail(('layout passes never settled',requests.count,len(fits)))
        self.assertGreater(len(fits),0)   # the resize and selection did go through the fit
        requests.count=0;fits.clear();run(600)
        self.assertFalse(w._minimum_fit_pending)
        self.assertEqual((requests.count,len(fits)),(0,0))
        # 860 x 600 natively; offscreen fonts may need a few more pixels, never an overlap.
        self.assertEqual(w.size().toTuple(),(max(860,w.minimumWidth()),600))
        self.check('idle-860')

    def test_narrow_rows_stack_and_restore_in_the_same_window(self):
        from PySide6.QtWidgets import QBoxLayout
        w=self.window;horizontal=QBoxLayout.Direction.LeftToRight
        rows=lambda:{name:getattr(w,name) for name in ('characteristic_row','export_action_row','secondary_export_row','hero_head',
                                                      'hero_body','hardware_effect_row','catalogue_state')}
        def state(width):
            w.resize(width,600);self.settle();seen={}
            for name,row in rows().items():
                if not row.isVisibleTo(w):continue
                fits=row.width()>=row._needed()
                self.assertEqual(row.box.direction()==horizontal,fits,(width,name,row.width(),row._needed()))
                seen[name]=fits
            self.assertGreaterEqual(w.btn_qr.height(),w.btn_qr.minimumSizeHint().height(),width)   # two-line label whole
            self.assertEqual(w._export_actions_inline,seen['export_action_row'])
            return seen
        first={width:state(width) for width in (1280,860,1000)}
        self.assertNotEqual(first[860],first[1280])   # the narrow width really reflows something
        for width in (860,1280,1000,860):self.assertEqual(state(width),first[width],width)

    def test_low_window_scrolls_filter_sections_instead_of_overlapping_them(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.resize(860,600);self.settle()
        frames=[section['frame'] for section in w._sections.values()]
        spans=sorted((f.mapTo(w.sidebar_scroll.widget(),QPoint(0,0)).y(),f.height()) for f in frames)
        for (top,height),(next_top,_) in zip(spans,spans[1:]):self.assertLessEqual(top+height,next_top,spans)
        self.assertTrue(w.sidebar_scroll.isAncestorOf(w.state_list))
        self.assertGreaterEqual(w.state_scope.y(),w.state_list.y()+w.state_list.height()-1)
