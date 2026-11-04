"""Offline regression checks for v0.3.5: locale, faceted filters and clear action."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core
from spoolscribe import i18n
from spoolscribe.packaging_rules import resources
from tests.support import ROOT
from tests import test_gui as fixture


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language('fr')

    def test_os_language_and_english_fallback(self):
        for system, expected in [('en-US','en'),('fr-FR','fr'),('es-MX','es'),('zh-Hans-CN','zh_CN'),
                                 ('zh_CN','zh_CN'),('zh-SG','zh_CN'),('de-DE','en'),('zh-Hant-TW','en')]:
            with self.subTest(system=system):
                self.assertEqual(i18n.resolve_language('auto',[system]),expected)
        self.assertEqual(i18n.resolve_language('fr',['en-US']),'fr')
        self.assertEqual(i18n.resolve_language('auto',[]),'en')
        self.assertEqual(i18n.resolve_language([],['es-ES']),'es')

    def test_catalogues_are_complete_with_identical_named_placeholders(self):
        messages=i18n.catalogue()
        self.assertGreater(len(messages),450)
        for source, translations in messages.items():
            self.assertEqual(set(translations),{'en','es','zh_CN'})
            for language, text in translations.items():
                with self.subTest(source=source,language=language):
                    self.assertTrue(text.strip())
                    self.assertEqual(i18n.placeholders(source),i18n.placeholders(text))
        for filename in ('app_gui.py','ui_catalogue.py','ui_widgets.py','ui_detail.py','ui_guidance.py','printer_presentations.py','ui_colour_measurements.py'):
            for node in ast.walk(ast.parse((ROOT/'src/spoolscribe'/filename).read_text(encoding='utf-8'))):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tr' and node.args and isinstance(node.args[0],ast.Constant):
                    self.assertIn(node.args[0].value,messages,f'{filename}:{node.lineno}')

    def test_translation_fallback_and_user_data_are_not_interpreted(self):
        i18n.set_language('es')
        self.assertEqual(i18n.tr('Effacer'),'Borrar')
        self.assertEqual(i18n.tr('Produit @U1 {custom}'),'Produit @U1 {custom}')
        self.assertEqual(i18n.tr('Export terminé : {v0}',v0='Red {private}'),'Exportación completada: Red {private}')
        self.assertEqual(i18n.tr('Unknown source log'),'Unknown source log')
        with patch('spoolscribe.i18n.catalogue',return_value={'Test':{'en':'English only'}}):
            self.assertEqual(i18n.tr('Test'),'English only')

    def test_language_roundtrip_and_invalid_import_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(core,'CONFIG_PATH',str(Path(tmp)/'config.json')):
            cfg=core.load_config();cfg['language']='zh_CN';core.save_config(cfg)
            target=Path(tmp)/'settings.json';core.export_settings(target)
            cfg['language']='auto';core.save_config(cfg);core.import_settings(target)
            self.assertEqual(core.load_config()['language'],'zh_CN')
            document=json.loads(target.read_text(encoding='utf-8'));document['settings']['language']='unsupported'
            target.write_text(json.dumps(document),encoding='utf-8');before=Path(core.CONFIG_PATH).read_bytes()
            with self.assertRaises(ValueError):core.import_settings(target)
            self.assertEqual(Path(core.CONFIG_PATH).read_bytes(),before)

    def test_translations_are_in_public_build_resources_but_no_catalogue(self):
        files=resources(ROOT)
        self.assertIn('data/translations/messages.json',files)
        self.assertNotIn('tests/fixtures/catalogues/polymaker_db.json',files)
        self.assertNotIn('docs/images/spoolscribe-animated.gif',files)

    def test_readme_logo_is_a_real_animation(self):
        from PIL import Image
        with Image.open(ROOT/'docs/images/spoolscribe-animated.gif') as image:
            self.assertGreater(image.n_frames,1)
            self.assertEqual(image.info['loop'],0)
        self.assertIn('docs/images/spoolscribe-animated.gif',(ROOT/'README.md').read_text(encoding='utf-8'))


@unittest.skipUnless(fixture.HAS_QT,'PySide6 not installed')
class InterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.GuiTests.setUpClass.__func__)

    def setUp(self):
        timer=patch('spoolscribe.app_gui.QTimer.singleShot');timer.start();self.addCleanup(timer.stop)
        fixture.GuiTests.setUp(self)
        self.addCleanup(i18n.set_language,'fr')

    @staticmethod
    def visible_values(widget):
        from PySide6.QtCore import Qt
        return [widget.item(i).data(Qt.UserRole) for i in range(widget.count()) if not widget.item(i).isHidden()]

    def seed_facets(self):
        # Names and product keys are synthetic. Every record retains the same
        # physical schema used by the real catalogue, without editing real data.
        db=copy.deepcopy(self.window.db)
        db['_products']={};db['_skus']={}
        for sku,brand,material in [('A','Alpha','PLA'),('B','Alpha','PETG'),('C','Beta','PETG'),('D','Gamma','ABS')]:
            product=f'{brand} {material}'
            db['_products'][product]={'type':material,'brand':brand,'diameter':1.75,'density':1.24,
                'min_temp':190,'max_temp':230,'bed_min_temp':60,'bed_max_temp':60}
            db['_skus'][sku]={'product':product,'color_name':'Red','hex':'FF0000','weight':1000}
        self.window.db=db;self.window._reload_table();self.window._reset_filters()

    def test_cross_filter_both_directions_and_counts(self):
        w=self.window;self.seed_facets()
        w._choose_brand('Alpha',remember=False)
        self.assertEqual(self.visible_values(w.family_list),['','PETG','PLA'])
        w._choose_family('PETG')
        self.assertEqual(self.visible_values(w.brand_list),['','Alpha','Beta'])
        w._choose_brand('Beta',remember=False)
        self.assertEqual(self.visible_values(w.family_list),['','PETG'])
        self.assertIn('(1)',w.family_list.item(1).text())
        self.assertEqual([r['sku'] for r in w._filtered_rows],['C'])
        w._choose_family('');self.assertEqual(self.visible_values(w.brand_list),['','Alpha','Beta','Gamma'])

    def test_clear_restores_facets_and_never_erases_favourites(self):
        w=self.window;self.seed_facets()
        cfg=core.load_config();cfg['favorite_brands']=['Gamma'];cfg['favorite_filaments']=[w._all_rows[0]['filament_id']];core.save_config(cfg)
        saved=core.load_config()
        w._choose_brand('Alpha',remember=False);w._choose_family('PETG');w.search.setText('missing');w._apply_filter()
        self.assertEqual(self.visible_values(w.family_list),[''])
        w._reset_filters()
        self.assertEqual(set(self.visible_values(w.brand_list)),{'','Alpha','Beta','Gamma'})
        self.assertEqual(set(self.visible_values(w.family_list)),{'','PLA','PETG','ABS'})
        self.assertEqual(core.load_config()['favorite_brands'],saved['favorite_brands'])
        self.assertEqual(core.load_config()['favorite_filaments'],saved['favorite_filaments'])
        self.assertIsNone(w.current_sku)

    def test_saved_filters_restore_with_correct_facets(self):
        w=self.window;self.seed_facets()
        cfg=core.load_config();cfg['ui']={'brand':'Beta','material':'PETG'};core.save_config(cfg)
        w._restore_ui_preferences()
        self.assertEqual(w.brand_filter.currentData(),'Beta')
        self.assertEqual(self.visible_values(w.family_list),['','PETG'])
        self.assertEqual(self.visible_values(w.brand_list),['','Alpha','Beta'])

    def test_clear_button_is_centred_clickable_and_keeps_keyboard_focus(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        w=self.window;w.show();w.search.setText('test');self.app.processEvents()
        button=w.search.clear_button
        self.assertTrue(button.isVisible())
        self.assertLessEqual(abs(button.geometry().center().y()-w.search.rect().center().y()),1)
        self.assertLess(button.geometry().right(),w.search.width())
        QTest.mouseClick(button,Qt.LeftButton);self.app.processEvents()
        self.assertEqual(w.search.text(),'');self.assertFalse(button.isVisible());self.assertTrue(w.search.hasFocus())

    def test_settings_language_applies_next_start_and_preserves_sources(self):
        from PySide6.QtWidgets import QDialog,QComboBox
        def choose(dialog):
            language=dialog.findChild(QComboBox,'interface_language')
            language.setCurrentIndex(language.findData('es'))
            cfg=core.load_config();cfg['selected_sources']=['sunlu'];core.save_config(cfg)
            return QDialog.Accepted
        with patch.object(QDialog,'exec',choose),patch.object(self.window,'_offer_language_restart'):
            self.window._open_settings()
        self.assertEqual(core.load_config()['language'],'es')
        self.assertEqual(core.load_config()['selected_sources'],['sunlu'])
        self.assertEqual(i18n.language(),'fr')
        other=fixture.app_gui.MainWindow();self.addCleanup(other.close)
        self.assertEqual(other.update_btn.text(),'Actualizar catálogo')

    def test_four_languages_export_identical_json_and_keep_favourite_ids(self):
        cfg=core.load_config();payloads=[];ids=[]
        for language in i18n.LANGUAGES:
            with self.subTest(language=language):
                cfg['language']=language;core.save_config(cfg)
                window=fixture.app_gui.MainWindow();self.addCleanup(window.close)
                self.assertEqual(i18n.language(),language)
                self.assertEqual(window.update_btn.text(),i18n.tr('Actualiser le catalogue'))
                window._show_detail('PB05001');window.current_sku='PB05001'
                payloads.append(core.serialize_openspool(window._build_payload()))
                ids.append([row.get('filament_id') for row in window._all_rows])
                self.assertEqual(window.characteristics.labels['Nozzle'].text(),i18n.tr('BUSE'))
        self.assertEqual(len(set(payloads)),1)
        self.assertTrue(all(values==ids[0] for values in ids))

    def test_auto_language_reads_system_and_falls_back_to_english(self):
        from PySide6.QtCore import QLocale
        cfg=core.load_config();cfg['language']='auto';core.save_config(cfg)
        with patch.object(QLocale,'system') as system,patch('spoolscribe.i18n._macos_preferred_languages',return_value=[]):
            system.return_value.uiLanguages.return_value=['de-DE']
            w=fixture.app_gui.MainWindow();self.addCleanup(w.close)
        self.assertEqual(w.update_btn.text(),'Refresh catalogue')
