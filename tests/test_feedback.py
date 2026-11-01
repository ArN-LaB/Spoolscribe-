"""Regressions from the real-screen review of 1 November; no network or user files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core
from scripts import catalogue_sources, catalogue_merge, db_io
from tests.support import small_db
from tests.test_universal import source_fixture, change


class FeedbackDataTests(unittest.TestCase):
    def test_brand_line_normalization_can_be_saved_without_deleting_metadata(self):
        db = small_db()
        db['_products']['Audit PLA']['brand'] = 'PolyLite'
        db['_brands']['PolyLite'] = {'name': 'PolyLite', 'note': 'retained'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.json'
            db_io.save_db(db, path)
            loaded = core.load_db(str(path))
            self.assertEqual(loaded['_products']['Audit PLA']['brand'], 'Polymaker')
            core.save_db(loaded, str(path))
            self.assertEqual(db_io.load_db(path)['_brands']['PolyLite']['note'], 'retained')

    def test_one_article_diameter_update_does_not_change_other_bobbins(self):
        local=small_db();local['_skus']['OTHER']=dict(local['_skus']['LOCAL'])
        incoming=copy.deepcopy(local)
        incoming['_products']['wide']=dict(incoming['_products']['Audit PLA'],diameter=2.85)
        incoming['_skus']['OTHER']['product']='wide'
        result,_=catalogue_merge.merge_catalogue(local,incoming,'Maker',100)
        a=result['_products'][result['_skus']['LOCAL']['product']]
        b=result['_products'][result['_skus']['OTHER']['product']]
        self.assertEqual(a['diameter'],1.75)
        self.assertEqual(b['diameter'],2.85)
        again,_=catalogue_merge.merge_catalogue(result,incoming,'Maker',100)
        self.assertEqual(result,again)

    def test_temperature_pair_cannot_be_inverted_by_partial_source(self):
        target = {'min_temp': 260, 'max_temp': 280}
        conflicts = []
        catalogue_merge.merge_fields(target, {'min_temp': None, 'max_temp': 230}, 'Maker', 100, conflicts, 'p')
        self.assertEqual((target['min_temp'], target['max_temp']), (260, 280))
        self.assertTrue(conflicts)

    def test_ofd_line_with_website_is_not_rejected_after_import(self):
        files = source_fixture()
        change(files, 'data/test/brand.json', name='PolyLite')
        second = {k.replace('/red/', '/blue/'): v for k, v in files.items() if '/red/' in k}
        change(second, 'data/test/PLA/pro/blue/variant.json', uuid='00000000-0000-4000-8000-000000000005')
        sizes = json.loads(second['data/test/PLA/pro/blue/sizes.json']);sizes[0]['uuid']='00000000-0000-4000-8000-000000000006'
        second['data/test/PLA/pro/blue/sizes.json']=json.dumps(sizes).encode();files.update(second)
        db, report = catalogue_sources.adapt_ofd(files, source_digest='x', preserve_curated=False)
        self.assertEqual(report['rejected'], [])
        self.assertEqual(len(db['_skus']), 2)

    def test_grouping_normalizes_brand_prefix_but_separates_diameter_and_grade(self):
        db = small_db()
        db['_skus']['LOCAL'].update(color_name='Polymaker Teal', hex='0091A5')
        db['_skus']['OFD-B'] = dict(db['_skus']['LOCAL'], color_name='Teal', hex='74CABF')
        db['_products']['large'] = dict(db['_products']['Audit PLA'], display_name='Audit PLA', diameter=2.85)
        db['_skus']['OFD-C'] = dict(db['_skus']['OFD-B'], product='large')
        groups = core.group_filaments(core.list_skus(db))
        self.assertEqual(len(groups), 2)
        small = next(g for g in groups if g['diameter']==1.75)
        self.assertEqual(small['variant_count'], 2)
        self.assertEqual(small['hex_variants'], 2)
        self.assertEqual(small['color_name'], 'Teal')
        self.assertFalse(small['ready'])
        self.assertIn('vérifier', small['quality'])

    def test_group_identity_survives_representative_and_color_changes(self):
        db = small_db();db['_skus']['OFD-B'] = dict(db['_skus']['LOCAL'])
        first = core.group_filaments(core.list_skus(db))[0]
        db['_skus']['OFD-B']['_field_sources'] = {'hex': db_io.user_correction('FF0000')}
        second = core.group_filaments(core.list_skus(db))[0]
        self.assertNotEqual(first['sku'], second['sku'])
        self.assertEqual(first['filament_id'], second['filament_id'])


from tests import test_gui as gui_fixture
if gui_fixture.HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QCheckBox


@unittest.skipUnless(gui_fixture.HAS_QT, 'Qt unavailable')
class FeedbackUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):gui_fixture.GuiTests.setUpClass()

    def setUp(self):gui_fixture.GuiTests.setUp(self)

    def test_new_install_does_not_assume_a_modified_u1_firmware(self):
        from spoolscribe import app_gui
        self.window.close()
        core.save_config(dict(core.DEFAULT_CONFIG))
        other=app_gui.MainWindow();self.addCleanup(other.close)
        self.assertEqual(other.firmware.currentData(),'unknown')
        self.assertFalse(other._can_export_for_printer())
        other.firmware.setCurrentIndex(other.firmware.findData('paxx12'))
        self.assertTrue(other._can_export_for_printer())
        other.firmware.setCurrentIndex(other.firmware.findData('stock'))
        self.assertFalse(other._can_export_for_printer())

    def test_browsing_does_not_create_or_reorder_favorites(self):
        w=self.window
        w._toggle_brand_favorite('Polymaker')
        w._choose_brand('Prusament');w._choose_brand('ROSA3D')
        self.assertEqual(core.load_config()['favorite_brands'], ['Polymaker'])
        path=Path(self.tmp.name)/'prefs.json';core.export_settings(str(path))
        w._toggle_brand_favorite('Polymaker');core.import_settings(str(path))
        w._fill_sidebar()
        starred=[w.brand_list.item(i).data(Qt.UserRole) for i in range(w.brand_list.count()) if w.brand_list.item(i).data(Qt.UserRole+1)]
        self.assertEqual(starred, ['Polymaker'])

    def test_filament_favorite_survives_reload_and_can_be_removed(self):
        w=self.window;w.current_sku='PB05001';w._show_detail('PB05001')
        w._toggle_filament_favorite();w._reload_table()
        self.assertTrue(w._is_favorite(w._group_for_sku('PB05001')))
        w._save_ui_preferences();w._restore_ui_preferences()
        w.current_sku='PB05001';w._toggle_filament_favorite()
        self.assertFalse(w._is_favorite(w._group_for_sku('PB05001')))

    def test_repeated_filter_restore_reuses_grid_cards_and_keeps_selection(self):
        w=self.window;w._save_ui_preferences()
        first=w.grid.item(0)
        cell=w.table.item(0,2)
        for _ in range(30):
            w._restore_ui_preferences()
        self.assertIs(w.grid.item(0),first)
        self.assertIs(w.table.item(0,2),cell)
        w.table.selectRow(0);selected=w.current_sku
        w._restore_ui_preferences()
        self.assertEqual(w.current_sku,selected)

    def test_old_two_pane_settings_do_not_expand_sidebar(self):
        w=self.window;cfg=core.load_config();cfg['ui']={'splitter':[950,400]};core.save_config(cfg)
        w._restore_ui_preferences();w.resize(1100,740);w.show();w.app.processEvents()
        self.assertLessEqual(w.splitter.sizes()[0],280)
        self.assertLessEqual(w.table.mapTo(w, w.table.rect().topLeft()).x(),320)
        self.assertGreater(w.table.width(),350)

    def test_hardware_controls_do_not_shrink_when_advanced_is_open(self):
        w=self.window;w._open_hardware();w.advanced_toggle.setChecked(True);w.hardware_dialog.resize(620,300);w.app.processEvents()
        self.assertGreaterEqual(w.nfc_profile.height(),24)
        self.assertGreaterEqual(w.nfc_reserve.height(),24)
        self.assertGreater(w.hardware_scroll.verticalScrollBar().maximum(),0)
        w.hardware_dialog.close()

    def test_conflicting_group_requires_variant_choice(self):
        w=self.window;db=small_db();db['_skus']['OTHER']=dict(db['_skus']['LOCAL'],hex='00FF00')
        w.db=db;w._reload_table();w.current_sku=w._all_rows[0]['sku'];w._show_detail(w.current_sku)
        self.assertFalse(w.btn_generate.isEnabled())
        w._apply_theme()
        self.assertEqual(w.swatch.text(), 'Teintes à vérifier')
        w.variant_choice.setCurrentIndex(1)
        self.assertTrue(w.btn_generate.isEnabled())
        self.assertEqual(w._build_payload()['color_hex'],db['_skus'][w.current_sku]['hex'])
