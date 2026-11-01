"""Real-screen follow-up: macOS bundle paths, filters, variants and hardware layout."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from spoolscribe import core
from spoolscribe import printer_profiles
from tests import test_gui as fixture
from tests.support import small_db


class BundleAndPrinterTests(unittest.TestCase):
    def test_historical_logo_is_available_without_downloaded_brand_metadata(self):
        self.assertTrue(Path(core.logo_abs_path({},'ROSA3D')).is_file())

    def test_bundle_logo_directory_symlink_is_allowed_but_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);frameworks=root/'Frameworks';resources=root/'Resources'
            frameworks.mkdir();(resources/'data').mkdir(parents=True)
            (resources/'data/logo.svg').write_text('<svg/>')
            (frameworks/'data').symlink_to(resources/'data',target_is_directory=True)
            (root/'outside.svg').write_text('<svg/>')
            (resources/'data/escape.svg').symlink_to(root/'outside.svg')
            with patch.multiple(core,DATA_HOME=str(root/'user'),RESOURCE_DIR=str(frameworks),_LOGO_MANIFEST={'polymaker':'data/logo.svg'}):
                self.assertEqual(core.logo_abs_path({},'Polymaker'),str((resources/'data/logo.svg').resolve()))
                with patch.object(core,'_LOGO_MANIFEST',{'polymaker':'data/escape.svg'}):
                    self.assertIsNone(core.logo_abs_path({},'Polymaker'))

    def test_unpublished_printer_list_is_an_available_bundled_list(self):
        fetch=lambda *_: (_ for _ in ()).throw(HTTPError(printer_profiles.PRINTERS_URL,404,'Not Found',{},None))
        with patch.object(printer_profiles,'install_catalogue') as install:
            self.assertIsNone(printer_profiles.refresh_catalogue(fetch))
            install.assert_not_called()
        with self.assertRaises(HTTPError):
            printer_profiles.refresh_catalogue(lambda *_: (_ for _ in ()).throw(HTTPError('url',503,'Unavailable',{},None)))


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class PolishUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_reset_clears_every_filter_but_preserves_both_favorite_lists(self):
        w=self.window;w.current_sku='PB05001';w._show_detail(w.current_sku)
        w._toggle_filament_favorite();w._toggle_brand_favorite('Polymaker')
        saved=copy.deepcopy(core.load_config())
        w.brand_search.setText('rosa');w.search.setText('red');w.favorites_only.setChecked(True)
        w._reset_filters()
        self.assertEqual(w.brand_search.text(),'');self.assertEqual(w.search.text(),'')
        self.assertFalse(w.favorites_only.isChecked())
        self.assertEqual((w.brand_filter.currentData(),w.material_filter.currentData(),w.quality_filter.currentData()),('','','all'))
        self.assertIsNone(w.current_sku)
        for key in ('favorite_brands','favorite_filaments'):self.assertEqual(core.load_config()[key],saved[key])
        self.assertTrue(all(not w.brand_list.item(i).isHidden() for i in range(w.brand_list.count())))

    def test_printer_switch_keeps_all_explanations_visible_in_small_dialog(self):
        w=self.window;w._open_hardware();w.hardware_dialog.resize(510,360)
        for key,setup in (('u1','paxx12'),('prusa_core','stock'),('bambu','stock'),('no_reader','stock'),('u1','paxx12')):
            w.printer.setCurrentIndex(w.printer.findData(key));w.firmware.setCurrentIndex(w.firmware.findData(setup))
            w.setup_details_toggle.setChecked(True);w.app.processEvents()
            label=w.printer_help
            self.assertGreaterEqual(label.height(),label.heightForWidth(label.width()))
            self.assertGreaterEqual(w.printer_card.height(),88)
            self.assertGreaterEqual(w.printer_card.description.height(),w.printer_card.description.heightForWidth(w.printer_card.description.width()))
        w.hardware_dialog.close()

    def test_printer_card_follows_the_theme(self):
        w=self.window
        with patch('spoolscribe.app_gui.is_dark_theme',return_value=True):w._apply_theme()
        self.assertIn('#252d34',w.printer_card.styleSheet())
        with patch('spoolscribe.app_gui.is_dark_theme',return_value=False):w._apply_theme()
        self.assertIn('#ffffff',w.printer_card.styleSheet())

    def test_conflicting_shades_are_visual_and_conditioning_is_separate(self):
        w=self.window;db=small_db();db['_skus']['OTHER']=dict(db['_skus']['LOCAL'],hex='00FF00',weight=3000)
        db['_skus']['SECOND']=dict(db['_skus']['LOCAL'],weight=1000)
        w.db=db;w._reload_table();w.current_sku=w._all_rows[0]['sku'];w._show_detail(w.current_sku)
        self.assertFalse(w.btn_generate.isEnabled())
        self.assertEqual(len(w.shade_buttons),2)
        self.assertTrue(all(not b.icon().isNull() for b in w.shade_buttons))
        w.shade_buttons[0].click()
        self.assertTrue(w.btn_generate.isEnabled())
        selected_hex=w.db['_skus'][w.current_sku]['hex']
        for i in range(w.variant_choice.count()):
            sku=w.variant_choice.itemData(i)
            if sku:self.assertEqual(db['_skus'][sku]['hex'],selected_hex)
        self.assertEqual(w._build_payload()['color_hex'],selected_hex)

    def test_progress_text_has_its_own_height_and_not_the_bar_height(self):
        w=self.window;w._on_update_progress('Catalogue multi-fabricants OFD',2,7)
        self.assertFalse(w.progress.isTextVisible())
        self.assertIn('2/7',w.progress_label.text())
        self.assertGreaterEqual(w.progress_label.minimumHeight(),24)

    def test_printer_refresh_404_does_not_display_a_failure(self):
        w=self.window;cfg=core.load_config();cfg['network_consent']=True;core.save_config(cfg)
        with patch('spoolscribe.printer_profiles.refresh_catalogue',return_value=None),patch('spoolscribe.ui_catalogue.QMessageBox.warning') as warning:
            w._update_printers()
        warning.assert_not_called()
        self.assertIn('publiée',w.printers_origin.text())
