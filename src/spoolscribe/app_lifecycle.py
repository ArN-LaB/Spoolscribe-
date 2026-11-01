"""Independent relaunch of the same installed binary or source entry point."""
import os
from pathlib import Path
import subprocess
import sys

RESTART_EXIT_CODE = 75


def launch_replacement(entry_script):
    command = [sys.executable]
    environment = dict(os.environ)
    if getattr(sys, 'frozen', False):
        # PyInstaller >= 6.9 must treat this as a new app, not a short-lived
        # worker sharing a onefile extraction directory with its parent.
        environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    else:
        entry = Path(entry_script).resolve()
        if entry == Path(__file__).with_name('app_gui.py').resolve():
            command.extend(['-m', 'spoolscribe'])
            root = entry.parents[2]
            paths = [str(root / 'src'), str(root)]
            if environment.get('PYTHONPATH'):
                paths.append(environment['PYTHONPATH'])
            environment['PYTHONPATH'] = os.pathsep.join(paths)
        else:
            # Isolated harnesses can still restart their explicit entry script.
            command.append(str(entry))
        environment.pop('PYINSTALLER_RESET_ENVIRONMENT', None)
    return subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            close_fds=True, start_new_session=(os.name != 'nt'))
