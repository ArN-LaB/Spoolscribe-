"""Configuration-level compatibility: connection, firmware and actual effect."""
import copy
import json
import unittest
from unittest.mock import patch
from tests.support import ROOT
from spoolscribe import printer_profiles as printers, core
from tests import test_gui as fixture


class PrinterConfigurationTests(unittest.TestCase):
    def test_u1_modes_are_one_firmware_with_different_detection(self):
        for key in ('paxx12_openrfid','paxx12_openrfid_generic'):
            c=printers.configuration('u1',key)
            self.assertEqual(c['connection'],'integrated')
            self.assertEqual(c['firmware_kind'],'modified')
            self.assertEqual(printers.formats('u1',key),('openspool','opentag3d'))
        self.assertEqual(printers.formats('u1','paxx12'),('openspool',))
        self.assertFalse(printers.can_export('u1','stock'))
        self.assertFalse(printers.can_export('u1','unknown'))

    def test_usb_requires_the_specific_plugin_and_firmware(self):
        c=printers.configuration('flashforge_ad5x','zmod')
        self.assertEqual(c['connection'],'usb')
        self.assertIn('FF_NFC',c['reader'])
        self.assertEqual(printers.formats('flashforge_ad5x','zmod'),('openspool','opentag3d'))
        self.assertFalse(printers.can_export('flashforge_ad5x','stock'))
        self.assertFalse(printers.can_export('bambu','usb_unknown'))
        self.assertIn('usb',printers.categories('flashforge_ad5x'))
        self.assertIn('stock',printers.categories('bambu'))

    def test_inventory_is_not_printer_detection_and_prusa_can_is_not_usb(self):
        c=printers.configuration('prusa_mk4','spoolsense')
        self.assertEqual(c['effect'],'inventory')
        self.assertEqual(c['evidence'],'experimental')
        c=printers.configuration('prusa_core','stock')
        self.assertEqual(c['connection'],'can')
        self.assertIn('openprinttag',c['reader_formats'])
        self.assertEqual(printers.formats('prusa_core','stock'),())
        self.assertNotIn('usb',printers.categories('prusa_core'))

    def test_legacy_settings_keep_the_actual_external_reader(self):
        self.assertEqual(printers.resolve('bambu_openspool','stock'),('bambu','openspool_network'))
        self.assertEqual(printers.resolve('u1_stock'),('u1','stock'))
        self.assertEqual(printers.resolve('prusa','stock'),('prusa_generic','stock'))

    def test_verified_metadata_cannot_claim_unverified_export_or_invalid_route(self):
        doc=json.loads((ROOT/'data/printers.json').read_text())
        for changes in [dict(connection='bluetooth'),dict(evidence='unverified'),dict(reader_formats=[]),dict(url='javascript:alert(1)')]:
            bad=copy.deepcopy(doc);bad['printers'][0]['firmwares'][0].update(changes)
            with self.assertRaises(ValueError):printers.validate_catalogue(bad)


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class PrinterConfigurationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_u1_explains_modes_without_presenting_openspool_as_firmware(self):
        w=self.window
        self.assertIn('Configuration',w.firmware_label.text())
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12_openrfid_generic'))
        self.assertEqual(w.nfc_format.count(),2)
        self.assertIn('OpenRFID',w.printer_help.text())
        self.assertIn('intégré',w.connection_info.text())
        self.assertFalse(w.configuration_source.isHidden())

    def test_optional_prusa_accessory_is_never_assumed_present(self):
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('prusa_core'))
        self.assertEqual(w.firmware.currentData(),'unknown')
        w.firmware.setCurrentIndex(w.firmware.findData('no_accessory'))
        self.assertIn('Aucun lecteur',w.connection_info.text())
        self.assertFalse(w._can_export_for_printer())
        w.firmware.setCurrentIndex(w.firmware.findData('stock'))
        self.assertIn('CAN',w.connection_info.text());self.assertIn('OpenPrintTag',w.printer_help.text())

    def test_reader_selection_updates_effect_and_export_without_stale_options(self):
        w=self.window
        w.printer.setCurrentIndex(w.printer.findData('flashforge_ad5x'))
        self.assertEqual(w.firmware.currentData(),'unknown')
        self.assertFalse(w._can_export_for_printer())
        w.firmware.setCurrentIndex(w.firmware.findData('zmod'))
        self.assertEqual(w.nfc_format.count(),2);self.assertIn('USB',w.connection_info.text())
        w.printer.setCurrentIndex(w.printer.findData('prusa_mk4'))
        w.firmware.setCurrentIndex(w.firmware.findData('spoolsense'))
        self.assertIn('inventaire',w.printer_help.text().casefold())
        self.assertIn('Inventaire',w.printer_card.status.text())
        w.printer.setCurrentIndex(w.printer.findData('prusa_core'))
        w.firmware.setCurrentIndex(w.firmware.findData('stock'))
        self.assertEqual(w.nfc_format.count(),0);self.assertFalse(w._can_export_for_printer())
        self.assertIn('OpenPrintTag',w.printer_help.text())

    def test_hidden_aliases_are_not_duplicate_printers_and_browser_routes_filter(self):
        from spoolscribe.ui_widgets import PrinterBrowser
        from PySide6.QtCore import Qt
        w=self.window
        self.assertEqual(w.printer.findData('bambu_openspool'),-1)
        b=PrinterBrowser(w.printer,w);self.addCleanup(b.close)
        b.category.setCurrentIndex(b.category.findData('usb'))
        visible=[b.list.item(i) for i in range(b.list.count()) if not b.list.item(i).isHidden()]
        self.assertTrue(visible)
        self.assertTrue(all('usb' in printers.categories(w.printer.itemData(i.data(Qt.UserRole))) for i in visible))

    def test_legacy_settings_import_retains_the_network_reader_and_source_opens_only_on_click(self):
        from pathlib import Path
        w=self.window
        path=Path(self.tmp.name)/'old-settings.json'
        cfg=core.load_config();cfg.update(printer_profile='bambu_openspool',printer_firmware='stock')
        core.save_config(cfg);core.export_settings(path)
        with patch('spoolscribe.ui_catalogue.QDesktopServices.openUrl',return_value=True) as opened:
            with patch('spoolscribe.ui_catalogue.QFileDialog.getOpenFileName',return_value=(str(path),'JSON')):w._import_settings()
            self.assertEqual(w.printer.currentData(),'bambu')
            self.assertEqual(w.firmware.currentData(),'openspool_network')
            self.assertEqual(printers.formats('bambu',w.firmware.currentData()),('openspool',))
            opened.assert_not_called()
            w.configuration_source.click()
            self.assertEqual(opened.call_args.args[0].toString(),'https://github.com/spuder/OpenSpool')

    def test_transient_empty_printer_does_not_raise_a_qt_slot_exception_or_enable_export(self):
        import sys
        w=self.window
        with patch.object(sys,'excepthook') as errors:
            w.printer.setCurrentIndex(-1)
            self.assertFalse(w._can_export_for_printer())
            self.assertFalse(w.btn_generate.isEnabled())
            errors.assert_not_called()

    def test_startup_migrates_the_old_bambu_reader_without_selecting_the_ams(self):
        cfg=core.load_config();cfg.update(printer_profile='bambu_openspool',printer_firmware='stock')
        core.save_config(cfg)
        w=fixture.app_gui.MainWindow();self.addCleanup(w.close)
        self.assertEqual(w.printer.currentData(),'bambu')
        self.assertEqual(w.firmware.currentData(),'openspool_network')
        saved=core.load_config()
        self.assertEqual(printers.resolve(saved['printer_profile'],saved['printer_firmware']),('bambu','openspool_network'))
        # A retained legacy ID must still resolve to the same reader on the next launch.
        again=fixture.app_gui.MainWindow();self.addCleanup(again.close)
        self.assertEqual(again.firmware.currentData(),'openspool_network')

    def test_unknown_or_removed_setup_stays_unconfirmed_after_restart(self):
        for software in (None,'unknown','removed_setup'):
            cfg=core.load_config();cfg.update(printer_profile='u1',printer_firmware=software)
            core.save_config(cfg)
            w=fixture.app_gui.MainWindow();self.addCleanup(w.close)
            self.assertEqual(w.firmware.currentData(),'unknown',software)
            self.assertFalse(w._can_export_for_printer())

    def test_list_refresh_reloads_setups_without_confirming_an_unknown_choice(self):
        w=self.window;cfg=core.load_config();cfg['network_consent']=True;core.save_config(cfg)
        w.firmware.setCurrentIndex(w.firmware.findData('unknown'))
        with patch.dict(printers.PROFILES,copy.deepcopy(printers.PROFILES)):
            def refresh(_fetch):
                extra=dict(printers.PROFILES['u1']['firmwares'][0],id='new_reviewed_setup')
                printers.PROFILES['u1']['firmwares'].append(extra)
                return {'updated':'2026-11-01','printers':list(printers.PROFILES)}
            with patch.object(printers,'refresh_catalogue',side_effect=refresh):w._update_printers()
            self.assertGreaterEqual(w.firmware.findData('new_reviewed_setup'),0)
            self.assertEqual(w.firmware.currentData(),'unknown')

    def test_hardware_fits_narrow_windows_in_all_interface_languages(self):
        from spoolscribe import i18n
        for language in ('fr','en','es','zh_CN'):
            core.save_config(dict(core.load_config(),language=language))
            w=fixture.app_gui.MainWindow();self.addCleanup(w.close)
            w.printer.setCurrentIndex(w.printer.findData('u1'))
            w.firmware.setCurrentIndex(w.firmware.findData('paxx12_openrfid'))
            w.hardware_dialog.show();w.hardware_dialog.resize(510,360);w.app.processEvents()
            self.assertEqual(w.hardware_scroll.horizontalScrollBar().maximum(),0,language)
        i18n.set_language('fr')

    def test_buttons_build_a_u1_setup_without_a_technical_dropdown(self):
        w=self.window;w.firmware.setCurrentIndex(w.firmware.findData('unknown'))
        w.reader_buttons.buttons['integrated'].click()
        self.assertEqual(w.firmware.currentData(),'unknown')
        w.software_buttons.buttons['modified'].click()
        self.assertEqual(w.firmware.currentData(),'unknown')
        self.assertEqual(set(w.setup_buttons.buttons),{'paxx12','paxx12_openrfid','paxx12_openrfid_generic'})
        w.setup_buttons.buttons['paxx12_openrfid'].click()
        self.assertEqual(w.firmware.currentData(),'paxx12_openrfid')
        self.assertEqual(set(w.format_buttons.buttons),{'openspool','opentag3d'})
        w.format_buttons.buttons['opentag3d'].click()
        self.assertIn('OpenTag3D',w.setup_result.text())
        self.assertIn('NTAG216',w.setup_result.text())
        self.assertTrue(w.firmware.isHidden());self.assertTrue(w.nfc_format.isHidden())
        self.assertTrue(w.setup_details.isHidden())
        w.setup_details_toggle.click();self.assertFalse(w.setup_details.isHidden())

    def test_even_a_single_reader_path_needs_explicit_confirmation(self):
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('prusa_core'))
        w.reader_buttons.buttons['can'].click()
        self.assertEqual(w.firmware.currentData(),'unknown')
        self.assertEqual(set(w.setup_buttons.buttons),{'stock'})
        w.setup_buttons.buttons['stock'].click()
        self.assertFalse(w._can_export_for_printer())
        self.assertIn('Aucun format',w.setup_result.text())

    def test_buttons_distinguish_network_inventory_from_printer_identification(self):
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('prusa_mk4'))
        w.reader_buttons.buttons['network'].click()
        w.setup_buttons.buttons['spoolsense'].click()
        self.assertIn('inventaire',w.setup_result.text());self.assertIn('inchangé',w.setup_result.text())
        w.printer.setCurrentIndex(w.printer.findData('flashforge_ad5x'))
        w.reader_buttons.buttons['usb'].click()
        self.assertEqual(w.firmware.currentData(),'unknown')
        w.setup_buttons.buttons['zmod'].click()
        self.assertIn('imprimante',w.setup_result.text())
        w.format_buttons.buttons['opentag3d'].click()
        w.writer_buttons.buttons['nfctools-desktop'].click()
        self.assertEqual(w.opentag_output.currentData(),'nfctools-desktop')
        w.hardware_dialog.show();w.app.processEvents()
        w.hardware_scroll.verticalScrollBar().setValue(w.hardware_scroll.verticalScrollBar().maximum())
        self.assertTrue(w.setup_result.isVisibleTo(w.hardware_dialog))
        self.assertGreater(w.setup_result_panel.geometry().top(),w.hardware_scroll.geometry().bottom())
