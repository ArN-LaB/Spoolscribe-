"""Final UI consistency, printer categories and optional support link."""
import unittest
from unittest.mock import patch
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class FinalPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_printer_categories_preserve_firmware_conditions_and_search(self):
        from ui_widgets import PrinterBrowser
        from PySide6.QtCore import Qt
        import printer_profiles
        w=self.window;browser=PrinterBrowser(w.printer,w);self.addCleanup(browser.close)
        for key in ('compatible','rfid','none'):
            browser.category.setCurrentIndex(browser.category.findData(key))
            visible=[browser.list.item(i) for i in range(browser.list.count()) if not browser.list.item(i).isHidden()]
            self.assertTrue(visible)
            for item in visible:
                profile=printer_profiles.PROFILES[w.printer.itemData(item.data(Qt.UserRole))]
                if key=='compatible':self.assertTrue(profile['nfc'])
                elif key=='rfid':self.assertEqual(profile['group'],'incompatible');self.assertFalse(profile['nfc'])
                else:self.assertFalse(profile['nfc']);self.assertNotEqual(profile['group'],'incompatible')
        browser.category.setCurrentIndex(browser.category.findData('rfid'));browser.search.setText('prusa')
        self.assertEqual(sum(not browser.list.item(i).isHidden() for i in range(browser.list.count())),1)
        browser.category.setCurrentIndex(browser.category.findData('compatible'))
        self.assertTrue(browser.empty.isVisibleTo(browser))

    def test_settings_have_no_native_baseline(self):
        from PySide6.QtWidgets import QDialog,QTabWidget
        def inspect(dialog):
            self.assertFalse(dialog.findChild(QTabWidget).tabBar().drawBase())
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):self.window._open_settings()

    def test_about_support_link_is_explicit_and_never_opens_on_display(self):
        from PySide6.QtWidgets import QDialog,QPushButton
        def inspect(dialog):
            button=dialog.findChild(QPushButton,'supportProject');self.assertIsNotNone(button)
            self.assertEqual(button.height(),32)
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect),patch('app_gui.QDesktopServices.openUrl') as opened:
            self.window._open_about();opened.assert_not_called()

    def test_about_support_click_opens_exact_author_url(self):
        from PySide6.QtWidgets import QDialog,QPushButton
        def inspect(dialog):dialog.findChild(QPushButton,'supportProject').click();return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect),patch('app_gui.QDesktopServices.openUrl',return_value=True) as opened:
            self.window._open_about();self.assertEqual(opened.call_args.args[0].toString(),'https://buymeacoffee.com/arn_lab')

    def test_referenced_printer_images_keep_native_transparency_and_manifest_hashes(self):
        import json,hashlib
        from pathlib import Path
        from PySide6.QtGui import QImage
        import core
        root=Path(core.RESOURCE_DIR)/'data/printer_photos'
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertIn('anycubic_ace',manifest)
        for key,meta in manifest.items():
            path=root/meta['file'];image=QImage(str(path))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),meta['sha256'])
            self.assertTrue(image.hasAlphaChannel(),key)
            self.assertLess(image.pixelColor(0,0).alpha(),255,key)
