"""Audit follow-up: identities, source emptying, plausibility and worker paths."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import core
from scripts import db_io, catalogue_merge as merge
from tests.support import small_db, entry


class IdentityTests(unittest.TestCase):
    def test_product_grades_and_colour_combinations_stay_distinct(self):
        self.assertNotEqual(merge.normalized('PLA+'), merge.normalized('PLA'))
        self.assertNotEqual(merge.normalized('Blue+Green'), merge.normalized('Blue Green'))
        self.assertEqual(merge.normalized('Polymaker™ PolyLite PLA'), merge.normalized('polymaker polylite pla'))

    def test_same_article_with_different_colours_is_not_one_filament(self):
        local = small_db()
        local['_skus']['LOCAL'].update(manufacturer_sku='ART-1', color_name='Purple', hex='6A6DCD')
        incoming = small_db()
        incoming['_skus'] = {'OFD-YELLOW': dict(entry(), manufacturer_sku='ART-1', color_name='Yellow', hex='F3E500')}
        result, _ = merge.merge_catalogue(local, incoming, 'OFD', 20)
        self.assertEqual(result['_skus']['LOCAL']['hex'], '6A6DCD')
        self.assertIn('OFD-YELLOW', result['_skus'])

    def test_same_article_and_same_hex_under_another_name_still_matches(self):
        local = small_db()
        local['_skus']['LOCAL'].update(manufacturer_sku='ART-1', color_name='Jet Black', hex='000000')
        incoming = small_db()
        incoming['_skus'] = {'OFD-BLACK': dict(entry(), manufacturer_sku='ART-1', color_name='Black', hex='000000', weight=None)}
        result, _ = merge.merge_catalogue(local, incoming, 'OFD', 20)
        self.assertEqual(set(result['_skus']), {'LOCAL'})

    def test_pla_plus_family_is_not_absorbed_by_pla(self):
        local = small_db()
        local['_products']['Audit PLA']['display_name'] = 'Audit PLA'
        local['_skus']['LOCAL'].pop('manufacturer_sku', None)
        incoming = small_db()
        incoming['_products'] = {'Audit PLA+': dict(incoming['_products']['Audit PLA'], display_name='Audit PLA+', min_temp=205, max_temp=225)}
        incoming['_skus'] = {'OFD-PLUS': dict(entry(), product='Audit PLA+')}
        result, _ = merge.merge_catalogue(local, incoming, 'OFD', 20)
        self.assertIn('OFD-PLUS', result['_skus'])
        self.assertEqual(result['_products']['Audit PLA']['min_temp'], small_db()['_products']['Audit PLA']['min_temp'])


class SourceEmptyingTests(unittest.TestCase):
    def test_a_source_cannot_empty_its_own_value(self):
        incoming = small_db()
        db, _ = merge.merge_catalogue(copy.deepcopy(core.EMPTY_DB), incoming, 'Maker', 100)
        self.assertEqual(db['_skus']['LOCAL']['hex'], incoming['_skus']['LOCAL']['hex'])
        emptied = copy.deepcopy(incoming)
        emptied['_skus']['LOCAL']['hex'] = None
        emptied['_products']['Audit PLA']['density'] = None
        result, conflicts = merge.merge_catalogue(db, emptied, 'Maker', 100)
        self.assertEqual(result['_skus']['LOCAL']['hex'], incoming['_skus']['LOCAL']['hex'])
        self.assertEqual(result['_products']['Audit PLA']['density'], incoming['_products']['Audit PLA']['density'])
        self.assertTrue(any('retirée par la source' in c for c in conflicts))

    def test_a_shrunken_source_is_refused_before_merging(self):
        db = {'_source_snapshots': {'ofd': {'references': 1000}}}
        with self.assertRaises(db_io.SourceUnavailable):
            db_io.check_source_shrink(db, 'ofd', 120, 'OFD')
        db_io.check_source_shrink(db, 'ofd', 900, 'OFD')
        db_io.check_source_shrink({}, 'ofd', 3, 'OFD')


class PlausibilityTests(unittest.TestCase):
    def test_black_hex_for_a_white_source_colour_needs_confirmation(self):
        db = small_db()
        sku = db['_skus']['LOCAL']
        sku.update(color_name='White', hex='000000', source='OFD')
        self.assertIsNotNone(db_io.implausible_color(sku))
        rows = {r['sku']: r for r in core.list_skus(db)}
        self.assertFalse(rows['LOCAL']['ready'])
        self.assertIn('Couleur à vérifier', rows['LOCAL']['quality'])
        with self.assertRaises(core.MissingColorError):
            core.build_openspool(sku, db['_products']['Audit PLA'])
        # An explicit user confirmation of the same HEX is trusted.
        sku['_field_sources'] = {'color_name': {'source': 'OFD', 'rank': 20, 'value': 'White'}}
        self.assertIsNone(db_io.implausible_color(sku))
        core.build_openspool(sku, db['_products']['Audit PLA'])

    def test_historical_entries_without_source_are_not_second_guessed(self):
        sku = dict(entry(), color_name='White', hex='000000')
        sku.pop('source', None)
        self.assertIsNone(db_io.implausible_color(sku))

    def test_out_of_range_source_physics_block_export_until_corrected(self):
        db = small_db()
        product = db['_products']['Audit PLA']
        product.update(density=7.23, bed_max_temp=0, bed_min_temp=0)
        product['_field_sources'] = {k: {'source': 'OFD', 'rank': 20, 'value': v} for k, v in product.items() if not k.startswith('_')}
        issues = db_io.implausible_physical(product)
        self.assertEqual(len(issues), 2)
        with self.assertRaises(core.ExportValidationError):
            core.build_openspool(db['_skus']['LOCAL'], product)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            db_io.save_db(db, path)
            loaded = db_io.load_db(path)
            core.set_product_physical(loaded, 'LOCAL', {'density': 1.24, 'bed_min_temp': 50, 'bed_max_temp': 60}, path=str(path))
            self.assertEqual(db_io.implausible_physical(loaded['_products']['Audit PLA']), [])
            core.build_openspool(loaded['_skus']['LOCAL'], loaded['_products']['Audit PLA'])

    def test_orca_profile_without_plate_temperature_has_unknown_bed(self):
        values = db_io.orca_values({'nozzle_temperature_range_low': [190], 'nozzle_temperature_range_high': [220],
                                    'filament_density': [1.24], 'filament_diameter': [1.75]})
        self.assertIsNone(values['bed_min_temp'])
        self.assertIsNone(values['bed_max_temp'])


class WorkerPathTests(unittest.TestCase):
    def test_workers_never_default_to_the_repository_fixture(self):
        with patch.dict(os.environ, {'SPOOLSCRIBE_DATA_HOME': '/tmp/spoolscribe-audit'}):
            self.assertEqual(db_io.default_db_path(), os.path.join('/tmp/spoolscribe-audit', 'data', 'polymaker_db.json'))
        env = {k: v for k, v in os.environ.items() if k != 'SPOOLSCRIBE_DATA_HOME'}
        with patch.dict(os.environ, env, clear=True):
            path = Path(db_io.default_db_path())
        self.assertNotIn(Path(__file__).resolve().parents[1], path.parents)
        self.assertEqual(path.name, 'polymaker_db.json')

    def test_development_snapshot_entries_carry_provenance_when_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'polymaker_db.json'
            db_io.save_db(copy.deepcopy(core.EMPTY_DB), base)
            snapshot = small_db()
            snapshot['_skus']['LOCAL']['source'] = 'Open Filament Database'
            db_io.save_db(snapshot, base.with_name('catalogue_ofd.json'))
            db = core.load_db(str(base))
            self.assertIn('hex', db['_skus']['LOCAL']['_field_sources'])
            self.assertEqual(db['_skus']['LOCAL']['_field_sources']['hex']['source'], 'Open Filament Database')


if __name__ == '__main__':
    unittest.main()
