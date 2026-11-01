"""Offline, independently specified OpenTag3D 2.004/NDEF interoperability vectors."""
import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.support import entry, product, ROOT
from spoolscribe import core, opentag3d, printer_profiles


def values():
    return dict(material='PLA', manufacturer='Polymaker', color_1='FF0000FF',
                diameter=1.75, density=1.24, print_temp=210, min_print_temp=190,
                max_print_temp=230, bed_temp=60, chamber_temp=0, weight=1000)


class OpenTagCodecTests(unittest.TestCase):
    def test_independent_memory_map_and_units(self):
        b=opentag3d.encode(values())
        self.assertEqual(len(b),224)
        self.assertEqual(b[:7],bytes.fromhex('07D4504C410000'))
        self.assertEqual(b[0x0c:0x1c],b'Polymaker'+b'\0'*7)
        self.assertEqual(b[0x3c:0x4c],bytes.fromhex('FF0000FF')+b'\0'*12)
        self.assertEqual(b[0x8c:0x8e],bytes.fromhex('06D6'))
        self.assertEqual(b[0x90:0x95],bytes([42,38,46,0,12]))
        self.assertEqual(b[0x9c:0xa0],bytes.fromhex('04D803E8'))
        self.assertEqual(opentag3d.decode(b)['density'],1.24)

    def test_required_unknowns_bad_numbers_and_unrepresentable_values_fail(self):
        for key in ['material','manufacturer','color_1','diameter','density','print_temp','bed_temp','chamber_temp','weight']:
            v=values();v.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):opentag3d.encode(v)
        for key,bad in [('print_temp',211),('weight',True),('density',float('nan')),
                        ('weight',-1),('diameter',1.7505),('print_temp',1300),('weight',65536),
                        ('chamber_temp',-5),('material','PLA-CF'),('manufacturer','é'*9),
                        ('material','A\0B'),('color_1','FF0000')]:
            v=values();v[key]=bad
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):opentag3d.encode(v)

    def test_explicit_transparency_and_four_colours(self):
        v=values();v.update(color_1='12345600',color_2='ABCDEF80',color_3='000000FF',color_4='FFFFFF00')
        b=opentag3d.encode(v)
        self.assertEqual(b[0x3c:0x4c],bytes.fromhex('12345600ABCDEF80000000FFFFFFFF00'))
        self.assertEqual(opentag3d.decode(b)['color_4'],'FFFFFF00')
        with self.assertRaises(ValueError):opentag3d.encode(dict(v,color_5='FF0000FF'))

    def test_target_must_be_in_source_bounds(self):
        with self.assertRaises(ValueError):opentag3d.encode(dict(values(),print_temp=250))
        with self.assertRaises(ValueError):opentag3d.encode(dict(values(),min_print_temp=240))

    def test_mime_record_and_capacity_are_binary_not_json(self):
        b=opentag3d.encode(values());n=opentag3d.ndef(b)
        self.assertEqual(n[:3],bytes([0xD2,len(b'application/opentag3d'),224]))
        self.assertEqual(n[3:24],b'application/opentag3d')
        self.assertEqual(n[24:],b)
        for tag in ['NTAG215','NTAG216']:
            budget=opentag3d.budget(b,tag,0)
            self.assertEqual(budget['occupied'],251)
            self.assertGreater(budget['remaining'],0)
        with self.assertRaises(ValueError):opentag3d.budget(b,'NTAG213',0)
        with self.assertRaises(ValueError):opentag3d.budget(b,'NTAG215',246)
        self.assertEqual(opentag3d.budget(b,'NTAG215',245)['remaining'],0)

    def test_writer_containers_preserve_exact_payload(self):
        b=opentag3d.encode(values())
        desktop=json.loads(opentag3d.export(b,'nfctools-desktop'))
        r=desktop['data'][0]['kRecordObject']
        self.assertEqual(r['kTnf'],2);self.assertEqual(bytes(r['kType']),b'application/opentag3d')
        self.assertEqual(bytes(r['kPayload']),b)
        mobile=json.loads(opentag3d.export(b,'nfctools-mobile'))
        fields=json.loads(base64.b64decode(mobile['profiles'][0]['data']))
        msg=json.loads(base64.b64decode(next(f['NDEFMessage'] for f in fields if 'NDEFMessage'in f)))
        rec=json.loads(base64.b64decode(msg[0]['NDEFRecord']))
        self.assertEqual(base64.b64decode(rec['payload']),b)
        self.assertEqual(base64.b64decode(rec['type']),b'application/opentag3d')
        self.assertEqual(base64.b64decode(rec['format']),b'\x02')
        self.assertEqual(opentag3d.export(b,'ndef'),opentag3d.ndef(b))

    def test_core_requires_explicit_targets_and_preserves_catalogue(self):
        e=dict(entry(),weight=1000);p=product();before=copy.deepcopy((e,p))
        f=core.opentag_fields(e,p)
        self.assertNotIn('print_temp',f);self.assertNotIn('chamber_temp',f)
        with self.assertRaises(core.ExportValidationError):core.prepare_opentag3d('LOCAL',e,p)
        out=core.prepare_opentag3d('LOCAL',e,p,settings={'print_temp':210,'bed_temp':60,'chamber_temp':0})
        self.assertIn('opentag3d',out.filename);self.assertEqual(opentag3d.decode(out.payload)['print_temp'],210)
        self.assertEqual((e,p),before)

    def test_internal_ids_not_fabricated_as_manufacturer_skus(self):
        f=core.opentag_fields(dict(entry(),sku='OFD-a-long-uuid',weight=1000),product())
        self.assertNotIn('sku',f)
        f=core.opentag_fields(dict(entry(),manufacturer_sku='AB123',weight=1000),product())
        self.assertEqual(f['sku'],'AB123')

    def test_existing_reader_settings_do_not_gain_unsupported_formats(self):
        self.assertEqual(printer_profiles.formats('u1','paxx12'),('openspool',))
        self.assertEqual(printer_profiles.formats('u1','stock'),())
        self.assertEqual(printer_profiles.formats('bambu','stock'),())
        self.assertEqual(printer_profiles.formats('u1','paxx12_openrfid'),('openspool','opentag3d'))
        self.assertEqual(printer_profiles.formats('opentag3d','any'),('opentag3d',))

    def test_optional_ranges_may_be_unknown_without_fabricating_them(self):
        p=product()
        for key in ['min_temp','max_temp','bed_min_temp','bed_max_temp']:p[key]=None
        out=core.prepare_opentag3d('LOCAL',dict(entry(),weight=1000),p,
            settings={'print_temp':210,'bed_temp':60,'chamber_temp':0})
        self.assertNotIn('min_print_temp',json.loads(out.preview)['fields'])
        self.assertEqual(out.payload[0x91:0x93],b'\0\0')

    def test_settings_roundtrip_and_invalid_import_keeps_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(core,'CONFIG_PATH',str(Path(temp)/'config.json')):
            core.save_opentag_settings('LOCAL',{'print_temp':210,'bed_temp':60,'chamber_temp':0})
            cfg=core.load_config();cfg.update(nfc_format='opentag3d',opentag3d_output='nfctools-desktop');core.save_config(cfg)
            path=Path(temp)/'settings.json';core.export_settings(path)
            core.import_settings(path)
            self.assertEqual(core.opentag_settings('LOCAL')['print_temp'],210)
            self.assertEqual(core.load_config()['nfc_format'],'opentag3d')
            doc=json.loads(path.read_text());doc['settings']['opentag3d_settings']['LOCAL']['print_temp']=211
            path.write_text(json.dumps(doc));before=Path(core.CONFIG_PATH).read_bytes()
            with self.assertRaises(ValueError):core.import_settings(path)
            self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)

    def test_failed_export_does_not_open_a_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                out=core.prepare_opentag3d('LOCAL',entry(),product())
                core.write_opentag3d(out,temp)
            self.assertEqual(list(Path(temp).iterdir()),[])


