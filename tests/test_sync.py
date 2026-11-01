"""Audit follow-up: refresh cadence, cancellation, locks and bounded downloads."""
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

import core
from scripts import db_io, app_updates, official_sources, download_orca_profiles
from tests.support import small_db


class CadenceTests(unittest.TestCase):
    def test_launch_refresh_follows_the_configured_interval(self):
        now = datetime(2026, 10, 31, 12, 0, 0)
        recent = (now - timedelta(hours=3)).isoformat()
        old = (now - timedelta(days=2)).isoformat()
        self.assertTrue(core.update_due({'update_interval_days': 0, 'last_update_attempt': recent}, now))
        self.assertFalse(core.update_due({'update_interval_days': 1, 'last_update_attempt': recent}, now))
        self.assertTrue(core.update_due({'update_interval_days': 1, 'last_update_attempt': old}, now))
        self.assertFalse(core.update_due({'update_interval_days': 7, 'last_update_attempt': old}, now))
        self.assertFalse(core.update_due({'update_interval_days': -1, 'last_update_attempt': None}, now))
        self.assertTrue(core.update_due({'update_interval_days': 1, 'last_update_attempt': None}, now))
        self.assertTrue(core.update_due({'update_interval_days': 'x', 'last_update_attempt': 'garbage'}, now))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db_path = root / 'data/polymaker_db.json'
        db = small_db()
        db['_update_status'] = 'failed'
        db['_source_results'] = []
        db_io.save_db(db, self.db_path)
        self.paths = patch.multiple(core, DB_PATH=str(self.db_path), DATA_HOME=str(root), CONFIG_PATH=str(root / 'config.json'))
        self.paths.start()
        self.addCleanup(self.paths.stop)

    @staticmethod
    def _completed(status, code=0):
        return subprocess.CompletedProcess([], code, stdout=db_io.STEP_PREFIX + json.dumps({'status': status, 'message': ''}), stderr='')

    def test_an_unchanged_offline_attempt_does_not_rewrite_the_database(self):
        with patch('core._run_step_process', return_value=self._completed('unavailable', 2)):
            core.run_update_pipeline(consent=True)
        first = self.db_path.read_bytes()
        attempt = core.load_config()['last_update_attempt']
        self.assertTrue(attempt)
        with patch('core._run_step_process', return_value=self._completed('unavailable', 2)):
            core.run_update_pipeline(consent=True)
        self.assertEqual(self.db_path.read_bytes(), first)
        self.assertNotIn('_last_attempt', db_io.load_db(self.db_path))
        self.assertEqual(core.load_config()['last_update_status'], 'failed')

    def test_cancellation_stops_remaining_steps_and_keeps_the_database(self):
        before = self.db_path.read_bytes()
        cancel = threading.Event()

        def first_step(cmd, **kwargs):
            cancel.set()
            raise core.UpdateCancelled('stop')
        with patch('core._run_step_process', side_effect=first_step) as run:
            results = core.run_update_pipeline(consent=True, cancel=cancel)
        self.assertEqual(run.call_count, 1)
        self.assertTrue(all(r.status == 'cancelled' for r in results))
        self.assertEqual(core.update_status(results), 'failed')
        self.assertEqual(db_io.load_db(self.db_path)['_skus'], small_db()['_skus'])
        self.assertNotEqual(self.db_path.read_bytes(), before)  # status recorded once

    def test_cancel_event_kills_a_running_worker(self):
        cancel = threading.Event()
        timer = threading.Timer(0.3, cancel.set)
        timer.start()
        with self.assertRaises(core.UpdateCancelled):
            core._run_step_process([sys.executable, '-c', 'import time; time.sleep(30)'], env=dict(os.environ), timeout=60, cancel=cancel)
        timer.cancel()

    def test_only_bundled_workers_can_run_as_script(self):
        with tempfile.TemporaryDirectory() as directory:
            foreign = Path(directory) / 'evil.py'
            foreign.write_text('print("executed")')
            with patch.object(sys, 'argv', ['app', core.RUN_SCRIPT_FLAG, str(foreign)]), \
                 patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as raised:
                    core.maybe_run_as_script_worker(sys.argv)
            self.assertEqual(raised.exception.code, 2)
            with patch.object(sys, 'argv', ['app', core.RUN_SCRIPT_FLAG, str(foreign)]), \
                 patch.dict(os.environ, {'SPOOLSCRIBE_RUN_SCRIPT_ALLOW': directory}), \
                 patch('sys.stdout', new_callable=io.StringIO) as out:
                self.assertTrue(core.maybe_run_as_script_worker(sys.argv))
            self.assertIn('executed', out.getvalue())


