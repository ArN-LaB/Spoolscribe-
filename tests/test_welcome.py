"""B18/A2: optional quick welcome for a brand-new profile, without network, writes or duplicated windows."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_gui as fixture
from spoolscribe import core, i18n


def wait_for(predicate,timeout_ms):
    """Run the real Qt event loop (never a sleep) until ``predicate`` holds or the time is up."""
    import time
    from PySide6.QtTest import QTest
    deadline=time.monotonic()+timeout_ms/1000
    while not predicate():
        if time.monotonic()>deadline:return False
        QTest.qWait(10)
    return True


class NewProfileDetectionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.cfg=self.root/'config.json';self.home=self.root/'home'

    def new(self):
        return core.is_new_profile(self.cfg,self.home)

    def test_only_nothing_at_all_is_a_new_profile(self):
        self.assertTrue(self.new())                                   # nothing yet
        self.home.mkdir();self.assertTrue(self.new())                 # empty folder
        (self.home/'.DS_Store').write_bytes(b'x');self.assertTrue(self.new())
        (self.home/'data').mkdir();self.assertFalse(self.new())       # user data without configuration: existing
        for content in (b'{}',b'{not json',b'[]'):
            with self.subTest(content=content):
                (self.home/'data').rmdir() if (self.home/'data').exists() else None
                self.cfg.write_bytes(content);self.assertFalse(self.new())   # present, even unreadable: existing
        self.cfg.unlink();self.cfg.mkdir();self.assertFalse(self.new())      # inaccessible as a file: existing

    def test_an_unreadable_data_folder_is_not_called_new(self):
        self.home.mkdir()
        with patch.object(Path,'iterdir',side_effect=PermissionError('denied')):
            self.assertFalse(self.new())


class RecordWelcomeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.cfg=Path(tmp.name)/'config.json'
        p=patch.object(core,'CONFIG_PATH',str(self.cfg));p.start();self.addCleanup(p.stop)

    def test_marker_is_local_and_never_written_over_an_unreadable_configuration(self):
        core.record_welcome('skipped');raw=json.loads(self.cfg.read_text())
        self.assertEqual(raw['welcome'],'skipped');self.assertIsNone(raw['network_consent'])   # skipping is not refusing
        raw.update(language='en',preferred_weight_g=750);self.cfg.write_text(json.dumps(raw))
        core.record_welcome('done');raw=json.loads(self.cfg.read_text())
        self.assertEqual((raw['welcome'],raw['language'],raw['preferred_weight_g']),('done','en',750))   # choices preserved
        self.assertNotIn('welcome',core.exportable_settings(raw,include_layout=True,include_export_path=True))
        self.assertIn('welcome',core.MACHINE_STATE_KEYS)
        self.cfg.write_bytes(b'{broken');before=self.cfg.read_bytes()
        with self.assertRaises(OSError):core.record_welcome('done')
        self.assertEqual(self.cfg.read_bytes(),before)                 # no reset, no overwrite
        with self.assertRaises(ValueError):core.record_welcome('maybe')


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class WelcomeWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()

    def window(self,*,config=None,data=False):
        """Main window on an isolated profile: nothing, configuration, or user data only."""
        from spoolscribe import app_gui
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        home=root/'home';self.cfg=root/'config.json'
        if data:
            (home/'data').mkdir(parents=True);(home/'data'/'polymaker_db.json').write_text(json.dumps(fixture.catalogue()),encoding='utf-8')
        if config is not None:self.cfg.write_text(json.dumps(config),encoding='utf-8')
        paths=patch.multiple(core,DB_PATH=str(home/'data'/'polymaker_db.json'),DATA_HOME=str(home),CONFIG_PATH=str(self.cfg),
                             OUTPUT_DIR=str(home/'output'),ORCA_DIR=str(home/'orca_profiles'))
        paths.start();self.addCleanup(paths.stop)
        errors=patch('spoolscribe.app_gui.QMessageBox.critical',side_effect=lambda *a,**k:self.fail(f'unexpected error: {a[-1]}'))
        errors.start();self.addCleanup(errors.stop)
        w=app_gui.MainWindow();self.addCleanup(w.close);i18n.set_language('fr')
        self.calls=[]
        for name in ('_choose_sources','_start_update','_ask_network_consent','_open_hardware','_open_settings'):
            spy=patch.object(w,name,side_effect=lambda *a,_n=name,**k:self.calls.append((_n,a,k)));spy.start();self.addCleanup(spy.stop)
        return w

    def start(self,w):
        w.show();w.app.processEvents();w._maybe_auto_update();w.app.processEvents()
        return getattr(w,'_welcome_dialog',None)

    def buttons(self,dlg):
        from PySide6.QtWidgets import QPushButton
        return {b.property('welcome_topic') or b.text():b for b in dlg.findChildren(QPushButton)}

    def test_a_new_profile_gets_the_optional_welcome_instead_of_the_sources_window(self):
        from PySide6.QtWidgets import QDialog
        w=self.window();self.assertTrue(w._new_profile)
        dlg=self.start(w)
        self.assertIsNotNone(dlg);self.assertTrue(dlg.isVisible());self.assertFalse(dlg.isModal())
        self.assertEqual(self.calls,[])                                # no sources window, no consent, no worker
        self.assertFalse(self.cfg.exists())                            # nothing written by showing it
        b=self.buttons(dlg);self.assertEqual(sorted(k for k in b if k in ('hardware','filaments','catalogue')),['catalogue','filaments','hardware'])
        b['hardware'].click();b['filaments'].click();b['catalogue'].click()
        self.assertEqual([c[0] for c in self.calls],['_open_hardware','_open_settings','_choose_sources'])   # each on its own click
        self.assertEqual(self.calls[1][2],{'filaments_tab':True})
        self.assertIs(w._open_welcome(),dlg)                           # reopening raises the same window
        b['Passer pour le moment'].click();w.app.processEvents()
        self.assertFalse(dlg.isVisible());self.assertEqual(dlg.result(),QDialog.Rejected)
        raw=json.loads(self.cfg.read_text());self.assertEqual(raw['welcome'],'skipped');self.assertIsNone(raw['network_consent'])
        self.calls.clear();w._maybe_auto_update();w.app.processEvents()
        self.assertIsNone(w._welcome_dialog);self.assertNotIn('_start_update',[c[0] for c in self.calls])

    def test_finish_close_and_reopen_from_the_menu(self):
        w=self.window();dlg=self.start(w)
        self.buttons(dlg)['Terminer'].click();w.app.processEvents()
        self.assertEqual(json.loads(self.cfg.read_text())['welcome'],'done')
        action=next(a for a in w.main_menu.actions() if a.text()=='Accueil rapide…')
        action.trigger();w.app.processEvents();again=w._welcome_dialog;self.assertTrue(again.isVisible())
        again.close();w.app.processEvents()                            # window close: remembered as skipped
        self.assertEqual(json.loads(self.cfg.read_text())['welcome'],'skipped');self.assertEqual(self.calls,[])

    def test_existing_profiles_keep_their_start_up_route(self):
        cases=[('config',dict(core.DEFAULT_CONFIG,language='fr',network_consent=False),False),('data',None,True)]
        for name,config,data in cases:
            with self.subTest(name=name):
                w=self.window(config=config,data=data);self.assertFalse(w._new_profile)
                self.assertIsNone(self.start(w))                      # no welcome imposed
                w.close()
        w=self.window(config=dict(core.DEFAULT_CONFIG,language='fr'),data=True);self.assertIsNone(self.start(w))
        self.assertEqual([c[0] for c in self.calls],['_choose_sources'])   # never asked: unchanged start-up route
        self.assertEqual(self.calls[0][2],{'startup':True})

    def test_an_unreadable_configuration_is_kept_and_not_called_new(self):
        from spoolscribe import app_gui
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        cfg=root/'config.json';cfg.write_bytes(b'{broken');home=root/'home'
        with patch.multiple(core,DB_PATH=str(home/'data'/'polymaker_db.json'),DATA_HOME=str(home),CONFIG_PATH=str(cfg),
                            OUTPUT_DIR=str(home/'output'),ORCA_DIR=str(home/'orca_profiles')):
            self.assertFalse(core.is_new_profile())
        self.assertEqual(cfg.read_bytes(),b'{broken')

    def test_a_failed_write_is_said_once_and_blocks_nothing(self):
        w=self.window();dlg=self.start(w)
        with patch('spoolscribe.core.save_config',side_effect=OSError('disque plein (essai)')):
            self.buttons(dlg)['Terminer'].click();w.app.processEvents()
        self.assertIn('disque plein (essai)',w.status.currentMessage());self.assertFalse(self.cfg.exists())
        self.assertIsNone(w._welcome_dialog);self.assertEqual(self.calls,[])

    def test_a_draft_or_restoration_keeps_its_protection(self):
        w=self.window()
        w._draft={'sku':'x'};self.assertIsNone(self.start(w));w._draft=None   # guarded before any welcome
        self.assertTrue(w._new_profile);self.assertEqual(self.calls,[])

    def test_an_open_welcome_does_no_work_at_rest(self):
        from PySide6.QtCore import QEvent,QObject,QAbstractAnimation
        from PySide6.QtTest import QTest
        w=self.window();dlg=self.start(w)
        self.assertTrue(wait_for(lambda:w._welcome_opening.done,5000));QTest.qWait(80)   # A4: measured after the opening
        self.assertEqual([a for a in dlg.findChildren(QAbstractAnimation) if a.state()!=QAbstractAnimation.Stopped],[])
        class Count(QObject):
            def __init__(c):super().__init__();c.n=[]
            def eventFilter(c,obj,event):
                mine=obj is dlg or (hasattr(obj,'window') and callable(obj.window) and obj.window() is dlg)
                if event.type()==QEvent.LayoutRequest or mine and event.type() in (QEvent.Timer,QEvent.Paint,QEvent.UpdateRequest):
                    c.n.append((event.type().name,type(obj).__name__,obj.objectName()))
                return False
        count=Count();w.app.installEventFilter(count)
        try:QTest.qWait(300)
        finally:w.app.removeEventFilter(count)
        self.assertEqual(count.n,[]);dlg.reject()

    def test_the_five_actions_share_the_longest_label_width_in_each_language(self):
        """B18/C21: three topics and the footer pair, one width per language and font; height 32,
        topics right-aligned, nothing clipped or outside the window, natural and 860×600."""
        import os
        from PySide6.QtCore import QPoint
        from spoolscribe import ui_opening
        w=self.window();w.show();w.app.processEvents();self.addCleanup(i18n.set_language,'fr');widths={}
        for code in ('fr','en','es','zh_CN'):
            with self.subTest(language=code):
                i18n.set_language(code)
                with patch.dict(os.environ,{ui_opening.REDUCE_MOTION_ENV:'1'}):dlg=w._open_welcome()
                try:
                    w.app.processEvents();found=self.buttons(dlg)
                    topics=[found[name] for name in ('hardware','filaments','catalogue')]
                    # By role, not isDefault(): on Cocoa the focused button is the temporary default.
                    done=next(b for b in found.values() if b.objectName()=='primary');skip=next(b for b in found.values() if b not in topics and b is not done)
                    group=topics+[skip,done];self.assertEqual(done.text(),i18n.tr('Terminer'))
                    for size in (None,(860,600)):
                        if size:dlg.resize(*size);w.app.processEvents()
                        self.assertEqual(len({b.width() for b in group}),1,[(b.text(),b.width()) for b in group])
                        self.assertEqual({b.height() for b in group},{32})
                        self.assertGreaterEqual(group[0].width(),max(b.sizeHint().width() for b in group))   # longest label whole
                        self.assertEqual(len({b.mapTo(dlg,QPoint(b.width(),0)).x() for b in topics}),1)
                        self.assertLess(skip.mapTo(dlg,QPoint(0,0)).x(),done.mapTo(dlg,QPoint(0,0)).x())
                        for b in group:
                            at=b.mapTo(dlg,QPoint(0,0))
                            self.assertTrue(dlg.rect().contains(at) and dlg.rect().contains(at+QPoint(b.width()-1,b.height()-1)),b.text())
                    widths[code]=group[0].width()
                finally:
                    dlg.reject();w.app.processEvents()
        self.assertGreater(len(set(widths.values())),1,widths)   # measured per language, not one fixed number


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class WelcomeOpeningTests(unittest.TestCase):
    """B18/A4 C18: the Companion opening inside the quick welcome — once, finite, safe, nothing at rest."""
    setUpClass=WelcomeWindowTests.setUpClass
    window=WelcomeWindowTests.window
    start=WelcomeWindowTests.start

    def setUp(self):
        env=patch.dict('os.environ');env.start();self.addCleanup(env.stop)
        import os;os.environ.pop('SPOOLSCRIBE_REDUCE_MOTION',None)

    def parts(self,dlg):
        from PySide6.QtWidgets import QLabel
        from spoolscribe import ui_opening
        return dlg.findChild(ui_opening.StaticLogo,'welcomeLogo'),dlg.findChild(QLabel,'welcomeTitle'),dlg.findChild(ui_opening._OpeningOverlay)

    def assert_final(self,dlg):
        from PySide6.QtCore import QPoint,QAbstractAnimation
        from PySide6.QtWidgets import QWidget
        logo,title,overlay=self.parts(dlg)
        self.assertTrue(logo.is_painted());self.assertTrue(overlay is None or not overlay.isVisible())
        self.assertEqual([x for x in dlg.findChildren(QWidget) if x.graphicsEffect() is not None],[])
        self.assertEqual([a for a in dlg.findChildren(QAbstractAnimation) if a.state()!=QAbstractAnimation.Stopped],[])
        at=logo.mapTo(dlg,QPoint(0,0));self.assertEqual(logo.size().width(),36)
        self.assertLess(at.x(),40);self.assertLess(at.y(),40)                       # top left, beside the title
        self.assertLess(logo.mapTo(dlg,QPoint(0,0)).x(),title.mapTo(dlg,QPoint(0,0)).x())

    def test_centre_pulse_move_then_top_left_once(self):
        import time
        from PySide6.QtTest import QTest
        from spoolscribe import ui_opening
        w=self.window();t0=time.perf_counter();dlg=self.start(w);op=w._welcome_opening
        self.assertTrue(op.played);self.assertTrue(op.is_animating())
        logo,title,overlay=self.parts(dlg);self.assertFalse(logo.is_painted());self.assertTrue(overlay.isVisible())
        start=op.logo_geometry(0.0);self.assertEqual(start.width(),112)
        self.assertAlmostEqual(start.center().x(),dlg.width()/2,delta=0.5);self.assertAlmostEqual(start.center().y(),dlg.height()/2,delta=0.5)
        self.assertAlmostEqual(op.logo_geometry(0.16).width(),112*1.04,delta=0.01)                # discreet pulse
        end=op.logo_geometry(1.0);self.assertEqual(end.width(),36)
        self.assertEqual(op.reveal_opacity(0.5),0.0);self.assertEqual(op.reveal_opacity(1.0),1.0)
        self.assertEqual(title.graphicsEffect().opacity(),0.0)
        self.assertTrue(wait_for(lambda:op.progress>=0.45,3000))                            # real intermediate frame
        mid=overlay.logo_rect;self.assertTrue(36<mid.width()<112*1.04,mid)
        self.assertTrue(end.center().x()<mid.center().x()<dlg.width()/2,mid)
        self.assertTrue(wait_for(lambda:op.done,5000));elapsed=time.perf_counter()-t0
        self.assertGreaterEqual(elapsed,0.70,elapsed)                                             # never cut short
        self.assert_final(dlg)
        dlg.reject();w.app.processEvents()
        again=w._open_welcome();w.app.processEvents()                                              # reopening: no replay
        self.assertFalse(w._welcome_opening.played);self.assertTrue(w._welcome_opening.done);self.assert_final(again)
        w._on_os_scheme_changed();w.app.processEvents()                                            # theme change: no replay
        self.assertTrue(w._welcome_opening.done);self.assert_final(again);again.reject()

    def test_early_close_and_resize_are_safe(self):
        from PySide6.QtTest import QTest
        w=self.window();dlg=self.start(w);op=w._welcome_opening
        self.assertTrue(wait_for(lambda:op.progress>0.1,3000))
        dlg.resize(dlg.width()+120,dlg.height()+40);w.app.processEvents()
        overlay=self.parts(dlg)[2];self.assertEqual(overlay.geometry(),dlg.rect())                 # follows the panel
        from PySide6.QtCore import QPoint,QRectF
        logo=self.parts(dlg)[0];self.assertEqual(op.logo_geometry(1.0),QRectF(logo.mapTo(dlg,QPoint(0,0)),logo.size()))   # lands on the moved slot
        dlg.reject();w.app.processEvents()                                                          # closed mid-way
        self.assertTrue(op.done);self.assert_final(dlg)
        self.assertEqual(json.loads(self.cfg.read_text())['welcome'],'skipped')                    # A3 behaviour unchanged

    def test_reduced_motion_and_missing_logo_give_the_final_state_at_once(self):
        import os
        from spoolscribe import ui_opening
        os.environ['SPOOLSCRIBE_REDUCE_MOTION']='1';self.assertTrue(ui_opening.reduced_motion())
        w=self.window();dlg=self.start(w);op=w._welcome_opening
        self.assertFalse(op.played);self.assertTrue(op.done);self.assertIsNone(self.parts(dlg)[2]);self.assert_final(dlg)
        dlg.reject();w.close()
        os.environ.pop('SPOOLSCRIBE_REDUCE_MOTION')
        self.assertIsInstance(ui_opening.reduced_motion(),bool)                                     # real system read, never written
        with patch('spoolscribe.core.app_logo_abs_path',return_value=None):
            w=self.window();dlg=self.start(w);op=w._welcome_opening
        self.assertTrue(op.done);self.assertFalse(op.played)
        self.assertEqual(self.parts(dlg)[:1]+self.parts(dlg)[2:],(None,None))                       # sober: title only, no timer
        self.assertFalse(getattr(w,'_welcome_opening_played',False));dlg.reject()


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class UsualSpoolDestinationTests(unittest.TestCase):
    """B18/A4 C17: the welcome button opens the real Settings on Filaments / Ma bobine habituelle."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass();cls.app=fixture.GuiTests.app
    def setUp(self):fixture.GuiTests.setUp(self)

    def settings(self,inspect,trigger):
        from PySide6.QtWidgets import QDialog
        seen={}
        def exec_(dialog):
            from PySide6.QtWidgets import QComboBox
            from spoolscribe.ui_surfaces import ReadingTabs
            dialog.show();self.app.processEvents();tabs=dialog.findChild(ReadingTabs)
            seen.update(label=tabs.tabText(tabs.currentIndex()),
                        visible={n:dialog.findChild(QComboBox,n).isVisibleTo(dialog) for n in ('preferred_weight_g','preferred_packaging')})
            return inspect(dialog)
        with patch('spoolscribe.app_gui.QDialog.exec',new=exec_):trigger()
        return seen

    def welcome_button(self):
        from PySide6.QtWidgets import QPushButton
        dlg=self.window._open_welcome();self.addCleanup(dlg.reject);self.app.processEvents()
        return next(b for b in dlg.findChildren(QPushButton) if b.property('welcome_topic')=='filaments')

    def test_welcome_button_shows_filaments_mass_and_format(self):
        from PySide6.QtWidgets import QDialog,QComboBox,QDialogButtonBox
        button=self.welcome_button();before=Path(core.CONFIG_PATH).read_bytes()
        def cancel(dialog):
            weight=dialog.findChild(QComboBox,'preferred_weight_g');weight.setCurrentIndex(weight.findData(750));return QDialog.Rejected
        seen=self.settings(cancel,button.click)
        self.assertEqual(seen,{'label':'Filaments','visible':{'preferred_weight_g':True,'preferred_packaging':True}})
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)                                # Annuler: neutral
        def save(dialog):
            weight=dialog.findChild(QComboBox,'preferred_weight_g');weight.setCurrentIndex(weight.findData(750))
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click();return dialog.result()
        self.settings(save,button.click)
        self.assertEqual(core.load_config()['preferred_weight_g'],750)                              # only on Enregistrer
        from spoolscribe.ui_widgets import WrapLabel
        self.assertIn('750 g',button.window().findChild(WrapLabel,'welcome_filaments_state').text())   # summary refreshed

    def test_normal_settings_and_colours_destinations_are_unchanged(self):
        from PySide6.QtWidgets import QDialog
        self.assertEqual(self.settings(lambda d:QDialog.Rejected,self.window._open_settings)['label'],'Catalogue')
        self.assertEqual(self.settings(lambda d:QDialog.Rejected,lambda:self.window._open_settings(colour_tab=True))['label'],'Couleurs')


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class FirstLaunchThroughMainTests(unittest.TestCase):
    """B18/A3 F1: the real app_gui.main(), its data folder, diagnostics and real QLockFile, then the real event loop."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass();cls.app=fixture.GuiTests.app

    def setUp(self):
        import os
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.home=self.root/'home';self.cfg=self.root/'config.json'
        self.addCleanup(i18n.set_language,'fr')
        env=patch.dict(os.environ);env.start();self.addCleanup(env.stop)   # --diagnostics exports its flag
        os.environ.pop('SPOOLSCRIBE_DIAGNOSTICS',None)

    def launch(self,*argv,status=None):
        """Run main() once; facts are read inside its event loop, after the 400 ms start-up callback."""
        from PySide6.QtCore import QEventLoop,QLockFile,QTimer
        from spoolscribe import app_gui,diagnostics,recovery
        facts={'sources':[],'workers':[]}
        foreign=set(self.app.topLevelWidgets())   # windows left by other tests: never observed, closed or saved here
        def event_loop():
            loop=QEventLoop()
            def observe():
                win=next(w for w in self.app.topLevelWidgets() if isinstance(w,app_gui.MainWindow) and w not in foreign)
                dlg=getattr(win,'_welcome_dialog',None)
                other=QLockFile(str(self.home/'spoolscribe.instance.lock'));other.setStaleLockTime(0)
                facts.update(window=True,welcome=bool(dlg and dlg.isVisible()),config=self.cfg.exists(),
                             config_bytes=self.cfg.read_bytes() if self.cfg.is_file() else None,
                             second_lock=other.tryLock(0),files=sorted(p.name for p in self.home.iterdir()))
                if dlg:dlg.reject()
                win.close();loop.quit()
            QTimer.singleShot(650,observe);loop.exec();return 0
        db=self.home/'data'/'polymaker_db.json'
        with patch.multiple(core,DB_PATH=str(db),DATA_HOME=str(self.home),DATA_DIR=str(db.parent),CONFIG_PATH=str(self.cfg),
                            OUTPUT_DIR=str(self.home/'output'),ORCA_DIR=str(self.home/'orca_profiles')), \
             patch.object(recovery,'STARTUP_STATUS',status), \
             patch('spoolscribe.app_gui.QApplication',return_value=self.app) as application, \
             patch.object(self.app,'exec',side_effect=event_loop), \
             patch('spoolscribe.app_gui.QMessageBox.information',side_effect=lambda *a,**k:facts.setdefault('information',a[-1])), \
             patch('spoolscribe.app_gui.QMessageBox.critical',side_effect=lambda *a,**k:self.fail(f'unexpected error: {a[-1]}')), \
             patch.object(app_gui.MainWindow,'_choose_sources',lambda w,*a,**k:w in foreign or facts['sources'].append(k)), \
             patch.object(app_gui.MainWindow,'_start_update',lambda w,*a,**k:w in foreign or facts['workers'].append(k)), \
             patch('sys.argv',['SpoolScribe',*argv]):
            application.instance.return_value=self.app
            try:facts['code']=app_gui.main()
            finally:
                diagnostics.shutdown(release_faulthandler=True)
                for w in self.app.topLevelWidgets():
                    if w not in foreign:w.close()   # only this launch's windows, while its paths are patched
        after=QLockFile(str(self.home/'spoolscribe.instance.lock'));after.setStaleLockTime(0)
        facts['released']=after.tryLock(0);after.unlock() if facts['released'] else None
        return facts

    def test_a_truly_empty_profile_gets_the_welcome_through_main(self):
        self.assertTrue(core.is_new_profile(str(self.cfg),str(self.home)))
        f=self.launch()
        self.assertEqual(f['code'],0);self.assertTrue(f['welcome'])
        self.assertEqual((f['sources'],f['workers']),([],[]))           # no sources window instead, no worker
        self.assertFalse(f['second_lock'])                              # single instance still enforced
        self.assertIn('spoolscribe.instance.lock',f['files'])          # the lock existed: decided before it
        self.assertFalse(f['config']);self.assertTrue(f['released'])

    def test_diagnostics_written_before_qapplication_do_not_hide_the_welcome(self):
        f=self.launch('--diagnostics')
        self.assertTrue(f['welcome']);self.assertEqual(f['sources'],[]);self.assertIn('diagnostics',f['files'])

    def test_existing_profiles_keep_their_route_through_main(self):
        cases={'config':lambda:self.cfg.write_text(json.dumps(dict(core.DEFAULT_CONFIG,language='fr')),encoding='utf-8'),
               'unknown file':lambda:(self.home.mkdir(),(self.home/'notes.txt').write_text('x')),
               'data':lambda:((self.home/'data').mkdir(parents=True),
                              (self.home/'data'/'polymaker_db.json').write_text(json.dumps(fixture.catalogue()),encoding='utf-8'))}
        for name,make in cases.items():
            with self.subTest(name=name):
                self.setUp();make();f=self.launch()
                self.assertTrue(f['window']);self.assertFalse(f['welcome'])
                self.assertEqual(f['sources'],[{'startup':True}])       # unchanged consent route, never the welcome
                self.assertEqual(f['workers'],[]);self.assertTrue(f['released'])

    def test_unreadable_configuration_is_kept_and_not_new(self):
        self.cfg.write_bytes(b'{broken');f=self.launch()
        self.assertFalse(f['welcome']);self.assertEqual(f['config_bytes'],b'{broken')   # untouched by the start-up
        # (Closing the window saves the layout, as at HEAD: outside this start-up check.)

    def test_a_start_up_recovery_is_never_a_new_profile(self):
        status={'state':'cleaned','code':'x','template':None,'values':{},'message':'nettoyé (essai)'}
        f=self.launch(status=status)
        self.assertFalse(f['welcome']);self.assertEqual(f['sources'],[{'startup':True}])

    def test_a_second_instance_is_refused_without_a_window(self):
        from PySide6.QtCore import QLockFile
        self.home.mkdir();held=QLockFile(str(self.home/'spoolscribe.instance.lock'));held.setStaleLockTime(0)
        self.assertTrue(held.tryLock(0));self.addCleanup(held.unlock)
        f=self.launch()
        self.assertEqual(f['code'],0);self.assertNotIn('window',f);self.assertIn('déjà ouvert',f['information'])
        self.assertFalse(f['released']);self.assertFalse(self.cfg.exists())
