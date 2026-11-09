"""A validated label exports without asking the temperature question again."""
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace
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
        w.printer.setCurrentIndex(w.printer.findData('opentag3d'));w.format_buttons.buttons['opentag3d'].click()  # explicit choice (B14 A)
        w.current_sku='PB05001';w._show_detail(w.current_sku)
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


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagValidationTests(unittest.TestCase):
    """B15: every blocking value is listed in the form, corrected in place, then exported as chosen."""
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):
        fixture.GuiTests.setUp(self);i18n.set_language('fr');w=self.window
        w.printer.setCurrentIndex(w.printer.findData('opentag3d'));w.format_buttons.buttons['opentag3d'].click()
        w.opentag_output.setCurrentIndex(w.opentag_output.findData('ndef'))
        w.current_sku='PB05001';self.entry=w.db['_skus'][w.current_sku];self.product=w.db['_products'][self.entry['product']]
        self.product.update(bed_min_temp=45,bed_max_temp=80)
        self.valid=dict(print_temp='245',bed_temp='60',chamber_temp='50',weight='1000')

    def source(self,**changes):
        """Write the synthetic source to the isolated base, as a synchronised record would be."""
        w=self.window;self.entry.update({k:v for k,v in changes.items() if k=='manufacturer_sku'})
        self.product.update({k:v for k,v in changes.items() if k!='manufacturer_sku'})
        core.save_db(w.db);w._show_detail(w.current_sku);self.db_bytes=Path(core.DB_PATH).read_bytes()

    def ui(self,dialog):
        """Accessors on one real label form."""
        from PySide6.QtWidgets import QLineEdit,QToolButton,QDialogButtonBox,QWidget,QPushButton,QCheckBox,QLabel
        w=self.window
        class Ui:
            def __init__(ui,dialog):ui.dialog=dialog
            def edit(ui,key):return ui.dialog.findChild(QLineEdit,'opentag_'+key)
            def rows(ui):
                box=ui.dialog.findChild(QWidget,'opentagProblems')
                return [row for row in box.findChildren(QWidget,'opentagProblem')]
            def keys(ui):return list(ui.dialog.property('opentag_problem_keys') or [])   # every problem, encoder order
            def hint(ui,key):return next((h for h in ui.dialog.findChildren(QLabel,'opentagHint') if h.property('opentag_key')==key),None)
            def row_text(ui,key):
                """The single message of a problem: above its control, or in the record group."""
                hint=ui.hint(key)
                if hint is not None:return hint.text() if not hint.isHidden() else ''
                return next(r for r in ui.rows() if r.property('opentag_key')==key).findChild(QLabel).text()
            def fix(ui,key):next(r for r in ui.rows() if r.property('opentag_key')==key).findChild(QPushButton).click();w.app.processEvents()
            def solution(ui,role):
                """Green « ready fix » button (split or abbreviation), or None."""
                return next((b for b in ui.dialog.findChildren(QPushButton,'opentagSolution') if b.property('opentag_role')==role),None)
            def confirm(ui):ui.dialog.findChild(QToolButton,'opentag_confirmed').setChecked(True)
            def confirmed(ui):return ui.dialog.findChild(QToolButton,'opentag_confirmed').isChecked()
            def save(ui):return ui.dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save)
            def omit(ui):return ui.dialog.findChild(QCheckBox,'opentag_sku_omit')
            def label(ui,name):return ui.dialog.findChild(QLabel,name)
            def split(ui):return ui.dialog.findChild(QWidget,'opentag_material_split')
            def fill(ui,values):
                for key,value in values.items():ui.edit(key).setText(value)
        return Ui(dialog)

    def form(self,act):
        """Run ``act(dialog, ui)`` inside the real label form; returns whether it was saved."""
        w=self.window
        def run(dialog):
            dialog.show();w.app.processEvents();act(dialog,self.ui(dialog))
            return dialog.result()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=run),patch('spoolscribe.ui_catalogue.QMessageBox.warning',side_effect=AssertionError('unexpected box')):
            return w._complete_opentag_settings()

    def export(self):
        """Normal export path to the isolated output folder; returns the decoded payload."""
        from spoolscribe import opentag3d
        w=self.window;before=set(Path(core.OUTPUT_DIR).glob('*')) if Path(core.OUTPUT_DIR).exists() else set()
        with patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',return_value=core.OUTPUT_DIR),\
             patch('spoolscribe.app_gui.QMessageBox.information'),patch('spoolscribe.ui_catalogue.QDialog.exec',side_effect=AssertionError('form reopened')):
            w._generate()
        written=[p for p in Path(core.OUTPUT_DIR).glob('*.ndef') if p not in before or True]
        data=max(written,key=lambda p:p.stat().st_mtime).read_bytes()
        self.assertEqual(data[:3],bytes([0xD2,len(opentag3d.MIME),224]));payload=data[3+len(opentag3d.MIME):]
        self.assertEqual(Path(core.DB_PATH).read_bytes(),self.db_bytes)   # the synchronised source is untouched
        return payload,opentag3d.decode(payload)

    def test_long_reference_is_shortened_or_omitted_by_choice_and_exported_as_shown(self):
        self.source(manufacturer_sku='REFERENCE-1234567')
        def shorten(dialog,ui):
            self.assertIn('sku',ui.keys())
            self.assertEqual(ui.row_text('sku'),'Référence trop longue pour l’étiquette. Raccourcissez-la ou omettez-la.')
            tip=ui.edit('sku').toolTip();self.assertIn('catalogue synchronisé',tip)
            self.assertIn('Limite de l’étiquette : 16 octets UTF-8 (17 utilisés).',tip)   # exact limit on demand (A2)
            ui.fill(self.valid);ui.confirm();self.assertFalse(ui.save().isEnabled())   # still invalid: no save
            ui.edit('sku').setText('é'*9);self.assertIn('(18 utilisés)',ui.edit('sku').toolTip());self.assertEqual(ui.keys(),['sku'])
            ui.edit('sku').setText('é'*8);self.assertEqual(ui.keys(),[])   # 16 bytes for 8 characters: accepted
            ui.edit('sku').setText('REF-1234567890AB')
            self.assertEqual(ui.keys(),[]);self.assertIn('(16 utilisés)',ui.edit('sku').toolTip());self.assertEqual(ui.row_text('sku'),'')
            self.assertEqual(ui.label('opentag_sku_preview').text(),'Valeur exportée : « REF-1234567890AB »')
            self.assertFalse(ui.save().isEnabled());ui.confirm();self.assertTrue(ui.save().isEnabled());ui.save().click()
        self.assertTrue(self.form(shorten))
        self.assertEqual(self.entry['manufacturer_sku'],'REFERENCE-1234567')
        payload,decoded=self.export()
        self.assertEqual(payload[0x6C:0x7C],b'REF-1234567890AB');self.assertEqual(decoded['sku'],'REF-1234567890AB')
        def omit(dialog,ui):
            ui.omit().setChecked(True);self.assertFalse(ui.edit('sku').isEnabled())
            self.assertEqual(ui.label('opentag_sku_preview').text(),'Valeur exportée : aucune référence')
            ui.confirm();ui.save().click()
        self.assertTrue(self.form(omit));self.assertEqual(core.opentag_settings(self.window.current_sku)['sku'],'')
        payload,decoded=self.export()
        self.assertEqual(payload[0x6C:0x7C],b'\0'*16);self.assertEqual(decoded['sku'],'')
        self.assertEqual(json.loads(self.window._prepare_opentag().preview)['fields']['sku'],'')   # never reintroduced
        def reopened(dialog,ui):
            self.assertTrue(ui.omit().isChecked());self.assertEqual(ui.edit('sku').text(),'REFERENCE-1234567');dialog.reject()
        self.assertFalse(self.form(reopened))

    def test_min45_and_chamber50_reach_the_file_unchanged(self):
        self.source();stages={}
        def ready(dialog,ui):
            self.assertEqual(ui.edit('min_bed_temp').text(),'45');ui.fill(self.valid)
            self.assertEqual(ui.keys(),[]);self.assertTrue(ui.label('opentag_ready').isVisible())
            stages['form']=(ui.edit('min_bed_temp').text(),ui.edit('chamber_temp').text());ui.confirm();ui.save().click()
        self.assertTrue(self.form(ready))
        saved=core.opentag_settings(self.window.current_sku);stages['model']=(saved['min_bed_temp'],saved['chamber_temp'])
        fields=json.loads(self.window._prepare_opentag().preview)['fields'];stages['prepared']=(fields['min_bed_temp'],fields['chamber_temp'])
        payload,decoded=self.export();stages['file']=(decoded['min_bed_temp'],decoded['chamber_temp'])
        self.assertEqual((payload[0x95],payload[0x93]),(9,10))   # 45 and 50 °C on the 5 °C grid
        self.assertEqual(stages,dict(form=('45','50'),model=(45.0,50.0),prepared=(45.0,50.0),file=(45.0,50.0)))

    def test_min46_is_listed_with_neighbours_and_never_rounded(self):
        self.source(bed_min_temp=46)
        def fix(dialog,ui):
            ui.fill(self.valid)
            self.assertEqual(ui.keys(),['min_bed_temp']);text=ui.row_text('min_bed_temp')
            self.assertIn('46 n’est pas un multiple de 5',text);self.assertIn('45 ou 50',text);self.assertIn('catalogue synchronisé',ui.edit('min_bed_temp').toolTip())
            self.assertEqual(ui.edit('min_bed_temp').text(),'46')   # shown as is, not rounded
            ui.confirm();self.assertFalse(ui.save().isEnabled())
            ui.edit('min_bed_temp').setText('4x');self.assertIn('« 4x » n’est pas un nombre',ui.row_text('min_bed_temp'))
            ui.edit('min_bed_temp').setText('45');self.assertEqual(ui.keys(),[]);ui.confirm();ui.save().click()
        self.assertTrue(self.form(fix));self.assertEqual(self.export()[1]['min_bed_temp'],45.0)

    def test_two_problems_are_listed_together_and_corrected_without_a_hidden_one(self):
        self.source(manufacturer_sku='REFERENCE-1234567',bed_min_temp=46)
        def both(dialog,ui):
            ui.fill(self.valid);self.assertEqual(ui.keys(),['sku','min_bed_temp'])
            ui.edit('sku').setText('REF-1');self.assertEqual(ui.keys(),['min_bed_temp'])
            ui.edit('min_bed_temp').setText('50');self.assertEqual(ui.keys(),[])
            ui.confirm();ui.save().click()
            self.assertFalse(ui.label('opentag_residual').isVisible())
        self.assertTrue(self.form(both))
        decoded=self.export()[1];self.assertEqual((decoded['sku'],decoded['min_bed_temp']),('REF-1',50.0))

    def test_change_after_confirmation_revokes_it_and_invalid_data_never_reach_a_destination(self):
        self.source(bed_min_temp=46)
        def change(dialog,ui):
            ui.fill(dict(self.valid,min_bed_temp='45'));ui.confirm();self.assertTrue(ui.save().isEnabled())
            ui.edit('weight').setText('750')
            self.assertFalse(ui.dialog.findChild(__import__('PySide6.QtWidgets',fromlist=['QToolButton']).QToolButton,'opentag_confirmed').isChecked())
            self.assertFalse(ui.save().isEnabled());dialog.reject()
        config=Path(core.CONFIG_PATH).read_bytes();opened=[]
        def cancelled(dialog):
            opened.append(dialog.windowTitle());return 0   # the form opens (invalid source) and is cancelled
        with patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory') as folder,patch('spoolscribe.ui_catalogue.QDialog.exec',new=cancelled):
            self.window._generate()
            folder.assert_not_called()
        self.assertEqual(len(opened),1)
        self.assertFalse(self.form(change))
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),config)
        self.assertEqual(list(Path(core.OUTPUT_DIR).glob('*')) if Path(core.OUTPUT_DIR).exists() else [],[])

    def test_a_residual_encoder_refusal_stays_in_the_form(self):
        w=self.window;self.source();w.tag_type.setCurrentIndex(w.tag_type.findData('NTAG215'));w.nfc_reserve.setValue(w.nfc_reserve.maximum())
        def capacity(dialog,ui):
            ui.fill(self.valid);ui.confirm();ui.save().click()
            residual=ui.label('opentag_residual');self.assertTrue(residual.isVisible());self.assertIn('Contrôle final',residual.text())
            self.assertFalse(ui.save().isEnabled());dialog.reject()
        self.assertFalse(self.form(capacity));self.assertEqual(core.opentag_settings(w.current_sku),{})

    def test_a_record_value_opens_the_record_editor_instead_of_a_dead_button(self):
        from PySide6.QtWidgets import QPushButton
        self.source(diameter=1.7505);w=self.window
        def record(dialog,ui):
            ui.fill(self.valid);self.assertEqual(ui.keys(),['diameter'])
            row=next(r for r in ui.rows() if r.property('opentag_key')=='diameter')
            self.assertEqual(row.findChild(QPushButton).text(),'Modifier la fiche…');ui.fix('diameter')
            self.assertEqual(dialog.result(),0)   # the form closed itself, nothing saved
        with patch.object(w,'_edit_physical') as editor:
            self.assertFalse(self.form(record));w.app.processEvents()
        editor.assert_called_once_with('diameter');self.assertEqual(core.opentag_settings(w.current_sku),{})


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagResumeTests(unittest.TestCase):
    """B16: label inputs survive « Modifier la fiche… » and come back on the record actually saved."""
    setUpClass=classmethod(lambda cls:fixture.GuiTests.setUpClass())
    setUp=OpenTagValidationTests.setUp;source=OpenTagValidationTests.source;ui=OpenTagValidationTests.ui
    TITLE='Préparer l’étiquette OpenTag3D'

    def start(self,**source):
        """Synthetic source with a blocking diameter and a too long reference; real window shown."""
        w=self.window;w.show();w.app.processEvents()
        self.source(diameter=1.7505,manufacturer_sku='SOURCE-REFERENCE-TROP-LONGUE',**source)
        self.origin=w.current_sku;self.typed=dict(self.valid,sku='ETIQUETTE-COURTE',chamber_temp='50',weight='750',
                                                  color_name='Bleu essai',material_mod='Mat')
        disk=json.loads(self.db_bytes);self.source_record=(disk['_skus'][self.origin],disk['_products'][self.entry['product']])
        self.config=core.opentag_settings(self.origin)

    def assert_source_intact(self):
        """The base file legitimately gains a copy; the source reference and product stay identical."""
        disk=json.loads(Path(core.DB_PATH).read_bytes())
        self.assertEqual((disk['_skus'][self.origin],disk['_products'][self.entry['product']]),self.source_record)
        self.assertEqual(core.opentag_settings(self.origin),self.config)
        self.assertEqual(list(Path(core.OUTPUT_DIR).glob('*')) if Path(core.OUTPUT_DIR).exists() else [],[])   # nothing exported

    @contextlib.contextmanager
    def forms(self,*acts):
        """Each real label form opened inside the block runs the next act; extra openings are recorded.

        Acts may run from a Qt timer, where an exception would only be printed: it is kept and raised here.
        """
        w=self.window;queue=list(acts);opened=[];errors=[]
        def run(dialog):
            opened.append((dialog.windowTitle(),w.current_sku))
            if not queue:return 0
            dialog.show();w.app.processEvents()
            try:queue.pop(0)(dialog,self.ui(dialog))
            except BaseException as exc:errors.append(exc);dialog.reject()
            return dialog.result()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=run),\
             patch('spoolscribe.ui_catalogue.QMessageBox.warning',side_effect=AssertionError('unexpected box')),\
             patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',side_effect=AssertionError('destination asked')):
            yield opened
            w.app.processEvents()
        if errors:raise errors[0]
        self.assertEqual(queue,[],'label form not reopened')
        self.assertTrue(all(title==self.TITLE for title,_ in opened),opened)

    def leave_for_record(self,values=None,omit=False):
        """First form: type the label inputs and confirm, then « Modifier la fiche… » on the diameter row."""
        def act(dialog,ui):
            ui.fill(values or self.typed);ui.omit().setChecked(omit)
            self.assertIn('diameter',ui.keys());ui.confirm();self.assertTrue(ui.confirmed())
            ui.fix('diameter')
        return act

    def resumed(self,seen,finish=None,keys=None):
        """Reopened form: what the user finds, before any action of theirs."""
        def act(dialog,ui):
            seen.update(sku=self.window.current_sku,fields={k:ui.edit(k).text() for k in keys or self.typed},
                        omit=ui.omit().isChecked(),sku_enabled=ui.edit('sku').isEnabled(),keys=ui.keys(),
                        confirmed=ui.confirmed(),save=ui.save().isEnabled(),
                        banner=bool(ui.label('opentag_resumed')) and ui.label('opentag_resumed').isVisible(),
                        preview=ui.label('opentag_sku_preview').text())
            (finish or (lambda d,u:d.reject()))(dialog,ui)
        return act

    def correct_record(self,sku=None,diameter='1.75'):
        """Real in-card editor, opened by the form on the diameter of the label's reference."""
        w=self.window;w.app.processEvents()
        self.assertTrue(w.draft_editor.isVisible());self.assertIn('opentag_resume',w._draft)
        self.assertEqual(w._draft['sku'],sku or self.origin);self.assertIs(w.focusWidget(),w.draft_fields['diameter'])
        w.draft_fields['diameter'].setText(diameter);w._draft_edited()

    def copies(self):
        return {s:e for s,e in self.window.db['_skus'].items() if e.get('_personal')}

    def test_r1_inputs_come_back_on_the_saved_copy_unconfirmed_and_unexported(self):
        self.start();w=self.window;seen={}
        def finish(dialog,ui):
            ui.confirm();self.assertTrue(ui.save().isEnabled());ui.save().click()   # the user's own final action
        with self.forms(self.leave_for_record(),self.resumed(seen,finish)) as opened:
            self.assertFalse(w._complete_opentag_settings())
            self.correct_record();self.assertEqual(len(opened),1)
            w.draft_save.click()   # real « Enregistrer une copie », real write of the personal copy
        (created,record),=self.copies().items()
        self.assertNotEqual(created,self.origin);self.assertEqual(record['_personal_origin'],self.origin)
        self.assertEqual([sku for _,sku in opened],[self.origin,created])
        self.assertEqual(seen['sku'],created);self.assertEqual(core.get_sku_view(w.db,created).product_data['diameter'],1.75)
        self.assertEqual(seen['fields'],self.typed)   # SKU, chamber, mass and other adaptations kept
        self.assertEqual((seen['keys'],seen['confirmed'],seen['save'],seen['banner']),([],False,False,True))
        self.assertEqual(seen['preview'],'Valeur exportée : « ETIQUETTE-COURTE »')
        saved=core.opentag_settings(created)
        self.assertEqual((saved['sku'],saved['chamber_temp'],saved['weight'],saved['color_name']),('ETIQUETTE-COURTE',50.0,750.0,'Bleu essai'))
        self.assertIsNone(w._draft);self.assert_source_intact()
        self.assertEqual(json.loads(w._prepare_opentag().preview)['fields']['diameter'],1.75)

    def test_cancel_puts_omission_and_invalid_inputs_back_on_the_origin_without_a_copy(self):
        self.start();w=self.window;seen={}
        typed=dict(self.typed,weight='',min_bed_temp='4x',color_name='')
        with self.forms(self.leave_for_record(typed,omit=True),self.resumed(seen,keys=typed)) as opened:
            self.assertFalse(w._complete_opentag_settings())
            self.correct_record()   # typed in the editor, then abandoned
            w.draft_cancel.click()
        self.assertEqual([sku for _,sku in opened],[self.origin,self.origin])
        self.assertEqual(seen['fields'],typed)   # as typed, empty and invalid included; the reference stays omitted
        self.assertEqual((seen['omit'],seen['sku_enabled'],seen['preview']),(True,False,'Valeur exportée : aucune référence'))
        self.assertEqual(seen['keys'],['weight','diameter','min_bed_temp'])   # recomputed in encoder order; record unchanged
        self.assertEqual((seen['confirmed'],seen['save'],seen['banner']),(False,False,True))
        self.assertEqual(self.copies(),{});self.assertEqual(Path(core.DB_PATH).read_bytes(),self.db_bytes)
        self.assertIsNone(w._draft);self.assert_source_intact()

    def test_failed_writes_keep_the_editor_and_inputs_until_a_real_copy_exists(self):
        self.start();w=self.window;seen={}
        with self.forms(self.leave_for_record(),self.resumed(seen)) as opened:
            self.assertFalse(w._complete_opentag_settings());self.correct_record()
            w.draft_suffix.setText('');w.draft_save.click();w.app.processEvents()   # refused before any write
            self.assertTrue(w.draft_error.isVisible());self.assertIn('Suffixe',w.draft_error.text())
            w.draft_suffix.setText('Essai')
            with patch('spoolscribe.core.save_db',side_effect=OSError('Disque plein (essai)')):
                w.draft_save.click();w.app.processEvents()
            self.assertIn('Disque plein (essai)',w.draft_error.text());w.app.processEvents()
            # Both failures: editor, error and context kept; no copy, so no form on a copy that does not exist.
            self.assertEqual(len(opened),1);self.assertTrue(w.draft_editor.isVisible());self.assertIn('opentag_resume',w._draft)
            self.assertEqual(Path(core.DB_PATH).read_bytes(),self.db_bytes);self.assertEqual(self.copies(),{})
            w.draft_save.click()   # retried once the cause is gone
        (created,_),=self.copies().items()
        self.assertEqual([sku for _,sku in opened],[self.origin,created]);self.assertEqual(seen['fields'],self.typed)
        self.assertFalse(seen['confirmed']);self.assert_source_intact()

    def test_an_updated_personal_copy_keeps_its_identifier(self):
        self.start();w=self.window;seen={}
        personal=core.save_personal_filament(w.db,self.origin,{'diameter':1.7505},'Personnel')
        w.current_sku=personal;w._reload_table();w.current_sku=personal;w._show_detail(personal);self.config=core.opentag_settings(self.origin)
        self.source_record=tuple(json.loads(Path(core.DB_PATH).read_bytes())[k][v] for k,v in (('_skus',self.origin),('_products',self.entry['product'])))
        with self.forms(self.leave_for_record(),self.resumed(seen)) as opened:
            self.assertFalse(w._complete_opentag_settings())
            self.correct_record(personal);self.assertEqual(w.draft_suffix.text(),'Personnel')
            self.assertTrue(w._save_draft())   # same outcome as the button, whatever calls the editor's save
        self.assertEqual(list(self.copies()),[personal])   # same suffix: the copy itself is updated
        self.assertEqual([sku for _,sku in opened],[personal,personal]);self.assertEqual(seen['fields'],self.typed)
        self.assertEqual(core.get_sku_view(w.db,personal).product_data['diameter'],1.75);self.assert_source_intact()

    def test_leaving_the_journey_drops_the_inputs_and_never_reaches_another_label(self):
        self.start();w=self.window;seen={}
        other=next(e['sku'] for e in w._filtered_rows if len(e.get('variants',[]))<=1 and w._group_for_sku(e['sku']) is not w._group_for_sku(self.origin))
        before_other=core.opentag_settings(other)
        with self.forms(self.leave_for_record(),self.resumed(seen)) as opened:
            self.assertFalse(w._complete_opentag_settings());self.correct_record()
            with patch.object(w,'_ask_draft_decision',return_value='save'):
                w.draft_suffix.setText('');w._select_result(other);w.app.processEvents()   # save chosen while leaving, refused
                self.assertEqual((w.current_sku,w._draft['sku']),(self.origin,self.origin));self.assertIn('opentag_resume',w._draft)
                self.assertEqual(self.copies(),{});w.draft_suffix.setText('Essai')
                self.assertTrue(w._select_result(other));w.app.processEvents()   # save chosen while leaving, written
            self.assertIsNone(w._draft);self.assertEqual(w.current_sku,other);w.app.processEvents()
            self.assertEqual(len(opened),1)
            self.assertFalse(w._complete_opentag_settings())   # the other label: nothing carried over
        self.assertEqual(seen['sku'],other);self.assertFalse(seen['banner'])
        self.assertNotEqual(seen['fields']['sku'],'ETIQUETTE-COURTE');self.assertNotEqual(seen['fields']['weight'],'750')
        self.assertEqual(core.opentag_settings(other),before_other)
        (created,_),=self.copies().items();self.assertEqual(core.opentag_settings(created),{})
        # Same journey ended by closing the window: no late form, no setting written.
        w._show_detail(self.origin);seen.clear()
        with self.forms(self.leave_for_record()) as opened:
            self.assertFalse(w._complete_opentag_settings());w.app.processEvents()
            self.assertIn('opentag_resume',w._draft);self.assertTrue(w.close());w.app.processEvents()
            self.assertEqual(len(opened),1)
        self.assertFalse(w.isVisible());self.assertEqual(core.opentag_settings(self.origin),self.config)


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagRefusalTests(unittest.TestCase):
    """B17: « Modifier la fiche… » refused (refresh running, or failing) never loses the label inputs."""
    R=OpenTagResumeTests
    setUpClass=classmethod(lambda cls:fixture.GuiTests.setUpClass())
    setUp=R.setUp;source=R.source;ui=R.ui;start=R.start;assert_source_intact=R.assert_source_intact
    forms=R.forms;correct_record=R.correct_record;copies=R.copies;TITLE=R.TITLE
    REFRESHING='Attendez la fin de la mise à jour avant de modifier ou exporter la fiche.'
    KEPT='Vos saisies restent dans ce formulaire.'

    def begin(self):
        """Raw inputs C1 asks for: empty SKU and omission, an invalid value, mass and chamber."""
        self.start();self.raw=dict(self.typed,sku='',min_bed_temp='4x',weight='750',chamber_temp='50')
        self.busy={'on':False};return patch.object(self.window,'worker',SimpleNamespace(isRunning=lambda:self.busy['on']))

    def press_record(self,ui):
        """« Modifier la fiche… » on the diameter row, without letting Qt run what it defers."""
        from PySide6.QtWidgets import QPushButton
        next(r for r in ui.rows() if r.property('opentag_key')=='diameter').findChild(QPushButton).click()

    def observe(self,dialog,ui):
        refusal=ui.label('opentag_refusal');banner=ui.label('opentag_resumed')
        return dict(sku=self.window.current_sku,visible=dialog.isVisible(),fields={k:ui.edit(k).text() for k in self.raw},
                    omit=ui.omit().isChecked(),confirmed=ui.confirmed(),save=ui.save().isEnabled(),
                    refusal=refusal.text() if refusal.isVisible() else None,banner=bool(banner) and banner.isVisible(),
                    draft=self.window._draft)

    def test_refusal_during_refresh_keeps_the_form_then_the_retry_reaches_the_saved_copy(self):
        w=self.window;seen={}
        with self.begin():
            self.busy['on']=True
            def first(dialog,ui):
                ui.fill(self.raw);ui.omit().setChecked(True);ui.confirm()
                ui.fix('diameter');seen['refused']=self.observe(dialog,ui)   # refresh running: refused in place
                self.busy['on']=False;ui.fix('diameter')                       # refresh over: same button, editor opens
            def back(dialog,ui):seen['back']=self.observe(dialog,ui);dialog.reject()
            with self.forms(first,back) as opened:
                w._refresh_export_state();w.export_details_button.click();w.app.processEvents()   # visible route
                self.assertTrue(w.btn_opentag_settings.isVisible());self.assertTrue(w.btn_opentag_settings.isEnabled())
                w.btn_opentag_settings.click();w.app.processEvents()
                self.correct_record();w.draft_save.click()   # real personal copy, written once the refresh is over
        refused=seen['refused']
        self.assertEqual((refused['visible'],refused['fields'],refused['omit'],refused['confirmed'],refused['draft']),(True,self.raw,True,True,None))
        self.assertEqual(refused['refusal'],self.REFRESHING+' '+self.KEPT)
        (created,_),=self.copies().items();back=seen['back']
        self.assertEqual([sku for _,sku in opened],[self.origin,created]);self.assertEqual(back['sku'],created)
        self.assertEqual((back['fields'],back['omit'],back['confirmed'],back['save'],back['banner'],back['refusal']),(self.raw,True,False,False,True,None))
        self.assertEqual(core.get_sku_view(w.db,created).product_data['diameter'],1.75);self.assert_source_intact()

    def test_a_refresh_starting_after_the_check_brings_the_form_back_with_the_reason(self):
        w=self.window;seen={}
        with self.begin():
            def first(dialog,ui):
                ui.fill(self.raw);ui.omit().setChecked(True);ui.confirm()
                self.press_record(ui);self.busy['on']=True   # the check passed; the refresh starts before the real opening
            def back(dialog,ui):seen.update(self.observe(dialog,ui));dialog.reject()
            with self.forms(first,back) as opened:
                self.assertFalse(w._complete_opentag_settings())
                for _ in range(3):w.app.processEvents()
        self.assertEqual([sku for _,sku in opened],[self.origin,self.origin]);self.assertEqual(seen['fields'],self.raw)
        self.assertEqual((seen['omit'],seen['confirmed'],seen['save'],seen['banner'],seen['draft']),(True,False,False,True,None))
        self.assertEqual(seen['refusal'],self.REFRESHING+' '+self.KEPT)
        self.assertIsNone(w._draft);self.assertEqual(Path(core.DB_PATH).read_bytes(),self.db_bytes);self.assertEqual(self.copies(),{})
        self.assert_source_intact()

    def test_an_editor_that_fails_to_open_gives_the_inputs_back(self):
        w=self.window;seen={}
        with self.begin(),patch.object(w,'_edit_physical',side_effect=RuntimeError('panne simulée')) as editor:
            def first(dialog,ui):ui.fill(self.raw);ui.omit().setChecked(True);ui.fix('diameter')
            def back(dialog,ui):seen.update(self.observe(dialog,ui));dialog.reject()
            with self.forms(first,back) as opened:
                self.assertFalse(w._complete_opentag_settings())
                for _ in range(3):w.app.processEvents()
        editor.assert_called_once_with('diameter')
        self.assertEqual([sku for _,sku in opened],[self.origin,self.origin]);self.assertEqual((seen['fields'],seen['omit']),(self.raw,True))
        self.assertEqual(seen['refusal'],'La fiche n’a pas pu être ouverte : panne simulée '+self.KEPT)
        self.assertIsNone(w._draft);self.assertEqual(Path(core.DB_PATH).read_bytes(),self.db_bytes);self.assert_source_intact()

    def test_another_selection_before_the_refused_opening_reaches_no_other_label(self):
        w=self.window;seen={}
        with self.begin():
            other=next(e['sku'] for e in w._filtered_rows if len(e.get('variants',[]))<=1 and w._group_for_sku(e['sku']) is not w._group_for_sku(self.origin))
            before_other=core.opentag_settings(other)
            def first(dialog,ui):ui.fill(self.raw);ui.omit().setChecked(True);self.press_record(ui);self.busy['on']=True
            def other_form(dialog,ui):seen.update(self.observe(dialog,ui));dialog.reject()
            with self.forms(first,other_form) as opened:
                self.assertFalse(w._complete_opentag_settings())
                self.assertTrue(w._select_result(other))   # chosen before Qt runs the deferred opening
                for _ in range(3):w.app.processEvents()
                self.assertEqual(len(opened),1);self.assertEqual(w.current_sku,other)
                self.busy['on']=False;self.assertFalse(w._complete_opentag_settings())   # the other label, opened by the user
        self.assertEqual(seen['sku'],other);self.assertFalse(seen['banner']);self.assertIsNone(seen['refusal'])
        self.assertNotEqual(seen['fields']['weight'],'750');self.assertNotEqual(seen['fields']['min_bed_temp'],'4x')
        self.assertEqual(core.opentag_settings(other),before_other);self.assertIsNone(w._draft);self.assertEqual(self.copies(),{})
        self.assert_source_intact()


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagClarityTests(unittest.TestCase):
    """B18: each problem said once, above its control; composite materials split only on request."""
    V=OpenTagValidationTests
    setUpClass=classmethod(lambda cls:fixture.GuiTests.setUpClass())
    setUp=V.setUp;source=V.source;ui=V.ui;form=V.form;export=V.export

    def capture(self,ui):
        """State of the human capture: catalogue PET-GF with no variant, mass and chamber left empty."""
        for key in ('weight','chamber_temp'):ui.edit(key).setText('')

    def visible_texts(self,dialog):
        from PySide6.QtWidgets import QLabel,QAbstractButton
        return [w.text() for w in dialog.findChildren(QLabel)+dialog.findChildren(QAbstractButton) if w.isVisible() and w.text()]

    def flagged(self,ui):
        return sorted(k for k in ('manufacturer','material','material_mod','color_name','sku','weight','print_temp','min_print_temp',
                                  'max_print_temp','bed_temp','min_bed_temp','max_bed_temp','chamber_temp') if ui.edit(k).property('opentagProblem'))

    def test_capture_case_says_each_problem_once_above_its_control_and_clears_progressively(self):
        from PySide6.QtWidgets import QPushButton
        self.source(type='PET-GF',subtype=None);w=self.window;seen={}
        def check(dialog,ui):
            self.capture(ui);w.app.processEvents()
            self.assertEqual(ui.keys(),['chamber_temp','weight','material'])
            expected={'weight':'Masse du filament à préciser, hors bobine vide.',
                      'chamber_temp':'Température de l’enceinte à préciser, ou sans chauffage.'}
            for key,text in expected.items():
                hint=ui.hint(key);self.assertTrue(hint.isVisible(),key);self.assertEqual(hint.text(),text)
                above=hint.mapTo(dialog,hint.rect().bottomLeft()).y();control=ui.edit(key).mapTo(dialog,ui.edit(key).rect().topLeft()).y()
                self.assertLessEqual(above,control,key)   # the message sits right above its control
            # A2: the material's proposal replaces its message (one compact row above it, both fields red).
            self.assertTrue(ui.hint('material').isHidden());self.assertTrue(ui.split().isVisible())
            self.assertLess(ui.split().mapTo(dialog,ui.split().rect().bottomLeft()).y(),ui.edit('material').mapTo(dialog,ui.edit('material').rect().topLeft()).y()+1)
            texts=self.visible_texts(dialog)
            self.assertFalse(any('octets' in t or 'UTF-8' in t for t in texts))   # no byte count in the main reading
            self.assertFalse(any(t in ('Corriger','Champs à corriger','Aller au premier') for t in texts));self.assertEqual(ui.rows(),[])
            self.assertEqual(self.flagged(ui),['chamber_temp','material','weight'])
            self.assertEqual(ui.label('opentag_summary').text(),'3 points à vérifier');self.assertFalse(ui.label('opentag_ready').isVisible())
            self.assertIn('catalogue synchronisé',ui.edit('material').toolTip())   # provenance on demand
            ui.edit('print_temp').setText('245');ui.confirm()
            ui.edit('weight').setText('1000');self.assertFalse(ui.confirmed())   # any change revokes the confirmation
            self.assertEqual((ui.keys(),ui.label('opentag_summary').text()),(['chamber_temp','material'],'2 points à vérifier'))
            self.assertTrue(ui.hint('weight').isHidden());self.assertFalse(ui.edit('weight').property('opentagProblem'))
            next(b for b in dialog.findChildren(QPushButton) if b.text()=='sans chauffage').click()
            self.assertEqual((ui.keys(),ui.label('opentag_summary').text()),(['material'],'1 point à vérifier'))
            seen['material']=ui.edit('material').text();dialog.reject()
        self.assertFalse(self.form(check));self.assertEqual(seen['material'],'PET-GF')
        self.assertEqual(core.opentag_settings(w.current_sku),{})

    def test_material_split_is_proposed_applied_on_request_and_exported_as_two_fields(self):
        from PySide6.QtWidgets import QPushButton
        w=self.window;seen={}
        split=lambda dialog:next(b for b in dialog.findChildren(QPushButton) if b.property('opentag_role')=='split')
        self.source(type='PETG-CF',subtype=None)   # first, while no label setting is saved for this reference
        def petg(dialog,ui):
            self.assertEqual(ui.label('opentag_material_split_text').text(),'Matière : PETG · Variante : CF')
            self.assertEqual(split(dialog).text(),'Appliquer PETG + CF')
            split(dialog).click();seen['petg']=(ui.edit('material').text(),ui.edit('material_mod').text());dialog.reject()
        self.assertFalse(self.form(petg));self.assertEqual(seen['petg'],('PETG','CF'));self.assertEqual(core.opentag_settings(w.current_sku),{})
        self.source(type='PET-GF',subtype=None)
        def apply(dialog,ui):
            ui.fill(self.valid);self.assertEqual(ui.keys(),['material'])
            self.assertEqual(ui.label('opentag_material_split_text').text(),'Matière : PET · Variante : GF')
            self.assertEqual(split(dialog).text(),'Appliquer PET + GF');self.assertEqual(split(dialog).objectName(),'opentagSolution')   # green
            self.assertEqual((ui.edit('material').text(),ui.edit('material_mod').text()),('PET-GF',''))   # untouched until asked
            ui.confirm();self.assertFalse(ui.save().isEnabled())
            split(dialog).click()
            self.assertEqual((ui.edit('material').text(),ui.edit('material_mod').text()),('PET','GF'))
            self.assertFalse(ui.confirmed());self.assertFalse(ui.save().isEnabled());self.assertEqual(ui.keys(),[])
            self.assertFalse(ui.split().isVisible());self.assertTrue(ui.label('opentag_ready').isVisible())
            self.assertIn('valeur d’origine : « PET-GF »',ui.edit('material').toolTip())   # the source value stays readable
            ui.confirm();self.assertTrue(ui.save().isEnabled());ui.save().click()
        self.assertTrue(self.form(apply))
        self.assertEqual((self.product['type'],self.product.get('subtype')),('PET-GF',None))   # catalogue unchanged
        payload,decoded=self.export()
        self.assertEqual((decoded['material'],decoded['material_mod']),('PET','GF'))
        self.assertEqual((payload[0x02:0x07],payload[0x07:0x0c]),(b'PET\0\0',b'GF\0\0\0'))

    def test_without_a_safe_split_values_are_kept_and_manual_edit_is_guided(self):
        seen={}
        for material,variant in [('PETG-CF','Recyc'),('PC-ABS',None),('PÉT-GF',None),('PETG12-CF',None)]:
            with self.subTest(material=material,variant=variant):
                self.source(type=material,subtype=variant)
                def check(dialog,ui):
                    seen.update(split=ui.split().isVisible(),values=(ui.edit('material').text(),ui.edit('material_mod').text()),
                                hint=ui.hint('material').text() if ui.hint('material').isVisible() else '');dialog.reject()
                self.assertFalse(self.form(check))
                self.assertFalse(seen['split']);self.assertEqual(seen['values'],(material,variant or ''))   # never shortened or replaced
                self.assertEqual(seen['hint'],'Nom trop long pour l’étiquette. Utilisez une abréviation.')   # guided, nothing guessed

    def test_record_values_stay_in_their_own_group_with_the_editor(self):
        from PySide6.QtWidgets import QPushButton,QLabel
        self.source(diameter=1.7505);w=self.window
        def check(dialog,ui):
            ui.fill(self.valid);self.assertEqual(ui.keys(),['diameter'])
            title=next(l for l in dialog.findChildren(QLabel) if l.text()=='Données de la fiche');self.assertTrue(title.isVisible())
            row=ui.rows()[0];self.assertEqual(row.property('opentag_key'),'diameter');self.assertIn('1.7505',ui.row_text('diameter'))
            button=row.findChild(QPushButton);self.assertEqual(button.text(),'Modifier la fiche…')
            self.assertEqual(self.flagged(ui),[]);self.assertIsNone(ui.hint('diameter'))   # no hidden field message for it
            self.assertEqual(ui.label('opentag_summary').text(),'1 point à vérifier');dialog.reject()
        self.assertFalse(self.form(check))
        def ready(dialog,ui):
            ui.fill(self.valid);seen=next((l for l in dialog.findChildren(QLabel) if l.text()=='Données de la fiche'),None)
            self.assertFalse(seen.isVisible());self.assertFalse(ui.label('opentag_summary').isVisible());dialog.reject()
        self.source(diameter=1.75);self.assertFalse(self.form(ready))

    def test_no_byte_counter_in_the_reading_limit_on_demand_and_an_idle_form_does_no_work(self):
        from PySide6.QtCore import QEvent,QObject
        from PySide6.QtTest import QTest
        self.source();w=self.window;seen={}
        from PySide6.QtWidgets import QToolButton
        class Count(QObject):
            """Relayouts anywhere, and any timer/paint/layout event addressed to the form itself."""
            def __init__(c,dialog):super().__init__();c.dialog=dialog;c.n=[]
            def eventFilter(c,obj,event):
                mine=obj is c.dialog or (hasattr(obj,'window') and callable(obj.window) and obj.window() is c.dialog)
                if event.type()==QEvent.LayoutRequest or mine and event.type() in (QEvent.Timer,QEvent.Paint,QEvent.UpdateRequest):
                    c.n.append((event.type().name,type(obj).__name__,obj.objectName()))
                return False
        def check(dialog,ui):
            dialog.activateWindow();ui.fill(self.valid);QTest.qWait(50)
            ui.edit('manufacturer').setFocus();QTest.qWait(20)   # A2: no counter appears while typing either
            seen['texts']=[t for t in self.visible_texts(dialog) if 'octets' in t or 'UTF-8' in t]
            seen['tip']=ui.edit('manufacturer').toolTip();seen['counter']=ui.label('opentag_manufacturer_bytes')
            # Idle with focus on a button (a text field's caret blink is Qt's own): no work in the form.
            dialog.findChild(QToolButton,'opentag_confirmed').setFocus();QTest.qWait(80)
            count=Count(dialog);w.app.installEventFilter(count)
            try:QTest.qWait(300)   # idle: no input
            finally:w.app.removeEventFilter(count)
            seen['idle']=count.n;dialog.reject()
        self.assertFalse(self.form(check))
        self.assertEqual((seen['texts'],seen['counter']),([],None))
        self.assertIn('Limite de l’étiquette : 16 octets UTF-8 (9 utilisés).',seen['tip'])
        self.assertEqual(seen['idle'],[])


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagSplitDestinationTests(unittest.TestCase):
    """B18/A1: a proposed split names both destinations and marks both fields, for every safe pair."""
    V=OpenTagValidationTests
    setUpClass=classmethod(lambda cls:fixture.GuiTests.setUpClass())
    setUp=V.setUp;source=V.source;ui=V.ui;form=V.form;export=V.export
    PAIRS=[('PET-GF','PET','GF'),('PETG-CF','PETG','CF'),('PA6-CF','PA6','CF'),('PLA-GF','PLA','GF'),
           ('ABS-CF','ABS','CF'),('PETG-GF','PETG','GF'),('PA-CF','PA','CF')]

    def state(self,ui):
        hint=ui.hint('material_mod')
        return dict(text=ui.label('opentag_material_split_text').text() if ui.split().isVisible() else None,
                    button=ui.solution('split').text() if ui.split().isVisible() else None,
                    marked=(ui.edit('material').property('opentagSplit') is True,ui.edit('material_mod').property('opentagSplit') is True),
                    note=hint.text() if hint.isVisible() else None,values=(ui.edit('material').text(),ui.edit('material_mod').text()),
                    keys=ui.keys(),summary=ui.label('opentag_summary').isVisible(),confirmed=ui.confirmed(),save=ui.save().isEnabled())

    def split_button(self,dialog):
        from PySide6.QtWidgets import QPushButton
        return next(b for b in dialog.findChildren(QPushButton) if b.property('opentag_role')=='split')

    def test_every_safe_pair_names_both_destinations_marks_both_fields_and_exports_them(self):
        config=Path(core.CONFIG_PATH).read_bytes()
        for source,base,mod in self.PAIRS:
            with self.subTest(source=source):
                Path(core.CONFIG_PATH).write_bytes(config);self.source(type=source,subtype=None);seen={}
                def act(dialog,ui):
                    ui.fill(self.valid);seen['before']=self.state(ui)
                    ui.confirm();self.split_button(dialog).click();seen['after']=self.state(ui)
                    ui.confirm();seen['saved']=ui.save().isEnabled();ui.save().click()
                self.assertTrue(self.form(act));before,after=seen['before'],seen['after']
                self.assertEqual((before['text'],before['button']),(f'Matière : {base} · Variante : {mod}',f'Appliquer {base} + {mod}'))
                self.assertEqual((before['marked'],before['note'],before['values']),((True,True),None,(source,'')))   # A2: no second note
                fits=len(source.encode())<=5   # PA-CF: representable as is, the proposal adds no error
                self.assertEqual(before['keys'],[] if fits else ['material']);self.assertEqual(before['summary'],not fits)
                self.assertEqual((after['text'],after['marked'],after['note'],after['values']),(None,(False,False),None,(base,mod)))
                self.assertEqual((after['keys'],after['confirmed'],after['save'],seen['saved']),([],False,False,True))
                self.assertEqual((self.product['type'],self.product.get('subtype')),(source,None))   # catalogue unchanged
                decoded=self.export()[1];self.assertEqual((decoded['material'],decoded['material_mod']),(base,mod))

    def test_a_short_representable_name_saves_without_applying_the_proposal(self):
        self.source(type='PA-CF',subtype=None);seen={}
        def act(dialog,ui):
            ui.fill(self.valid);ui.confirm();seen.update(self.state(ui));ui.save().click()   # no obligation to split
        self.assertTrue(self.form(act));self.assertEqual((seen['keys'],seen['save'],seen['marked']),([],True,(True,True)))
        decoded=self.export()[1];self.assertEqual((decoded['material'],decoded['material_mod']),('PA-CF',''))

    def test_typed_variant_removes_the_proposal_and_is_never_overwritten(self):
        self.source(type='PET-GF',subtype=None);seen={}
        def act(dialog,ui):
            ui.fill(self.valid);ui.edit('material_mod').setText('Recyc');seen['typed']=self.state(ui)
            ui.edit('material_mod').setText('');seen['cleared']=self.state(ui)
            ui.edit('material').setText('PET');seen['manual']=self.state(ui)   # proposal gone after a manual edit
            ui.edit('material').setText('PETG-CF');seen['other']=self.state(ui);dialog.reject()
        self.assertFalse(self.form(act))
        typed=seen['typed']
        self.assertEqual((typed['text'],typed['marked'],typed['note'],typed['values']),(None,(False,False),None,('PET-GF','Recyc')))
        self.assertEqual(typed['keys'],['material'])   # the real error stays, with its own message
        self.assertEqual((seen['cleared']['marked'],seen['cleared']['text']),((True,True),'Matière : PET · Variante : GF'))
        self.assertEqual((seen['manual']['text'],seen['manual']['marked'],seen['manual']['keys']),(None,(False,False),[]))
        self.assertEqual((seen['other']['text'],seen['other']['button'],seen['other']['marked']),('Matière : PETG · Variante : CF','Appliquer PETG + CF',(True,True)))

    def test_a_really_invalid_variant_keeps_its_error_and_gets_no_split_proposal(self):
        self.source(type='PETG-CF',subtype='Recycled Carbon');seen={}
        def act(dialog,ui):
            ui.fill(self.valid);seen.update(self.state(ui));seen['problem']=ui.edit('material_mod').property('opentagProblem')
            seen['hint']=ui.hint('material_mod').text();seen['short']=ui.solution('abbreviate').isVisible();dialog.reject()
        self.assertFalse(self.form(act))
        self.assertEqual((seen['text'],seen['marked'],seen['values']),(None,(False,False),('PETG-CF','Recycled Carbon')))
        self.assertEqual((seen['keys'],seen['problem'],seen['short']),(['material','material_mod'],True,False))   # unknown name: nothing guessed
        self.assertEqual(seen['hint'],'Nom trop long pour l’étiquette. Utilisez une abréviation.')


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class OpenTagA2FormTests(unittest.TestCase):
    """B18/A2: fewer lines, visible solutions, the usual spool's mass proposed, never confirmed for the user."""
    V=OpenTagValidationTests
    setUpClass=classmethod(lambda cls:fixture.GuiTests.setUpClass())
    setUp=V.setUp;source=V.source;ui=V.ui;form=V.form;export=V.export

    def top(self,dialog,widget):return widget.mapTo(dialog,widget.rect().topLeft())

    def prefer(self,grams):
        """« Ma bobine habituelle » in the isolated configuration; None removes the key."""
        raw=json.loads(Path(core.CONFIG_PATH).read_text(encoding='utf-8'))
        if grams is None:raw.pop('preferred_weight_g',None)
        else:raw['preferred_weight_g']=grams
        Path(core.CONFIG_PATH).write_text(json.dumps(raw),encoding='utf-8')

    def test_count_sits_by_save_and_chamber_field_and_action_share_the_row(self):
        from PySide6.QtWidgets import QPushButton,QScrollArea
        self.source();seen={}
        def check(dialog,ui):
            dialog.resize(860,600);self.window.app.processEvents()
            body=dialog.findChild(QScrollArea).widget();summary=ui.label('opentag_summary');save=ui.save()
            self.assertFalse(body.isAncestorOf(summary))   # in the footer, not in the scrolled form
            self.assertLessEqual(abs(self.top(dialog,summary).y()+summary.height()/2-self.top(dialog,save).y()-save.height()/2),6)
            self.assertLess(self.top(dialog,summary).x(),self.top(dialog,save).x())
            self.assertFalse(any(b.text()=='Aller au premier' for b in dialog.findChildren(QPushButton)))
            chamber=ui.edit('chamber_temp');unheated=next(b for b in dialog.findChildren(QPushButton) if b.text()=='sans chauffage')
            self.assertEqual(chamber.text(),'')   # empty never becomes 0 by itself
            self.assertEqual(self.top(dialog,unheated).y(),self.top(dialog,chamber).y())
            self.assertGreater(self.top(dialog,unheated).x(),self.top(dialog,chamber).x()+chamber.width()-1)
            hint=ui.hint('chamber_temp');self.assertEqual(hint.text(),'Température de l’enceinte à préciser, ou sans chauffage.')
            self.assertGreater(hint.width(),chamber.width()*2)   # the message uses the row, not one narrow column
            unheated.click();self.assertEqual((chamber.text(),'chamber_temp' in ui.keys()),('0',False))
            ui.fill(self.valid);seen['ready']=(ui.label('opentag_ready').isVisible(),ui.label('opentag_ready').text(),summary.isVisible());dialog.reject()
        self.assertFalse(self.form(check));self.assertEqual(seen['ready'],(True,'Aucun point à vérifier',False))

    def test_footer_actions_share_one_width_through_toggle_and_validation(self):
        """B18/C21: Annuler, the confirmation (sized for both of its texts, radius 5) and Enregistrer
        keep one width while confirming, typing and at 860×600; « sans chauffage » stays in its column."""
        from PySide6.QtCore import QPoint,QEvent,QObject
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QPushButton,QToolButton
        from spoolscribe.ui_widgets import BUTTON_RADIUS
        self.source();seen={}
        self.assertIn(f'QToolButton#opentag_confirmed {{ border-radius:{BUTTON_RADIUS}px; }}',self.window.styleSheet())
        def check(dialog,ui):
            app=self.window.app;confirmed=dialog.findChild(QToolButton,'opentag_confirmed')
            cancel=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Annuler');footer=[cancel,confirmed,ui.save()]
            def state():
                self.assertEqual({b.height() for b in footer},{32})
                for b in footer:
                    at=b.mapTo(dialog,QPoint(0,0));self.assertTrue(dialog.rect().contains(at+QPoint(b.width()-1,b.height()-1)),b.text())
                return [b.width() for b in footer]
            class Count(QObject):
                def __init__(c):super().__init__();c.n=0
                def eventFilter(c,obj,event):
                    if event.type()==QEvent.LayoutRequest:c.n+=1
                    return False
            seen['initial']=state();texts=[]
            for checked in (True,False,True):
                confirmed.setChecked(checked);app.processEvents();texts.append(confirmed.text());seen.setdefault('toggled',[]).append(state())
            self.assertGreaterEqual(footer[0].width(),max(b.sizeHint().width() for b in footer))
            ui.fill(self.valid);app.processEvents();ui.confirm();app.processEvents();seen['validated']=state()
            dialog.resize(860,600);app.processEvents();seen['small']=state();QTest.qWait(150)   # settle, then watch
            count=Count();app.installEventFilter(count)
            try:QTest.qWait(300)
            finally:app.removeEventFilter(count)
            seen['settled']=count.n
            unheated=next(b for b in dialog.findChildren(QPushButton) if b.text()=='sans chauffage')
            seen['unheated']=unheated.width()!=footer[0].width() or unheated.minimumWidth()!=unheated.maximumWidth()
            seen['texts']=texts;dialog.reject()
        self.assertFalse(self.form(check))
        widths={tuple(seen['initial'])}|{tuple(w) for w in seen['toggled']}|{tuple(seen['validated']),tuple(seen['small'])}
        self.assertEqual(len(widths),1,widths);self.assertEqual(len(set(next(iter(widths)))),1,widths)
        self.assertEqual(seen['texts'],['Températures vérifiées','Valider les températures','Températures vérifiées'])
        self.assertEqual(seen['settled'],0)   # no relayout loop once validated and settled
        self.assertTrue(seen['unheated'])     # column-sized, not forced into the footer group

    def test_match_widths_is_measured_idempotent_and_covers_every_text(self):
        from PySide6.QtWidgets import QPushButton,QToolButton,QWidget,QHBoxLayout
        from spoolscribe.ui_widgets import match_widths
        host=QWidget(self.window);row=QHBoxLayout(host);short=QPushButton('OK');long=QToolButton();long.setText('Un');row.addWidget(short);row.addWidget(long)
        width=match_widths([short,long],{long:('Un','Un texte nettement plus long')})
        self.assertEqual((short.width(),long.width(),long.text()),(width,width,'Un'))
        long.setText('Un texte nettement plus long');self.assertLessEqual(long.sizeHint().width(),width)
        long.setText('Un');self.assertEqual(match_widths([short,long],{long:('Un','Un texte nettement plus long')}),width)
        self.assertEqual(match_widths([]),0)

    def test_unheated_button_is_lowercase_explicit_and_exports_zero_only_after_saving(self):
        """B18/A3 F2: exactly « sans chauffage »; the click writes 0, revokes the confirmation, keeps the rest."""
        from PySide6.QtWidgets import QPushButton
        self.source();seen={}
        typed=dict(print_temp='245',bed_temp='60',weight='1000')
        def act(dialog,ui):
            buttons=[b for b in dialog.findChildren(QPushButton) if b.text().casefold()=='sans chauffage']
            seen['labels']=[b.text() for b in buttons]
            ui.fill(typed);ui.confirm();self.assertTrue(ui.confirmed())
            others={k:ui.edit(k).text() for k in ('print_temp','bed_temp','weight','material','min_bed_temp','max_bed_temp')}
            buttons[0].click();self.window.app.processEvents()
            seen['after']=(ui.edit('chamber_temp').text(),ui.confirmed(),'chamber_temp' in ui.keys())
            seen['others']=others=={k:ui.edit(k).text() for k in others}
            seen['written']=sorted(p.name for p in Path(core.OUTPUT_DIR).glob('*')) if Path(core.OUTPUT_DIR).exists() else []
            ui.confirm();ui.save().click()
        self.assertTrue(self.form(act))
        self.assertEqual(seen['labels'],['sans chauffage'])                 # one button, exact lowercase label
        self.assertEqual(seen['after'],('0',False,False))                   # 0, confirmation revoked, problem gone
        self.assertTrue(seen['others']);self.assertEqual(seen['written'],[])   # other fields kept, nothing exported
        self.assertEqual(core.opentag_settings(self.window.current_sku)['chamber_temp'],0)
        self.assertEqual(self.export()[1]['chamber_temp'],0)
        translations={code:(i18n.set_language(code),i18n.tr('sans chauffage'))[1] for code in ('en','es','zh_CN','fr')}
        self.assertEqual(translations,{'en':'No heating','es':'Sin calefacción','zh_CN':'不加热','fr':'sans chauffage'})

    def test_carbon_fiber_is_abbreviated_only_on_request_and_exported(self):
        for subtype,short in [('Carbon Fiber','CF'),('Glass Fibre','GF')]:
            with self.subTest(subtype=subtype):
                config=Path(core.CONFIG_PATH).read_bytes();self.source(type='ASA',subtype=subtype);seen={}
                def act(dialog,ui):
                    ui.fill(self.valid);seen['hint']=ui.hint('material_mod').text();button=ui.solution('abbreviate')
                    seen['before']=(ui.label('opentag_variant_short_text').text(),button.text(),button.isVisible(),ui.edit('material_mod').text())
                    ui.confirm();button.click()
                    seen['after']=(ui.edit('material_mod').text(),ui.confirmed(),ui.keys(),button.isVisible())
                    ui.confirm();ui.save().click()
                self.assertTrue(self.form(act))
                self.assertEqual(seen['hint'],'Nom trop long pour l’étiquette. Utilisez une abréviation.')
                self.assertEqual(seen['before'],(f'{subtype} → {short}',f'Utiliser {short}',True,subtype))   # nothing changed before the click
                self.assertEqual(seen['after'],(short,False,[],False))
                self.assertEqual(self.product['subtype'],subtype)   # catalogue unchanged
                self.assertEqual(self.export()[1]['material_mod'],short);Path(core.CONFIG_PATH).write_bytes(config)

    def test_usual_spool_mass_is_proposed_visibly_and_saved_only_with_the_label(self):
        self.prefer(750);self.source();seen={}
        def act(dialog,ui):
            note=ui.label('opentag_weight_note')
            seen['proposed']=(ui.edit('weight').text(),note.isVisible(),note.text(),'weight' in ui.keys())
            seen['tip']=ui.edit('weight').toolTip()
            ui.fill({k:v for k,v in self.valid.items() if k!='weight'});ui.confirm();ui.save().click()
        self.assertTrue(self.form(act))
        self.assertEqual(seen['proposed'],('750',True,'Valeur proposée · bobine habituelle',False))
        self.assertIn('Valeur proposée · bobine habituelle',seen['tip'])
        self.assertEqual(core.opentag_settings(self.window.current_sku)['weight'],750.0)
        self.assertNotIn('weight',self.entry);decoded=self.export()[1];self.assertEqual(decoded['weight'],750.0)   # filament only, no tare

    def test_mass_proposal_never_hides_or_overwrites_a_value(self):
        cases=[('cle absente',None,{},('1000','Valeur proposée · 1 kg par défaut')),
               ('selon la fiche',0,{},('',None)),
               ('masse connue',750,{'weight':500},('500',None)),
               ('masse invalide',750,{'weight':-5},('-5',None))]
        for name,preference,entry,expected in cases:
            with self.subTest(name=name):
                config=Path(core.CONFIG_PATH).read_bytes();self.prefer(preference)
                self.entry.pop('weight',None);self.entry.update(entry);self.source();seen={}
                def act(dialog,ui):
                    note=ui.label('opentag_weight_note')
                    seen['state']=(ui.edit('weight').text(),note.text() if note.isVisible() else None);seen['keys']=ui.keys();dialog.reject()
                self.assertFalse(self.form(act));self.assertEqual(seen['state'],expected)
                if name=='masse invalide':self.assertIn('weight',seen['keys'])   # the source error stays visible
                Path(core.CONFIG_PATH).write_bytes(config);self.entry.pop('weight',None)
        self.prefer(750);self.source()
        core.save_opentag_settings(self.window.current_sku,dict(print_temp=245,bed_temp=60,chamber_temp=50,weight=800))
        def saved(dialog,ui):
            seen['saved']=(ui.edit('weight').text(),ui.label('opentag_weight_note').isVisible())
            ui.edit('weight').setText('');seen['cleared']=(ui.edit('weight').text(),ui.label('opentag_weight_note').isVisible());dialog.reject()
        seen={};self.assertFalse(self.form(saved))
        self.assertEqual((seen['saved'],seen['cleared']),(('800',False),('',False)))   # saved setting wins; emptied stays empty

    def test_an_edited_proposal_is_the_users_value(self):
        self.prefer(750);self.source();seen={}
        def act(dialog,ui):
            ui.edit('weight').setText('900');note=ui.label('opentag_weight_note')
            seen['state']=(note.isVisible(),ui.edit('weight').toolTip());dialog.reject()
        self.assertFalse(self.form(act));self.assertFalse(seen['state'][0]);self.assertIn('saisie dans ce formulaire',seen['state'][1])
        self.assertEqual(core.opentag_settings(self.window.current_sku),{})   # nothing saved on cancel