class LockTests(unittest.TestCase):
    def test_a_lock_left_by_a_dead_process_is_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            lock = Path(str(path) + '.lock')
            lock.write_text('999999999')
            db_io.save_db(small_db(), path)
            self.assertFalse(lock.exists())
            self.assertTrue(path.exists())

    def test_real_child_process_state_and_abandoned_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            lock = Path(str(path) + '.lock')
            process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            try:
                lock.write_text(str(process.pid))
                os.utime(lock, (0, 0))
                with self.assertRaises(db_io.DatabaseError):
                    db_io.save_db(small_db(), path)
                self.assertTrue(lock.exists())
            finally:
                process.terminate()
                process.wait(timeout=10)
            db_io.save_db(small_db(), path)
            self.assertFalse(lock.exists())

    def test_uncertain_process_state_never_removes_a_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'db.json.lock'
            lock.write_text('1234')
            os.utime(lock, (0, 0))
            with patch.object(db_io, '_pid_is_alive', return_value=None):
                self.assertFalse(db_io._lock_is_stale(lock))
            self.assertTrue(lock.exists())

    def test_an_old_lock_of_a_live_process_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            lock = Path(str(path) + '.lock')
            lock.write_text(str(os.getpid()))
            os.utime(lock, (0, 0))
            with self.assertRaises(db_io.DatabaseError):
                db_io.save_db(small_db(), path)
            self.assertTrue(lock.exists())

    def test_a_fresh_lock_of_a_live_process_still_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            lock = Path(str(path) + '.lock')
            lock.write_text(str(os.getpid()))
            with self.assertRaises(db_io.DatabaseError):
                db_io.save_db(small_db(), path)
            lock.unlink()


class BoundedDownloadTests(unittest.TestCase):
    def test_conditional_fetch_reports_not_modified(self):
        class Opener:
            def open(self, request, timeout=0):
                self.request = request
                raise urllib.error.HTTPError(request.full_url, 304, 'Not Modified', {}, None)
        opener = Opener()
        with patch('urllib.request.build_opener', return_value=opener):
            with self.assertRaises(official_sources.NotModified):
                official_sources.fetch('https://example.invalid/data.json', etag='"abc"')
        self.assertEqual(opener.request.get_header('If-none-match'), '"abc"')
        self.assertIn('SpoolScribe', opener.request.get_header('User-agent'))
        with self.assertRaises(db_io.SourceUnavailable):
            official_sources.fetch('http://example.invalid/data.json')

    def test_throttled_source_is_retried_then_reported_as_unavailable(self):
        calls = []
        class Opener:
            def open(self, request, timeout=0):
                calls.append(request.full_url)
                raise urllib.error.HTTPError(request.full_url, 429, 'Too Many Requests', {'Retry-After': '1'}, None)
        with patch('urllib.request.build_opener', return_value=Opener()), patch('scripts.official_sources.time.sleep') as sleep:
            with self.assertRaises(db_io.SourceUnavailable) as raised:
                official_sources.fetch('https://example.invalid/products.json')
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertIn('429', str(raised.exception))

    def test_orca_filenames_cannot_escape_their_folder(self):
        for bad in ('D:evil', 'a/b', 'a\\b', '..', ' PLA', 'x\x00y'):
            with self.assertRaises(ValueError):
                download_orca_profiles.local_filename(bad)
        self.assertTrue(download_orca_profiles.local_filename('PolyLite PLA').endswith('.json'))

    def test_release_check_tolerates_development_versions(self):
        self.assertEqual(app_updates.version_tuple('0.3.1-dev'), (0, 3, 1))
        with self.assertRaises(ValueError):
            app_updates.version_tuple('dev')
        response = dict(tag_name='v0.3.1', draft=False, prerelease=False, html_url=core.APP_URL + '/releases/tag/v0.3.1')
        self.assertFalse(app_updates.parse_release(response, '0.3.1-dev')['newer'])


if __name__ == '__main__':
    unittest.main()