from tests import test_gui as gui_fixture

@unittest.skipUnless(gui_fixture.HAS_QT,'PySide6 unavailable')
class OpenTagGuiTests(unittest.TestCase):
    setUpClass=classmethod(gui_fixture.GuiTests.setUpClass.__func__)
    def setUp(self):
        gui_fixture.GuiTests.setUp(self)
        self.window._show_detail('PB05001')

    def select_reader(self):
        w=self.window;w.printer.setCurrentIndex(w.printer.findData('opentag3d'))
        self.assertEqual(w.nfc_format.currentData(),'opentag3d')
        return w

    def test_automatic_choices_do_not_enable_bambu_or_stock_u1(self):
        w=self.select_reader();self.assertTrue(w.btn_generate.isEnabled())
        self.assertFalse(w.btn_opentag_settings.isHidden())
        w.printer.setCurrentIndex(w.printer.findData('bambu'))
        self.assertFalse(w.btn_generate.isEnabled());self.assertEqual(w.nfc_format.count(),0)
        w.printer.setCurrentIndex(w.printer.findData('u1'))
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12'))
        self.assertEqual([w.nfc_format.itemData(i) for i in range(w.nfc_format.count())],['openspool'])
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12_openrfid'))
        self.assertEqual(w.nfc_format.count(),2)
        w.firmware.setCurrentIndex(w.firmware.findData('stock'));self.assertFalse(w.btn_generate.isEnabled())

    def fill_dialog(self,dialog):
        from PySide6.QtWidgets import QLineEdit,QDialogButtonBox
        p=core.get_sku_view(self.window.db,'PB05001').product_data
        chosen={'print_temp':p['min_temp'],'bed_temp':p['bed_min_temp'],'chamber_temp':0,'weight':1000}
        for key,value in chosen.items():dialog.findChild(QLineEdit,'opentag_'+key).setText(str(value))
        box=dialog.findChild(QDialogButtonBox)
        next(b for b in box.buttons() if b.text()=='Enregistrer').click()
        return dialog.result()

    def test_real_dialog_validation_then_writer_export_preserves_source_db(self):
        w=self.select_reader();before=Path(core.DB_PATH).read_bytes()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=lambda dialog:self.fill_dialog(dialog)),patch('spoolscribe.app_gui.QMessageBox.information'):
            w._generate()
        files=list(Path(core.OUTPUT_DIR).glob('*opentag3d*.json'));self.assertEqual(len(files),1)
        self.assertEqual(json.loads(files[0].read_text())['type'],'nfc-tools-profiles')
        self.assertEqual(Path(core.DB_PATH).read_bytes(),before)
        w._refresh_inspector();self.assertEqual(w.inspector.toPlainText(),files[0].read_text())
        w.opentag_output.setCurrentIndex(w.opentag_output.findData('ndef'));w._refresh_inspector()
        self.assertIn('ndef_hex',w.inspector.toPlainText())
        self.assertEqual(core.opentag_settings('PB05001')['chamber_temp'],0)

    def test_cancel_dialog_or_destination_writes_no_export(self):
        w=self.select_reader()
        with patch('spoolscribe.ui_catalogue.QDialog.exec',return_value=0):w._generate()
        self.assertFalse(Path(core.OUTPUT_DIR).exists())
        with patch('spoolscribe.ui_catalogue.QDialog.exec',new=lambda dialog:self.fill_dialog(dialog)),patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',return_value=''):
            w._generate()
        self.assertFalse(Path(core.OUTPUT_DIR).exists())

    def test_reader_switch_persists_effective_format_and_refreshes_inspection(self):
        w=self.window
        p=core.get_sku_view(w.db,'PB05001').product_data
        core.save_opentag_settings('PB05001',dict(print_temp=p['min_temp'],bed_temp=p['bed_min_temp'],chamber_temp=0,weight=1000))
        w.show();w.inspector.show();w.app.processEvents();w._refresh_inspector()
        self.select_reader()
        self.assertEqual(core.load_config()['nfc_format'],'opentag3d')
        self.assertIn('nfc-tools-profiles',w.inspector.toPlainText())
        w.printer.setCurrentIndex(w.printer.findData('u1'))
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12'))
        self.assertEqual(core.load_config()['nfc_format'],'openspool')
        self.assertNotIn('nfc-tools-profiles',w.inspector.toPlainText())

