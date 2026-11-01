import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import core
from scripts import db_io, catalogue_merge as merge, official_sources, app_updates
from tests.support import small_db, product, entry, ROOT


class SourcePolicyTests(unittest.TestCase):
    def test_official_priority_then_user_correction_survives_updates(self):
        incoming=small_db();incoming['_products']['Audit PLA']['display_name']='Audit PLA'
        db,_=merge.merge_catalogue(copy.deepcopy(core.EMPTY_DB),incoming,'Community',10)
        fact=dict(brand='Polymaker',names=['Audit PLA'],physical={'density':1.28},url='https://example.invalid/facts')
        count,_=merge.apply_official_facts(db,[fact],'Maker')
        self.assertEqual(count,1);self.assertEqual(db['_products']['Audit PLA']['density'],1.28)
        db,_=merge.merge_catalogue(db,incoming,'Community',10)
        self.assertEqual(db['_products']['Audit PLA']['density'],1.28)
        db['_products']['Audit PLA']['density']=1.33
        fact['physical']['density']=1.29
        _,conflicts=merge.apply_official_facts(db,[fact],'Maker')
        self.assertEqual(db['_products']['Audit PLA']['density'],1.33)
        self.assertIn('_products.Audit PLA.density',conflicts)

    def test_exact_identity_merges_and_ambiguous_identity_is_not_added(self):
        db=small_db();db['_skus']['LOCAL']['manufacturer_sku']='ABC'
        incoming=small_db();incoming['_skus']={'OFD-NEW':dict(entry(),manufacturer_sku='ABC',weight=None)}
        result,_=merge.merge_catalogue(db,incoming,'OFD',20)
        self.assertEqual(set(result['_skus']),{'LOCAL'})
        self.assertEqual(result['_skus']['LOCAL']['_source_aliases']['OFD'],['OFD-NEW'])
        db['_skus']['DUPLICATE']=dict(db['_skus']['LOCAL'])
        result,_=merge.merge_catalogue(db,incoming,'OFD',20)
        self.assertNotIn('OFD-NEW',result['_skus'])
        self.assertEqual(len(result['_pending_source_matches']['OFD']),1)

    def test_source_unknowns_can_be_completed_but_an_explicit_null_is_protected(self):
        incoming=small_db();incoming['_products']['Audit PLA']['density']=None
        db,_=merge.merge_catalogue(copy.deepcopy(core.EMPTY_DB),incoming,'Manufacturer',100)
        complement=small_db()
        db,_=merge.merge_catalogue(db,complement,'Community',10)
        self.assertEqual(db['_products']['Audit PLA']['density'],1.24)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.json';db_io.save_db(db,path);db=db_io.load_db(path)
            core.set_product_physical(db,'LOCAL',{'density':None},path=str(path))
            after,_=merge.merge_catalogue(db,complement,'Community',10)
            self.assertIsNone(after['_products']['Audit PLA']['density'])

    def test_intentionally_unknown_multicolor_cannot_be_filled_by_another_source(self):
        incoming=small_db();incoming['_skus']['LOCAL'].update(hex=None,color_name='Rainbow',source_colors=['FF0000','0000FF'])
        db,_=merge.merge_catalogue(copy.deepcopy(core.EMPTY_DB),incoming,'Community',10)
        other=copy.deepcopy(incoming);other['_skus']['LOCAL']['hex']='FF0000'
        result,conflicts=merge.merge_catalogue(db,other,'Manufacturer',100)
        self.assertIsNone(result['_skus']['LOCAL']['hex'])
        self.assertEqual(result['_skus']['LOCAL']['source_colors'],['FF0000','0000FF'])
        self.assertIn('_skus.LOCAL.hex',conflicts)

    def test_manufacturer_catalogue_is_first_and_has_no_guessed_physics(self):
        from scripts import sync_polymaker_official as polymaker
        incoming,rejected=polymaker.adapt([{'id':1,'title':'PolyLite™ PLA','variants':[
            {'id':2,'sku':'PB0001','title':'1.75mm / 1kg / Black','option3':'Black (HEX: #000000)'}]}])
        self.assertFalse(rejected)
        e=incoming['_skus']['PB0001'];p=incoming['_products'][e['product']]
        self.assertEqual((p['diameter'],e['weight']),(1.75,1000))
        self.assertIsNone(p['density']);self.assertIsNone(p['min_temp'])
        self.assertEqual(core.selected_pipeline()[0][0],'sync_polymaker_official.py')
        with self.assertRaises(db_io.SourceUnavailable):polymaker.adapt([])

    def test_legacy_brand_uncertain_community_variant_is_held_without_mutation(self):
        db=small_db();db['_brands']={'Polymaker':{'name':'Polymaker','source':'curated-offline'}}
        incoming=small_db();incoming['_skus']={'OFD-OTHER':dict(entry(),color_name='Different name')}
        merged,_=merge.merge_catalogue(db,incoming,'Open Filament Database',20)
        self.assertEqual(merged['_skus'],db['_skus'])
        self.assertEqual(len(merged['_pending_source_matches']['Open Filament Database']),1)

    def test_source_selection_and_no_automatic_unselected_hosts(self):
        steps=core.selected_pipeline(['sunlu'])
        self.assertEqual([s[0] for s in steps],['sync_sunlu_official.py'])
        self.assertEqual(core.selected_pipeline([]),[])
        with self.assertRaises(ValueError):core.selected_pipeline(['arbitrary-url'])

    def test_bambu_contextual_temperatures_are_not_generalized(self):
        fact=official_sources.bambu_fact({'name':'Bambu PLA Basic @base','filament_density':['1.26'],
               'textured_plate_temp':['60'],'nozzle_temperature':['220'],'filament_start_gcode':['not executed']},'https://example.invalid')
        self.assertEqual(fact['physical'],{'density':1.26})
        with self.assertRaises(ValueError):official_sources.bambu_fact({'name':'Generic @some printer'},'url')

    def test_sunlu_strict_table_and_partial_markup_failure(self):
        html='<table><tr><td>Density（g/cm³）</td><td>1.23</td><td>Bed Temperature</td><td>50-60℃</td></tr><tr><td>Black</td><td>#000000</td></tr></table>'
        fact,=official_sources.sunlu_facts(html)
        self.assertEqual(fact['physical'],dict(density=1.23,bed_min_temp=50,bed_max_temp=60))
        self.assertEqual(fact['colors'],{'black':'000000'})
        with self.assertRaises(db_io.SourceUnavailable):official_sources.sunlu_facts('<html>unavailable</html>')

    def test_fresh_packaged_install_contains_no_catalogue_and_existing_db_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'user/data/polymaker_db.json'
            with patch.multiple(core,_FROZEN=True,RESOURCE_DIR=str(root/'empty-bundle'),DB_PATH=str(path)):
                self.assertFalse(core.load_db()['_skus'])
                db_io.save_db(small_db(),path);before=path.read_bytes()
                self.assertEqual(core.load_db()['_skus']['LOCAL']['hex'],'FF0000')
                self.assertEqual(path.read_bytes(),before)
        from packaging_rules import resources
        files=resources(ROOT)
        self.assertFalse(any(p.startswith('orca_profiles/') or p.endswith('polymaker_db.json') or 'catalogue_' in p and p.startswith('data/') for p in files))
        self.assertIn('data/brand_logos/manifest.json',files)

    def test_recommendation_is_essential_and_full_stays_an_explicit_choice(self):
        payload=core.build_openspool(dict(entry(),color_name='x'*400),product())
        self.assertEqual(core.recommended_nfc(payload,'NTAG215')['profile'],'essential')
        self.assertEqual(core.recommended_nfc(payload,'NTAG216')['profile'],'essential')
        self.assertEqual(core.recommended_nfc(payload,'NTAG216',profile='full')['profile'],'full')
        with self.assertRaises(core.NfcCapacityError):core.recommended_nfc(payload,'NTAG215',profile='full')
        with self.assertRaises(core.NfcCapacityError):core.recommended_nfc(payload,'NTAG215',reserved_bytes=490)
        # Unknown brand metadata is never written as null bytes on the tag.
        full=core.build_openspool(entry(),product(),{'name':'Audit'})
        self.assertEqual(full['brand_meta'],{'name':'Audit'});self.assertNotIn('logo_url',full);self.assertNotIn('image',full)

    def test_settings_roundtrip_does_not_grant_network_authorization(self):
        with tempfile.TemporaryDirectory() as directory,patch('core.CONFIG_PATH',str(Path(directory)/'config.json')):
            cfg=core.load_config();cfg.update(printer_profile='bambu',nfc_tag_type='NTAG215',selected_sources=['sunlu'])
            cfg['ui']={'brand':'SUNLU','sort1':'color_name','view':'grid'};core.save_config(cfg)
            target=Path(directory)/'saved.json';core.export_settings(target)
            core.save_config(dict(core.DEFAULT_CONFIG,network_consent=False))
            core.import_settings(target)
            actual=core.load_config();self.assertEqual(actual['ui'],cfg['ui'])
            self.assertEqual(actual['printer_profile'],'bambu');self.assertFalse(core.has_network_consent())
            invalid=json.loads(target.read_text());invalid['settings']['nfc_reserved_bytes']=-1;target.write_text(json.dumps(invalid))
            before=Path(core.CONFIG_PATH).read_bytes()
            with self.assertRaises(ValueError):core.import_settings(target)
            self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)

    def test_app_update_never_downgrades_or_trusts_a_foreign_url(self):
        response=dict(tag_name='v0.2.2',draft=False,prerelease=False,html_url=core.APP_URL+'/releases/tag/v0.2.2')
        self.assertFalse(app_updates.parse_release(response,'0.3.0')['newer'])
        response.update(tag_name='v0.3.1',html_url=core.APP_URL+'/releases/tag/v0.3.1')
        self.assertTrue(app_updates.parse_release(response,'0.3.0')['newer'])
        response['html_url']='https://example.invalid/program'
        with self.assertRaises(ValueError):app_updates.parse_release(response,'0.3.0')


