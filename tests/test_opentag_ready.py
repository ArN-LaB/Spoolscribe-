"""A validated label exports without asking the temperature question again."""
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_gui as fixture
from spoolscribe import core,i18n

@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagReadyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self);i18n.set_language('fr');w=self.window
        w.printer.setCurrentIndex(w.printer.findData('opentag3d'));w.current_sku='PB05001';w._show_detail(w.current_sku)
        self.settings=dict(print_temp=240,bed_temp=75,chamber_temp=0,weight=1000)

    def test_prepare_then_nfc_qr_and_preview_do_not_reopen_the_editor(self):
        from PySide6.QtWidgets import QDialog,QLineEdit,QDialogButtonBox,QToolButton
        from spoolscribe import ui_qr,qr_transfer
        w=self.window;before=Path(core.DB_PATH).read_bytes();calls=[]
        def review(dialog):
            calls.append(dialog.windowTitle())
            for key,value in self.settings.items():dialog.findChild(QLineEdit,'opentag_'+key).setText(str(value))
            dialog.findChild(QToolButton,'opentag_confirmed').setChecked(True)
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click()
            return dialog.result()
        self.assertEqual(w._primary_kind,'opentag_settings')
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=review):w.btn_generate.click()
        self.assertEqual(len(calls),1);self.assertEqual(w._primary_kind,'export');expected=w._prepare_opentag()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',side_effect=AssertionError('Repeated temperature prompt')),patch('spoolscribe.app_gui.QMessageBox.information'),patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',return_value=core.OUTPUT_DIR):
            w.btn_generate.click();w.btn_inspect.click();q=w._open_qr()
        self.addCleanup(q.close)
        self.assertEqual(qr_transfer.decode(q.symbol.text).ndef,ui_qr.snapshot(w).ndef)
        self.assertEqual((Path(core.OUTPUT_DIR)/expected.filename).read_bytes(),expected.data)
        self.assertEqual(Path(core.DB_PATH).read_bytes(),before)

    def test_invalidated_targets_still_require_preparation_before_writing(self):
        w=self.window;core.save_opentag_settings(w.current_sku,dict(self.settings,print_temp=300))
        with patch.object(w,'_complete_opentag_settings',return_value=False) as editor,patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory') as folder:
            w._generate()
        editor.assert_called_once();folder.assert_not_called()

    def test_saved_targets_survive_reload_but_explicit_edit_always_opens(self):
        from PySide6.QtWidgets import QDialog,QToolButton
        w=self.window;core.save_opentag_settings(w.current_sku,self.settings);w._show_detail(w.current_sku)
        with patch('spoolscribe.ui_catalogue.QDialog.exec',side_effect=AssertionError('Already prepared')):
            self.assertTrue(w._ensure_opentag_settings());w._refresh_inspector()
        before=core.opentag_settings(w.current_sku)
        def edit(dialog):
            self.assertFalse(dialog.findChild(QToolButton,'opentag_confirmed').isChecked())
            return QDialog.Rejected
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=edit):w.btn_opentag_settings.click()
        self.assertEqual(core.opentag_settings(w.current_sku),before)

    def test_label_reference_is_informative_and_specific_to_exact_dimensions(self):
        from spoolscribe import ui_qr
        w=self.window;core.save_opentag_settings(w.current_sku,self.settings);w._refresh_nfc_capacity()
        q=ui_qr.QrWindow(ui_qr.snapshot(w),w);self.addCleanup(q.close);q.show()
        self.assertTrue(q.support_reference.isHidden())
        q.support.setCurrentIndex(q.support.findData('label-62x100'))
        self.assertIn('DK-11202',q.support_reference.text());self.assertTrue(q.support_reference.font().italic())
        q.support.setCurrentIndex(q.support.findData('label-50x50'))
        self.assertTrue(q.support_reference.isHidden())
