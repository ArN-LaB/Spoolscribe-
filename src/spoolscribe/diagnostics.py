"""Diagnostic local opt-in : rendre un crash natif analysable, sans le « corriger ».

Désactivé par défaut. Activé par ``--diagnostics`` (retiré d'argv avant Qt) ou
par ``SPOOLSCRIBE_DIAGNOSTICS=1`` : la variable d'environnement sert surtout à
conserver le diagnostic lors d'une relance (``launch_replacement`` recopie
l'environnement mais pas les arguments) et pour ``open --env`` sur macOS.

Une session crée ``<DATA_HOME>/diagnostics/<AAAAMMJJTHHMMSSZ>-<pid>/`` (0700) :

* ``faulthandler.log`` : ouvert **avant** QApplication et conservé ouvert
  jusqu'à la fin du processus ; reçoit la pile Python de tous les threads lors
  d'un SIGSEGV/SIGBUS/SIGABRT. Il ne capture ni ne répare le signal natif.
* ``events.log`` (+ ``.1``, ``.2``) : journal technique JSON-lines, rotation
  3 × 1 Mio, privé (0600). Chemins personnels et identifiants d'écran expurgés.
* ``summary.json`` : synthèse expurgée (comptes et versions, aucun chemin).

Aucun réseau, aucune préférence, aucun nom de filament ni texte de recherche.
Le code de diagnostic ne lève jamais d'exception vers Qt : les erreurs internes
sont comptées. Rien n'est conservé vers un QScreen ou un widget : identifiants
éphémères stockés comme propriété dynamique de l'objet Qt lui-même.
"""
from __future__ import annotations

import atexit
import faulthandler
import json
import logging
import logging.handlers
import os
import platform
import re
import sys
import threading
import time
import weakref

CLI_FLAG = "--diagnostics"
ENV_FLAG = "SPOOLSCRIBE_DIAGNOSTICS"
FOLDER_NAME = "diagnostics"
LOG_NAME = "events.log"
FAULT_NAME = "faulthandler.log"
SUMMARY_NAME = "summary.json"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 2            # events.log + .1 + .2 = 3 fichiers au plus
SUMMARY_EVERY = 100         # réécriture périodique : la synthèse survit à un crash
RESIZE_MIN_INTERVAL = 0.1   # un Resize journalisé par fenêtre et par 100 ms (tous comptés)
MAX_FIELD = 4000
MAX_CATEGORIES = 64

EVENT_NAMES = frozenset({
    "session_start", "qapp_attached", "about_to_quit", "session_end",
    "window_show", "window_hide", "window_resize", "window_close", "window_state",
    "window_destroyed", "window_screen_changed",
    "dialog_show", "dialog_hide", "dialog_finished",
    "screen_added", "screen_removed", "primary_screen_changed",
    "geometry_restore_begin", "geometry_restore_end", "main_close_accepted",
    "restart_requested", "restart_spawn",
    "python_exception", "thread_exception", "qt_message",
})

_SESSION: "Session | None" = None
_ATEXIT_REGISTERED = False
_FAULT_FILES: list = []     # garde les fichiers faulthandler ouverts jusqu'à la fin
_RETAINED: list = []        # sessions fermées dont le faulthandler reste volontairement ouvert


# ─── Activation ──────────────────────────────────────────────────────────
def consume_cli_flag(argv: list) -> bool:
    """Retire ``--diagnostics`` d'argv (sur place) ; True s'il était présent."""
    found = CLI_FLAG in argv
    if found:
        argv[:] = [arg for arg in argv if arg != CLI_FLAG]
    return found


def requested(argv: list, environ=None) -> bool:
    """Opt-in explicite : drapeau CLI ou ``SPOOLSCRIBE_DIAGNOSTICS=1`` exactement."""
    environ = os.environ if environ is None else environ
    return CLI_FLAG in argv or environ.get(ENV_FLAG) == "1"


def create_application(argv: list, factory, data_home: str, *, environ=None, stderr=None, **options):
    """Point d'entrée de main() : session (si demandée) **puis** QApplication.

    ``argv`` est modifié sur place pour que Qt ne voie jamais le drapeau.
    Retourne ``(app, session_ou_None)``. Sans opt-in : aucun fichier, aucun
    gestionnaire installé, ``factory(argv)`` est simplement appelé.
    """
    environ = os.environ if environ is None else environ
    from_cli = consume_cli_flag(argv)
    session = None
    if from_cli or environ.get(ENV_FLAG) == "1":
        session = start(data_home, stderr=stderr, **options)
        if session is not None and from_cli:
            environ[ENV_FLAG] = "1"  # même diagnostic après une relance de langue
    app = factory(argv)
    if session is not None:
        session.attach(app)
    return app, session