from tests import test_gui as gui_fixture
if gui_fixture.HAS_QT:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QCheckBox, QDialogButtonBox
    import app_gui


@unittest.skipUnless(gui_fixture.HAS_QT, "PySide6 non installé : interactions Qt non mesurées")
class CatalogueInteractionTests(unittest.TestCase):
    setUpClass=classmethod(gui_fixture.GuiTests.setUpClass.__func__)
    def setUp(self):
        schedule=patch('app_gui.QTimer.singleShot');schedule.start();self.addCleanup(schedule.stop)
        gui_fixture.GuiTests.setUp(self)

    def test_header_cycle_secondary_sort_and_column_visibility_persist(self):
        w=self.window
        self.assertEqual(w.brand_filter.currentData(),'Polymaker')
        self.assertTrue(w.sort1.isHidden());self.assertTrue(w.sort2.isHidden())
        w._sort_column(3);self.assertEqual(w.sort1.currentData(),'color_name');self.assertFalse(w.sort1_direction.currentData())
        w._sort_column(3);self.assertTrue(w.sort1_direction.currentData())
        w._set_column_sort('weight',True);self.assertEqual(w.sort2.currentData(),'weight')
        self.assertIn('2↑',w.table.horizontalHeaderItem(7).text())
        w._set_column_visible(7,False);w._save_ui_preferences()
        other=app_gui.MainWindow();self.addCleanup(other.close)
        self.assertTrue(other.table.isColumnHidden(7));self.assertEqual(other.sort1.currentData(),'color_name')
        self.assertTrue(other.sort1_direction.currentData())

    def test_click_same_row_blank_area_and_escape_deselect(self):
        w=self.window;w.show();self.app.processEvents()
        w.table.selectRow(0);self.assertIsNotNone(w.current_sku)
        rect=w.table.visualItemRect(w.table.item(0,2));QTest.mouseClick(w.table.viewport(),Qt.LeftButton,pos=rect.center())
        self.assertIsNone(w.current_sku)
        w.table.selectRow(0);QTest.keyClick(w.table,Qt.Key_Escape)
        self.assertIsNone(w.current_sku)

    def test_manufacturer_completion_and_printer_guidance(self):
        w=self.window;self.assertTrue(w.brand_filter.isEditable())
        w._brand_typed('rosa');self.assertEqual(w.brand_filter.currentData(),'ROSA3D')
        w.current_sku='PB05001';w._show_detail(w.current_sku)
        w.printer.setCurrentIndex(w.printer.findData('bambu'))
        self.assertFalse(w.btn_generate.isEnabled());self.assertIn('RFID Bambu',w.printer_help.toolTip());self.assertIn('ne lit pas',w.printer_help.text())
        w.printer.setCurrentIndex(w.printer.findData('prusa'));self.assertIn('ISO 15693',w.printer_help.toolTip())
        w.printer.setCurrentIndex(w.printer.findData('u1'));self.assertFalse(w.btn_generate.isEnabled())
        w.firmware.setCurrentIndex(w.firmware.findData('paxx12'));self.assertTrue(w.btn_generate.isEnabled())
        self.assertTrue(w.nfc_advanced.isHidden())
        self.assertFalse(w.stats_label.isVisible());self.assertIn('filaments',w.database_btn.text())

    def test_startup_refresh_every_launch_except_after_restore(self):
        w=self.window;w.show();core.set_network_consent(True)
        with patch.object(w,'_start_update') as update,patch('core.db_restored_this_session',return_value=False):
            w._maybe_auto_update();update.assert_called_once()
        with patch.object(w,'_start_update') as update,patch('core.db_restored_this_session',return_value=True):
            w._maybe_auto_update();update.assert_not_called()

    def test_source_dialog_saves_exact_selection_without_launch_when_save_only(self):
        w=self.window
        def choose(dialog):
            for checkbox in dialog.findChildren(QCheckBox):checkbox.setChecked(checkbox.text().startswith('SUNLU'))
            buttons=dialog.findChild(QDialogButtonBox)
            next(b for b in buttons.buttons() if b.text()=='Enregistrer seulement').click()
            return QDialog.Accepted
        with patch.object(QDialog,'exec',choose),patch.object(w,'_start_update') as update:
            w._choose_sources();update.assert_not_called()
        self.assertEqual(core.load_config()['selected_sources'],['sunlu'])

    def test_logo_keeps_transparent_corners(self):
        from PySide6.QtGui import QPixmap,QColor
        pixmap=QPixmap(20,20);pixmap.fill(QColor('white'))
        actual=self.window._transparent_logo(pixmap).toImage()
        self.assertEqual(actual.pixelColor(0,0).alpha(),0)

    def test_archive_remains_available_when_neither_nfc_profile_fits(self):
        w=self.window;w.current_sku='PB05001';w.db['_skus']['PB05001']['color_name']='x'*1400
        w.nfc_reserve.setValue(490);w.tag_type.setCurrentIndex(w.tag_type.findData('NTAG215'))
        with patch('app_gui.QMessageBox.information'):
            w._generate(mode='archive')
        files=list(Path(core.OUTPUT_DIR).glob('*archive.json'))
        self.assertEqual(len(files),1)
        self.assertEqual(json.loads(files[0].read_text())['color_name'],'x'*1400)

    def test_uniform_raster_margin_is_transparent_without_erasing_artwork(self):
        from PySide6.QtGui import QPixmap,QColor,QPainter
        pixmap=QPixmap(30,30);pixmap.fill(QColor('white'))
        painter=QPainter(pixmap);painter.fillRect(10,10,10,10,QColor('red'));painter.end()
        image=self.window._transparent_logo(pixmap).toImage()
        self.assertEqual(image.pixelColor(4,4).alpha(),0)
        self.assertEqual(image.pixelColor(16,16),QColor('red'))

    def test_settings_save_preserves_sources_changed_in_nested_dialog(self):
        def edit(dialog):
            cfg=core.load_config();cfg['selected_sources']=['sunlu'];core.save_config(cfg)
            return QDialog.Accepted
        with patch.object(QDialog,'exec',edit):self.window._open_settings()
        self.assertEqual(core.load_config()['selected_sources'],['sunlu'])
