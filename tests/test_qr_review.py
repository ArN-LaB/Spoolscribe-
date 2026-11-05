"""User review: screen-first QR and confirmed, sourced temperature suggestions."""
import copy
import unittest
from unittest.mock import patch
from spoolscribe import core, qr_layout, qr_transfer
from tests import test_gui as fixture

class TemperatureSuggestionTests(unittest.TestCase):
    def test_range_suggestions_are_explicit_and_never_mutate_source(self):
        fields=dict(min_print_temp=230,max_print_temp=260,min_bed_temp=70,max_bed_temp=80)
        before=copy.deepcopy(fields)
        suggested=core.opentag_temperature_suggestions(fields)
        self.assertEqual(suggested['print_temp']['value'],245)
        self.assertEqual(suggested['bed_temp']['value'],75)
        self.assertEqual(suggested['print_temp']['source'],'range')
        self.assertNotIn('chamber_temp',suggested)
        self.assertEqual(fields,before)

    def test_documented_profile_target_wins_but_conflicting_plates_do_not(self):
        fields=dict(min_print_temp=230,max_print_temp=260,min_bed_temp=70,max_bed_temp=80)
        result=core.opentag_temperature_suggestions(fields,dict(nozzle_temperature=['240'],hot_plate_temp=['70'],textured_plate_temp=['80'],chamber_temperature=['0']))
        self.assertEqual(result['print_temp'],dict(value=240,source='orca'))
        self.assertEqual(result['bed_temp'],dict(value=75,source='range'))
        self.assertEqual(result['chamber_temp'],dict(value=0,source='orca'))

    def test_no_invention_outside_bounds_or_over_saved_targets(self):
        result=core.opentag_temperature_suggestions(dict(print_temp=240,min_print_temp=231,max_print_temp=234),dict(nozzle_temperature=['300']))
        self.assertEqual(result,{})
        for invalid in (float('nan'),True,-5):
            result=core.opentag_temperature_suggestions(dict(min_print_temp=invalid,max_print_temp=260))
            self.assertNotIn('print_temp',result)

@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class QrReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self)
        from spoolscribe import i18n,ui_qr
        i18n.set_language('fr');w=self.window;w.current_sku='PB05001';w._show_detail(w.current_sku)
        cfg=core.load_config();cfg['qr_label']={'preset':'d101-25x50'};core.save_config(cfg)
        self.qr=ui_qr.QrWindow(ui_qr.snapshot(w),w);self.qr.show();w.app.processEvents()
        self.addCleanup(self.qr.close)
    def test_opening_is_screen_only_even_with_old_paper_preference(self):
        qr=self.qr
        self.assertEqual(qr.support.currentData(),'screen')
        self.assertIsNone(qr.plan())
        self.assertTrue(qr.btn_print.isHidden())
        self.assertNotIn('NIIMBOT',' '.join(qr.support.itemText(i) for i in range(qr.support.count())))
        self.assertEqual(qr_transfer.decode(qr.symbol.text).ndef,qr.snap.ndef)
    def test_error_correction_is_available_without_technical_details(self):
        qr=self.qr
        self.assertTrue(qr.details.isHidden())
        self.assertFalse(qr.error.isHidden())
        self.assertFalse(qr.details.isAncestorOf(qr.error))
        message=qr.snap.ndef;qr.error.setCurrentIndex(qr.error.findData('Q'))
        self.assertEqual(qr_transfer.decode(qr.symbol.text).ndef,message)
    def test_temperature_review_requires_confirmation_and_resets_after_edits(self):
        from PySide6.QtWidgets import QToolButton,QDialogButtonBox,QLineEdit
        from pathlib import Path
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('opentag3d'))
        before=Path(core.DB_PATH).read_bytes()
        def review(dialog):
            check=dialog.findChild(QToolButton,'opentag_confirmed')
            save=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save)
            target=dialog.findChild(QLineEdit,'opentag_print_temp')
            self.assertTrue(target.text());self.assertFalse(check.isChecked());self.assertFalse(save.isEnabled())
            save.click();self.assertEqual(core.opentag_settings(w.current_sku),{})
            dialog.findChild(QLineEdit,'opentag_weight').setText('1000')
            chamber=dialog.findChild(QLineEdit,'opentag_chamber_temp');chamber.setText('0')
            dialog.show();w.app.processEvents()
            check.click();self.assertTrue(save.isEnabled())
            top=lambda widget:widget.mapTo(dialog,widget.rect().topLeft()).y()
            self.assertLessEqual(abs(top(check)-top(save)),2)
            self.assertEqual(top(target),top(dialog.findChild(QLineEdit,"opentag_min_print_temp")))
            chamber.setText('5');self.assertFalse(check.isChecked());self.assertFalse(save.isEnabled())
            chamber.setText('0');check.click();save.click()
            return dialog.result()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=review):
            self.assertTrue(w._complete_opentag_settings())
        self.assertEqual(core.opentag_settings(w.current_sku)['chamber_temp'],0)
        self.assertEqual(Path(core.DB_PATH).read_bytes(),before)

    def test_writer_menu_is_absent_for_both_protocols(self):
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('u1'))
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12_openrfid'))
        for key in ('openspool','opentag3d'):
            w.nfc_format.setCurrentIndex(w.nfc_format.findData(key));w._refresh_export_state()
            self.assertTrue(w.writer_buttons.isHidden());self.assertTrue(w.writer_label.isHidden());self.assertTrue(w.writer_expert.isHidden())
            self.assertNotIn('NFC Tools',w.setup_result.text())

    def test_companion_has_one_common_information_entry(self):
        from spoolscribe import ui_qr
        from PySide6.QtWidgets import QPushButton
        self.assertTrue(self.qr.companion_button.isEnabled())
        self.assertIn('disponibilité', self.qr.companion_button.text())
        self.assertNotIn('apps.apple.com', ui_qr.COMPANION_URL)
        self.assertNotIn('play.google.com', ui_qr.COMPANION_URL)
        with patch.object(ui_qr.QDesktopServices, 'openUrl') as opened:
            self.qr.companion_button.click()
        self.assertEqual(opened.call_args.args[0].toString(), ui_qr.COMPANION_URL)
        self.assertTrue((__import__('tests.support', fromlist=['ROOT']).ROOT / 'docs/COMPANION.md').is_file())

    def test_paper_references_are_help_only_and_do_not_change_message(self):
        from PySide6.QtWidgets import QLabel
        before = self.qr.snap.ndef
        self.qr._paper_help()
        self.addCleanup(self.qr._paper_guide.close)
        text = ' '.join(label.text() for label in self.qr._paper_guide.findChildren(QLabel))
        for reference in ('L7165', 'J8165', 'DK-11202'):
            self.assertIn(reference, text)
        self.assertEqual(self.qr.snap.ndef, before)
        self.assertEqual(self.qr.support.currentData(), 'screen')