class OpenTagCliTests(unittest.TestCase):
    def run_cli(self,root,extra,typed=''):
        import os,subprocess,sys
        env=dict(os.environ,SPOOLSCRIBE_DATA_HOME=str(root),SPOOLSCRIBE_CONFIG_PATH=str(root/'config.json'),
                 PYTHONPATH=os.pathsep.join([str(ROOT/'src'),str(ROOT)]))
        return subprocess.run([sys.executable,'-B','-m','spoolscribe.convert_profile',*extra],
                              input=typed,text=True,encoding='utf-8',capture_output=True,env=env,cwd=root,timeout=30)

    def test_real_cli_writes_a_writer_profile_without_touching_the_database(self):
        from tests.support import small_db
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();db=root/'data/polymaker_db.json'
            data=small_db();data['_skus']['LOCAL']['weight']=1000;db.write_text(json.dumps(data))
            (root/'config.json').write_text(json.dumps(dict(core.DEFAULT_CONFIG,network_consent=False,update_interval_days=-1)))
            settings=root/'label.json';settings.write_text(json.dumps({'print_temp':210,'bed_temp':60,'chamber_temp':0}))
            before=db.read_bytes()
            result=self.run_cli(root,['--nfc-format','opentag3d','--printer','opentag3d','--firmware','any','--opentag-settings',str(settings)],'LOCAL\ni\no\nq\n')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('ndef_hex',result.stdout)
            files=list((root/'output').glob('*opentag3d*.json'));self.assertEqual(len(files),1,result.stdout)
            self.assertEqual(json.loads(files[0].read_text())['type'],'nfc-tools-profiles')
            self.assertEqual(db.read_bytes(),before)

    def test_incompatible_reader_and_archive_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for extra in [['--printer','bambu','--firmware','stock'],['--export-format','archive']]:
                result=self.run_cli(root,['--nfc-format','opentag3d',*extra])
                self.assertEqual(result.returncode,2)
                self.assertFalse((root/'output').exists())

