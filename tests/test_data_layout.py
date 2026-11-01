"""Data cleanup must preserve fixtures, old user paths and an empty installer."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.resource_paths import canonical_resource_path, legacy_snapshot_path
from spoolscribe import core
from spoolscribe.packaging_rules import resources
from tests.support import ROOT, catalogue


class DataLayoutTests(unittest.TestCase):
    def test_all_54_historical_files_keep_their_original_bytes(self):
        fixture = json.loads((ROOT/'tests/fixtures/manifest.json').read_text(encoding='utf-8'))['files']
        self.assertEqual(len(fixture), 54)
        for name, entry in fixture.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), entry['sha256'], name)
        self.assertEqual(sum(name.startswith('tests/fixtures/orca/') for name in fixture),48)

    def test_the_three_historical_brand_paths_still_resolve_without_rewriting_catalogues(self):
        database = catalogue()
        before = json.dumps(database, sort_keys=True)
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DATA_HOME', directory):
            for brand in ('Polymaker', 'Prusament', 'ROSA3D'):
                path = core.logo_abs_path(database, brand)
                self.assertTrue(Path(path).is_file(), brand)
                self.assertTrue(Path(path).is_relative_to(ROOT/'data/brands/logos'))
        self.assertEqual(json.dumps(database,sort_keys=True),before)

    def test_an_older_user_logo_has_priority_and_is_never_moved_or_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory);old = user/'data/polymaker_logo.svg';old.parent.mkdir()
            raw=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle r="4" cx="5" cy="5"/></svg>'
            old.write_bytes(raw)
            with patch.multiple(core, DATA_HOME=str(user), _LOGO_MANIFEST={
                    'polymaker':'data/brands/logos/polymaker-lines.svg'}):
                self.assertEqual(core.logo_abs_path({},'Polymaker'),str(old.resolve()))
            self.assertEqual(old.read_bytes(),raw)
            self.assertFalse((user/'data/brands').exists())

    def test_packaging_excludes_undeclared_images_and_every_fixture(self):
        declared = resources(ROOT)
        self.assertFalse(any(name.startswith('tests/') for name in declared))
        self.assertNotIn('data/polymaker_db.json',declared)
        self.assertIn('data/translations/messages.json',declared)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in declared:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
            extra=root/'data/brands/logos/private.png';extra.write_bytes(b'not a public asset')
            self.assertNotIn('data/brands/logos/private.png',resources(root))
            self.assertEqual(extra.read_bytes(),b'not a public asset')

    def test_legacy_dump_uses_a_user_copy_before_the_read_only_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            self.assertEqual(legacy_snapshot_path(ROOT,home),ROOT/'tests/fixtures/legacy/thefilamentdb.jsonl.gz')
            user=home/'data/thefilamentdb.jsonl.gz';user.parent.mkdir();user.write_bytes(b'custom')
            self.assertEqual(legacy_snapshot_path(ROOT,home),user)
            self.assertEqual(user.read_bytes(),b'custom')

    def test_the_published_printer_catalogue_endpoint_is_unchanged(self):
        from spoolscribe import printer_profiles
        self.assertEqual(printer_profiles.PRINTERS_URL,
                         'https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers.json')
        self.assertEqual(printer_profiles.bundled_path(),ROOT/'data/printers.json')
        self.assertEqual(canonical_resource_path('data/prusament_logo.png'),'data/brands/logos/prusament.svg')

    def test_retouched_shared_artwork_keeps_every_provenance_entry_consistent(self):
        import importlib.util
        from PIL import Image
        spec=importlib.util.spec_from_file_location('logo_import',ROOT/'.github/scripts/import_brand_logos.py')
        importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'data/brands/logos/shared.png'
            target.parent.mkdir(parents=True)
            image=Image.new('RGBA',(24,16),(0,0,0,0));image.save(target)
            raw=target.read_bytes()
            manifest={key:dict(name=key,path='data/brands/logos/shared.png',sha256='old',source_commit=key)
                      for key in ('First','Second')}
            with patch.object(importer,'ROOT',root):
                importer.record(manifest,'First','First',target,raw,image,{})
            for key in manifest:
                self.assertEqual(manifest[key]['sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual((manifest[key]['width'],manifest[key]['height']),(24,16))
                self.assertEqual(manifest[key]['source_commit'],key)

    def test_standalone_legacy_workers_default_to_user_storage_without_an_environment_override(self):
        import os, subprocess, sys
        workers=['download_orca_profiles','scrape_wiki_hex','seed_rosa3d','sync_multibrand_assets',
                 'scrape_thefilamentdb_hex','seed_prusament','scrape_wholesale',
                 'scrape_thefilamentdb_multibrand_hex','sync_polymaker_brand_assets',
                 'import_orca_profiles','scrape_spoolman_multibrand_hex','scrape_spoolman_hex','scrape_internal_exact_hex']
        with tempfile.TemporaryDirectory() as directory:
            env=dict(os.environ,HOME=directory,USERPROFILE=directory,APPDATA=directory,XDG_CONFIG_HOME=directory,
                     PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
            env.pop('SPOOLSCRIBE_DATA_HOME',None)
            code='''import importlib,json,sys
from pathlib import Path
from scripts.db_io import default_db_path
expected=Path(default_db_path()).parents[1]
for name in json.loads(sys.argv[1]):
    worker=importlib.import_module('scripts.'+name)
    assert Path(worker._DATA_HOME)==expected,(name,worker._DATA_HOME,expected)
    if hasattr(worker,'DB_FILE'):assert Path(worker.DB_FILE)==Path(default_db_path())
print('13 workers use user storage; no repository write')
'''
            result=subprocess.run([sys.executable,'-B','-c',code,json.dumps(workers)],env=env,cwd=directory,
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(list(Path(directory).rglob('*.json')))

    def test_curated_legacy_sync_reads_relocated_artwork_without_copying_it_into_user_data(self):
        from scripts import sync_multibrand_assets, db_io
        from tests.support import small_db
        import sys
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)/'data';database=data/'polymaker_db.json'
            db_io.save_db(small_db(),database)
            with patch.multiple(sync_multibrand_assets,DATA_DIR=str(data),DB_FILE=str(database),
                                BRANDS=[('ROSA3D','rosa3d','rosa3d_logo.png',True)]), \
                    patch.object(sync_multibrand_assets,'_fetch_json',return_value={'id':'rosa3d','name':'ROSA3D'}), \
                    patch.object(sync_multibrand_assets,'_fetch_bytes',side_effect=AssertionError('Unexpected download')), \
                    patch.object(sys,'argv',['worker']):
                sync_multibrand_assets.main()
            self.assertEqual(db_io.load_db(database)['_brands']['ROSA3D']['logo_path'],
                             'data/brands/logos/rosa3d.png')
            self.assertFalse((data/'rosa3d_logo.png').exists())
