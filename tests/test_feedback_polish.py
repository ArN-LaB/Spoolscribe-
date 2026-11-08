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
        # Same card surface and border as the other cards of the theme (B14 D).
        for dark in (True,False):
            with patch('spoolscribe.app_gui.is_dark_theme',return_value=dark):w._apply_theme()
            self.assertIn(f"background:{w._tok['card']}",w.printer_card.styleSheet())
            self.assertIn(f"border:1px solid {w._tok['border']}",w.printer_card.styleSheet())
            from spoolscribe.ui_widgets import CARD_RADIUS;self.assertIn(f"border-radius:{CARD_RADIUS}px",w.printer_card.styleSheet())
        self.assertEqual(w._tok['card'],'#ffffff')

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
        self.assertEqual(w.progress_label.text(),'Catalogue multi-fabricants OFD')
        self.assertEqual(w.progress_step.text(),'Étape 2 sur 7')
        self.assertGreaterEqual(w.progress_label.minimumHeight(),24)

    def test_printer_refresh_404_does_not_display_a_failure(self):
        w=self.window;cfg=core.load_config();cfg['network_consent']=True;core.save_config(cfg)
        with patch('spoolscribe.printer_profiles.refresh_catalogue',return_value=None),patch('spoolscribe.ui_catalogue.QMessageBox.warning') as warning:
            w._update_printers()
        warning.assert_not_called()
        self.assertIn('publiée',w.printers_origin.text())


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class MessagesAndStatusTests(unittest.TestCase):
    """B14/15: the two dialogs keep their decisions; their text and the status line are readable."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def shown_labels(self,box):
        from PySide6.QtWidgets import QLabel
        box.show();self.window.app.processEvents()
        labels={label.objectName():label for label in box.findChildren(QLabel)}
        box.hide();return labels

    def test_refused_network_explains_the_real_route_and_never_starts_github(self):
        from PySide6.QtWidgets import QMessageBox,QDialog,QPushButton
        from spoolscribe.i18n import tr
        w=self.window;shown=[]
        def seen(box):   # read while the box is alive: the caller deletes it after exec
            labels=self.shown_labels(box)
            shown.append(dict(icon=box.icon(),text=box.text(),informative=box.informativeText(),
                              weights=(labels['qt_msgbox_label'].font().weight(),labels['qt_msgbox_informativelabel'].font().weight())))
            return 0
        with patch('spoolscribe.ui_catalogue.ReleaseWorker') as worker,patch.object(QMessageBox,'exec',new=seen):
            w._check_app_update()
        worker.assert_not_called();self.assertEqual(len(shown),1)
        box=shown[0]
        self.assertEqual(box['icon'],QMessageBox.Information)
        self.assertEqual(box['text'],tr('L’autorisation réseau est retirée.'))
        for name in (tr('Actualiser le catalogue'),tr('Paramètres'),tr('Catalogue'),tr('Sources du catalogue…')):self.assertIn(name,box['informative'])
        self.assertNotIn('Sources de la base',box['informative']+box['text'])
        statement,explanation=box['weights']
        self.assertGreater(statement,explanation);self.assertEqual(explanation,400)
        # The named controls are the real ones: the catalogue button opens the sources while refused…
        self.assertEqual(w.update_btn.text(),tr('Actualiser le catalogue'))
        with patch.object(w,'_choose_sources') as choose:w.update_btn.click()
        choose.assert_called_once()
        # …and Paramètres › Catalogue holds « Sources du catalogue… », wired to the same dialog.
        found=[]
        def inspect(dialog):
            found.extend(b for b in dialog.findChildren(QPushButton) if b.text()==tr('Sources du catalogue…'));return 0
        with patch('spoolscribe.app_gui.QDialog.exec',new=inspect):w._open_settings()
        self.assertEqual(len(found),1)
        with patch.object(w,'_choose_sources') as choose:found[0].click()
        choose.assert_called_once()
        # With the permission, the same action does contact the release worker.
        cfg=core.load_config();cfg['network_consent']=True;core.save_config(cfg)
        asked=[]
        with patch('spoolscribe.ui_catalogue.ReleaseWorker') as worker,patch.object(QMessageBox,'exec',new=lambda box:asked.append(box) or 0):
            w._check_app_update()
        worker.assert_called_once();self.assertEqual(asked,[])

    def test_quit_during_sync_keeps_the_careful_default_and_cancels_only_after_confirmation(self):
        from unittest.mock import Mock
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QMessageBox
        from spoolscribe.i18n import tr
        w=self.window
        box,quit_button=w._quit_during_sync_box()
        keep=box.defaultButton();labels=self.shown_labels(box)
        self.assertIs(box.escapeButton(),keep);self.assertIsNot(keep,quit_button)
        self.assertEqual((keep.text(),quit_button.text()),(tr('Continuer la synchronisation'),tr('Quitter')))
        self.assertEqual(box.buttonRole(quit_button),QMessageBox.DestructiveRole)
        self.assertEqual(box.icon(),QMessageBox.Information)
        self.assertEqual(box.text(),tr('Quitter pendant la synchronisation ?'))
        self.assertIn(tr('La synchronisation sera interrompue. Les étapes déjà terminées peuvent avoir modifié les données locales.'),box.informativeText())
        self.assertGreater(labels['qt_msgbox_label'].font().weight(),labels['qt_msgbox_informativelabel'].font().weight())
        box.deleteLater()
        def close_with(answer):
            worker=Mock();worker.isRunning.return_value=True;w.worker=worker;event=QCloseEvent()
            with patch.object(QMessageBox,'exec',new=answer):w.closeEvent(event)
            w.worker=None;return event.isAccepted(),worker
        escape=lambda box:QTest.keyClick(box,Qt.Key_Escape) or 0
        for answer in (escape,lambda box:box.defaultButton().click() or 0,lambda box:0):   # Escape, « Continuer », window closed
            accepted,worker=close_with(answer)
            self.assertFalse(accepted);worker.cancel.set.assert_not_called();worker.wait.assert_not_called()
        with patch.object(w,'_save_ui_preferences'):
            accepted,worker=close_with(lambda box:[b for b in box.buttons() if box.buttonRole(b)==QMessageBox.DestructiveRole][0].click() or 0)
        self.assertTrue(accepted);worker.cancel.set.assert_called_once();worker.wait.assert_called_once_with(10000)
        # Without a synchronisation the window closes without asking.
        event=QCloseEvent()
        asked=[]
        with patch.object(QMessageBox,'exec',new=lambda box:asked.append(box) or 0),patch.object(w,'_save_ui_preferences'):w.closeEvent(event)
        self.assertEqual(asked,[]);self.assertTrue(event.isAccepted())

    def test_status_text_is_inset_elided_with_full_text_and_keeps_timeouts(self):
        from PySide6.QtCore import QEvent,QEventLoop,QObject,QTimer
        from spoolscribe.i18n import tr
        w=self.window;w.show();w.resize(860,600);w.current_sku='PB05001';w._show_detail('PB05001')
        def run(ms):
            loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
        run(50);status=w.status
        self.assertEqual((status.currentMessage(),status.displayed_text()),(tr('Échap : désélectionner'),tr('Échap : désélectionner')))
        self.assertGreaterEqual(status.contentsRect().left(),14)   # aligned with the window content, clear of the rounded corner
        self.assertGreaterEqual(status.contentsRect().height(),status.fontMetrics().height())
        self.assertGreaterEqual(status.height(),status.fontMetrics().height()+8)
        class Requests(QObject):
            count=0
            def eventFilter(self,watched,event):
                if event.type()==QEvent.LayoutRequest:self.count+=1
                return False
        requests=Requests();w.installEventFilter(requests);self.addCleanup(w.removeEventFilter,requests)
        for _ in range(60):   # let the shown and resized window settle: a 50 ms slice without layout pass
            seen=requests.count;run(50)
            if requests.count==seen and not w._minimum_fit_pending:break
        else:self.fail('window never settled')
        requests.count=0
        minimum=w.minimumWidth();full='Export terminé : '+'/très/long/dossier'*40+'/PB05001.json'
        status.showMessage(full,150);run(30)
        shown=status.displayed_text()
        self.assertNotEqual(shown,full);self.assertTrue(shown.endswith('…'))
        self.assertEqual((status.toolTip(),status.currentMessage()),(full,full))
        self.assertEqual((w.minimumWidth(),requests.count),(minimum,0))   # a message never relayouts the window
        run(300)   # the timeout expired
        self.assertNotEqual(status.currentMessage(),full)
        status.clearMessage()
        self.assertEqual((status.displayed_text(),status.toolTip()),('',''))