class OpenTagSettingsUiTests(unittest.TestCase):
    setUpClass=OpenTagGuiTests.__dict__["setUpClass"]
    setUp=OpenTagGuiTests.setUp
    select_reader=OpenTagGuiTests.select_reader
    # Only the additional scenario; inherited interaction cases are covered above.
    def test_import_restores_reader_format_writer_and_label_values(self):
        w=self.select_reader()
        cfg=core.load_config();cfg.update(printer_profile='u1',printer_firmware='paxx12_openrfid',
            nfc_format='opentag3d',opentag3d_output='nfctools-desktop')
        core.save_config(cfg);path=Path(self.tmp.name)/'settings.json';core.export_settings(path)
        w.printer.setCurrentIndex(w.printer.findData('bambu'))
        with patch('spoolscribe.ui_catalogue.QFileDialog.getOpenFileName',return_value=(str(path),'JSON')):w._import_settings()
        self.assertEqual(w.printer.currentData(),'u1');self.assertEqual(w.firmware.currentData(),'paxx12_openrfid')
        self.assertEqual(w.nfc_format.currentData(),'opentag3d');self.assertEqual(w.opentag_output.currentData(),'nfctools-desktop')

class OpenTagBoundaryTests(unittest.TestCase):
    def test_utf8_boundary_is_preserved_not_cut_between_codepoints(self):
        v=dict(values(),manufacturer='é'*8)
        raw=opentag3d.encode(v)
        self.assertEqual(raw[12:28],('é'*8).encode())
        self.assertEqual(opentag3d.decode(raw)['manufacturer'],'é'*8)

    def test_five_source_colours_are_rejected_without_mutating_the_entry(self):
        e=dict(entry(),source_colors=['FF0000','00FF00','0000FF','FFFFFF','000000'])
        before=copy.deepcopy(e)
        with self.assertRaises(core.ExportValidationError):core.opentag_fields(e,product())
        self.assertEqual(e,before)

    def test_catalogue_cannot_advertise_conflicting_or_unknown_formats(self):
        doc=json.loads((ROOT/'data/printers.json').read_text())
        for formats in [['opentag3d'],['openspool','unknown'],['openspool','openspool']]:
            bad=copy.deepcopy(doc);bad['printers'][0]['firmwares'][0]['formats']=formats
            with self.assertRaises(ValueError):printer_profiles.validate_catalogue(bad)
