"""Visual catalogue and packaging preferences; offline synthetic data only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import core
from tests import test_gui as fixture
from tests.support import small_db


class PackagingTests(unittest.TestCase):
    def test_preference_selects_only_real_packaging_and_preserves_input(self):
        variants=[dict(sku='A',weight=250),dict(sku='B',weight=1000,spool_refill=False),dict(sku='C',weight=1000,spool_refill=True)]
        original=copy.deepcopy(variants)
        self.assertEqual(core.preferred_packaging(variants,{'preferred_weight_g':1000,'preferred_packaging':'refill'},'A')['sku'],'C')
        self.assertEqual(core.preferred_packaging(variants,{'preferred_weight_g':2000},'A')['sku'],'A')
        self.assertEqual(variants,original)

    def test_packaging_settings_roundtrip_and_invalid_import_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(core,'CONFIG_PATH',str(Path(directory)/'config.json')):
            cfg=dict(core.DEFAULT_CONFIG,preferred_weight_g=3000,preferred_packaging='refill');core.save_config(cfg)
            out=Path(directory)/'export.json';core.export_settings(str(out))
            core.save_config(dict(core.DEFAULT_CONFIG));core.import_settings(str(out))
            self.assertEqual(core.load_config()['preferred_weight_g'],3000)
            self.assertEqual(core.load_config()['preferred_packaging'],'refill')
            doc=json.loads(out.read_text());doc['settings']['preferred_weight_g']=True;out.write_text(json.dumps(doc))
            before=Path(core.CONFIG_PATH).read_bytes()
            with self.assertRaises(ValueError):core.import_settings(str(out))
            self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class VisualWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_default_packaging_and_explicit_choice_do_not_resolve_a_color_conflict(self):
        w=self.window;db=small_db();db['_skus']['LOCAL']['weight']=250
        db['_skus']['ONE']=dict(db['_skus']['LOCAL'],weight=1000)
        w.db=db;w._reload_table();w._show_detail('LOCAL')
        self.assertEqual(w.current_sku,'ONE')
        w._set_view_mode('grid');self.assertEqual(len(w.grid.selectedItems()),1)
        self.assertEqual(w.current_sku,'ONE')
        w.variant_choice.setCurrentIndex(w.variant_choice.findData('LOCAL'))
        self.assertEqual(w.current_sku,'LOCAL')
        self.assertEqual(w._build_payload()['color_hex'],db['_skus']['LOCAL']['hex'])
        db['_skus']['OTHER']=dict(db['_skus']['ONE'],hex='00FF00');w.db=db;w._reload_table()
        w._show_detail('LOCAL');self.assertFalse(w.btn_generate.isEnabled())

    def test_brand_and_filament_favorite_filters_are_homogeneous_and_resettable(self):
        w=self.window
        self.assertEqual(type(w.favorites_only),type(w.brand_favorites_only))
        w._toggle_brand_favorite('Polymaker');w.brand_favorites_only.setChecked(True)
        self.assertTrue(all(r['brand']=='Polymaker' for r in w._filtered_rows))
        saved=core.load_config()['favorite_brands'];w._reset_filters()
        self.assertFalse(w.brand_favorites_only.isChecked());self.assertFalse(w.favorites_only.isChecked())
        self.assertEqual(core.load_config()['favorite_brands'],saved)

    def test_spool_uses_selected_hex_and_shows_unknown_for_unresolved_hue(self):
        w=self.window;w._show_detail('PB05001')
        self.assertEqual(w.spool_preview.hex_color,w._build_payload()['color_hex'])
        db=small_db();db['_skus']['OTHER']=dict(db['_skus']['LOCAL'],hex='00FF00')
        w.db=db;w._reload_table();w._show_detail('LOCAL')
        self.assertIsNone(w.spool_preview.hex_color)
        w.shade_buttons[0].click()
        self.assertEqual(w.spool_preview.hex_color,w._build_payload()['color_hex'])

    def test_sync_uses_saved_sources_without_opening_source_preferences(self):
        w=self.window
        with patch('core.has_network_consent',return_value=True),patch.object(w,'_start_update') as start,patch.object(w,'_choose_sources') as choose:
            w.update_btn.click();start.assert_called_once_with(manual=True);choose.assert_not_called()

    def test_characteristics_are_tiles_and_grid_names_the_product(self):
        w=self.window;w._show_detail('PB05001')
        self.assertEqual(w.characteristics.columns,2)
        self.assertIn(w._rows[0]['product'],w.grid.item(0).text())
        self.assertGreaterEqual(w.grid.gridSize().width(),170)

    def test_grid_view_restore_and_card_favorite_are_consistent(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        w=self.window;w.resize(1300,820);w.show();w._set_view_mode('grid');w.app.processEvents()
        self.assertTrue(w.btn_view_grid.isChecked());self.assertFalse(w.btn_view_list.isChecked())
        self.assertFalse(w.grid.itemDelegate().dark)
        item=w.grid.item(0);sku=item.data(Qt.UserRole);rect=w.grid.visualItemRect(item)
        QTest.mouseClick(w.grid.viewport(),Qt.LeftButton,pos=QPoint(rect.right()-18,rect.top()+18))
        self.assertTrue(w._is_favorite(w._group_for_sku(sku)))
        self.assertTrue(w.grid.itemDelegate().rows[sku]['_favorite'])

    def test_settings_save_the_preferred_packaging(self):
        from PySide6.QtWidgets import QDialog,QComboBox
        w=self.window
        def choose(dialog):
            combo=dialog.findChild(QComboBox,'preferred_weight_g');combo.setCurrentIndex(combo.findData(3000))
            form=dialog.findChild(QComboBox,'preferred_packaging');form.setCurrentIndex(form.findData('refill'))
            return QDialog.Accepted
        with patch.object(QDialog,'exec',choose):w._open_settings()
        self.assertEqual(core.load_config()['preferred_weight_g'],3000)
        self.assertEqual(core.load_config()['preferred_packaging'],'refill')
