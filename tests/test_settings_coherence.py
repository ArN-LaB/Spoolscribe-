"""SPOOLSCRIBE-DESKTOP-002 P1: preferences validation/portability, settings dialog, About and provenance.

Offline; every test isolates the catalogue and configuration in a temporary folder.
"""
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from spoolscribe import core, i18n, presentation
from tests.support import ROOT, catalogue
from tests import test_gui as fixture

ORCA_PARTIAL = {"nozzle_temperature_range_low": ["200"], "nozzle_temperature_range_high": ["230"],
                "filament_density": ["1.24"], "filament_diameter": ["1.75"], "hot_plate_temp": ["60"]}


def synthetic_v1_export():
    """Equivalent of the user's 25-key export (no real data): layout, absolute path, eight OpenTag3D entries."""
    # The historical export dropped consent, revision and last_update, but kept the two other machine keys.
    settings = {k: copy.deepcopy(v) for k, v in core.DEFAULT_CONFIG.items()
                if k not in ("network_consent", "network_sources_revision", "last_update")}
    settings.update(language="fr", auto_update=False, update_interval_days=7, orca_overrides=False,
                    selected_sources=["polymaker", "ofd", "spoolman", "orca"], nfc_format="opentag3d",
                    favorite_brands=["Polymaker"], favorite_filaments=["PB05001"], recent_brands=["Polymaker"],
                    export_directory="/Users/example/Exports", ui={"view": "grid", "geometry": "00ff"},
                    qr_label={}, last_update_attempt="2026-11-06T10:00:00", last_update_status="complete",
                    opentag3d_settings={f"PB0500{i}": {"min_print_temp": 200 + 5 * i} for i in range(8)})
    assert len(settings) == 25
    return {"format": "spoolscribe-settings", "version": 1, "settings": settings}


class PreferencesModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        patcher = patch.multiple(core, CONFIG_PATH=str(root / "config.json"), DATA_HOME=str(root))
        patcher.start(); self.addCleanup(patcher.stop)
        core.save_config(dict(core.DEFAULT_CONFIG, language="fr", update_interval_days=1, network_consent=False))
        self.root = root

    def write(self, document, name="prefs.json"):
        path = self.root / name; path.write_text(json.dumps(document), encoding="utf-8"); return path

    def test_invalid_cadence_and_version_are_refused_before_any_write(self):
        before = Path(core.CONFIG_PATH).read_bytes()
        for cadence in (True, False, "weekly", "7", 3.5, 7.0, 123, 3, -2, None):
            with self.subTest(cadence=cadence), self.assertRaises(ValueError):
                core.import_settings(self.write({"format": "spoolscribe-settings", "version": 1,
                                                 "settings": {"update_interval_days": cadence}}))
        for version in (True, 1.0, 2, "1", None):
            with self.subTest(version=version), self.assertRaises(ValueError):
                core.import_settings(self.write({"format": "spoolscribe-settings", "version": version, "settings": {}}))
        big = self.root / "big.json"; big.write_bytes(b" " * (128 * 1024 + 1))
        for path in (big, self.write("not json"), self.write([1, 2])):
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                core.import_settings(path)
        (self.root / "broken.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            core.import_settings(self.root / "broken.json")
        for bad in ({"favorite_brands": "x"}, {"ui": []}, {"qr_label": {"paper": 5}}, {"nfc_tag_type": "NTAG999"},
                    {"opentag3d_settings": []}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                core.import_settings(self.write({"format": "spoolscribe-settings", "version": 1, "settings": bad}))
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)

    def test_old_25_key_export_is_read_without_consent_or_machine_state(self):
        document = synthetic_v1_export()
        core.import_settings(self.write(document))
        cfg = core.load_config()
        self.assertEqual((cfg["update_interval_days"], cfg["auto_update"]), (7, False))   # false + 7 stays valid
        self.assertIsNot(cfg["network_consent"], True)
        self.assertEqual(cfg["network_sources_revision"], 0)    # sources changed → consent asked again
        self.assertIsNone(cfg["last_update_attempt"]); self.assertIsNone(cfg["last_update_status"])
        self.assertEqual(len(cfg["opentag3d_settings"]), 8)
        self.assertEqual(cfg["favorite_filaments"], ["PB05001"])
        self.assertEqual(cfg["ui"]["view"], "grid")             # the historical API imports layout when present
        self.assertTrue(core.update_due(dict(cfg, last_update_attempt=None)))

    def test_export_is_an_explicit_allow_list_with_optional_layout_and_path(self):
        cfg = core.load_config()
        cfg.update(ui={"view": "grid"}, export_directory=str(self.root), last_update_attempt="2026-01-01T00:00:00",
                   last_update_status="failed", network_consent=True, future_secret_token="never")
        core.save_config(cfg)
        target = self.root / "out.json"
        core.export_settings(target, include_layout=False, include_export_path=False)
        settings = json.loads(target.read_text())["settings"]
        for key in core.MACHINE_STATE_KEYS + ("ui", "export_directory", "future_secret_token"):
            self.assertNotIn(key, settings)
        self.assertEqual(set(settings), set(core.PORTABLE_SETTINGS_KEYS) & set(cfg))
        core.export_settings(target, include_layout=True, include_export_path=True)
        settings = json.loads(target.read_text())["settings"]
        self.assertIn("ui", settings); self.assertIn("export_directory", settings)
        self.assertNotIn("last_update_attempt", settings); self.assertNotIn("future_secret_token", settings)

    def test_consent_in_a_file_is_never_imported(self):
        document = synthetic_v1_export()
        document["settings"].update(network_consent=True, network_sources_revision=core.NETWORK_SOURCES_REVISION,
                                    last_update="2026-11-01T10:00:00")
        core.import_settings(self.write(document))
        self.assertFalse(core.has_network_consent())
        self.assertIsNone(core.load_config()["last_update"])

    def test_preview_lists_replaced_kept_and_ignored_categories(self):
        incoming = core.read_settings_file(self.write(synthetic_v1_export()))
        preview = core.settings_import_preview(incoming)
        names = [c["name"] for c in preview["categories"]]
        self.assertEqual(names, ["catalogue", "filaments", "labels", "colours", "interface", "layout", "export_path"])
        self.assertEqual(preview["kept"], [])
        self.assertEqual(set(preview["machine_state"]), {"last_update_attempt", "last_update_status"})
        self.assertTrue(preview["sources_change"]); self.assertEqual(preview["export_directory"], "/Users/example/Exports")
        minimal = core.settings_import_preview({"language": "es"})
        self.assertEqual([c["name"] for c in minimal["categories"]], ["interface"])
        self.assertIn("filaments", minimal["kept"]); self.assertFalse(minimal["sources_change"])

    def test_invalid_local_cadence_is_reported_and_kept(self):
        raw = json.dumps(dict(core.DEFAULT_CONFIG, update_interval_days="weekly")).encode()
        Path(core.CONFIG_PATH).write_bytes(raw)
        self.assertEqual(core.update_interval_state(), (1, "weekly", False))
        self.assertTrue(core.update_due({"update_interval_days": "weekly", "last_update_attempt": None}))
        core.import_settings(self.write({"format": "spoolscribe-settings", "version": 1, "settings": {"language": "es"}}))
        self.assertEqual(core.load_config()["update_interval_days"], "weekly")   # imported file did not touch it
        self.assertEqual(core.update_interval_state({"update_interval_days": 3}), (3, 3, False))


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self): fixture.GuiTests.setUp(self)

    def dialog(self, inspect, **kwargs):
        from PySide6.QtWidgets import QDialog
        with patch("spoolscribe.app_gui.QDialog.exec", inspect):
            self.window._open_settings(**kwargs)

    def test_free_action_groups_share_one_width_and_column_actions_keep_their_column(self):
        """B18/C21: Enregistrer/Annuler, and the data actions whose rows line up; the catalogue
        actions stretched by their column are left to it. Four languages, natural and 860×600."""
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPushButton, QTabWidget
        self.addCleanup(i18n.set_language, "fr")
        for code in ("fr", "en", "es", "zh_CN"):
            with self.subTest(language=code):
                i18n.set_language(code); seen = {}
                def inspect(dialog):
                    dialog.show(); self.window.app.processEvents()
                    at = lambda b: b.mapTo(dialog, QPoint(0, 0))
                    column = [dialog.findChild(QPushButton, "revokeNetworkConsent")] + [b for b in dialog.findChildren(QPushButton) if b.text() == i18n.tr("Sources du catalogue…")]
                    seen["column"] = (len({b.width() for b in column}), len({at(b).x() for b in column}), column[0].width() > 2 * column[0].sizeHint().width())
                    dialog.findChild(QTabWidget).setCurrentIndex(dialog.findChild(QTabWidget).count() - 1)
                    for size in (None, (860, 600)):
                        if size: dialog.resize(*size)
                        self.window.app.processEvents()
                        bb = dialog.findChild(QDialogButtonBox)
                        pair = [bb.button(QDialogButtonBox.Save), bb.button(QDialogButtonBox.Cancel)]
                        data = [dialog.findChild(QPushButton, n) for n in ("exportPreferences", "importPreferences", "createBackup", "restoreBackup", "revertRestore")]
                        for group in (pair, data):
                            self.assertEqual(len({b.width() for b in group}), 1, [(b.text(), b.width()) for b in group])
                            self.assertGreaterEqual(group[0].width(), max(b.sizeHint().width() for b in group))
                            for b in group:
                                self.assertTrue(dialog.rect().contains(at(b) + QPoint(b.width() - 1, b.height() - 1)), b.text())
                        self.assertEqual({at(data[0]).x(), at(data[2]).x(), at(data[4]).x()}.__len__(), 1)   # rows line up
                        self.assertEqual(at(data[1]).x(), at(data[3]).x())
                    return QDialog.Rejected
                self.dialog(inspect)
                self.assertEqual(seen["column"], (1, 1, True))   # stretched by its column, not forced into a group

    def test_six_tabs_keep_every_option_and_save_cancel_semantics(self):
        from PySide6.QtWidgets import QDialog, QTabWidget, QComboBox, QCheckBox, QLineEdit, QDoubleSpinBox, QPushButton, QDialogButtonBox
        seen = {}
        def cancel(dialog):
            tabs = dialog.findChild(QTabWidget)
            seen["tabs"] = [tabs.tabText(i) for i in range(tabs.count())]
            for name, kind in (("update_interval_days", QComboBox), ("preferred_weight_g", QComboBox),
                               ("preferred_packaging", QComboBox), ("export_directory", QLineEdit), ("orca_overrides", QCheckBox),
                               ("colour_delta_preset", QComboBox), ("colour_delta_max", QDoubleSpinBox), ("interface_language", QComboBox),
                               ("exportPreferences", QPushButton), ("importPreferences", QPushButton), ("createBackup", QPushButton),
                               ("restoreBackup", QPushButton), ("openHardware", QPushButton), ("revokeNetworkConsent", QPushButton)):
                self.assertIsNotNone(dialog.findChild(kind, name), name)
            dialog.findChild(QComboBox, "update_interval_days").setCurrentIndex(
                dialog.findChild(QComboBox, "update_interval_days").findData(7))
            return QDialog.Rejected
        before = Path(core.CONFIG_PATH).read_bytes()
        self.dialog(cancel)
        self.assertEqual(seen["tabs"], ["Catalogue", "Filaments", "Étiquettes et export", "Couleurs", "Interface",
                                        "Données et sauvegardes"])
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)   # Annuler: nothing written

        def save(dialog):
            combo = dialog.findChild(QComboBox, "update_interval_days"); combo.setCurrentIndex(combo.findData(7))
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click(); return dialog.result()
        self.dialog(save)
        self.assertEqual(core.load_config()["update_interval_days"], 7)
        # A new process reads the same saved value (no in-memory illusion).
        env = dict(os.environ, SPOOLSCRIBE_CONFIG_PATH=core.CONFIG_PATH, SPOOLSCRIBE_DATA_HOME=core.DATA_HOME,
                   PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]), QT_QPA_PLATFORM="offscreen")
        done = subprocess.run([sys.executable, "-B", "-c", "from spoolscribe import core;print(core.load_config()['update_interval_days'])"],
                              env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.stdout.strip(), "7", done.stderr)

    def test_unrepresentable_local_cadence_is_shown_and_not_rewritten(self):
        from PySide6.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QLabel
        cfg = core.load_config(); cfg["update_interval_days"] = 3; core.save_config(cfg)
        def save(dialog):
            combo = dialog.findChild(QComboBox, "update_interval_days")
            self.assertNotEqual(combo.currentData(), 0)             # never shown as « À chaque lancement »
            self.assertIsNotNone(dialog.findChild(QLabel, "cadenceWarning"))
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Save).click(); return dialog.result()
        self.dialog(save)
        self.assertEqual(core.load_config()["update_interval_days"], 3)

    def test_data_actions_run_after_the_settings_window_closes(self):
        from PySide6.QtWidgets import QDialog, QPushButton
        for name, method in (("exportPreferences", "_export_settings"), ("importPreferences", "_import_settings"),
                             ("createBackup", "_create_backup"), ("restoreBackup", "_restore_backup"),
                             ("openHardware", "_open_hardware")):
            with self.subTest(name=name), patch.object(self.window, method) as action:
                def click(dialog):
                    dialog.findChild(QPushButton, name).click()
                    action.assert_not_called(); return dialog.result()
                self.dialog(click)
                action.assert_called_once()

    def test_import_ui_shows_a_preview_and_cancel_writes_nothing(self):
        target = Path(self.tmp.name) / "prefs.json"
        target.write_text(json.dumps(synthetic_v1_export()), encoding="utf-8")
        before = Path(core.CONFIG_PATH).read_bytes()
        with patch("spoolscribe.ui_catalogue.QFileDialog.getOpenFileName", return_value=(str(target), "JSON")), \
                patch.object(self.window, "_confirm_settings_import", return_value=False) as preview:
            self.window._import_settings()
        names = [c["name"] for c in preview.call_args.args[0]["categories"]]
        self.assertIn("labels", names)
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)

    def test_export_ui_defaults_exclude_layout_and_path(self):
        target = Path(self.tmp.name) / "out.json"
        cfg = core.load_config(); cfg.update(ui={"view": "grid"}, export_directory=self.tmp.name); core.save_config(cfg)
        with patch.object(self.window, "_ask_settings_export_options", return_value=dict(include_layout=False, include_export_path=False)), \
                patch("spoolscribe.ui_catalogue.QFileDialog.getSaveFileName", return_value=(str(target), "JSON")):
            self.window._export_settings()
        settings = json.loads(target.read_text())["settings"]
        self.assertNotIn("ui", settings); self.assertNotIn("export_directory", settings)

    def test_archive_action_is_named_as_a_single_filament_openspool_file(self):
        self.assertEqual(self.window.act_archive.text(), "Exporter le JSON OpenSpool du filament…")
        self.assertIn("pas une sauvegarde", self.window.act_archive.toolTip())


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class AboutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self): fixture.GuiTests.setUp(self)

    def test_about_announces_real_formats_links_and_optional_donation(self):
        from PySide6.QtWidgets import QDialog, QPushButton, QLabel
        found = {}
        def inspect(dialog):
            found["summary"] = dialog.findChild(QLabel, "aboutSummary").text()
            found["licence"] = dialog.findChild(QLabel, "aboutLicence").text()
            found["credits_visible"] = dialog.findChild(QLabel, "aboutCredits").isVisibleTo(dialog)
            found["buttons"] = {b.objectName(): b.toolTip() for b in dialog.findChildren(QPushButton) if b.objectName()}
            return QDialog.Rejected
        with patch("spoolscribe.app_gui.QDialog.exec", inspect), patch("spoolscribe.app_gui.QDesktopServices.openUrl") as opened:
            self.window._open_about()
        opened.assert_not_called()
        for name in ("OpenSpool 1.0", "OpenTag3D 2.004", "SSQR1", "Companion"):
            self.assertIn(name, found["summary"])
        self.assertNotIn("Snapmaker U1", found["summary"])
        self.assertIn("MIT", found["licence"]); self.assertFalse(found["credits_visible"])
        for name, _label, url in presentation.LINKS:
            self.assertEqual(found["buttons"][name], url)
        self.assertIn("supportProject", found["buttons"])
        self.assertNotIn("docs/privacy", found["buttons"]["projectPrivacy"])

    def test_presentation_metadata_follows_the_implementations_and_readme(self):
        from spoolscribe import opentag3d, qr_transfer
        db = catalogue(); entry = dict(db["_skus"]["PB05001"], sku="PB05001")
        payload = core.build_openspool(entry, db["_products"][entry["product"]])
        self.assertEqual(f"OpenSpool {payload['version']}", presentation.FORMAT_NAMES["openspool"])
        self.assertEqual(presentation.FORMAT_NAMES["opentag3d"], "OpenTag3D " + opentag3d.VERSION)
        self.assertTrue(qr_transfer.PREFIX.startswith(presentation.FORMAT_NAMES["ssqr1"]))
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name in presentation.FORMAT_NAMES.values():
            self.assertIn(name, readme)   # a README/app divergence on formats becomes visible here
        for path in ("docs/PRIVACY.md", "docs/COMPANION.md"):
            self.assertTrue((ROOT / path).is_file())
        # Capabilities announced by the summary have real entry points.
        for module, attribute in ((core, "build_openspool"), (core, "prepare_opentag3d"), (core, "save_personal_filament")):
            self.assertTrue(callable(getattr(module, attribute)))
        from spoolscribe import colour_import, measurement_store
        self.assertTrue(hasattr(measurement_store, "MeasurementRegistry") and colour_import)

    def test_presentation_and_new_ui_texts_exist_in_four_languages(self):
        messages = i18n.catalogue()
        texts = [presentation.ABOUT_SUMMARY, presentation.ABOUT_INDEPENDENCE, *presentation.CREDITS,
                 *(label for _, label, _ in presentation.LINKS), presentation.DONATION[1]]
        from spoolscribe.ui_catalogue import CatalogueUx
        texts += list(CatalogueUx.SETTINGS_CATEGORY_LABELS.values())
        for filename in ("ui_reading.py", "ui_backup.py"):
            path = ROOT / "src/spoolscribe" / filename
            if path.is_file():
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr" \
                            and node.args and isinstance(node.args[0], ast.Constant):
                        texts.append(node.args[0].value)
        for text in texts:
            with self.subTest(text=text[:40]):
                self.assertIn(text, messages)
                self.assertEqual(set(messages[text]), {"en", "es", "zh_CN"})
                for translated in messages[text].values():
                    self.assertEqual(i18n.placeholders(text), i18n.placeholders(translated))
        i18n.set_language("zh_CN")
        try:
            self.assertIn("OpenTag3D 2.004", i18n.tr(presentation.ABOUT_SUMMARY, **presentation.format_arguments()))
        finally:
            i18n.set_language("fr")


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self): fixture.GuiTests.setUp(self)

    def orca(self, values=ORCA_PARTIAL):
        folder = Path(self.tmp.name) / "orca"; folder.mkdir(exist_ok=True)
        (folder / "Polymaker PETG @Snapmaker U1 - OrcaSlicer.json").write_text(json.dumps(values))
        return patch.object(core, "ORCA_DIR", str(folder))

    def open(self):
        w = self.window; w.show(); w._show_detail("PB05001"); w.provenance_toggle.setChecked(True)
        w.comparison_sources_toggle.setChecked(True); w.app.processEvents(); return w

    def test_without_orca_the_summary_is_about_values_not_orca(self):
        w = self.open()
        self.assertEqual(w.comparison_sources_toggle.text(), "Origine et fiabilité")
        self.assertNotIn("Orca", w.comparison_note.text())
        self.assertIn("Origine effective : provenance inconnue", w.comparison_origin.text())
        self.assertIn("couleur déclarée", w.comparison_note.text())

    def test_orca_complement_and_override_are_distinguished_and_match_the_encoder(self):
        db = core.load_db(); entry = dict(db["_skus"]["PB05001"], sku="PB05001")
        product = dict(db["_products"][entry["product"]], density=None)
        db["_products"][entry["product"]] = product; core.save_db(db); self.window.db = core.load_db()
        with self.orca():
            w = self.open()
            self.assertIn("Profil Orca : complète Densité g/cm³", w.comparison_note.text())
            self.assertNotIn("remplace", w.comparison_note.text())
            data = w._comparison()
            self.assertEqual(data["orca"]["completed"], ["density"])
            payload = core.build_openspool(entry, product)
            rows = {r["key"]: r for r in data["rows"]}
            self.assertEqual(rows["density"]["effective"], {"value": payload["density"], "origin": "orca", "orca_mode": "complement"})
            self.assertIn("profil Orca · complète", w.comparison_origin.text())
            cfg = core.load_config(); cfg["orca_overrides"] = True; core.save_config(cfg)
            w._refresh_comparison()
            self.assertIn("Profil Orca : remplace", w.comparison_note.text())
            override = core.build_openspool(entry, product, use_orca_overrides=True)
            rows = {r["key"]: r for r in w._comparison()["rows"]}
            self.assertEqual((rows["min_temp"]["effective"]["value"], rows["min_temp"]["effective"]["orca_mode"]),
                             (override["min_temp"], "override"))

    def test_invalid_orca_profile_message_has_no_local_path(self):
        folder = Path(self.tmp.name) / "orca"; folder.mkdir()
        (folder / "Polymaker PETG @Snapmaker U1 - OrcaSlicer.json").write_text("{invalid")
        with patch.object(core, "ORCA_DIR", str(folder)):
            w = self.open()
            self.assertIn("Profil Orca inutilisable : contenu invalide.", w.comparison_note.text())
            for text in (w.comparison_note.text(), w.comparison_alert.text()):
                self.assertNotIn(str(folder), text); self.assertNotIn(".json", text)

    def test_opentag_explicit_and_unknown_values_are_named(self):
        w = self.open()
        data = copy.deepcopy(w._comparison())
        row = next(r for r in data["rows"] if r["key"] == "min_temp")
        self.assertEqual(w._effective_origin_text(dict(row, effective={"value": 215, "origin": "opentag_settings"})),
                         "réglage OpenTag3D explicite")
        self.assertEqual(w._effective_origin_text(dict(row, effective={"value": None, "origin": "reference"})), "non renseigné")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(fixture.HAS_QT, "Qt unavailable")
