"""Diagnostic opt-in : absent par défaut, borné, privé, chaîné, sûr à la destruction."""
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from tests.support import catalogue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer, qInstallMessageHandler, qWarning
    from PySide6.QtWidgets import QApplication, QDialog, QWidget
    from spoolscribe import diagnostics


def _current_qt_handler():
    previous = qInstallMessageHandler(None)
    qInstallMessageHandler(previous)
    return previous


def _events(session):
    session._handler.flush()
    lines = Path(session.log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@unittest.skipUnless(HAS_QT, "PySide6 non installé : diagnostic Qt non mesuré")
class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "data-home"
        self.home.mkdir()
        self.addCleanup(diagnostics.shutdown, release_faulthandler=True)
        self.stderr = io.StringIO()

    def _start(self, **options):
        environ = {}
        argv = ["spoolscribe", "--diagnostics"]
        app, session = diagnostics.create_application(argv, lambda a: self.app, str(self.home),
                                                      environ=environ, stderr=self.stderr, **options)
        self.assertIs(app, self.app)
        self.assertIsNotNone(session, self.stderr.getvalue())
        self.assertEqual(argv, ["spoolscribe"])
        self.assertEqual(environ.get(diagnostics.ENV_FLAG), "1")
        return session

    def _pump(self):
        for _ in range(3):
            QCoreApplication.processEvents()

    # ── Opt-in absent ──
    def test_absent_opt_in_creates_nothing_and_installs_nothing(self):
        hook, thread_hook, qt_handler = sys.excepthook, threading.excepthook, _current_qt_handler()
        filters_before = diagnostics.active_session()
        argv = ["spoolscribe", "--other"]
        seen = []
        app, session = diagnostics.create_application(argv, lambda a: seen.append(list(a)) or self.app,
                                                      str(self.home), environ={})
        self.assertIsNone(session)
        self.assertIsNone(filters_before)
        self.assertEqual(seen, [["spoolscribe", "--other"]])
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertIs(sys.excepthook, hook)
        self.assertIs(threading.excepthook, thread_hook)
        self.assertIs(_current_qt_handler(), qt_handler)
        diagnostics.record("dialog_show")  # sans session : aucun effet, aucune exception
        diagnostics.record_window("geometry_restore_begin", QWidget())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_environment_value_must_be_exactly_one(self):
        for value in ("0", "true", "yes", ""):
            _, session = diagnostics.create_application(["x"], lambda a: self.app, str(self.home),
                                                        environ={diagnostics.ENV_FLAG: value})
            self.assertIsNone(session)
        self.assertFalse((self.home / "diagnostics").exists())
        _, session = diagnostics.create_application(["x"], lambda a: self.app, str(self.home),
                                                    environ={diagnostics.ENV_FLAG: "1"}, stderr=self.stderr)
        self.assertIsNotNone(session)

    # ── Activé ──
    def test_session_layout_permissions_and_faulthandler_before_qapplication(self):
        import faulthandler
        observed = {}

        def factory(argv):
            # QApplication n'existe pas encore pour main() : la session est déjà prête.
            session = diagnostics.active_session()
            observed.update(argv=list(argv), enabled=faulthandler.is_enabled(),
                            fault=os.path.isfile(session.fault_path), open=not session._fault_file.closed)
            return self.app

        argv = ["spoolscribe", "--diagnostics"]
        _, session = diagnostics.create_application(argv, factory, str(self.home), environ={}, stderr=self.stderr)
        self.assertEqual(observed, {"argv": ["spoolscribe"], "enabled": True, "fault": True, "open": True})
        root = self.home / "diagnostics"
        directory = Path(session.directory)
        self.assertEqual(directory.parent, root)
        self.assertRegex(directory.name, r"^\d{8}T\d{6}Z-%d$" % os.getpid())
        if os.name != "nt":
            for path in (root, directory):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            for name in ("faulthandler.log", "events.log", "summary.json"):
                self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), 0o600, name)
        diagnostics.shutdown()
        self.assertTrue(faulthandler.is_enabled(), "le fichier faulthandler reste actif jusqu'à la fin")
        self.assertFalse(session._fault_file.closed)
        summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "clean_exit")
        self.assertEqual(summary["runtime"]["qpa_platform"], "offscreen")

    def test_window_and_dialog_events_are_recorded_and_bounded(self):
        session = self._start()
        dialog = QDialog()
        self.addCleanup(lambda: shiboken6.isValid(dialog) and dialog.deleteLater())
        dialog.resize(300, 200)
        dialog.show(); self._pump()
        for width in range(301, 341):
            dialog.resize(width, 200)
        self._pump()
        QTimer.singleShot(0, dialog.accept)
        self._pump()
        dialog.hide(); self._pump()
        events = _events(session)
        names = [event["event"] for event in events]
        self.assertIn("dialog_show", names)
        self.assertIn("dialog_hide", names)
        finished = [event for event in events if event["event"] == "dialog_finished"]
        self.assertEqual([event["result"] for event in finished], [1])
        show = next(event for event in events if event["event"] == "dialog_show")
        self.assertEqual(show["kind"], "dialog")
        self.assertRegex(show["id"], r"^w\d+$")
        self.assertTrue(show["valid"])
        self.assertEqual(show["screens"], len(self.app.screens()))
        self.assertIn("dpr", show)
        self.assertNotIn("title", show)
        summary = session.summary()
        resizes = summary["events"]["window_resize"]
        logged = names.count("window_resize")
        self.assertGreaterEqual(resizes, 40)
        self.assertLess(logged, resizes)
        self.assertEqual(summary["suppressed_from_log"]["window_resize"], resizes - logged)
        self.assertEqual(summary["internal_errors"], 0)

    def test_log_rotation_keeps_three_bounded_files(self):
        session = self._start(max_bytes=2000, backup_count=2)
        for index in range(400):
            diagnostics.record("geometry_restore_begin", index=index)
        directory = Path(session.directory)
        logs = sorted(path.name for path in directory.glob("events.log*"))
        self.assertEqual(logs, ["events.log", "events.log.1", "events.log.2"])
        for path in directory.glob("events.log*"):
            self.assertLessEqual(path.stat().st_size, 2000 + 400)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(session.summary()["events"]["geometry_restore_begin"], 400)

    def test_home_paths_and_screen_identifiers_are_redacted(self):
        session = self._start()
        home = os.path.expanduser("~")
        session.redact.add_screen_identifiers(["ACME Panel 27X", "SN-0042-SECRET"])
        qWarning(f"probe {home}/Documents/private.json on ACME Panel 27X serial SN-0042-SECRET")
        diagnostics.record("geometry_restore_begin", note=f"{self.home}/diagnostics and /Users/someone/x")
        try:
            raise ValueError(f"{home}/secret")
        except ValueError:
            exc_info = sys.exc_info()
        with patch("sys.stderr", io.StringIO()):  # le hook précédent (défaut) imprime la trace
            sys.excepthook(*exc_info)
        diagnostics.shutdown()
        raw = "".join(path.read_text(encoding="utf-8") for path in Path(session.directory).iterdir())
        self.assertNotIn(home, raw)
        self.assertNotIn(str(self.home), raw)
        self.assertNotIn("ACME Panel 27X", raw)
        self.assertNotIn("SN-0042-SECRET", raw)
        self.assertNotIn("someone", raw)
        self.assertIn("<screen>", raw)
        self.assertIn("~/Documents/private.json", raw)
        summary_text = (Path(session.directory) / "summary.json").read_text(encoding="utf-8")
        self.assertNotIn("/", summary_text.replace("spoolscribe-diagnostics-summary", ""))
        summary = json.loads(summary_text)
        self.assertEqual(summary["exceptions"]["python"], {"ValueError": 1})
        self.assertEqual(summary["qt_messages"]["warning"]["default"], 1)
        for key in ("python", "qt_runtime", "pyside6", "os", "arch", "frozen", "app_version"):
            self.assertIn(key, summary["runtime"])

    def test_excepthooks_are_chained_and_restored(self):
        calls = []
        previous_hook = lambda *args: calls.append("sys")
        previous_thread = lambda args: calls.append("thread")
        with patch.object(sys, "excepthook", previous_hook), patch.object(threading, "excepthook", previous_thread):
            session = self._start()
            self.assertIsNot(sys.excepthook, previous_hook)
            try:
                raise KeyError("x")
            except KeyError:
                sys.excepthook(*sys.exc_info())
            worker = threading.Thread(target=lambda: 1 / 0)
            worker.start(); worker.join()
            self.assertEqual(calls, ["sys", "thread"])
            summary = session.summary()
            self.assertEqual(summary["exceptions"], {"python": {"KeyError": 1}, "thread": {"ZeroDivisionError": 1}})
            diagnostics.shutdown()
            self.assertIs(sys.excepthook, previous_hook)
            self.assertIs(threading.excepthook, previous_thread)

    def test_qt_message_handler_is_chained_and_restored(self):
        received = []
        handler = lambda mode, context, message: received.append(message)
        original = qInstallMessageHandler(handler)
        self.addCleanup(qInstallMessageHandler, original)
        session = self._start()
        qWarning("diagnostic-probe")
        self.assertEqual(received, ["diagnostic-probe"])
        self.assertEqual(session.summary()["events"]["qt_message"], 1)
        diagnostics.shutdown()
        self.assertIs(_current_qt_handler(), handler)
        qWarning("after")
        self.assertEqual(received, ["diagnostic-probe", "after"])
        self.assertEqual(session.summary()["events"]["qt_message"], 1)

    def test_unwritable_folder_is_graceful(self):
        hook, qt_handler = sys.excepthook, _current_qt_handler()
        blocker = Path(self.tmp.name) / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        argv = ["spoolscribe", "--diagnostics"]
        app, session = diagnostics.create_application(argv, lambda a: self.app, str(blocker),
                                                      environ={}, stderr=self.stderr)
        self.assertIs(app, self.app)
        self.assertIsNone(session)
        self.assertEqual(argv, ["spoolscribe"])
        self.assertEqual(len(self.stderr.getvalue().splitlines()), 1)
        self.assertNotIn(str(blocker), self.stderr.getvalue())
        self.assertIs(sys.excepthook, hook)
        self.assertIs(_current_qt_handler(), qt_handler)
        if os.name != "nt" and os.geteuid() != 0:
            locked = Path(self.tmp.name) / "locked"
            locked.mkdir(); locked.chmod(0o500)
            self.addCleanup(locked.chmod, 0o700)
            self.assertIsNone(diagnostics.start(str(locked), stderr=self.stderr))
            self.assertEqual(list(locked.iterdir()), [])

    def test_destroyed_window_with_pending_events_does_not_call_back(self):
        session = self._start()
        dialog = QDialog()
        dialog.show(); self._pump()
        fired = []
        QTimer.singleShot(0, dialog, lambda: fired.append(True))
        QCoreApplication.postEvent(dialog, QEvent(QEvent.Type.Resize))
        handle = dialog.windowHandle()
        self.assertIsNotNone(handle)
        shiboken6.delete(dialog)
        self._pump()
        self.assertEqual(fired, [])
        self.assertEqual(session.snapshot(dialog), {"valid": False})
        session.record_window("geometry_restore_end", dialog)
        # Signaux d'écran après destruction : aucune référence à la fenêtre disparue.
        screen = self.app.primaryScreen()
        self.app.screenAdded.emit(screen)
        self.app.primaryScreenChanged.emit(screen)
        self.app.screenRemoved.emit(screen)
        summary = session.summary()
        self.assertEqual(summary["windows"]["destroyed"], 1)
        self.assertEqual(summary["screens"]["added"], 1)
        self.assertEqual(summary["screens"]["removed"], 1)
        self.assertEqual(summary["internal_errors"], 0)
        names = [event["event"] for event in _events(session)]
        self.assertIn("window_destroyed", names)
        self.assertIn("screen_removed", names)

    def test_shutdown_disconnects_filter_and_signals(self):
        session = self._start()
        dialog = QDialog()
        dialog.show(); self._pump()
        self.assertTrue(session._connections)
        diagnostics.shutdown()
        self.assertEqual(session._connections, [])
        self.assertIsNone(session._probe)
        self.assertIsNone(diagnostics.active_session())
        before = dict(session.counts)
        dialog.hide(); dialog.show(); dialog.resize(500, 300); self._pump()
        self.app.screenAdded.emit(self.app.primaryScreen())
        dialog.accept(); self._pump()
        shiboken6.delete(dialog); self._pump()
        self.assertEqual(session.counts, before)
        diagnostics.shutdown()  # idempotent

    def test_restart_spawn_failure_and_success_are_recorded(self):
        from spoolscribe import app_gui
        session = self._start()
        app = Mock(); app.exec.side_effect = [app_gui.RESTART_EXIT_CODE, 0]
        window = Mock(); window._restart_requested = True
        lock = Mock(); lock.tryLock.return_value = True
        with patch("spoolscribe.app_gui.launch_replacement", side_effect=PermissionError("fixture /Users/x")), \
                patch("spoolscribe.app_gui.QMessageBox.warning"):
            self.assertEqual(app_gui.run_application(app, window, lock), 0)
        app.exec.side_effect = None; app.exec.return_value = app_gui.RESTART_EXIT_CODE
        window._restart_requested = True
        with patch("spoolscribe.app_gui.launch_replacement"):
            self.assertEqual(app_gui.run_application(app, window, lock), 0)
        spawns = [event for event in _events(session) if event["event"] == "restart_spawn"]
        self.assertEqual([(event["ok"], event.get("error")) for event in spawns],
                         [(False, "PermissionError"), (True, None)])
        self.assertEqual(session.summary()["events"]["restart_requested"], 2)

    def test_main_window_geometry_restore_and_close_are_traced(self):
        from spoolscribe import app_gui, core
        root = Path(self.tmp.name)
        db = root / "db.json"
        db.write_text(json.dumps(catalogue()), encoding="utf-8")
        paths = patch.multiple(core, DB_PATH=str(db), DATA_HOME=str(root), CONFIG_PATH=str(root / "config.json"),
                               OUTPUT_DIR=str(root / "output"), ORCA_DIR=str(root / "orca_profiles"))
        paths.start(); self.addCleanup(paths.stop)
        core.save_config(dict(core.DEFAULT_CONFIG, language="fr", network_consent=False))
        session = self._start()
        window = app_gui.MainWindow()
        window.show(); self._pump()
        self.assertTrue(window.close())
        self._pump()
        events = _events(session)
        names = [event["event"] for event in events]
        for name in ("geometry_restore_begin", "geometry_restore_end", "window_show", "window_close",
                     "main_close_accepted"):
            self.assertIn(name, names)
        end = next(event for event in events if event["event"] == "geometry_restore_end")
        self.assertEqual(end["kind"], "main")
        self.assertFalse(end["had_geometry"])
        raw = Path(session.log_path).read_text(encoding="utf-8")
        self.assertNotIn("Polymaker", raw)  # aucun nom de filament ou de marque
        self.assertEqual(session.summary()["internal_errors"], 0)
        window.deleteLater(); self._pump()


if __name__ == "__main__":
    unittest.main()
