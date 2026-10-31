import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import core
from tests.support import catalogue

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit
    import app_gui


@unittest.skipUnless(HAS_QT, "PySide6 non installé : contrôles GUI non mesurés")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        db = root / "db.json"
        db.write_text(json.dumps(catalogue()), encoding="utf-8")
        self.paths = patch.multiple(core, DB_PATH=str(db), CONFIG_PATH=str(root / "config.json"),
                                    OUTPUT_DIR=str(root / "output"))
        self.paths.start()
        self.addCleanup(self.paths.stop)
        errors = patch("app_gui.QMessageBox.critical", side_effect=lambda *args, **kwargs:
                       self.fail(f"Dialogue d'erreur inattendu : {args[-1]}"))
        errors.start()
        self.addCleanup(errors.stop)
        self.window = app_gui.MainWindow()
        self.addCleanup(self.window.close)

    def test_startup_and_inspection_are_offline_and_identical_to_export(self):
        self.window.current_sku = "PB05001"
        self.window._show_detail("PB05001")
        self.window._refresh_inspector()
        text = self.window.inspector.toPlainText()
        self.assertEqual(text, core.serialize_openspool(self.window._build_payload(), **self.window._nfc_options()))
        with patch("app_gui.QMessageBox.information"):
            self.window._generate()
            self.window._generate(mode="archive")
        files = list(Path(core.OUTPUT_DIR).glob("*.json"))
        self.assertEqual(len(files), 2)
        self.assertTrue(all(json.loads(p.read_text())["color_hex"] == "070908" for p in files))
        self.assertFalse(core.has_network_consent())

    def test_missing_color_is_an_error_in_preview_without_a_black_export(self):
        self.window.current_sku = "FB04001"
        self.window._refresh_inspector()
        self.assertIn("Couleur HEX inconnue", self.window.inspector.toPlainText())
        self.assertIsNone(self.window.db["_skus"]["FB04001"]["hex"])
        self.assertFalse(Path(core.OUTPUT_DIR).exists())

    def test_manual_color_and_transparency_are_saved_and_exported(self):
        self.window.current_sku = "FB04001"
        def fill_dialog(dialog):
            inputs = dialog.findChildren(QLineEdit)
            inputs[0].setText("abcdef")
            inputs[1].setText("00")
            return QDialog.Accepted
        with patch.object(QDialog, "exec", fill_dialog), patch("app_gui.QMessageBox.information"):
            self.window._generate()
        stored = core.load_db()["_skus"]["FB04001"]
        self.assertEqual((stored["hex"], stored["alpha"]), ("ABCDEF", "00"))
        files = list(Path(core.OUTPUT_DIR).glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["alpha"], "00")

    def test_export_is_blocked_while_updating(self):
        self.window.current_sku = "PB05001"
        class Running:
            def isRunning(self): return True
        self.window.worker = Running()
        self.window._generate()
        self.assertFalse(Path(core.OUTPUT_DIR).exists())
        self.window.worker = None

    def test_universal_filters_double_sort_pagination_and_selection(self):
        from scripts import db_io
        from tests.support import ROOT
        extension = db_io.load_db(ROOT / "data/catalogue_ofd.json")
        self.window.db.update(db_io.merge_bundled_db(self.window.db, extension)[0])
        self.window._reload_table()
        self.assertEqual(self.window.table.rowCount(), 250)
        self.assertEqual(self.window.brand_filter.currentData(), "Polymaker")
        self.window.brand_filter.setCurrentIndex(0)
        self.assertGreater(len(self.window._filtered_rows), 23000)
        self.window.brand_filter.setCurrentIndex(self.window.brand_filter.findData("Bambu Lab"))
        self.window.material_filter.setCurrentIndex(self.window.material_filter.findData("PLA"))
        self.window.sort1.setCurrentIndex(self.window.sort1.findData("color_name"))
        self.window.sort2.setCurrentIndex(self.window.sort2.findData("weight"))
        self.window.sort2_direction.setCurrentIndex(1)
        expected = core.query_catalogue(self.window._all_rows, brand="Bambu Lab", material="PLA",
                                        sort1="color_name", sort2="weight", descending2=True)
        self.assertEqual(self.window._filtered_rows, expected)
        self.window.table.selectRow(0)
        selected = self.window.current_sku
        self.window._set_view_mode("grid")
        self.assertEqual(self.window.current_sku, selected)
        self.window._apply_filter()
        self.assertEqual(self.window.current_sku, selected)
        self.window.search.setText("absent-unique-example")
        self.assertTrue(self.window._search_timer.isActive())  # typing is debounced
        self.window._apply_filter()
        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertIsNone(self.window.current_sku)
        self.window._reset_filters()
        self.assertEqual(self.window.brand_filter.currentData(), "Polymaker")
        self.window.brand_filter.setCurrentIndex(0)
        self.window._change_page(1)
        self.assertEqual(self.window._rows[0], self.window._filtered_rows[250])

    def test_ntag215_essential_inspector_and_export_are_identical(self):
        self.window.current_sku = "PB05001"
        self.window._show_detail("PB05001")
        self.window.tag_type.setCurrentIndex(self.window.tag_type.findData("NTAG215"))
        self.window.nfc_profile.setCurrentIndex(self.window.nfc_profile.findData("essential"))
        self.window.nfc_reserve.setValue(32)
        self.window._refresh_inspector()
        expected = self.window.inspector.toPlainText()
        self.assertNotIn("brand_meta", json.loads(expected))
        self.assertIn("marge", self.window.nfc_capacity.text())
        with patch("app_gui.QMessageBox.information"):
            self.window._generate()
            self.window._generate(mode="archive")
        files = list(Path(core.OUTPUT_DIR).glob("*ntag215_essential.json"))
        self.assertEqual(files[0].read_text(), expected)
        archive, = Path(core.OUTPUT_DIR).glob("*archive.json")
        self.assertIn("brand_meta", json.loads(archive.read_text()))

    def test_all_approved_logos_render_at_full_hidpi_size_with_an_outline(self):
        from tests.support import ROOT
        manifest = json.loads((ROOT / "data/brand_logos/manifest.json").read_text())
        rendered = 0
        for asset in manifest.values():
            with self.subTest(brand=asset["name"]):
                pixmap = app_gui.load_brand_pixmap(str(ROOT / asset["path"]), 48, 2, max_w=152)
                if pixmap is None:
                    continue  # Too small to stay legible: the name fallback is used.
                rendered += 1
                self.assertFalse(pixmap.isNull())
                self.assertLessEqual(pixmap.height(), 96)
                outlined = self.window._transparent_logo(pixmap)
                self.assertEqual(outlined.devicePixelRatio(), 2)
                self.assertEqual((outlined.width(), outlined.height()), (pixmap.width() + 8, pixmap.height() + 8))
        self.assertGreater(rendered, 100)
        logo = Path(self.tmp.name) / "white.svg"
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 30"><rect width="100" height="30" fill="white"/></svg>')
        outlined = self.window._transparent_logo(app_gui.load_brand_pixmap(str(logo), 48, 2))
        self.assertLess(outlined.toImage().pixelColor(2, outlined.height() // 2).lightness(), 255)
        tiny = Path(self.tmp.name) / "tiny.png"
        app_gui.QPixmap(40, 12).save(str(tiny))
        self.assertIsNone(app_gui.load_brand_pixmap(str(tiny), 48, 2))

    def test_real_startup_restore_stays_exact_with_auto_update_enabled(self):
        from PySide6.QtCore import QEventLoop, QTimer
        from scripts import db_io

        self.window.close()
        for frozen in (False, True):
            with self.subTest(frozen=frozen), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                db_path = root / "user/db.json"
                bundled = root / "bundle/data/polymaker_db.json"
                bundled.parent.mkdir(parents=True)
                db = catalogue()
                db["_last_updated"] = "2020-01-01T00:00:00"
                db["_skus"]["PB05001"].update(hex="ABCDEF", user_note="local")
                bundled.write_text(json.dumps(catalogue()), encoding="utf-8")
                db_io.save_db(db, db_path)
                backup = Path(str(db_path) + ".bak")
                backup.write_bytes(db_path.read_bytes())
                chosen = backup.read_bytes()
                db_path.write_text("corrupt")

                def event_loop():
                    loop = QEventLoop()
                    QTimer.singleShot(650, loop.quit)
                    loop.exec()
                    return 0

                with patch.multiple(core, _FROZEN=frozen, DB_PATH=str(db_path),
                                    CONFIG_PATH=str(root / "config.json"), RESOURCE_DIR=str(root / "bundle"),
                                    DATA_DIR=str(db_path.parent), ORCA_DIR=str(root / "user/orca_profiles")), \
                     patch("app_gui.QApplication", return_value=self.app) as application, \
                     patch.object(self.app, "exec", side_effect=event_loop), \
                     patch("app_gui.QMessageBox.question", return_value=app_gui.QMessageBox.Yes), \
                     patch.object(app_gui.MainWindow, "_start_update") as update, \
                     patch("sys.argv", ["SpoolScribe"]):
                    application.instance.return_value = self.app
                    core.set_network_consent(True, auto_update=True)
                    preferences = Path(core.CONFIG_PATH).read_bytes()
                    try:
                        self.assertEqual(app_gui.main(), 0)
                        update.assert_not_called()
                        self.assertEqual(db_path.read_bytes(), chosen)
                        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), preferences)
                        # A later callback in this same process must also remain inert.
                        for window in self.app.topLevelWidgets():
                            if isinstance(window, app_gui.MainWindow) and window.isVisible():
                                window._maybe_auto_update()
                        update.assert_not_called()
                    finally:
                        for window in self.app.topLevelWidgets():
                            window.close()
