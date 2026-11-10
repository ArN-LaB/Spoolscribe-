"""System UI language detection and restart lifecycle; no real user settings/apps."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from spoolscribe import core
from spoolscribe import i18n
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT,'PySide6 not installed')
class SystemLanguageTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language('fr')

    def test_macos_preferred_languages_override_a_c_or_english_qt_locale(self):
        from PySide6.QtCore import QLocale
        for qt in (['C'],['en-US']):
            with patch.object(i18n.sys,'platform','darwin'), patch('spoolscribe.i18n._macos_preferred_languages',return_value=['fr-FR']),patch.object(QLocale,'system') as system:
                system.return_value.uiLanguages.return_value=qt
                self.assertEqual(i18n.system_ui_languages(),['fr-FR'])
                self.assertEqual(i18n.resolve_language('auto',i18n.system_ui_languages()),'fr')

    def test_macos_missing_preferences_falls_back_to_qt(self):
        from PySide6.QtCore import QLocale
        with patch.object(i18n.sys,'platform','darwin'),patch('spoolscribe.i18n._macos_preferred_languages',return_value=[]),patch.object(QLocale,'system') as system:
            system.return_value.uiLanguages.return_value=['es-MX']
            self.assertEqual(i18n.system_ui_languages(),['es-MX'])

    def test_valid_unsupported_native_language_keeps_english_fallback(self):
        from PySide6.QtCore import QLocale
        with patch.object(i18n.sys,'platform','darwin'),patch('spoolscribe.i18n._macos_preferred_languages',return_value=['de-DE']),patch.object(QLocale,'system') as system:
            system.return_value.uiLanguages.return_value=['fr-FR']
            self.assertEqual(i18n.resolve_language('auto',i18n.system_ui_languages()),'en')
            self.assertEqual(i18n.resolve_language('zh_CN',i18n.system_ui_languages()),'zh_CN')

    def test_other_platforms_use_qt_without_loading_corefoundation(self):
        from PySide6.QtCore import QLocale
        for platform in ('win32','linux'):
            with patch.object(i18n.sys,'platform',platform),patch('spoolscribe.i18n._macos_preferred_languages') as native,patch.object(QLocale,'system') as system:
                system.return_value.uiLanguages.return_value=['es-ES']
                self.assertEqual(i18n.system_ui_languages(),['es-ES']);native.assert_not_called()

    def test_invalid_locale_entries_are_ignored(self):
        self.assertEqual(i18n.resolve_language('auto',[None,42,'','C','fr_FR']),'fr')


@unittest.skipUnless(fixture.HAS_QT,'PySide6 not installed')
class RestartInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.GuiTests.setUpClass.__func__)

    def setUp(self):
        timer=patch('spoolscribe.app_gui.QTimer.singleShot');timer.start();self.addCleanup(timer.stop)
        fixture.GuiTests.setUp(self)
        self.addCleanup(i18n.set_language,'fr')

    @staticmethod
    def select_spanish(dialog):
        from PySide6.QtWidgets import QComboBox,QDialog
        combo=dialog.findChild(QComboBox,'interface_language')
        combo.setCurrentIndex(combo.findData('es'))
        return QDialog.Accepted

    def test_prompt_only_after_language_change_has_been_saved(self):
        from PySide6.QtWidgets import QDialog
        w=self.window
        def saved():self.assertEqual(core.load_config()['language'],'es')
        with patch.object(QDialog,'exec',self.select_spanish),patch.object(w,'_offer_language_restart',side_effect=saved) as prompt:
            w._open_settings();prompt.assert_called_once()
        self.assertEqual(i18n.language(),'fr')

    def test_cancel_unchanged_and_failed_save_never_propose_restart(self):
        from PySide6.QtWidgets import QDialog
        w=self.window
        with patch.object(w,'_offer_language_restart') as prompt:
            with patch.object(QDialog,'exec',return_value=QDialog.Rejected):w._open_settings()
            with patch.object(QDialog,'exec',return_value=QDialog.Accepted):w._open_settings()
            with patch.object(QDialog,'exec',self.select_spanish),patch.object(core,'save_config',side_effect=OSError('fixture')),patch('spoolscribe.app_gui.QMessageBox.critical'):
                w._open_settings()
            prompt.assert_not_called()

    def test_later_keeps_window_and_saved_language(self):
        from PySide6.QtWidgets import QMessageBox
        w=self.window;w.show()
        def later(box):
            self.assertEqual(len(box.buttons()),2)
            self.assertTrue(any(b.text()=='Redémarrer maintenant' for b in box.buttons()))
            next(b for b in box.buttons() if b.text()=='Plus tard').click()
            return 0
        with patch.object(QMessageBox,'exec',later),patch.object(w,'_request_language_restart') as restart:
            w._offer_language_restart();restart.assert_not_called()
        self.assertTrue(w.isVisible())

    def test_active_update_disables_restart_and_never_cancels_worker(self):
        from PySide6.QtWidgets import QMessageBox
        w=self.window;worker=Mock();worker.isRunning.return_value=True;w.worker=worker
        def inspect(box):
            now=next(b for b in box.buttons() if b.text()=='Redémarrer maintenant')
            self.assertFalse(now.isEnabled())
            return 0
        with patch.object(QMessageBox,'exec',inspect),patch.object(w,'close') as close:
            w._offer_language_restart();w._request_language_restart();close.assert_not_called()
        worker.cancel.set.assert_not_called();w.worker=None

    def test_now_requests_clean_shutdown_and_preserves_preferences(self):
        from spoolscribe import app_gui
        w=self.window
        with patch.object(w,'close',return_value=True) as close,patch.object(w.app,'exit') as exit_app:
            w._request_language_restart();close.assert_called_once();exit_app.assert_called_once_with(app_gui.RESTART_EXIT_CODE)
        self.assertTrue(w._restart_requested)

    def test_relaunch_happens_after_unlock_and_launch_error_keeps_app_available(self):
        from spoolscribe import app_gui
        app=Mock();window=Mock();window._restart_requested=True;lock=Mock()
        app.exec.side_effect=[app_gui.RESTART_EXIT_CODE,0];lock.tryLock.return_value=True
        def launch(entry):
            lock.unlock.assert_called_once()
            raise OSError('cannot start fixture')
        with patch('spoolscribe.app_gui.launch_replacement',side_effect=launch),patch('spoolscribe.app_gui.QMessageBox.warning') as warning:
            self.assertEqual(app_gui.run_application(app,window,lock),0)
        lock.tryLock.assert_called_once_with(200);window.show.assert_called_once();warning.assert_called_once()
        self.assertFalse(window._restart_requested)

    def test_successful_restart_spawns_once_after_unlock(self):
        from spoolscribe import app_gui
        app=Mock();app.exec.return_value=app_gui.RESTART_EXIT_CODE
        window=Mock();window._restart_requested=True;lock=Mock()
        with patch('spoolscribe.app_gui.launch_replacement',side_effect=lambda entry:lock.unlock.assert_called_once()) as launch:
            self.assertEqual(app_gui.run_application(app,window,lock),0)
        launch.assert_called_once();app.exec.assert_called_once();lock.tryLock.assert_not_called()

    def test_importing_a_different_language_also_offers_restart_after_save(self):
        from PySide6.QtWidgets import QFileDialog
        w=self.window
        path=Path(self.tmp.name)/'language-settings.json'
        core.export_settings(path)
        document=json.loads(path.read_text(encoding='utf-8'));document['settings']['language']='zh_CN'
        path.write_text(json.dumps(document),encoding='utf-8')
        with patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'JSON')),patch.object(w,'_offer_language_restart') as prompt,patch.object(w,'_confirm_settings_import',return_value=True):
            w._import_settings();prompt.assert_called_once()
        self.assertEqual(core.load_config()['language'],'zh_CN')
        self.assertEqual(i18n.language(),'fr')

    def test_relaunch_error_does_not_reopen_without_the_data_lock(self):
        from spoolscribe import app_gui
        app=Mock();app.exec.return_value=app_gui.RESTART_EXIT_CODE
        window=Mock();window._restart_requested=True;lock=Mock();lock.tryLock.return_value=False
        with patch('spoolscribe.app_gui.launch_replacement',side_effect=OSError('fixture')),patch('spoolscribe.app_gui.QMessageBox.critical') as critical:
            self.assertEqual(app_gui.run_application(app,window,lock),1)
        window.show.assert_not_called();critical.assert_called_once()


class RelaunchCommandTests(unittest.TestCase):
    def test_frozen_process_uses_the_same_binary_with_reset_environment(self):
        from spoolscribe import app_lifecycle
        with patch.object(app_lifecycle.sys,'frozen',True,create=True),patch.object(app_lifecycle.sys,'executable','/tmp/SpoolScribe.app/Contents/MacOS/SpoolScribe'),patch.object(app_lifecycle.subprocess,'Popen') as spawn:
            app_lifecycle.launch_replacement('/untrusted/entry.py')
        args,kwargs=spawn.call_args
        self.assertEqual(args[0],['/tmp/SpoolScribe.app/Contents/MacOS/SpoolScribe'])
        self.assertEqual(kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'1')
        self.assertNotIn('shell',kwargs)

    def test_source_process_uses_absolute_entry_and_same_interpreter(self):
        from spoolscribe import app_lifecycle
        with patch.object(app_lifecycle.sys,'frozen',False,create=True),patch.object(app_lifecycle.subprocess,'Popen') as spawn:
            app_lifecycle.launch_replacement('app_gui.py')
        self.assertEqual(spawn.call_args.args[0],[sys.executable,str(Path('app_gui.py').resolve())])
        self.assertNotIn('PYINSTALLER_RESET_ENVIRONMENT',spawn.call_args.kwargs['env'])

    @unittest.skipUnless(fixture.HAS_QT,'PySide6 not installed')
    def test_real_source_relaunch_uses_new_process_and_reacquires_data_lock(self):
        import textwrap
        import time
        from tests.support import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);wrapper=directory/'restart_fixture.py'
            wrapper.write_text(textwrap.dedent('''
                import json, os
                from pathlib import Path
                from unittest.mock import patch
                from spoolscribe import app_gui, core, i18n
                from PySide6.QtCore import QTimer
                from PySide6.QtWidgets import QComboBox, QDialog, QMessageBox
                root=Path(os.environ['SPOOLSCRIBE_DATA_HOME'])
                marker=root/'restart-stage.json'
                if not marker.exists():
                    marker.write_text(json.dumps({'parent':os.getpid(),'phase':1}),encoding='utf-8')
                    core.save_config(dict(core.DEFAULT_CONFIG,language='fr',network_consent=False,favorite_brands=['Alpha']))
                original=app_gui.MainWindow
                class Window(original):
                    def __init__(self,*args,**kwargs):   # main() passes the start-up profile state
                        super().__init__(*args,**kwargs)
                        QTimer.singleShot(40,self.drive)
                        QTimer.singleShot(10000,lambda:self.app.exit(2))
                    def _maybe_auto_update(self):
                        pass
                    def drive(self):
                        state=json.loads(marker.read_text(encoding='utf-8'))
                        if state['phase']==1:
                            state['phase']=2;marker.write_text(json.dumps(state),encoding='utf-8')
                            def select(dialog):
                                choice=dialog.findChild(QComboBox,'interface_language')
                                choice.setCurrentIndex(choice.findData('es'))
                                return QDialog.Accepted
                            def restart(box):
                                next(b for b in box.buttons() if b.text()=='Redémarrer maintenant').click()
                                return 0
                            with patch.object(QDialog,'exec',select),patch.object(QMessageBox,'exec',restart):
                                self._open_settings()
                        else:
                            cfg=core.load_config()
                            lock=root/'spoolscribe.instance.lock'
                            (root/'result.json').write_text(json.dumps(dict(
                                language=i18n.language(),preference=cfg['language'],
                                pid=os.getpid(),parent=state['parent'],
                                lock_pid=int(lock.read_text(encoding='utf-8').splitlines()[0]),
                                favourites=cfg['favorite_brands'])),encoding='utf-8')
                            self.close()
                app_gui.MainWindow=Window
                app_gui.__file__=__file__
                raise SystemExit(app_gui.main())
            '''),encoding='utf-8')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',PYTHONPATH=os.pathsep.join((str(ROOT/'src'),str(ROOT))),
                     SPOOLSCRIBE_DATA_HOME=tmp,SPOOLSCRIBE_CONFIG_PATH=str(directory/'config.json'))
            process=subprocess.run([sys.executable,str(wrapper)],env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(process.returncode,0,process.stderr)
            result=directory/'result.json';deadline=time.monotonic()+15
            while not result.exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(result.is_file(),'Replacement did not complete its startup')
            data=json.loads(result.read_text(encoding='utf-8'))
            self.assertNotEqual(data['pid'],data['parent']);self.assertEqual(data['lock_pid'],data['pid'])
            self.assertEqual((data['language'],data['preference']),('es','es'))
            self.assertEqual(data['favourites'],['Alpha'])
            # Allow the replacement's clean shutdown to finish before removing its fixture.
            deadline=time.monotonic()+5
            while (directory/'spoolscribe.instance.lock').exists() and time.monotonic()<deadline:time.sleep(.05)
            self.assertFalse((directory/'spoolscribe.instance.lock').exists())