def start(data_home: str, *, stderr=None, max_bytes=MAX_BYTES, backup_count=BACKUP_COUNT):
    """Ouvre la session ; None (et une ligne sur stderr) si le dossier est inutilisable."""
    global _SESSION, _ATEXIT_REGISTERED
    if _SESSION is not None and _SESSION.active:
        return _SESSION
    try:
        session = Session(data_home, max_bytes=max_bytes, backup_count=backup_count)
    except (OSError, ValueError) as exc:
        stream = sys.stderr if stderr is None else stderr
        try:
            print(f"SpoolScribe : diagnostic désactivé ({type(exc).__name__}, dossier non inscriptible).", file=stream)
        except Exception:
            pass
        return None
    _SESSION = session
    if not _ATEXIT_REGISTERED:
        atexit.register(shutdown)
        _ATEXIT_REGISTERED = True
    return session


def active_session():
    return _SESSION if _SESSION is not None and _SESSION.active else None


def record(name: str, **fields) -> None:
    """Point d'accroche des modules UI : sans session, ne fait rien (et ne coûte rien)."""
    session = _SESSION
    if session is not None and session.active:
        session.record(name, **fields)


def record_window(name: str, widget, **fields) -> None:
    session = _SESSION
    if session is not None and session.active:
        session.record_window(name, widget, **fields)


def shutdown(*, release_faulthandler: bool = False) -> None:
    """Détache Qt, restaure les gestionnaires chaînés, écrit la synthèse finale.

    Idempotent. Le fichier faulthandler reste ouvert et actif (un crash pendant
    la destruction de Qt reste capturé), sauf ``release_faulthandler`` (tests).
    """
    session = _SESSION
    if session is not None:
        session.close(release_faulthandler=release_faulthandler)
    if release_faulthandler:
        # Une session déjà fermée normalement (fichier conservé) n'est plus la session globale :
        # la libération explicite la retrouve ici, de la plus récente à la plus ancienne.
        for retained in reversed(list(_RETAINED)):
            retained.close(release_faulthandler=True)


# ─── Expurgation ─────────────────────────────────────────────────────────
_USER_DIR_PATTERNS = (
    re.compile(r"/Users/[^/\s'\"]+"),
    re.compile(r"/home/[^/\s'\"]+"),
    re.compile(r"[A-Za-z]:\\\\?Users\\\\?[^\\\s'\"]+", re.IGNORECASE),
)


class Redactor:
    """Remplace dossier personnel, DATA_HOME et identifiants d'écran connus."""
    def __init__(self, data_home: str | None = None):
        self._pairs: list[tuple[str, str]] = []
        for path, label in ((data_home, "<DATA_HOME>"), (os.path.expanduser("~"), "~")):
            if not path or len(path) < 2:
                continue
            for variant in {path, os.path.realpath(path), os.path.abspath(path)}:
                self._pairs.append((variant.rstrip(os.sep) or variant, label))
        self._screen_ids: set[str] = set()
        self._screen_pairs: list[str] = []
        self._sort()

    def _sort(self):
        self._pairs.sort(key=lambda pair: -len(pair[0]))

    def add_screen_identifiers(self, values) -> None:
        for value in values:
            value = (value or "").strip()
            if len(value) >= 3 and value not in self._screen_ids:
                self._screen_ids.add(value)
        self._screen_pairs = sorted(self._screen_ids, key=len, reverse=True)

    def __call__(self, text) -> str:
        text = str(text)
        for value in self._screen_pairs:
            text = text.replace(value, "<screen>")
        for needle, label in self._pairs:
            text = text.replace(needle, label)
        for pattern in _USER_DIR_PATTERNS:
            text = pattern.sub("~", text)
        return text


# ─── Fichiers privés ─────────────────────────────────────────────────────
def _private_dir(path: str) -> None:
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name != "nt":
        os.chmod(path, 0o700)


def _open_private(path: str, flags: int, encoding="utf-8"):
    fd = os.open(path, flags, 0o600)
    if os.name != "nt":
        os.fchmod(fd, 0o600)
    return os.fdopen(fd, "a" if flags & os.O_APPEND else "w", encoding=encoding)


