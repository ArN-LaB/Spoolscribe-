"""Offline export feedback and isolated, durable personal filament copies."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from spoolscribe import core
from scripts import db_io, catalogue_merge
from tests.support import small_db
from tests import test_gui as fixture


class PersonalCopyTests(unittest.TestCase):
    def test_personal_copy_preserves_source_and_survives_source_merge_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.json';db=small_db();before=copy.deepcopy(db);db_io.save_db(db,path)
            sku=core.save_personal_filament(db,'LOCAL',{'min_temp':205,'density':None},'U1',path=str(path))
            self.assertNotEqual(sku,'LOCAL');self.assertEqual(db['_skus']['LOCAL'],before['_skus']['LOCAL'])
            self.assertEqual(db['_products'][before['_skus']['LOCAL']['product']],before['_products'][before['_skus']['LOCAL']['product']])
            product=db['_products'][db['_skus'][sku]['product']];self.assertTrue(product['display_name'].endswith(' @U1'))
            saved=copy.deepcopy((db['_skus'][sku],product))
            incoming=copy.deepcopy(before);incoming['_skus']['LOCAL']['hex']='112233';incoming['_products'][before['_skus']['LOCAL']['product']]['min_temp']=220
            merged,_=catalogue_merge.merge_catalogue(db,incoming,'Open Filament Database',10)
            self.assertEqual((merged['_skus'][sku],merged['_products'][db['_skus'][sku]['product']]),saved)
            db_io.save_db(merged,path);loaded=db_io.load_db(path)
            self.assertEqual(loaded['_products'][loaded['_skus'][sku]['product']]['min_temp'],205)
            self.assertIsNone(loaded['_products'][loaded['_skus'][sku]['product']]['density'])
            self.assertEqual(len(core.group_filaments(core.list_skus(loaded))),2)

    def test_editing_same_personal_suffix_updates_copy_and_cancelled_write_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.json';db=small_db();db_io.save_db(db,path)
            sku=core.save_personal_filament(db,'LOCAL',{'min_temp':205},'Personnel',path=str(path))
            self.assertEqual(core.save_personal_filament(db,'LOCAL',{'max_temp':230},'Personnel',path=str(path)),sku)
            self.assertEqual(len(db['_skus']),2)
            self.assertEqual(core.save_personal_filament(db,sku,{'min_temp':206},'Personnel',path=str(path)),sku)
            before=copy.deepcopy(db);raw=path.read_bytes()
            with patch('spoolscribe.core.save_db',side_effect=OSError('fixture')):
                with self.assertRaises(OSError):core.save_personal_filament(db,sku,{'min_temp':207},'U1',path=str(path))
            self.assertEqual(db,before);self.assertEqual(path.read_bytes(),raw)

    def test_invalid_suffix_and_physical_values_never_create_a_copy(self):
        for suffix,values in [('../U1',{'min_temp':205}),('',{'min_temp':205}),('U1',{'min_temp':-1}),('U1',{'min_temp':205.5})]:
            with self.subTest(suffix=suffix,values=values):
                db=small_db();before=copy.deepcopy(db)
                with self.assertRaises((ValueError,core.ExportValidationError)):core.save_personal_filament(db,'LOCAL',values,suffix)
                self.assertEqual(db,before)

    def test_copying_does_not_confirm_an_implausible_source_color(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'db.json';db=small_db();db['_skus']['LOCAL'].update(color_name='White',hex='000000');db_io.save_db(db,path)
            sku=core.save_personal_filament(db,'LOCAL',{'min_temp':205},'U1',path=str(path))
            self.assertTrue(db_io.implausible_color(db['_skus'][sku]))
            view=core.get_sku_view(db,sku)
            with self.assertRaises(core.MissingColorError):core.build_openspool(dict(db['_skus'][sku],sku=sku),view.product_data)


@unittest.skipUnless(fixture.HAS_QT,'Qt unavailable')
class ExportPersonalUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.GuiTests.setUpClass()
    def setUp(self):fixture.GuiTests.setUp(self)

    def test_inspection_cycles_never_resize_the_window(self):
        w=self.window;w.resize(1000,720);w.show();w._show_detail('PB05001');w.app.processEvents();before=w.size()
        for _ in range(3):
            w.btn_inspect.click();w.app.processEvents();self.assertEqual(w.size(),before)
            w.btn_inspect.click();w.app.processEvents();self.assertEqual(w.size(),before)

    def test_export_chooses_folder_persists_it_and_confirms_only_after_write(self):
        w=self.window;w._show_detail('PB05001');folder=Path(self.tmp.name)/'chosen';folder.mkdir()
        with patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',return_value=str(folder)),patch('spoolscribe.app_gui.QMessageBox.information') as message:
            w._generate();files=list(folder.glob('*.json'));self.assertEqual(len(files),1)
            self.assertEqual(core.load_config()['export_directory'],str(folder))
            self.assertEqual(message.call_args.args[1],'Export terminé');self.assertEqual(Path(message.call_args.args[2].split('\n',1)[1]).resolve(),files[0].resolve())
            self.assertEqual(files[0].read_text(),core.serialize_openspool(w._build_payload(),**w._nfc_options()))

    def test_export_folder_cancellation_creates_nothing_and_does_not_confirm(self):
        w=self.window;w._show_detail('PB05001')
        with patch('spoolscribe.app_gui.QFileDialog.getExistingDirectory',return_value=''),patch('spoolscribe.app_gui.QMessageBox.information') as message:
            w._generate();message.assert_not_called();self.assertFalse(Path(core.OUTPUT_DIR).exists())

    def test_gui_saves_a_personal_copy_and_selects_it_without_changing_source(self):
        from PySide6.QtWidgets import QLineEdit
        w=self.window;w._show_detail('PB05001');original=copy.deepcopy(w.db['_products'])
        # The former modal dialog is now an in-card draft with the same guarantees.
        w._edit_physical()
        w.draft_editor.findChild(QLineEdit,'personal_suffix').setText('U1')
        field=w.draft_editor.findChild(QLineEdit,'min_temp');field.setText('225');field.textEdited.emit('225')
        w.draft_save.click()
        self.assertTrue(w.current_sku.startswith('USER-'))
        for name,product in original.items():self.assertEqual(w.db['_products'][name],product)
        view=core.get_sku_view(w.db,w.current_sku)
        self.assertTrue(view.display_product.endswith(' @U1'));self.assertEqual(view.product_data['min_temp'],225)
        loaded=core.load_db();self.assertIn(w.current_sku,loaded['_skus'])

    def test_release_check_status_is_cleared_on_success_and_error(self):
        w=self.window
        for result in ({'newer':False,'version':'0.2.2'},{'error':'offline'}):
            w.status.showMessage('Vérification de la version publiée sur GitHub…')
            with patch('spoolscribe.ui_catalogue.QMessageBox.information'),patch('spoolscribe.ui_catalogue.QMessageBox.warning'):w._release_result(result)
            self.assertNotIn('Vérification',w.status.currentMessage())

    def test_reset_has_same_width_and_right_edge_as_filament_favorites(self):
        from PySide6.QtCore import QPoint
        w=self.window;w.show();w.app.processEvents()
        self.assertEqual(w.reset_filters.width(),w.favorites_only.width())
        right=lambda x:x.mapTo(w,QPoint()).x()+x.width()
        self.assertEqual(right(w.reset_filters),right(w.favorites_only))

    def test_about_links_are_a_pair_of_equal_buttons(self):
        from PySide6.QtWidgets import QDialog,QPushButton
        def inspect(dialog):
            dialog.show();self.window.app.processEvents()
            a=dialog.findChild(QPushButton,'projectGithub');b=dialog.findChild(QPushButton,'supportProject')
            self.assertIsNotNone(a);self.assertEqual(a.width(),b.width());self.assertEqual(a.height(),b.height())
            return QDialog.Rejected
        with patch.object(QDialog,'exec',inspect):self.window._open_about()
