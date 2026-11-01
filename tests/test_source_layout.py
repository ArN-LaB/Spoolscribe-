"""Exercise source entry points after grouping the application into a package."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import app_lifecycle
from tests.support import ROOT


class SourceLayoutTests(unittest.TestCase):
    def test_source_cli_help_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT))),
                       SPOOLSCRIBE_DATA_HOME=directory,
                       SPOOLSCRIBE_CONFIG_PATH=str(Path(directory) / 'config.json'))
            result = subprocess.run([sys.executable, '-m', 'spoolscribe.convert_profile', '--help'],
                                    cwd=directory, env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('--restore-db', result.stdout)
            self.assertFalse((Path(directory) / 'tests/fixtures/catalogues/polymaker_db.json').exists())

    def test_source_gui_restarts_as_a_package_with_resource_imports_available(self):
        entry = ROOT / 'src/spoolscribe/app_gui.py'
        with patch.object(app_lifecycle.sys, 'frozen', False, create=True), \
                patch.object(app_lifecycle.subprocess, 'Popen') as spawn:
            app_lifecycle.launch_replacement(entry)
        self.assertEqual(spawn.call_args.args[0], [sys.executable, '-m', 'spoolscribe'])
        paths = spawn.call_args.kwargs['env']['PYTHONPATH'].split(os.pathsep)
        self.assertEqual(paths[:2], [str(ROOT / 'src'), str(ROOT)])