class _PrivateRotatingHandler(logging.handlers.RotatingFileHandler):
    """Rotation stdlib ; chaque nouveau fichier est créé en 0600."""
    def _open(self):
        return _open_private(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, self.encoding or "utf-8")


def _enum_int(value):
    try:
        return int(value.value)
    except (AttributeError, TypeError, ValueError):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ─── Session ─────────────────────────────────────────────────────────────
class Session:
    _serial = 0

    def __init__(self, data_home: str, *, max_bytes=MAX_BYTES, backup_count=BACKUP_COUNT):
        if not data_home:
            raise ValueError("DATA_HOME vide")
        Session._serial += 1
        self.serial = Session._serial
        self.redact = Redactor(data_home)
        self._lock = threading.RLock()
        self.active = False
        self._closed = False
        self.counts: dict[str, int] = {}
        self.suppressed: dict[str, int] = {}
        self.qt_messages: dict[str, dict[str, int]] = {}
        self.exceptions: dict[str, dict[str, int]] = {"python": {}, "thread": {}}
        self.internal_errors = 0
        self.windows_seen = 0
        self.windows_destroyed = 0
        self.screens = {"count_at_attach": None, "count_current": None, "max": 0,
                        "added": 0, "removed": 0, "primary_changed": 0}
        self.runtime = self._runtime()
        self.status = "running"
        self.qapp_preexisting = self._qapp_exists()
        self._started = time.monotonic()
        self.started_utc = _utc_now()
        self._since_summary = 0
        self._last_resize: dict[str, float] = {}
        self._connections: list = []
        self._app_ref = None
        self._probe = None
        self._previous_qt_handler = None
        self._qt_handler_installed = False
        self._faulthandler_was_enabled = faulthandler.is_enabled()
        self._fault_file = None
        self._handler = None

        root = os.path.join(data_home, FOLDER_NAME)
        _private_dir(root)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        base = f"{stamp}-{os.getpid()}"
        for attempt in range(100):
            name = base if attempt == 0 else f"{base}-{attempt}"
            candidate = os.path.join(root, name)
            try:
                os.mkdir(candidate, 0o700)
                break
            except FileExistsError:
                continue
        else:
            raise OSError("aucun nom de session libre")
        if os.name != "nt":
            os.chmod(candidate, 0o700)
        self.directory = candidate
        self.fault_path = os.path.join(candidate, FAULT_NAME)
        self.log_path = os.path.join(candidate, LOG_NAME)
        self.summary_path = os.path.join(candidate, SUMMARY_NAME)
        try:
            # Ouvert avant QApplication et jamais fermé avant la fin du processus.
            self._fault_file = _open_private(self.fault_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND)
            handler = _PrivateRotatingHandler(self.log_path, maxBytes=max_bytes, backupCount=backup_count,
                                              encoding="utf-8", delay=False)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._handler = handler
            self._logger = logging.Logger(f"spoolscribe.diagnostics.{self.serial}")
            self._logger.propagate = False
            self._logger.addHandler(handler)
            self._write_summary()
        except BaseException:
            for stream in (self._fault_file, self._handler):
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass
            raise
        faulthandler.enable(file=self._fault_file, all_threads=True)
        _FAULT_FILES.append(self._fault_file)
        self.active = True
        self._install_python_hooks()
        self._install_qt_handler()
        self.record("session_start", qapp_preexisting=self.qapp_preexisting, **self._runtime_brief())

    # ── Versions (sans chemin) ──
    @staticmethod
    def _qapp_exists():
        try:
            from PySide6.QtCore import QCoreApplication
            return QCoreApplication.instance() is not None
        except Exception:
            return False

    @staticmethod
    def _runtime():
        info = {"python": platform.python_version(), "implementation": platform.python_implementation(),
                "os": platform.system(), "os_release": platform.mac_ver()[0] or platform.release(),
                "arch": platform.machine(), "frozen": bool(getattr(sys, "frozen", False)),
                "app_version": None, "qt_runtime": None, "qt_compiled": None, "pyside6": None, "qpa_platform": None}
        try:
            from .core import APP_VERSION
            info["app_version"] = APP_VERSION
        except Exception:
            pass
        try:
            import PySide6
            from PySide6.QtCore import qVersion, __version__ as qt_compiled
            info.update(qt_runtime=qVersion(), qt_compiled=qt_compiled, pyside6=PySide6.__version__)
        except Exception:
            pass
        return info

    def _runtime_brief(self):
        keys = ("app_version", "python", "qt_runtime", "pyside6", "os", "os_release", "arch", "frozen")
        return {key: self.runtime.get(key) for key in keys}

    # ── Journal ──
    def _internal_error(self):
        with self._lock:
            self.internal_errors += 1

    def record(self, name: str, **fields) -> None:
        if not self.active:
            return
        try:
            if name not in EVENT_NAMES:
                fields["unknown_name"] = True
                name = "other"
            with self._lock:
                self.counts[name] = self.counts.get(name, 0) + 1
                self._since_summary += 1
                periodic = self._since_summary >= SUMMARY_EVERY
                if periodic:
                    self._since_summary = 0
            line = {"t": round(time.monotonic() - self._started, 4), "utc": _utc_now(), "event": name,
                    "thread": "main" if threading.current_thread() is threading.main_thread() else "other"}
            for key, value in fields.items():
                if isinstance(value, str):
                    value = self.redact(value)[:MAX_FIELD]
                line[key] = value
            self._logger.info(json.dumps(line, ensure_ascii=False, sort_keys=False, default=str))
            if periodic:
                self._write_summary()
        except Exception:
            self._internal_error()

    def _suppress(self, name):
        with self._lock:
            self.counts[name] = self.counts.get(name, 0) + 1
            self.suppressed[name] = self.suppressed.get(name, 0) + 1

    # ── Synthèse expurgée ──
    def summary(self) -> dict:
        with self._lock:
            fault_bytes = None
            try:
                fault_bytes = os.path.getsize(self.fault_path)
            except OSError:
                pass
            return {
                "format": "spoolscribe-diagnostics-summary", "version": 1,
                "status": self.status, "started_utc": self.started_utc, "updated_utc": _utc_now(),
                "duration_s": round(time.monotonic() - self._started, 1),
                "qapp_preexisting": self.qapp_preexisting,
                "runtime": dict(self.runtime),
                "events": dict(sorted(self.counts.items())),
                "suppressed_from_log": dict(sorted(self.suppressed.items())),
                "qt_messages": {kind: dict(sorted(cats.items())) for kind, cats in sorted(self.qt_messages.items())},
                "exceptions": {kind: dict(sorted(types.items())) for kind, types in self.exceptions.items()},
                "screens": dict(self.screens),
                "windows": {"seen": self.windows_seen, "destroyed": self.windows_destroyed},
                "internal_errors": self.internal_errors,
                "faulthandler_bytes": fault_bytes,
            }

    def _write_summary(self):
        try:
            data = json.dumps(self.summary(), ensure_ascii=False, indent=2, sort_keys=False)
            temporary = self.summary_path + ".tmp"
            with _open_private(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC) as stream:
                stream.write(data + "\n")
            os.replace(temporary, self.summary_path)
        except Exception:
            self._internal_error()

    # ── Exceptions Python (chaînées, jamais avalées) ──
    def _install_python_hooks(self):
        self._previous_excepthook = sys.excepthook
        self._previous_thread_hook = threading.excepthook
        session_ref = weakref.ref(self)
        previous = self._previous_excepthook
        previous_thread = self._previous_thread_hook

        def excepthook(exc_type, exc, tb):
            session = session_ref()
            if session is not None:
                session._on_exception("python", exc_type, exc, tb)
            previous(exc_type, exc, tb)

        def thread_excepthook(args):
            session = session_ref()
            if session is not None:
                session._on_exception("thread", args.exc_type, args.exc_value, args.exc_traceback)
            previous_thread(args)

        self._excepthook = excepthook
        self._thread_excepthook = thread_excepthook
        sys.excepthook = excepthook
        threading.excepthook = thread_excepthook

    def _on_exception(self, kind, exc_type, exc, tb):
        if not self.active:
            return
        try:
            import traceback
            type_name = getattr(exc_type, "__name__", "Exception")
            with self._lock:
                bucket = self.exceptions[kind]
                bucket[type_name] = bucket.get(type_name, 0) + 1
            text = "".join(traceback.format_exception(exc_type, exc, tb))
            self.record("python_exception" if kind == "python" else "thread_exception",
                        type=type_name, traceback=text[-MAX_FIELD:])
        except Exception:
            self._internal_error()

    def _restore_python_hooks(self):
        # Ne restaure que si personne n'a chaîné par-dessus : sinon on se rend inerte.
        if getattr(self, "_excepthook", None) is not None and sys.excepthook is self._excepthook:
            sys.excepthook = self._previous_excepthook
        if getattr(self, "_thread_excepthook", None) is not None and threading.excepthook is self._thread_excepthook:
            threading.excepthook = self._previous_thread_hook

    # ── Messages Qt (enregistrés puis transmis au gestionnaire précédent) ──
    def _install_qt_handler(self):
        try:
            from PySide6.QtCore import qInstallMessageHandler
        except Exception:
            return
        session_ref = weakref.ref(self)
        previous_holder = [None]

        def handler(mode, context, message):
            session = session_ref()
            if session is not None:
                session._on_qt_message(mode, context, message)
            previous = previous_holder[0]
            try:
                if previous is not None:
                    previous(mode, context, message)
                else:  # gestionnaire Qt par défaut : la sortie d'erreur
                    sys.stderr.write(f"{message}\n")
            except Exception:
                pass

        self._qt_handler = handler
        previous_holder[0] = self._previous_qt_handler = qInstallMessageHandler(handler)
        self._qt_handler_installed = True

    def _on_qt_message(self, mode, context, message):
        if not self.active:
            return
        try:
            kind = getattr(mode, "name", str(mode)).replace("Qt", "").replace("Msg", "").lower() or "unknown"
            category = getattr(context, "category", None) or "default"
            with self._lock:
                cats = self.qt_messages.setdefault(kind, {})
                if category not in cats and len(cats) >= MAX_CATEGORIES:
                    category = "other"
                cats[category] = cats.get(category, 0) + 1
            self.record("qt_message", kind=kind, category=str(category), message=str(message))
        except Exception:
            self._internal_error()

    def _restore_qt_handler(self):
        if not self._qt_handler_installed:
            return
        try:
            from PySide6.QtCore import qInstallMessageHandler
            current = qInstallMessageHandler(self._previous_qt_handler)
            if current is not self._qt_handler:
                # Quelqu'un a chaîné après nous : remettre son gestionnaire en place.
                qInstallMessageHandler(current)
        except Exception:
            self._internal_error()
        self._qt_handler_installed = False

    # ── Qt : écrans et fenêtres ──
    def attach(self, app) -> None:
        """Après création de QApplication : signaux d'écran et filtre d'événements."""
        if not self.active or self._probe is not None or _EventProbe is None:
            return
        try:
            from PySide6.QtCore import QObject
            self._app_ref = weakref.ref(app)
            self.runtime["qpa_platform"] = app.platformName()
            self._probe = _EventProbe(self)
            app.installEventFilter(self._probe)
            for signal, slot in ((app.screenAdded, self._on_screen_added),
                                 (app.screenRemoved, self._on_screen_removed),
                                 (app.primaryScreenChanged, self._on_primary_changed),
                                 (app.aboutToQuit, self._on_about_to_quit)):
                self._connections.append(signal.connect(slot))
            screens = app.screens()
            self._remember_screens(screens)
            with self._lock:
                self.screens["count_at_attach"] = len(screens)
            self.record("qapp_attached", qpa_platform=self.runtime["qpa_platform"],
                        screens=[self._screen_brief(index, screen) for index, screen in enumerate(screens)])
            self._write_summary()
        except Exception:
            self._internal_error()

    def _remember_screens(self, screens):
        values = []
        for screen in screens:
            for getter in ("name", "manufacturer", "model", "serialNumber"):
                try:
                    values.append(getattr(screen, getter)())
                except Exception:
                    pass
        self.redact.add_screen_identifiers(values)
        with self._lock:
            self.screens["count_current"] = len(screens)
            self.screens["max"] = max(self.screens["max"], len(screens))

    @staticmethod
    def _screen_brief(index, screen):
        # Géométrie et DPR seulement : ni nom, ni fabricant, ni modèle, ni numéro de série.
        geometry = screen.geometry()
        available = screen.availableGeometry()
        return {"index": index, "geom": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
                "avail": [available.x(), available.y(), available.width(), available.height()],
                "dpr": round(screen.devicePixelRatio(), 3)}

    def _screens(self):
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.screens()

    def _screen_index(self, screen, screens=None):
        if screen is None:
            return None
        screens = self._screens() if screens is None else screens
        for index, candidate in enumerate(screens):
            if candidate is screen or candidate == screen:
                return index
        return -1

    def _on_screen_added(self, screen):
        try:
            screens = self._screens()
            self._remember_screens(screens)
            with self._lock:
                self.screens["added"] += 1
            self.record("screen_added", screens=len(screens), index=self._screen_index(screen, screens),
                        screen=self._screen_brief(-1, screen) if screen is not None else None)
            self._write_summary()
        except Exception:
            self._internal_error()

    def _on_screen_removed(self, screen):
        # Pendant ce signal l'écran existe encore ; aucune référence n'est gardée.
        try:
            screens = self._screens()
            with self._lock:
                self.screens["removed"] += 1
                self.screens["count_current"] = len(screens)
            self.record("screen_removed", screens=len(screens), index=self._screen_index(screen, screens))
            self._write_summary()
        except Exception:
            self._internal_error()

    def _on_primary_changed(self, screen):
        try:
            screens = self._screens()
            with self._lock:
                self.screens["primary_changed"] += 1
            self.record("primary_screen_changed", screens=len(screens), index=self._screen_index(screen, screens))
            self._write_summary()
        except Exception:
            self._internal_error()

    def _on_about_to_quit(self):
        # Une relance échouée peut relancer app.exec() : on garde les observateurs.
        self.record("about_to_quit")
        self._write_summary()

    # Identifiant éphémère : propriété dynamique de l'objet (meurt avec lui),
    # compteur local ; jamais d'adresse mémoire ni de référence Python durable.
    def _window_id(self, widget, create=True):
        key = f"_spoolscribe_diag_{self.serial}"
        value = widget.property(key)
        if value is None and create:
            with self._lock:
                self.windows_seen += 1
                value = f"w{self.windows_seen}"
            widget.setProperty(key, value)
            self._connect_lifetime(widget, value)
        return value

    def _connect_lifetime(self, widget, window_id):
        session_ref = weakref.ref(self)

        def destroyed(*_):
            session = session_ref()
            if session is not None and session.active:
                with session._lock:
                    session.windows_destroyed += 1
                    session._last_resize.pop(window_id, None)
                session.record("window_destroyed", id=window_id)

        self._connections.append(widget.destroyed.connect(destroyed))
        from PySide6.QtWidgets import QDialog
        if isinstance(widget, QDialog):
            def finished(result):
                session = session_ref()
                if session is not None and session.active:
                    session.record("dialog_finished", id=window_id, result=_enum_int(result))
            self._connections.append(widget.finished.connect(finished))

    def _watch_handle(self, widget, window_id):
        handle = widget.windowHandle()  # ne crée pas de handle
        if handle is None:
            return
        key = f"_spoolscribe_diag_{self.serial}"
        if handle.property(key) == window_id:
            return
        handle.setProperty(key, window_id)
        session_ref = weakref.ref(self)

        def screen_changed(screen):
            session = session_ref()
            if session is None or not session.active:
                return
            try:
                screens = session._screens()
                session.record("window_screen_changed", id=window_id, screens=len(screens),
                               index=session._screen_index(screen, screens))
            except Exception:
                session._internal_error()

        self._connections.append(handle.screenChanged.connect(screen_changed))

    def _window_kind(self, widget):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QMainWindow
        if isinstance(widget, QMainWindow):
            return "main"
        if isinstance(widget, QDialog):
            return "dialog"
        try:
            if widget.windowType() in (Qt.Popup, Qt.ToolTip):
                return "popup"
        except Exception:
            pass
        return "window"

    def snapshot(self, widget, *, create_id=True) -> dict:
        """État technique d'une fenêtre, sans titre ni contenu.

        N'appelle pas ``QWidget.screen()`` (chemin même du crash) : l'écran et le
        DPR viennent du handle natif s'il existe déjà.
        """
        import shiboken6
        if widget is None or not shiboken6.isValid(widget):
            return {"valid": False}
        info = {"id": self._window_id(widget, create=create_id), "valid": True,
                "kind": self._window_kind(widget), "cls": widget.metaObject().className()}
        geometry = widget.geometry()
        info["geom"] = [geometry.x(), geometry.y(), geometry.width(), geometry.height()]
        info["visible"] = widget.isVisible()
        info["state"] = _enum_int(widget.windowState())
        handle = widget.windowHandle()
        info["handle"] = handle is not None
        screens = self._screens()
        info["screens"] = len(screens)
        if handle is not None:
            info["dpr"] = round(handle.devicePixelRatio(), 3)
            info["screen"] = self._screen_index(handle.screen(), screens)
        return info

    def record_window(self, name, widget, **fields):
        if not self.active:
            return
        try:
            fields.update(self.snapshot(widget))
            self.record(name, **fields)
        except Exception:
            self._internal_error()

    def _on_window_event(self, widget, kind: str):
        # Hide/Close peuvent arriver pendant la destruction : aucune propriété ni
        # connexion n'est alors créée, seule la lecture QWidget de base a lieu.
        create = kind in ("show", "resize", "state")
        window_id = self._window_id(widget, create=create)
        dialog = self._window_kind(widget) == "dialog"
        if kind == "resize":
            now = time.monotonic()
            with self._lock:
                last = self._last_resize.get(window_id, -1.0)
                throttled = now - last < RESIZE_MIN_INTERVAL
                if not throttled:
                    self._last_resize[window_id] = now
            if throttled:
                self._suppress("window_resize")
                return
        if kind == "show" and window_id is not None:
            self._watch_handle(widget, window_id)
        name = {"show": "dialog_show" if dialog else "window_show",
                "hide": "dialog_hide" if dialog else "window_hide",
                "resize": "window_resize", "close": "window_close", "state": "window_state"}[kind]
        self.record(name, **self.snapshot(widget, create_id=create))

    # ── Arrêt ──
    def detach_qt(self):
        """Retire filtre et connexions ; sûr même si QApplication est déjà détruite."""
        try:
            import shiboken6
            from PySide6.QtCore import QObject
        except Exception:
            return
        probe, self._probe = self._probe, None
        if probe is not None:
            probe.session_ref = lambda: None
            app = self._app_ref() if self._app_ref is not None else None
            try:
                if app is not None and shiboken6.isValid(app) and shiboken6.isValid(probe):
                    app.removeEventFilter(probe)
            except Exception:
                self._internal_error()
        connections, self._connections = self._connections, []
        for connection in connections:
            try:
                QObject.disconnect(connection)  # sûr si l'émetteur a déjà disparu
            except Exception:
                pass

    def close(self, *, release_faulthandler=False):
        global _SESSION
        with self._lock:
            if self._closed:
                if release_faulthandler:
                    self._release_faulthandler()
                return
            self._closed = True
        self.record("session_end")
        self.detach_qt()
        self._restore_qt_handler()
        self._restore_python_hooks()
        self.status = "clean_exit"
        self._write_summary()
        self.active = False
        try:
            self._logger.removeHandler(self._handler)
            self._handler.flush()
            self._handler.close()
        except Exception:
            self._internal_error()
        if release_faulthandler:
            self._release_faulthandler()
        elif self._fault_file is not None and self not in _RETAINED:
            _RETAINED.append(self)
        if _SESSION is self:
            _SESSION = None

    def _release_faulthandler(self):
        stream, self._fault_file = self._fault_file, None
        if self in _RETAINED:
            _RETAINED.remove(self)
        if stream is None:
            return
        try:
            faulthandler.disable()
            if self._faulthandler_was_enabled:
                faulthandler.enable(all_threads=True)
        finally:
            if stream in _FAULT_FILES:
                _FAULT_FILES.remove(stream)
            stream.close()


try:
    from PySide6.QtCore import QObject as _QObject, QEvent as _QEvent, QCoreApplication as _QCoreApplication

    _WATCHED = {_QEvent.Type.Show: "show", _QEvent.Type.Hide: "hide", _QEvent.Type.Resize: "resize",
                _QEvent.Type.Close: "close", _QEvent.Type.WindowStateChange: "state"}

    class _EventProbe(_QObject):
        """Filtre d'application passif : renvoie toujours False, ne lève jamais."""
        def __init__(self, session):
            super().__init__()
            self.session_ref = weakref.ref(session)

        def eventFilter(self, watched, event):
            session = self.session_ref()
            if session is None or not session.active:
                return False
            try:
                kind = _WATCHED.get(event.type())
                if kind is None or _QCoreApplication.closingDown():
                    return False
                if watched.isWidgetType() and watched.isWindow():
                    session._on_window_event(watched, kind)
            except Exception:
                session._internal_error()
            return False
except Exception:  # pragma: no cover - PySide6 absent : seul le journal Python reste possible
    _EventProbe = None