class NavigationAndDataTests(unittest.TestCase):
    """B14 B/E/F: one navigation menu, data actions in Settings, explicit unencrypted files, balanced About."""
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()
    def setUp(self): fixture.GuiTests.setUp(self)

    def test_menu_lists_navigation_only_and_every_function_keeps_one_place(self):
        w = self.window
        texts = [a.text() for a in w.main_menu.actions() if not a.isSeparator()]
        # B18/A2: the optional quick welcome can be reopened from the same navigation menu.
        self.assertEqual(texts, ["Mon matériel…", "Paramètres…", "Accueil rapide…", "À propos de SpoolScribe"])
        self.assertIsNone(w.menu_btn.menu())   # anchored by the window, not a free tool-button popup
        # The single-filament OpenSpool JSON is in that filament's export details.
        w.current_sku = "PB05001"; w._show_detail("PB05001"); w._refresh_export_journey()
        self.assertTrue(w.export_details.archive_button.isEnabled())
        self.assertIn("OpenSpool", w.export_details.archive_button.text())
        with patch.object(w, "_generate") as generate:
            w.export_details.archive_button.click()
        generate.assert_called_once_with(mode="archive")

    def test_menu_opens_inside_the_window_and_closes_with_escape(self):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        w = self.window; screen = w.screen().availableGeometry()
        w.setGeometry(screen.left() + 10, screen.top() + 30, min(860, screen.width() - 20), min(560, screen.height() - 40)); w.show(); w.app.processEvents()
        w.menu_btn.setFocus(); QTest.keyClick(w.menu_btn, Qt.Key_Space); w.app.processEvents()
        menu = w.main_menu
        self.assertTrue(menu.isVisible())
        frame, geometry = w.frameGeometry(), menu.geometry()
        self.assertGreaterEqual(geometry.left(), max(frame.left(), screen.left()))
        self.assertLessEqual(geometry.right(), min(frame.right(), screen.right()))
        # Right-aligned under the button (or against the screen edge when the window overflows it).
        button_right = w.menu_btn.mapToGlobal(w.menu_btn.rect().bottomRight()).x()
        self.assertLessEqual(abs(geometry.right() - min(button_right, screen.right())), 2)
        self.assertGreater(geometry.top(), w.menu_btn.mapToGlobal(w.menu_btn.rect().topLeft()).y())
        QTest.keyClick(menu, Qt.Key_Escape); w.app.processEvents()
        self.assertFalse(menu.isVisible())

    def test_data_tab_shows_unencrypted_beside_each_creating_action(self):
        from PySide6.QtWidgets import QLabel, QPushButton
        seen = {}
        def inspect(dialog):
            dialog.show(); dialog.app = None
            from PySide6.QtWidgets import QTabWidget
            tabs = dialog.findChild(QTabWidget); tabs.setCurrentIndex(tabs.count() - 1); self.window.app.processEvents()
            badges = {b.property("badgeFor"): b for b in dialog.findChildren(QLabel, "unencryptedBadge")}
            seen["badges"] = sorted(badges)
            for name, badge in badges.items():
                button = dialog.findChild(QPushButton, name)
                seen[name] = (badge.isVisible(), badge.text(), abs(badge.geometry().center().y() - button.geometry().center().y()) <= 4,
                              badge.geometry().left() > button.geometry().right())
            seen["intro"] = dialog.findChild(QLabel, "dataIntro").text()
            seen["prefs"] = dialog.findChild(QLabel, "preferencesScope").text()
            seen["backup"] = dialog.findChild(QLabel, "backupScope").text()
            dialog.hide(); return 0
        with patch("spoolscribe.app_gui.QDialog.exec", inspect):
            self.window._open_settings()
        self.assertEqual(seen["badges"], ["createBackup", "exportPreferences"])
        for name in ("createBackup", "exportPreferences"):
            self.assertEqual(seen[name], (True, "Non chiffré", True, True))
        self.assertIn("non enregistrées", seen["intro"]); self.assertIn("Annuler n’écrit rien", seen["intro"])
        self.assertIn("JSON en clair, partiel", seen["prefs"]); self.assertIn("ZIP en clair, plus complet", seen["backup"])
        self.assertIn("chemins locaux", seen["backup"])
        for text in seen["prefs"], seen["backup"], seen["intro"]:
            self.assertNotIn("Excel", text)

    def test_unsaved_settings_are_not_exported_and_cancel_writes_nothing(self):
        from PySide6.QtWidgets import QComboBox, QPushButton
        target = Path(self.tmp.name) / "prefs.json"
        before = Path(core.CONFIG_PATH).read_bytes()
        def change_then_export(dialog):
            language = dialog.findChild(QComboBox, "interface_language")
            language.setCurrentIndex(language.findData("es"))       # unsaved change
            dialog.findChild(QPushButton, "exportPreferences").click(); return dialog.result()
        # Options cancelled, then picker cancelled: nothing is written anywhere.
        for options, picked in ((None, ("", "")), (dict(include_layout=False, include_export_path=False), ("", ""))):
            with self.subTest(options=options), patch.object(self.window, "_ask_settings_export_options", return_value=options), \
                    patch("spoolscribe.ui_catalogue.QFileDialog.getSaveFileName", return_value=picked) as picker, \
                    patch("spoolscribe.app_gui.QDialog.exec", change_then_export):
                self.window._open_settings()
            self.assertEqual(picker.called, options is not None)
            self.assertFalse(target.exists()); self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), before)
        with patch.object(self.window, "_ask_settings_export_options", return_value=dict(include_layout=False, include_export_path=False)), \
                patch("spoolscribe.ui_catalogue.QFileDialog.getSaveFileName", return_value=(str(target), "JSON")), \
                patch("spoolscribe.app_gui.QDialog.exec", change_then_export):
            self.window._open_settings()
        self.assertEqual(json.loads(target.read_text())["settings"]["language"], "fr")   # saved value, not the unsaved one
        self.assertEqual(core.load_config()["language"], "fr")

    def test_export_options_warn_visibly_before_the_file_is_created(self):
        from PySide6.QtWidgets import QCheckBox, QLabel
        seen = {}
        def inspect(dialog):
            dialog.show(); self.window.app.processEvents()
            warning, path = dialog.findChild(QLabel, "unencryptedWarning"), dialog.findChild(QLabel, "exportPathWarning")
            seen["warning"] = (warning.isVisible(), warning.text())
            seen["path_before"] = path.isVisible()
            dialog.findChild(QCheckBox, "includeExportPath").setChecked(True); self.window.app.processEvents()
            seen["path_after"] = path.isVisible()
            seen["checked"] = [b.isChecked() for b in (dialog.findChild(QCheckBox, "includeLayout"),)]
            dialog.hide(); return 0
        with patch("spoolscribe.ui_catalogue.QDialog.exec", inspect):
            self.assertIsNone(self.window._ask_settings_export_options())
        self.assertTrue(seen["warning"][0]); self.assertIn("Non chiffré", seen["warning"][1])
        self.assertFalse(seen["path_before"]); self.assertTrue(seen["path_after"]); self.assertEqual(seen["checked"], [False])

    def test_about_order_balanced_resources_and_visible_optional_support(self):
        from PySide6.QtWidgets import QPushButton, QLabel, QFrame, QDialogButtonBox
        from spoolscribe.ui_widgets import CONTROL_HEIGHT
        seen = {}
        def inspect(dialog):
            dialog.show(); self.window.app.processEvents()
            order = [dialog.layout().itemAt(i).widget() or dialog.layout().itemAt(i).layout() for i in range(dialog.layout().count())]
            seen["order"] = [item.objectName() for item in order if item.objectName()]
            seen["last"] = isinstance(order[-1], QDialogButtonBox)
            buttons = [b for b in dialog.findChildren(QPushButton) if b.objectName() in
                       {n for n, _, _ in presentation.LINKS} | {"checkAppUpdate"}]
            seen["count"] = len(buttons)
            seen["heights"] = {b.height() for b in buttons}
            for width, key in ((640, "wide"), (420, "narrow")):
                dialog.resize(width, dialog.height()); self.window.app.processEvents()
                seen[key] = (len({b.width() for b in buttons}), len({b.x() for b in buttons}))
            support = dialog.findChild(QPushButton, "supportProject")
            seen["support"] = (support.isVisible(), support.width() >= dialog.findChild(QFrame, "supportCard").width() - 30)
            seen["data"] = [n for n in ("exportPreferences", "createBackup", "restoreBackup", "importPreferences")
                            if dialog.findChild(QPushButton, n)]
            dialog.hide(); return 0
        with patch("spoolscribe.app_gui.QDialog.exec", inspect), patch("spoolscribe.app_gui.QDesktopServices.openUrl") as opened:
            self.window._open_about()
        opened.assert_not_called()
        # Identity, description, credits, resources, optional support, then Close.
        self.assertEqual(seen["order"], ["aboutSummary", "aboutLicence", "aboutCreditsToggle", "aboutCredits", "sectionTitle",
                                         "aboutResources", "supportCard"])
        self.assertTrue(seen["last"])
        self.assertEqual(seen["count"], 6); self.assertEqual(seen["heights"], {CONTROL_HEIGHT})
        self.assertEqual(seen["wide"], (1, 2))     # one width, two columns
        self.assertEqual(seen["narrow"][1], 1)     # one column in a narrow window
        self.assertEqual(seen["support"], (True, True)); self.assertEqual(seen["data"], [])
        with patch.object(self.window, "_check_app_update") as check, patch("spoolscribe.app_gui.QDialog.exec",
                lambda dialog: dialog.findChild(QPushButton, "checkAppUpdate").click() or 0):
            self.window._open_about()
        check.assert_called_once()
