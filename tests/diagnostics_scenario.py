"""Scénario de reproduction borné pour le crash macOS P0 (diagnostic opt-in).

Ce n'est pas un test unitaire (hors découverte ``test_*.py``) : il passe par le
vrai ``app_gui.main()`` avec ``--diagnostics``, sur une copie jetable des
fixtures, réseau refusé, puis pilote l'interface pendant ~30 s au plus :

  Paramètres (chaque onglet) → Annuler ; Paramètres (chaque onglet) →
  Enregistrer ; À propos → Fermer ; détail d'un filament + « Détails et
  sources » (provenance) ; redimensionnement min/max, plein écran système
  (maximiser) puis normal, déplacement près du bord ; fermeture ; recréation
  d'une fenêtre principale ; fermeture ; fin. Relancer la même commande une
  seconde fois = relance (géométrie restaurée depuis la configuration copiée).

Usage (depuis la racine du dépôt) ::

    T=$(mktemp -d) ;
    SPOOLSCRIBE_DATA_HOME=$T/data SPOOLSCRIBE_CONFIG_PATH=$T/config.json \\
    PYTHONPATH=src:. python -B tests/diagnostics_scenario.py

``QT_QPA_PLATFORM`` non défini = Cocoa natif sur macOS ; ``offscreen`` sinon.
Aucun réglage global n'est modifié ; les changements physiques d'écran et la
veille restent à pratiquer par le titulaire, pendant une exécution normale
``--diagnostics``. Le script affiche la synthèse expurgée (aucun chemin).
Code retour : celui de ``main()``, 3 si le chien de garde a dû interrompre.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEADLINE_MS = 90_000


def _refuse(message):
    print(f"Scénario refusé : {message}", file=sys.stderr)
    raise SystemExit(2)


def _deny_network(event, args):
    if event in ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname"):
        raise PermissionError("Réseau refusé pendant le scénario de diagnostic.")


def _check_isolated_paths():
    data_home = os.environ.get("SPOOLSCRIBE_DATA_HOME")
    config = os.environ.get("SPOOLSCRIBE_CONFIG_PATH")
    if not data_home or not config:
        _refuse("SPOOLSCRIBE_DATA_HOME et SPOOLSCRIBE_CONFIG_PATH sont tous deux requis.")
    roots = {os.path.realpath(tempfile.gettempdir()), os.path.realpath("/private/tmp"), os.path.realpath("/tmp")}
    for value in (data_home, config):
        real = os.path.realpath(value)
        if not any(real == root or real.startswith(root + os.sep) for root in roots):
            _refuse("les deux chemins doivent être dans un dossier temporaire jetable.")
    return Path(data_home), Path(config)


def _prepare(data_home: Path, config: Path):
    from spoolscribe import core
    os.makedirs(core.DATA_DIR, exist_ok=True)
    if not os.path.isfile(core.DB_PATH):
        shutil.copyfile(ROOT / "tests/fixtures/catalogues/polymaker_db.json", core.DB_PATH)
    if not config.exists():
        core.save_config(dict(core.DEFAULT_CONFIG, language="fr", network_consent=False, update_interval_days=-1))


class Autopilot:
    def __init__(self, app_gui):
        from PySide6.QtCore import QTimer
        self.app_gui = app_gui
        self.log = []
        self.plan = None
        self.tab_queue = None
        self.timer = QTimer()
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._tick)
        self.steps = []
        self.aborted = False

    # Dialogues modaux : parcourir les onglets puis Enregistrer/Annuler.
    def _tick(self):
        from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTabWidget
        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        if isinstance(modal, QMessageBox) or self.plan is None:
            self.log.append(f"modal-inattendu:{modal.metaObject().className()}:rejeté")
            modal.reject(); return
        if self.tab_queue is None:
            self.tab_queue = [(tabs, index) for tabs in modal.findChildren(QTabWidget) for index in range(tabs.count())]
            self.log.append(f"{self.plan[0]}:onglets={len(self.tab_queue)}")
        if self.tab_queue:
            tabs, index = self.tab_queue.pop(0)
            tabs.setCurrentIndex(index); return
        name, outcome = self.plan
        self.plan = None; self.tab_queue = None
        self.log.append(f"{name}:{outcome}")
        (modal.accept if outcome == "accept" else modal.reject)()

    def _main_window(self):
        from PySide6.QtWidgets import QApplication
        windows = [w for w in QApplication.topLevelWidgets() if isinstance(w, self.app_gui.MainWindow) and w.isVisible()]
        return windows[-1] if windows else None

    def start(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(False)
        QTimer.singleShot(DEADLINE_MS, self._abort)
        self.timer.start()
        win = lambda: self._main_window()

        def modal(name, outcome, opener):
            def run():
                self.plan = (name, outcome)
                opener()
            return run

        def provenance():
            w = win(); skus = sorted(w.db.get("_skus", {}))
            if not skus: self.log.append("provenance:aucun-filament"); return
            w.current_sku = skus[0]; w._show_detail(skus[0])
            w.provenance_toggle.setChecked(True); self.log.append("provenance:ouverte")

        def resize_cycle():
            w = win(); w.resize(w.minimumSize()); QApplication.processEvents()
            w.resize(1600, 1000); QApplication.processEvents()

        def near_edge():
            w = win(); handle = w.windowHandle()
            screen = handle.screen() if handle is not None else QApplication.primaryScreen()
            area = screen.availableGeometry()
            # Reste dans l'écran : on ne simule pas de retrait d'écran.
            w.move(max(area.left(), area.right() - w.width() + 1), area.top())

        def recreate():
            fresh = self.app_gui.MainWindow(); fresh.show(); self.log.append("fenetre:recreee")

        self.steps = [
            (800, "settings-cancel", modal("settings", "reject", lambda: win()._open_settings())),
            (500, "settings-save", modal("settings", "accept", lambda: win()._open_settings())),
            (500, "about", modal("about", "accept", lambda: win()._open_about())),
            (700, "provenance", provenance),
            (300, "provenance-close", lambda: win().provenance_toggle.setChecked(False)),
            (500, "resize", resize_cycle),
            (500, "maximize", lambda: win().showMaximized()),
            (500, "normal", lambda: win().showNormal()),
            (500, "near-edge", near_edge),
            (500, "close", lambda: self.log.append(f"close:{win().close()}")),
            (500, "recreate", recreate),
            (700, "close-again", lambda: self.log.append(f"close:{win().close()}")),
        ]
        QTimer.singleShot(1000, self._next)

    def _next(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        if not self.steps:
            self.timer.stop(); self.log.append("fin")
            QApplication.instance().quit(); return
        delay, label, action = self.steps.pop(0)
        try:
            action()
            self.log.append(f"ok:{label}")
        except Exception as exc:  # consigné, le scénario continue
            self.log.append(f"erreur:{label}:{type(exc).__name__}")
        QTimer.singleShot(delay, self._next)

    def _abort(self):
        from PySide6.QtWidgets import QApplication
        self.aborted = True; self.log.append("chien-de-garde")
        QApplication.instance().exit(3)


def main():
    data_home, config = _check_isolated_paths()
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    sys.addaudithook(_deny_network)
    _prepare(data_home, config)
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from spoolscribe import app_gui, core, diagnostics

    pilot = Autopilot(app_gui)

    class ScenarioApplication(QApplication):
        def __init__(self, argv):
            super().__init__(argv)
            QTimer.singleShot(0, pilot.start)

    app_gui.QApplication = ScenarioApplication  # seul point d'injection ; main() reste intact
    sys.argv = [sys.argv[0], "--diagnostics"]
    code = app_gui.main()
    session_root = Path(core.DATA_HOME) / diagnostics.FOLDER_NAME
    sessions = sorted(session_root.iterdir()) if session_root.is_dir() else []
    summary = json.loads((sessions[-1] / diagnostics.SUMMARY_NAME).read_text(encoding="utf-8")) if sessions else None
    print(json.dumps({"exit_code": code, "steps": pilot.log, "sessions": len(sessions), "summary": summary},
                     ensure_ascii=False, indent=2))
    return 3 if pilot.aborted else (code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
