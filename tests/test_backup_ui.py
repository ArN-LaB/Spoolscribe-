"""Interface of « Sauvegarder / Restaurer mes données » over the backup engine (synthetic fixtures only)."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from spoolscribe import backup, core, recovery
from tests import test_gui as fixture


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class BackupUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        from spoolscribe import ui_backup
        self.ui = ui_backup
        out = tempfile.TemporaryDirectory()
        self.addCleanup(out.cleanup)
        self.archive = Path(out.name) / "sauvegarde.zip"
        for name in ("warning", "information"):
            p = patch(f"spoolscribe.ui_backup.QMessageBox.{name}")
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        self.critical = MagicMock()
        p = patch("spoolscribe.ui_backup.QMessageBox.critical", self.critical)
        p.start(); self.addCleanup(p.stop)
        p = patch.object(self.ui, "_offer_restart")
        self.restart = p.start(); self.addCleanup(p.stop)

    def make_backup(self, options=None):
        with patch.object(self.ui, "_ask_backup_options", return_value=options or backup.Options()), \
                patch("spoolscribe.ui_backup.QFileDialog.getSaveFileName", return_value=(str(self.archive), "ZIP")):
            self.ui.create_backup(self.window)
        self.warning.assert_not_called()
        self.assertTrue(zipfile.is_zipfile(self.archive))

    def restore(self, confirm=True):
        with patch("spoolscribe.ui_backup.QFileDialog.getOpenFileName", return_value=(str(self.archive), "ZIP")), \
                patch.object(self.ui, "_confirm_restore", return_value=confirm) as preview:
            self.ui.restore_backup(self.window)
        return preview

    def edit_catalogue(self, name="Modifié après sauvegarde"):
        db = core.load_db()
        sku = next(iter(db["_skus"]))
        db["_skus"][sku]["color_name"] = name
        core.save_db(db)
        return sku

    def test_options_dialog_defaults_and_inventory_preview(self):
        from PySide6.QtWidgets import QCheckBox, QDialog, QLabel
        seen = {}

        def inspect(dialog):
            boxes = {n: dialog.findChild(QCheckBox, n) for n in ("includeConfig", "includeLayout", "includeExportPath",
                                                                 "includeExports")}
            seen["checked"] = {n: b.isChecked() for n, b in boxes.items()}
            seen["inventory"] = dialog.findChild(QLabel, "backupInventory").text()
            return QDialog.Accepted
        with patch("spoolscribe.ui_backup.QDialog.exec", inspect):
            options = self.ui._ask_backup_options(self.window)
        self.assertEqual(seen["checked"], {"includeConfig": True, "includeLayout": False, "includeExportPath": False,
                                           "includeExports": False})
        self.assertEqual(options, backup.Options())
        self.assertIn("Catalogue", seen["inventory"])
        self.assertIn("Registre des mesures de couleur : absent", seen["inventory"])
        self.assertNotIn("{", seen["inventory"])

    def test_backup_restore_and_explicit_revert_through_the_interface(self):
        original = Path(core.DB_PATH).read_bytes()
        self.make_backup()
        with zipfile.ZipFile(self.archive) as archive:
            prefs = json.loads(archive.read("config/preferences.json"))["settings"]
        self.assertNotIn("network_consent", prefs)
        sku = self.edit_catalogue()
        edited = Path(core.DB_PATH).read_bytes()
        preview = self.restore()
        lines = self.ui.analysis_text(preview.call_args.args[1])
        self.assertTrue(any(line.startswith("Remplacés : ") and "Catalogue" in line for line in lines), lines)
        self.assertTrue(any("copie exacte de vos fichiers actuels" in line for line in lines))
        self.warning.assert_not_called(); self.critical.assert_not_called()
        self.assertEqual(Path(core.DB_PATH).read_bytes(), original)
        self.assertNotEqual(self.window.db["_skus"][sku]["color_name"], "Modifié après sauvegarde")  # views reloaded
        self.restart.assert_called_once()
        self.assertIsNotNone(self.ui.last_restore())

        self.restart.reset_mock()
        with patch("spoolscribe.ui_backup.QMessageBox.question", return_value=self.ui.QMessageBox.Yes):
            self.ui.revert_last_restore(self.window)
        self.critical.assert_not_called()
        self.assertEqual(Path(core.DB_PATH).read_bytes(), edited)
        self.assertEqual(self.window.db["_skus"][sku]["color_name"], "Modifié après sauvegarde")
        self.restart.assert_called_once()

    def test_cancelled_preview_and_identical_data_write_nothing(self):
        self.make_backup()
        self.edit_catalogue()
        before = Path(core.DB_PATH).read_bytes(), Path(core.CONFIG_PATH).read_bytes()
        self.restore(confirm=False)
        self.assertEqual((Path(core.DB_PATH).read_bytes(), Path(core.CONFIG_PATH).read_bytes()), before)
        self.assertIsNone(self.ui.last_restore())
        self.restart.assert_not_called()

    def test_running_update_or_open_draft_refuses_before_any_file_dialog(self):
        self.make_backup()
        self.window.worker = MagicMock(isRunning=lambda: True)
        with patch("spoolscribe.ui_backup.QFileDialog.getOpenFileName") as picker:
            self.ui.restore_backup(self.window)
            picker.assert_not_called()
        self.information.assert_called_once()
        self.window.worker = None
        with patch.object(self.window, "_confirm_draft_transition", return_value=False), \
                patch("spoolscribe.ui_backup.QFileDialog.getOpenFileName") as picker:
            self.ui.restore_backup(self.window)
            picker.assert_not_called()

    def test_change_after_preview_requires_a_new_preview(self):
        self.make_backup()
        self.edit_catalogue()
        def change_then_confirm(window, analysis):
            self.edit_catalogue("Autre modification")   # concurrent change between preview and commit
            return True
        before_tx = self.ui.last_restore()
        with patch("spoolscribe.ui_backup.QFileDialog.getOpenFileName", return_value=(str(self.archive), "ZIP")), \
                patch.object(self.ui, "_confirm_restore", side_effect=change_then_confirm):
            self.ui.restore_backup(self.window)
        self.warning.assert_called_once()
        self.assertIn("a changé depuis l'aperçu", self.warning.call_args.args[2])
        self.assertEqual(self.ui.last_restore(), before_tx)
        self.restart.assert_not_called()

    def test_invalid_archive_is_refused_with_a_translated_message(self):
        self.archive.write_bytes(b"pas une archive")
        self.restore()
        self.warning.assert_called_once()
        self.assertEqual(self.warning.call_args.args[2], "Ce fichier n'est pas une sauvegarde SpoolScribe.")
        self.assertNotIn("{", self.warning.call_args.args[2])

    def test_restored_layout_is_not_overwritten_when_the_window_closes(self):
        self.window._restoring_ui = False           # as after the deferred startup restore
        self.window._set_view_mode("list")
        self.make_backup(backup.Options(include_layout=True))   # saves the live (list) layout first
        self.window._set_view_mode("grid")
        self.window._save_ui_preferences()
        self.assertEqual(core.load_config()["ui"]["view"], "grid")
        self.restore()
        self.assertTrue(self.window._skip_ui_save)
        self.assertEqual(core.load_config()["ui"]["view"], "list")
        self.window._save_ui_preferences()          # e.g. on close: the restored layout wins
        self.assertEqual(core.load_config()["ui"]["view"], "list")

    def test_settings_tab_offers_revert_only_when_a_restore_is_kept(self):
        from PySide6.QtWidgets import QDialog, QPushButton
        states = []
        def inspect(dialog):
            states.append(dialog.findChild(QPushButton, "revertRestore").isEnabled()); return QDialog.Rejected
        with patch("spoolscribe.app_gui.QDialog.exec", inspect):
            self.window._open_settings()
        self.make_backup(); self.edit_catalogue(); self.restore()
        with patch("spoolscribe.app_gui.QDialog.exec", inspect):
            self.window._open_settings()
        self.assertEqual(states, [False, True])

    def test_startup_status_is_reported_and_never_shown_as_success_when_recoverable(self):
        self.ui.show_startup_recovery(self.window, {"state": "clean"})
        self.information.assert_not_called(); self.warning.assert_not_called()
        done = {"state": "recovered", "template": recovery.MESSAGES["recovery_done"], "values": {"v0": 2}}
        self.ui.show_startup_recovery(self.window, done)
        self.assertIn("2 élément(s)", self.information.call_args.args[2])
        kept = {"state": "recoverable", "template": recovery.MESSAGES["recovery_incomplete"],
                "values": {"v0": 1, "v1": "<dossier>"}}
        self.ui.show_startup_recovery(self.window, kept)
        self.warning.assert_called_once()
        self.assertIn("Retour arrière incomplet", self.warning.call_args.args[2])

    def test_pending_recovery_blocks_restore_and_offers_rollback(self):
        with patch.object(backup, "pending_recovery", return_value={"txid": "x", "dir": "d", "conflicts": []}), \
                patch.object(self.ui, "resolve_pending") as resolve, \
                patch("spoolscribe.ui_backup.QFileDialog.getOpenFileName") as picker:
            self.ui.restore_backup(self.window)
        resolve.assert_called_once()
        picker.assert_not_called()

    def test_error_text_translates_nested_values(self):
        error = backup.BackupError("source_invalid", v0="config.json", v1=ValueError("Favoris invalides"))
        self.assertEqual(self.ui.error_text(error), "config.json invalide : Favoris invalides. Sauvegarde non créée.")


class BackupTranslationTests(unittest.TestCase):
    def test_engine_templates_and_labels_exist_in_every_language_with_the_same_placeholders(self):
        from spoolscribe import i18n
        catalogue = i18n.catalogue()
        sources = set(backup.MESSAGES.values()) | set(recovery.MESSAGES.values()) \
            | set(backup.CATEGORY_LABELS.values()) | set(backup.REASON_LABELS.values())
        if fixture.HAS_QT:
            from spoolscribe import ui_backup
            sources |= set(ui_backup.STATE_LABELS.values()) | set(ui_backup.SETTINGS_CATEGORY_LABELS.values())
        for source in sorted(sources):
            with self.subTest(source=source):
                self.assertIn(source, catalogue)
                for language in ("en", "es", "zh_CN"):
                    self.assertEqual(i18n.placeholders(catalogue[source][language]), i18n.placeholders(source))


if __name__ == "__main__":
    unittest.main()
