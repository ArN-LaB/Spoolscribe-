"""Installed-app feedback: discoverable choices and quiet, aligned layouts."""
import unittest
from unittest.mock import patch
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class ErgonomicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_printer_choice_has_a_searchable_visual_browser(self):
        from PySide6.QtWidgets import QDialog
        from spoolscribe.ui_widgets import PrinterBrowser
        w=self.window
        self.assertFalse(w.printer.isEditable())
        browser=PrinterBrowser(w.printer,w)
        self.addCleanup(browser.close)
        browser.search.setText('snapmaker');w.app.processEvents()
        visible=[browser.list.item(i) for i in range(browser.list.count()) if not browser.list.item(i).isHidden()]
        self.assertTrue(visible)
        self.assertLess(len(visible),browser.list.count())
        self.assertTrue(any('Snapmaker' in item.text() for item in visible))
        browser.search.setText('zzzz-inexistant');self.assertTrue(browser.empty.isVisibleTo(browser))
        before=w.printer.currentData()
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected):w.printer.showPopup()
        self.assertEqual(w.printer.currentData(),before)
        browser.search.setText('prusa');browser._choose()
        self.assertIsNotNone(browser.selected_index)
        self.assertEqual(w.printer.itemData(browser.selected_index),'prusa_core')
        def choose(dialog):
            dialog.search.setText('prusa');dialog._choose();return dialog.result()
        with patch.object(QDialog,'exec',choose):w.printer.showPopup()
        self.assertEqual(w.printer.currentData(),'prusa_core')

    def test_printer_results_fit_when_resizing(self):
        from spoolscribe.ui_widgets import PrinterBrowser
        browser=PrinterBrowser(self.window.printer,self.window);self.addCleanup(browser.close)
        browser.resize(440,340);browser.show();self.window.app.processEvents()
        for i in range(browser.list.count()):
            rect=browser.list.visualItemRect(browser.list.item(i))
            self.assertGreaterEqual(rect.height(),88)
            self.assertLessEqual(rect.width(),browser.list.viewport().width())

    def test_materials_are_alphabetical_searchable_and_reset_keeps_favorites(self):
        from PySide6.QtCore import Qt
        from spoolscribe import core
        w=self.window
        names=[w.family_list.item(i).data(Qt.UserRole) for i in range(1,w.family_list.count())]
        self.assertEqual(names,sorted(names,key=str.casefold))
        before=core.load_config()['favorite_brands']
        w.material_search.setText('petg')
        self.assertTrue(any(w.family_list.item(i).isHidden() for i in range(1,w.family_list.count())))
        w._reset_filters();self.assertEqual(w.material_search.text(),'')
        self.assertTrue(all(not w.family_list.item(i).isHidden() for i in range(w.family_list.count())))
        self.assertEqual(core.load_config()['favorite_brands'],before)

    def test_detail_has_no_scrollbar_without_overflow_but_keeps_export_edges(self):
        from PySide6.QtCore import Qt,QPoint
        w=self.window;w.resize(1360,1200);w.show();w._show_detail('PB05001');w.app.processEvents();w.app.processEvents()
        self.assertEqual(w.detail_scroll.verticalScrollBarPolicy(),Qt.ScrollBarAsNeeded)
        self.assertEqual(w.detail_scroll.verticalScrollBar().maximum(),0)
        self.assertFalse(w.detail_scroll.verticalScrollBar().isVisible())
        for height in (720,1200):
            w.resize(1000,height);w.app.processEvents();w.app.processEvents()
            right=lambda widget:widget.mapTo(w,QPoint()).x()+widget.width()
            self.assertEqual(right(w.hero),right(w.btn_generate))

    def test_characteristic_actions_are_equal_and_grouped_below_tiles(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.show();w._show_detail('PB05001');w.app.processEvents()
        a=w.btn_edit_physical;b=w.provenance_toggle
        self.assertEqual(a.height(),32);self.assertEqual(a.height(),b.height());self.assertEqual(a.width(),b.width())
        self.assertEqual(w.btn_generate.height(),48)
        self.assertEqual(a.mapTo(w,QPoint()).y(),b.mapTo(w,QPoint()).y())
        self.assertGreater(a.mapTo(w,QPoint()).y(),w.card.mapTo(w,QPoint()).y()+w.card.height())

    def test_native_font_metrics_do_not_expand_compact_action_columns(self):
        w=self.window
        font=w.font();font.setPointSize(20)
        for button in (w.reset_filters,w.favorites_only,w.brand_favorites_only,w.btn_edit_physical,w.provenance_toggle):button.setFont(font)
        w._apply_theme();w.show();w.app.processEvents()
        diagnostics=[(b.text(),b.width(),b.minimumSizeHint().width(),b.font().pixelSize()) for b in (w.reset_filters,w.favorites_only,w.brand_favorites_only,w.btn_edit_physical,w.provenance_toggle)]
        self.assertLessEqual(w.sidebar.width(),280,diagnostics)
        for b in (w.reset_filters,w.favorites_only,w.brand_favorites_only,w.btn_edit_physical,w.provenance_toggle):
            self.assertGreaterEqual(b.width(),b.fontMetrics().horizontalAdvance(b.text())+18,diagnostics)
        self.assertEqual(w.reset_filters.width(),w.favorites_only.width())
        self.assertEqual(w.btn_edit_physical.width(),w.provenance_toggle.width())

    def test_settings_separate_spool_preferences_from_export_options(self):
        from PySide6.QtWidgets import QDialog,QTabWidget
        def inspect(dlg):
            tabs=dlg.findChild(QTabWidget)
            self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],['Catalogue','Filaments','Étiquettes et export','Couleurs','Interface','Données et sauvegardes'])
            self.assertTrue(tabs.widget(1).findChild(fixture.app_gui.QComboBox,'preferred_weight_g'))
            self.assertIsNone(tabs.widget(2).findChild(fixture.app_gui.QComboBox,'preferred_weight_g'))
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):self.window._open_settings()

    def test_database_report_is_structured_and_translates_source_statuses(self):
        from PySide6.QtWidgets import QDialog,QLabel,QPlainTextEdit
        w=self.window;w.db['_source_results']=[dict(source='Polymaker officiel',status='unchanged',ok=True,message='')]
        w.db['_last_updated']='2026-11-01T11:11:50.539673'
        def inspect(dlg):
            self.assertTrue(dlg.findChildren(QLabel,'reportMetricValue'))
            labels=' '.join(x.text() for x in dlg.findChildren(QLabel))
            self.assertIn('À jour',labels);self.assertNotIn('unchanged',labels)
            self.assertNotIn('539673',labels)
            self.assertTrue(all(not text.isVisibleTo(dlg) for text in dlg.findChildren(QPlainTextEdit)))
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):w._database_details()

    def test_partial_sync_report_does_not_claim_complete_success(self):
        from PySide6.QtWidgets import QDialog,QLabel
        from spoolscribe import core
        w=self.window;before=w._snapshot_stats()
        results=[core.StepResult('Polymaker officiel',True,status='unchanged'),core.StepResult('SUNLU officiel',False,2,'CERTIFICATE_VERIFY_FAILED',status='unavailable')]
        w._show_sync_report(results,before)
        dialog=next(d for d in w.findChildren(QDialog) if d.windowTitle()=='Actualisation du catalogue');self.addCleanup(dialog.close)
        text=' '.join(label.text() for label in dialog.findChildren(QLabel))
        self.assertIn('Certaines sources restent',text);self.assertIn('Connexion sécurisée impossible',text);self.assertIn('1 / 2',text)
        self.assertFalse(next(label for label in dialog.findChildren(QLabel,'sourceStatus') if 'Connexion' in label.text()).property('success'))


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class CatalogueStateTests(unittest.TestCase):
    """B14 C: refresh action, state and progress together with the catalogue; simulated workers, no network."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def fake_worker(self):
        from PySide6.QtCore import QObject, Signal
        import threading
        class FakeWorker(QObject):
            progress=Signal(str,int,int);finished_ok=Signal(list);failed=Signal(str)
            def __init__(self,parent=None):
                super().__init__(parent);self.cancel=threading.Event();self.running=False
            def start(self):self.running=True
            def isRunning(self):return self.running
            def wait(self,*_):return True
        return FakeWorker

    def start(self):
        w=self.window
        with patch('spoolscribe.app_gui.UpdateWorker',self.fake_worker()),patch.object(w,'_ask_network_consent',return_value=True):
            w._start_update(manual=True)
        worker=w.worker;self.addCleanup(setattr,worker,'running',False)   # never leave a « running » refresh at close
        return worker

    def test_refresh_lives_with_the_catalogue_apart_from_the_search(self):
        w=self.window;w.show();w.app.processEvents()
        self.assertTrue(w.catalogue_state.isAncestorOf(w.update_btn));self.assertTrue(w.catalogue_state.isAncestorOf(w.database_btn))
        self.assertFalse(w.catalogue_state.isAncestorOf(w.search))
        self.assertIs(w.update_progress_card.parentWidget(),w.catalogue_state.parentWidget())
        self.assertEqual(w.update_btn.height(),w.search.height())
        with patch.object(w,'_start_update') as update,patch.object(w,'_choose_sources') as sources:
            w.search.setText('PLA');w._apply_filter()
        update.assert_not_called();sources.assert_not_called()   # local search never synchronises
        # Narrow catalogue panel: the state and the action stack instead of being cut.
        w.catalogue_state.resize(260,w.catalogue_state.height());w.catalogue_state.reflow()
        from PySide6.QtWidgets import QBoxLayout
        self.assertEqual(w.catalogue_state.box.direction(),QBoxLayout.Direction.TopToBottom)

    def test_state_text_never_presents_a_partial_or_failed_refresh_as_complete(self):
        w=self.window
        cases=[(dict(_update_status='complete',_last_updated='2026-11-07T10:00:00'),'actualisée le 07/11/2026',None),
               (dict(_update_status='partial',_last_updated='2026-11-01T09:00:00'),'actualisation partielle · complète le 01/11/2026','actualisée le'),
               (dict(_update_status='failed'),'actualisation échouée','actualisée le'),
               (dict(_update_status=None),'à synchroniser','actualisée')]
        for metadata,expected,absent in cases:
            with self.subTest(metadata=metadata):
                w.db.pop('_last_updated',None);w.db.update(metadata);w._refresh_database_summary()
                self.assertIn(expected,w.database_btn.text())
                if absent:self.assertNotIn(absent,w.database_btn.text())

    def test_running_cancelled_failed_and_complete_states_stay_in_one_place(self):
        w=self.window;w.show();w.app.processEvents()
        worker=self.start();w.app.processEvents()
        self.assertTrue(w.update_progress_card.isVisible());self.assertFalse(w.update_btn.isEnabled())
        self.assertIn('actualisation en cours',w.database_btn.text())
        self.assertNotIn('Mise à jour',w.status.currentMessage())   # no floating « Mise à jour en cours… »
        w._on_update_progress('Catalogue multi-fabricants OFD',2,5)
        self.assertEqual(w.progress_step.text(),'Étape 2 sur 5');self.assertEqual(w.progress.value(),1)
        w._cancel_update();self.assertIn('Annulation demandée',w.progress_label.text());self.assertTrue(worker.cancel.is_set())
        worker.running=False
        from spoolscribe import core
        before=w.db.get('_last_updated')
        with patch.object(w,'_show_sync_report') as report:
            w._on_update_done([core.StepResult('Catalogue multi-fabricants OFD',False,-3,'',"cancelled")])
        report.assert_not_called()
        self.assertFalse(w.update_progress_card.isVisible());self.assertTrue(w.update_btn.isEnabled())
        self.assertIn('actualisation annulée · base conservée',w.database_btn.text());self.assertEqual(w.db.get('_last_updated'),before)
        # A crashed worker: failed state, never « actualisée ».
        self.start();w.worker.running=False
        with patch('spoolscribe.app_gui.QMessageBox.critical'):w._on_update_failed('Traceback')
        self.assertIn('actualisation échouée',w.database_btn.text());self.assertFalse(w.update_progress_card.isVisible())
        # A complete manual refresh: dated state and the report, card hidden.
        self.start();w.worker.running=False
        def complete(*_a,**_k):
            db=core.load_db();db.update(_update_status='complete',_last_updated='2026-11-08T08:00:00');core.save_db(db)
            return db
        complete()
        with patch.object(w,'_show_sync_report') as report:
            w._on_update_done([core.StepResult('Catalogue multi-fabricants OFD',True,0,'','changed')])
        report.assert_called_once()
        self.assertIn('actualisée le 08/11/2026',w.database_btn.text());self.assertFalse(w.update_progress_card.isVisible())

    def test_reopening_after_a_cancelled_run_shows_the_stored_state_only(self):
        from spoolscribe import app_gui, core
        w=self.window;self.start();w.worker.running=False
        w._on_update_done([core.StepResult('Catalogue multi-fabricants OFD',False,-3,'',"cancelled")])
        self.assertIn('annulée',w.database_btn.text())
        w.close();other=app_gui.MainWindow();self.addCleanup(other.close)
        self.assertNotIn('annulée',other.database_btn.text());self.assertNotIn('en cours',other.database_btn.text())
        self.assertFalse(other.update_progress_card.isVisible())
