"""Shared printer catalogue contract: strict reading, update decisions, Companion snapshot.

See docs/PRINTER-CATALOGUE-CONTRACT.md. All tests stay offline (tests.support).
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from tests.support import ROOT
from spoolscribe import printer_profiles as printers, core
from tests import test_gui as fixture

sys.path.insert(0, str(ROOT / 'scripts'))
import export_printer_catalogue as exporter  # noqa: E402

REAL = (ROOT / 'data/printers.json').read_bytes()
LEGACY = (ROOT / exporter.LEGACY).read_bytes()


def companion_root():
    """Companion checkout to compare with, if any (env, then the sibling folder)."""
    for candidate in (os.environ.get('SPOOLSCRIBE_COMPANION_ROOT'), ROOT.parent / 'spoolscribe_companion'):
        if candidate and (Path(candidate) / 'pubspec.yaml').is_file():
            return Path(candidate)
    return None


def with_updated(raw: bytes, updated: str, **changes) -> bytes:
    doc = json.loads(raw)
    doc['updated'] = updated
    doc.update(changes)
    return json.dumps(doc, ensure_ascii=False).encode('utf-8')


class SharedCorpusTests(unittest.TestCase):
    def test_every_declared_case_matches_the_python_reader_and_is_reproducible(self):
        first = exporter.build_outputs(ROOT)   # raises SystemExit on any mismatch
        self.assertEqual(first, exporter.build_outputs(ROOT))
        corpus = json.loads(first[exporter.CORPUS])
        bases = {k: v['document'] for k, v in corpus['bases'].items()}
        self.assertEqual(hashlib.sha256(REAL).hexdigest(), corpus['bases']['real']['sha256'])
        for case in corpus['documents']:
            doc = exporter.apply_ops(bases[case['input']['document']['base']], case['input']['document']['ops'])
            try:
                printers.validate_catalogue(doc)
                code = None
            except printers.CatalogueError as exc:
                code = exc.code
            self.assertEqual(code, case['expect']['code'], case['id'])
            if code is None:
                view = exporter.canonical(printers.projection(doc))
                self.assertEqual(hashlib.sha256(view).hexdigest(), case['expect']['projectionSha256'], case['id'])
        codes = {c['expect']['code'] for c in corpus['documents'] + corpus['bytes']}
        # Every structural and byte-level rule is exercised at least once.
        self.assertTrue({'format', 'version', 'schema', 'updated', 'source', 'groups', 'printers', 'printer', 'id',
                         'duplicate', 'hidden', 'group', 'text', 'fields', 'firmwares', 'url', 'formats',
                         'reader_formats', 'metadata', 'date', 'export', 'external_readers', 'unverified',
                         'size', 'utf8', 'json'} <= codes)
        self.assertEqual({u['expect']['decision'] for u in corpus['updates']},
                         {'install', 'unchanged', 'conflict', 'regression', 'not_admissible'})

    def test_extra_fields_and_future_tokens_are_inert(self):
        corpus = json.loads(exporter.build_outputs(ROOT)[exporter.CORPUS])
        by_id = {c['id']: c for c in corpus['documents']}
        self.assertEqual(by_id['real-inert-extras']['expect']['projectionSha256'],
                         by_id['real']['expect']['projectionSha256'])
        doc = exporter.apply_ops(json.loads(REAL), by_id['real-future-reader-token']['input']['document']['ops'])
        view = printers.projection(doc)['printers'][0]['configurations'][0]
        self.assertIn('openrfid_v2', view['readerFormats'])
        self.assertEqual(view['formats'], ['openspool'], 'an unknown token never becomes an export')

    def test_companion_outputs_are_current(self):
        root = companion_root()
        if root is None:
            self.skipTest('no Companion checkout next to this repository')
        self.assertEqual(exporter.differences(root, exporter.build_outputs(ROOT)), [])


class HistoricalReadingTests(unittest.TestCase):
    def test_v1_without_metadata_is_readable_with_unknowns_and_no_conclusions(self):
        doc = printers.parse_catalogue_bytes(LEGACY)
        self.assertNotIn('configuration_schema', doc)
        view = printers.projection(doc)
        self.assertIsNone(view['configurationSchema'])
        u1 = next(p for p in view['printers'] if p['id'] == 'u1')
        stock = next(c for c in u1['configurations'] if c['id'] == 'stock')
        for key in ('connection', 'firmwareKind', 'effect', 'evidence', 'readerFormats', 'checked'):
            self.assertIsNone(stock[key], key)
        self.assertEqual(stock['formats'], [])
        self.assertEqual(printers.update_refusal(doc), None)
        self.assertEqual(printers.compare_update(printers.parse_catalogue_bytes(REAL), doc), 'regression')

    def test_hidden_aliases_and_historical_identifiers_are_kept(self):
        view = printers.projection(printers.parse_catalogue_bytes(REAL))
        self.assertEqual(sorted(p['id'] for p in view['printers'] if p['hidden']), ['bambu_openspool', 'prusa'])
        self.assertEqual(printers.resolve('bambu_openspool', 'stock'), ('bambu', 'openspool_network'))
        self.assertEqual(printers.resolve('u1_stock'), ('u1', 'stock'))
        self.assertEqual(printers.resolve('prusa', 'stock'), ('prusa_generic', 'stock'))

    def test_dates_are_compared_by_time_value(self):
        p = printers.parse_instant
        self.assertEqual(p('2026-11-01T22:00:00+08:00'), p('2026-11-01T14:00:00Z'))
        self.assertLess(p('2026-11-01'), p('2026-11-01T14:00:00Z'))
        self.assertGreater(p('2026-11-01T14:00:00.5Z'), p('2026-11-01T14:00:00Z'))
        # Textual order would say the opposite here.
        self.assertLess(p('2026-11-01T23:00:00+10:00'), p('2026-11-01T14:00:00Z'))
        for bad in ('2026-02-30', '2026-11-01T14:00:00', '2026-11-01T24:00:00Z', '0000-01-01', '', None, 20261101):
            self.assertIsNone(p(bad), bad)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {'SPOOLSCRIBE_DATA_HOME': self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        profiles = patch.dict(printers.PROFILES)  # restored after each test
        profiles.start()
        self.addCleanup(profiles.stop)
        self.target = printers.user_path()

    def listing(self):
        return sorted(p.name for p in self.target.parent.glob('*')) if self.target.parent.exists() else []

    def test_a_newer_list_is_installed_and_profiles_swap_in_place(self):
        before = id(printers.PROFILES)
        raw = with_updated(REAL, '2026-11-02T00:00:00Z')
        result = printers.install_catalogue(raw)
        self.assertEqual(result['_update'], 'installed')
        self.assertEqual(printers.load_catalogue()['_origin'], 'user')
        self.assertEqual(id(printers.PROFILES), before, 'the GUI keeps its global reference')
        self.assertEqual(printers.semantic_bytes(json.loads(self.target.read_bytes())),
                         printers.semantic_bytes(json.loads(raw)))

    def test_same_data_is_unchanged_even_reformatted_and_nothing_is_written(self):
        compact = json.dumps(json.loads(REAL), separators=(',', ':'), ensure_ascii=False).encode()
        for raw in (REAL, compact, with_updated(REAL, '2026-11-01T22:00:00+08:00')):
            self.assertEqual(printers.install_catalogue(raw)['_update'], 'unchanged')
        self.assertFalse(self.target.exists())

    def test_conflict_regression_and_inadmissible_lists_keep_the_active_one(self):
        doc = json.loads(REAL)
        doc['printers'][0]['label'] = 'Snapmaker U1 bis'
        with self.assertRaises(printers.CatalogueError) as ctx:
            printers.install_catalogue(json.dumps(doc).encode())
        self.assertEqual(ctx.exception.code, 'conflict')
        self.assertFalse(self.target.exists())
        printers.install_catalogue(with_updated(REAL, '2026-11-03T00:00:00Z'))
        active = self.target.read_bytes()
        # Newer than the bundled list but older than the active user copy.
        for raw, code in ((with_updated(REAL, '2026-11-02T00:00:00Z'), 'regression'), (LEGACY, 'regression'),
                          (with_updated(REAL, '2026-11-04', source='http://example.org'), 'source'),
                          (b'{"format":', 'json'), (b'\xef\xbb\xbf' + REAL, 'utf8')):
            with self.assertRaises(printers.CatalogueError) as ctx:
                printers.install_catalogue(raw)
            self.assertEqual(ctx.exception.code, code)
            self.assertEqual(self.target.read_bytes(), active)
        undated = json.loads(REAL)
        del undated['updated']
        with self.assertRaises(printers.CatalogueError) as ctx:
            printers.install_catalogue(json.dumps(undated).encode())
        self.assertEqual(ctx.exception.code, 'updated_missing')

    def test_storage_failure_keeps_file_and_profiles(self):
        printers.install_catalogue(with_updated(REAL, '2026-11-02T00:00:00Z'))
        active, profiles = self.target.read_bytes(), copy.deepcopy(dict(printers.PROFILES))
        from scripts import db_io
        with patch.object(db_io, 'atomic_write', side_effect=OSError('disk full')):
            with self.assertRaises(printers.CatalogueError) as ctx:
                printers.install_catalogue(with_updated(REAL, '2026-11-03T00:00:00Z'))
        self.assertEqual(ctx.exception.code, 'storage')
        self.assertEqual(self.target.read_bytes(), active)
        self.assertEqual(dict(printers.PROFILES), profiles)

    def test_a_concurrent_change_is_preserved_not_overwritten(self):
        printers.install_catalogue(with_updated(REAL, '2026-11-02T00:00:00Z'))
        concurrent = with_updated(REAL, '2026-11-05T00:00:00Z')
        real_compare = printers.compare_update

        def compare_then_someone_writes(active, candidate):
            self.target.write_bytes(concurrent)  # another process, after our revision was read
            return real_compare(active, candidate)

        with patch.object(printers, 'compare_update', side_effect=compare_then_someone_writes):
            with self.assertRaises(printers.CatalogueError) as ctx:
                printers.install_catalogue(with_updated(REAL, '2026-11-03T00:00:00Z'))
        self.assertEqual(ctx.exception.code, 'storage')
        self.assertEqual(self.target.read_bytes(), concurrent)
        self.assertTrue(any('.concurrent-' in name for name in self.listing()))

    def test_profiles_are_prepared_before_anything_is_written(self):
        with patch.object(printers, '_profiles', side_effect=KeyError('label')):
            with self.assertRaises(KeyError):
                printers.install_catalogue(with_updated(REAL, '2026-11-02T00:00:00Z'))
        self.assertFalse(self.target.exists())

    def test_bad_or_undated_user_copies_never_replace_the_bundled_list(self):
        self.target.parent.mkdir(parents=True)
        undated = json.loads(REAL)
        del undated['updated']
        for raw in (b'not json', b'\xef\xbb\xbf' + REAL, json.dumps(undated).encode(), LEGACY,
                    with_updated(REAL, '2026-11-01T13:59:59Z')):
            self.target.write_bytes(raw)
            self.assertEqual(printers.load_catalogue()['_origin'], 'bundled')
        self.target.write_bytes(with_updated(REAL, '2026-11-01T14:00:00Z'))
        self.assertEqual(printers.load_catalogue()['_origin'], 'user', 'equal date keeps the user copy (v1 rule)')

    def test_refresh_keeps_url_limit_and_404_behaviour(self):
        calls = []

        def not_found(url, limit):
            calls.append((url, limit))
            raise HTTPError(url, 404, 'Not Found', {}, None)

        self.assertIsNone(printers.refresh_catalogue(not_found))
        self.assertEqual(calls, [(printers.PRINTERS_URL, 512 * 1024)])
        with self.assertRaises(HTTPError):
            printers.refresh_catalogue(lambda *_: (_ for _ in ()).throw(HTTPError('u', 503, 'Unavailable', {}, None)))
        with self.assertRaises(TimeoutError):
            printers.refresh_catalogue(lambda *_: (_ for _ in ()).throw(TimeoutError('timed out')))
        self.assertFalse(self.target.exists())


class ExportInvariantTests(unittest.TestCase):
    def test_exports_follow_the_unchanged_historical_rule_for_every_configuration(self):
        doc = json.loads(REAL)
        for printer in doc['printers']:
            for fw in printer['firmwares']:
                expected = tuple(fw.get('formats', ['openspool'] if fw['openspool'] else []))
                if printer['id'] in printers._LEGACY_IDS:
                    continue  # historical aliases resolve to their replacement (tested above)
                self.assertEqual(printers.formats(printer['id'], fw['id']), expected, (printer['id'], fw['id']))
                self.assertEqual(printers.can_export(printer['id'], fw['id']), bool(expected))
        self.assertEqual(printers.EXPORT_FORMATS, ('openspool', 'opentag3d'))


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.companion = Path(self.tmp.name) / 'companion'
        (self.companion / 'assets/compatibility').mkdir(parents=True)
        (self.companion / 'pubspec.yaml').write_text('name: probe\n')
        (self.companion / 'assets/compatibility/keep.txt').write_text('other asset')

    def run_cli(self, *extra, env=None):
        return subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/export_printer_catalogue.py'),
                               '--companion-root', str(self.companion), *extra],
                              capture_output=True, text=True, env=env or dict(os.environ))

    def test_write_then_check_is_deterministic_and_check_never_writes(self):
        self.assertEqual(self.run_cli('--check').returncode, 1)
        self.assertFalse((self.companion / exporter.SNAPSHOT).exists(), '--check wrote a file')
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        files = {name: (self.companion / name).read_bytes() for name in exporter.OUTPUTS}
        self.assertEqual(files[exporter.SNAPSHOT], REAL)
        again = self.run_cli()
        self.assertIn('nothing (already identical)', again.stdout)
        self.assertEqual({n: (self.companion / n).read_bytes() for n in exporter.OUTPUTS}, files)
        self.assertEqual(self.run_cli('--check').returncode, 0)
        (self.companion / exporter.MANIFEST).write_text('{}')
        self.assertEqual(self.run_cli('--check').returncode, 1)
        self.assertEqual((self.companion / exporter.MANIFEST).read_text(), '{}')
        self.assertEqual((self.companion / 'assets/compatibility/keep.txt').read_text(), 'other asset')
        manifest = json.loads(files[exporter.MANIFEST])
        self.assertEqual(manifest['provenance'], 'local-canonical')
        self.assertEqual(manifest['snapshot']['sha256'], hashlib.sha256(REAL).hexdigest())
        self.assertEqual(manifest['catalogue']['updated'], '2026-11-01T14:00:00Z')
        self.assertIn(manifest['source']['catalogueAgainstHead'], ('identical', 'modified', 'untracked', 'unknown'))
        self.assertNotIn('2026-11-0', json.dumps(manifest['source']), 'no run time in the artefacts')

    def test_personal_data_and_settings_are_never_read_or_created(self):
        home = Path(self.tmp.name) / 'home'
        (home / 'data').mkdir(parents=True)
        decoy = with_updated(REAL, '2099-01-01T00:00:00Z')
        (home / 'data/printers.json').write_bytes(decoy)
        before = sorted(str(p) for p in home.rglob('*'))
        env = dict(os.environ, SPOOLSCRIBE_DATA_HOME=str(home), SPOOLSCRIBE_CONFIG_PATH=str(home / 'config.json'))
        result = self.run_cli(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.companion / exporter.SNAPSHOT).read_bytes(), REAL)
        self.assertEqual(sorted(str(p) for p in home.rglob('*')), before)


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class RefreshGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)

    def test_a_removed_printer_stays_to_be_specified_and_the_saved_choice_is_kept(self):
        w = self.window
        cfg = core.load_config()
        cfg['network_consent'] = True
        core.save_config(cfg)
        w.printer.setCurrentIndex(w.printer.findData('flashforge_ad5x'))
        w.firmware.setCurrentIndex(w.firmware.findData('zmod'))
        saved = Path(core.CONFIG_PATH).read_bytes()
        with patch.dict(printers.PROFILES, copy.deepcopy(printers.PROFILES)):
            def refresh(_fetch):
                del printers.PROFILES['flashforge_ad5x']
                return {'updated': '2026-11-02T00:00:00Z', 'printers': list(printers.PROFILES), '_update': 'installed'}
            with patch.object(printers, 'refresh_catalogue', side_effect=refresh):
                w._update_printers()
            self.assertIsNone(w.printer.currentData(), 'no other machine chosen for the user')
            self.assertFalse(w._can_export_for_printer())
            self.assertIn('plus dans la liste', w.printers_origin.text())
            self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), saved, 'saved choice not overwritten')

    def test_an_unchanged_list_says_so_and_keeps_the_choice(self):
        w = self.window
        cfg = core.load_config()
        cfg['network_consent'] = True
        core.save_config(cfg)
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12_openrfid'))
        with patch.object(printers, 'refresh_catalogue', return_value=dict(printers.load_catalogue(), _update='unchanged')):
            w._update_printers()
        self.assertEqual((w.printer.currentData(), w.firmware.currentData()), ('u1', 'paxx12_openrfid'))

    def test_without_consent_nothing_is_fetched(self):
        w = self.window
        with patch.object(printers, 'refresh_catalogue') as refresh, \
                patch('spoolscribe.ui_catalogue.QMessageBox.information') as info:
            w._update_printers()
        refresh.assert_not_called()
        info.assert_called_once()


@unittest.skipUnless(fixture.HAS_QT, 'PySide6 non installé : contrôles GUI non mesurés')
class SetupKeptAfterRefreshTests(unittest.TestCase):
    """007-F01: the confirmed (printer, setup) pair survives a successful list refresh.

    A setup that is gone stays explicitly to be specified, even when a single
    other one remains: nothing is chosen, saved or exported on the user's behalf.
    Only the download is replaced by a double; the GUI transition, the saved
    configuration and the export are the real ones.
    """
    @classmethod
    def setUpClass(cls):
        fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        profiles = patch.dict(printers.PROFILES, copy.deepcopy(printers.PROFILES))
        profiles.start()
        self.addCleanup(profiles.stop)

    def choose(self, printer, setup):
        w = self.window
        cfg = core.load_config()
        cfg['network_consent'] = True
        core.save_config(cfg)
        w.printer.setCurrentIndex(w.printer.findData(printer))
        w.firmware.setCurrentIndex(w.firmware.findData(setup))
        self.assertEqual((w.printer.currentData(), w.firmware.currentData()), (printer, setup))
        return Path(core.CONFIG_PATH).read_bytes()

    def refresh(self, change=None, *, response='installed', error=None):
        """Run the real ``_update_printers``; returns the (printer, setup) pairs saved and the setups shown meanwhile."""
        w, saved, shown = self.window, [], []
        real_save = core.save_config

        def save(cfg):
            saved.append((cfg.get('printer_profile'), cfg.get('printer_firmware')))
            real_save(cfg)

        def fetched(_fetch):
            if error:
                raise error
            if response is None:
                return None  # HTTP 404: no list published for this version
            if change:
                change(printers.PROFILES)
            return {'updated': '2026-11-02T00:00:00Z', 'printers': list(printers.PROFILES), '_update': response}

        def track(*_):
            shown.append(w.firmware.currentData())

        w.firmware.currentIndexChanged.connect(track)
        try:
            with patch.object(printers, 'refresh_catalogue', side_effect=fetched), \
                    patch.object(core, 'save_config', side_effect=save):
                w._update_printers()
        finally:
            w.firmware.currentIndexChanged.disconnect(track)
        return saved, shown

    @staticmethod
    def rename(printer, old, new):
        def change(profiles):
            setup = next(f for f in profiles[printer]['firmwares'] if f['id'] == old)
            setup.update(id=new, label='Different reader configuration', choice_label='Replacement reader')
        return change

    @staticmethod
    def keep_only(printer, *ids):
        def change(profiles):
            profiles[printer]['firmwares'] = [f for f in profiles[printer]['firmwares'] if f['id'] in ids]
        return change

    def export(self):
        w = self.window
        with patch('spoolscribe.app_gui.QMessageBox.information'):
            w.current_sku = 'PB05001'
            w._show_detail('PB05001')
            w._generate()
        return list(Path(core.OUTPUT_DIR).glob('*.json'))

    def assert_to_be_specified(self, printer, others):
        w = self.window
        self.assertEqual((w.printer.currentData(), w.firmware.currentData()), (printer, 'unknown'))
        self.assertFalse(w._can_export_for_printer())
        self.assertEqual(w.nfc_format.count(), 0, 'no format offered for an unconfirmed setup')
        self.assertIn('Configuration à préciser', w.printers_origin.text())
        cfg = core.load_config()
        self.assertEqual((cfg['printer_profile'], cfg['printer_firmware']), (printer, 'unknown'), 'explicit marker only')
        self.assertNotIn(cfg['printer_firmware'], others)
        self.assertEqual(self.export(), [], 'no export for an unconfirmed setup')

    def test_a_confirmed_setup_still_listed_is_kept_exactly(self):
        before = self.choose('u1', 'paxx12_openrfid')
        could = self.window._can_export_for_printer()
        saved, shown = self.refresh(self.keep_only('u1', 'paxx12_openrfid', 'stock'))
        w = self.window
        self.assertEqual((w.printer.currentData(), w.firmware.currentData()), ('u1', 'paxx12_openrfid'))
        self.assertEqual(w._can_export_for_printer(), could)
        self.assertEqual(set(saved), {('u1', 'paxx12_openrfid')})
        self.assertNotIn('stock', shown)
        self.assertNotIn('Configuration à préciser', w.printers_origin.text())
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)

    def test_the_sole_confirmed_setup_removed_is_not_replaced(self):
        self.choose('openspool', 'any')
        self.assertTrue(self.window._can_export_for_printer())
        saved, shown = self.refresh(self.rename('openspool', 'any', 'replacement_reader'))
        self.assert_to_be_specified('openspool', ['replacement_reader'])
        self.assertNotIn('replacement_reader', [setup for _, setup in saved], 'never saved, even transiently')
        self.assertNotIn('replacement_reader', shown, 'no transient switch through a Qt signal')

    def test_a_removed_setup_among_several_does_not_fall_back_to_the_first(self):
        self.choose('flashforge_ad5x', 'kiln')
        saved, shown = self.refresh(self.keep_only('flashforge_ad5x', 'stock', 'zmod', 'lanetag'))
        self.assert_to_be_specified('flashforge_ad5x', ['stock', 'zmod', 'lanetag'])
        self.assertLessEqual({setup for _, setup in saved}, {'unknown'})
        self.assertFalse({'stock', 'zmod', 'lanetag'} & set(shown))

    def test_a_setup_still_to_be_specified_is_not_confirmed_when_one_remains(self):
        self.choose('flashforge_ad5x', 'unknown')
        saved, shown = self.refresh(self.keep_only('flashforge_ad5x', 'zmod'))
        self.assert_to_be_specified('flashforge_ad5x', ['zmod'])
        self.assertLessEqual({setup for _, setup in saved}, {'unknown'})
        self.assertNotIn('zmod', shown)

    def test_the_unconfirmed_state_survives_a_restart(self):
        self.choose('openspool', 'any')
        self.refresh(self.rename('openspool', 'any', 'replacement_reader'))
        self.window.close()
        self.window = fixture.app_gui.MainWindow()
        self.addCleanup(self.window.close)
        self.assertEqual((self.window.printer.currentData(), self.window.firmware.currentData()), ('openspool', 'unknown'))
        self.assertFalse(self.window._can_export_for_printer())
        self.assertEqual(core.load_config()['printer_firmware'], 'unknown')

    def test_an_explicit_choice_after_removal_is_saved_and_exports_follow_it(self):
        self.choose('openspool', 'any')
        self.refresh(self.rename('openspool', 'any', 'replacement_reader'))
        w = self.window
        # The user's own clicks: reader, then the setup offered for it.
        w.reader_buttons.buttons[printers.configuration('openspool', 'replacement_reader')['connection']].click()
        self.assertEqual(w.firmware.currentData(), 'unknown', 'a route alone confirms nothing')
        w.setup_buttons.buttons['replacement_reader'].click()
        self.assertEqual(w.firmware.currentData(), 'replacement_reader')
        cfg = core.load_config()
        self.assertEqual((cfg['printer_profile'], cfg['printer_firmware']), ('openspool', 'replacement_reader'))
        self.assertEqual([w.nfc_format.itemData(i) for i in range(w.nfc_format.count())],
                         list(printers.formats('openspool', 'replacement_reader')))
        self.assertTrue(w._can_export_for_printer())
        files = self.export()
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text(encoding='utf-8')),
                         json.loads(core.serialize_openspool(w._build_payload(), **w._nfc_options())))

    def test_refusals_errors_404_and_unchanged_keep_the_pair_and_its_bytes(self):
        before = self.choose('openspool', 'any')
        for label, kwargs in (('refus', {'error': printers.CatalogueError('regression', 'older list')}),
                              ('erreur', {'error': OSError('timeout')}),
                              ('404', {'response': None}),
                              ('inchangée', {'response': 'unchanged'})):
            with self.subTest(label):
                saved, shown = self.refresh(**kwargs)
                w = self.window
                self.assertEqual((w.printer.currentData(), w.firmware.currentData()), ('openspool', 'any'))
                self.assertTrue(w._can_export_for_printer())
                self.assertEqual((saved, shown), ([], []))
                self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
