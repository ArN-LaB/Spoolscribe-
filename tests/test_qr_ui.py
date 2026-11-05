"""QR window (SPOOLSCRIBE-QR-2026-001): secondary action, frozen message, files and simulated printing.

No print job is sent: the printer is a PDF device in the test folder or a refusal before any job.
"""
import ast
import json
import re
from pathlib import Path
import unittest
from unittest.mock import patch

from spoolscribe import core, i18n, opentag3d, qr_layout, qr_transfer
from tests import test_gui as fixture
from tests.support import ROOT

if fixture.HAS_QT:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtGui import QPageSize
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton
    from spoolscribe import ui_qr
    from spoolscribe.ui_widgets import CONTROL_HEIGHT


def files_under(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


@unittest.skipUnless(fixture.HAS_QT, "PySide6 non installé : fenêtre QR non mesurée")
class QrWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.GuiTests.setUpClass()

    def setUp(self):
        fixture.GuiTests.setUp(self)
        i18n.set_language("fr")
        self.addCleanup(i18n.set_language, "fr")
        w = self.window
        w.resize(1280, 800); w.show()
        w.current_sku = "PB05001"; w._show_detail("PB05001"); w.app.processEvents()
        self.warnings = patch("spoolscribe.ui_qr.QMessageBox.warning").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(lambda: getattr(w, "_qr_window", None) and self.close_quietly(w._qr_window))

    def open_qr(self, **kwargs):
        qr = ui_qr.QrWindow(ui_qr.snapshot(self.window), self.window, **kwargs)
        self.addCleanup(self.close_quietly, qr)
        return qr

    @staticmethod
    def close_quietly(widget):
        try:
            widget.close()
        except RuntimeError:  # Already deleted on close (WA_DeleteOnClose)
            pass

    def select_opentag(self):
        w = self.window
        w.printer.setCurrentIndex(w.printer.findData("opentag3d"))
        product = core.get_sku_view(w.db, "PB05001").product_data
        core.save_opentag_settings("PB05001", dict(print_temp=product["min_temp"], bed_temp=product["bed_min_temp"], chamber_temp=0, weight=1000))
        w._refresh_nfc_capacity(); w.app.processEvents()
        self.assertEqual((w.nfc_format.currentData(), w._primary_kind), ("opentag3d", "export"))

    # ── QR-08: one primary action, QR secondary, same verdict as the export ──
    def test_secondary_action_beside_the_existing_ones(self):
        w = self.window
        self.assertEqual(w.btn_qr.objectName(), "secondary")
        self.assertIn("SpoolScribe Companion", w.btn_qr.text())
        self.assertTrue(w.btn_qr.isEnabled())
        # The catalogue update button is the sidebar's own action; the export panel keeps one primary.
        primary = [b for b in w.detail_footer.findChildren(QPushButton) if b.objectName() == "primary" and b.isVisible()]
        self.assertEqual(primary, [w.btn_generate])
        w.resize(1450,850);w.splitter.setSizes([250,450,700]);w.app.processEvents();w.app.processEvents()
        self.assertTrue(w._export_actions_inline)
        left = lambda b: b.mapTo(w, b.rect().topLeft()).x()
        right = lambda b: b.mapTo(w, b.rect().topRight()).x()
        top = lambda b: b.mapTo(w, b.rect().topLeft()).y()
        # Export and QR share the action row when the pane is wide enough.
        self.assertEqual(top(w.btn_inspect), top(w.btn_open_out))
        self.assertEqual(top(w.btn_qr), top(w.btn_generate))
        self.assertGreater(left(w.btn_qr), right(w.btn_generate))
        self.assertEqual((left(w.btn_generate), right(w.btn_qr)), (left(w.btn_inspect), right(w.btn_open_out)))
        self.assertEqual(w.btn_qr.height(), w.btn_generate.height())
        self.assertEqual(w.btn_inspect.height(), w.btn_open_out.height())
        for width in (1100, 1280):
            w.resize(width, 800); w.app.processEvents()
            for button in (w.btn_inspect, w.btn_qr, w.btn_open_out):
                self.assertGreaterEqual(button.width(), max(button.fontMetrics().horizontalAdvance(line) for line in button.text().splitlines()) + 12, (width, button.text()))

    def test_every_blocked_export_blocks_the_qr(self):
        w = self.window

        def blocked(label):
            w.app.processEvents()
            self.assertFalse(w.btn_qr.isEnabled(), label)
            self.assertNotEqual((w._primary_kind, w.btn_generate.isEnabled()), ("export", True), label)
            with self.assertRaises(ValueError):
                ui_qr.snapshot(w)
            self.assertIsNone(w._open_qr())
        w.current_sku = "FB04001"; w._show_detail("FB04001"); blocked("unknown HEX")
        w.current_sku = "PB05001"; w._show_detail("PB05001"); self.assertTrue(w.btn_qr.isEnabled())
        w.nfc_reserve.setValue(w.nfc_reserve.maximum()); blocked("capacity")
        w.nfc_reserve.setValue(0); self.assertTrue(w.btn_qr.isEnabled())
        w.firmware.setCurrentIndex(w.firmware.findData("unknown")); blocked("unknown configuration")
        w.firmware.setCurrentIndex(w.firmware.findData("paxx12")); self.assertTrue(w.btn_qr.isEnabled())
        w._edit_physical(); field = w.draft_fields["min_temp"]; field.setText("235"); field.textEdited.emit("235"); blocked("draft")
        w._cancel_draft(); w._refresh_nfc_capacity(); self.assertTrue(w.btn_qr.isEnabled())
        w.current_sku = None; w._refresh_nfc_capacity(); blocked("no selection")

    def test_opentag_settings_missing_block_the_qr(self):
        w = self.window
        w.printer.setCurrentIndex(w.printer.findData("opentag3d")); w.app.processEvents()
        self.assertEqual(w._primary_kind, "opentag_settings")
        self.assertFalse(w.btn_qr.isEnabled())

    # ── QR-01 through the real window: the export's own message ──
    def test_openspool_snapshot_is_the_export_ndef(self):
        w = self.window
        for profile in ("essential", "full"):
            with self.subTest(profile=profile):
                w.nfc_profile.setCurrentIndex(w.nfc_profile.findData(profile)); w.app.processEvents()
                snap = ui_qr.snapshot(w)
                text = core.serialize_openspool(w._build_payload(), **w._nfc_options())
                self.assertEqual(snap.ndef, qr_transfer.openspool_ndef(text.encode("utf-8")))
                self.assertEqual(snap.ndef[-len(text.encode()):], w._export_bytes())
                self.assertEqual((snap.protocol, snap.nfc_profile, snap.tag_type), (qr_transfer.OPENSPOOL, profile, "NTAG216"))
                self.assertEqual(qr_transfer.decode(qr_layout.make_symbol(snap.protocol, snap.ndef).text).ndef, snap.ndef)

    def test_opentag_snapshot_is_the_ndef_never_the_writer_container(self):
        self.select_opentag()
        w = self.window
        w.opentag_output.setCurrentIndex(w.opentag_output.findData("nfctools-desktop"))  # Explicit legacy container, not the new GUI default.
        prepared = w._prepare_opentag()
        snap = ui_qr.snapshot(w)
        self.assertEqual(snap.ndef, opentag3d.ndef(prepared.payload))
        self.assertEqual((len(prepared.payload), len(snap.ndef), snap.ndef[:3]), (224, 248, bytes([0xD2, 0x15, 0xE0])))
        self.assertNotEqual(snap.ndef, prepared.data)  # NFC Tools profile file, not a second record
        self.assertEqual(dict(snap.settings)["chamber_temp"], 0)

    def test_window_keeps_its_snapshot_and_reopening_takes_a_fresh_one(self):
        w = self.window
        first = w._open_qr()
        frozen = (first.snap, first.file_data("svg"), first.file_data("png"))
        other = None
        for sku in w.db["_skus"]:
            w.current_sku = sku; w._show_detail(sku)
            if sku != "PB05001" and w._primary_kind == "export" and w.btn_generate.isEnabled():
                other = sku
                break
        self.assertIsNotNone(other)
        w.tag_type.setCurrentIndex(w.tag_type.findData("NTAG215")); w.nfc_profile.setCurrentIndex(w.nfc_profile.findData("full"))
        w.app.processEvents()
        self.assertEqual((first.snap, first.file_data("svg"), first.file_data("png")), frozen)
        self.assertIn("PB05001", first.subtitle.text())
        w.tag_type.setCurrentIndex(w.tag_type.findData("NTAG216")); w.nfc_profile.setCurrentIndex(w.nfc_profile.findData("auto"))
        w.app.processEvents()
        self.assertTrue(w.btn_qr.isEnabled())
        second = w._open_qr()
        self.assertIsNot(second, first)
        self.assertEqual(second.snap.sku, other)
        self.assertNotEqual(second.snap.ndef, frozen[0].ndef)
        self.assertFalse(first.isVisible())

    def test_opening_generates_no_file(self):
        root = Path(core.DATA_HOME)
        before = files_under(root)
        qr = self.window._open_qr(); self.window.app.processEvents()
        self.assertIsNotNone(qr)
        self.assertEqual(files_under(root), before)

    # ── QR-06/QR-09: files through the native dialog, honest outcomes ──
    def test_save_cancel_error_and_success(self):
        qr = self.open_qr()
        root = Path(core.DATA_HOME)
        before = files_under(root)
        with patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=("", "")) as dialog:
            self.assertIsNone(qr._save("png"))
        default = dialog.call_args[0][2]
        self.assertTrue(Path(default).name.startswith("PB05001_") and default.endswith("_openspool_qr.png"))
        self.assertEqual(files_under(root), before)
        self.assertNotIn("enregistrée", qr.status.text())
        target = root / "sortie" / "code"
        target.parent.mkdir()
        with patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=(str(target), "")), \
                patch("spoolscribe.ui_qr.core.db_io.atomic_write", side_effect=OSError("disque plein")):
            self.assertIsNone(qr._save("svg"))
        self.assertFalse(target.with_suffix(".svg").exists())
        self.assertIn("disque plein", self.warnings.call_args[0][2])
        self.assertEqual(qr.status.text(), "Aucun fichier enregistré.")
        for kind in ("png", "svg"):
            with patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=(str(target), "")):
                path = qr._save(kind)
            self.assertEqual(path, str(target) + "." + kind)
            self.assertEqual(Path(path).read_bytes(), qr.file_data(kind))
            self.assertEqual(qr.status.text(), f"Image enregistrée : {path}")

    def test_png_keeps_the_label_size_when_printable(self):
        qr = self.open_qr()
        qr.support.setCurrentIndex(qr.support.findData("label-50x50"))
        plan = qr.plan()
        self.assertEqual(plan.status, "ready")
        from PySide6.QtGui import QImage
        image = QImage.fromData(qr.file_data("png"))
        dpi = round(image.dotsPerMeterX() * 0.0254)
        self.assertAlmostEqual(image.width() / dpi * 25.4, plan.qr_mm, delta=0.01)
        self.assertEqual(image.width() % qr.symbol.total_modules, 0)

    # ── QR-07: simulated devices, nothing sent to a real printer ──
    def pdf_printer(self, name="label.pdf"):
        path = Path(core.DATA_HOME) / name
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(path))
        return printer, path

    def printable_window(self, dialog, printer=None, **kwargs):
        printer = printer or self.pdf_printer()[0]
        qr = self.open_qr(printer_factory=lambda: printer, print_dialog=dialog, **kwargs)
        qr.support.setCurrentIndex(qr.support.findData("label-50x50"))
        self.assertTrue(qr.btn_print.isEnabled())
        return qr

    def test_print_success_renders_whole_dots_on_the_accepted_page(self):
        printer, path = self.pdf_printer()
        calls = []
        qr = self.printable_window(lambda p, parent: calls.append(p.resolution()) or True, printer)
        self.assertTrue(qr._print())
        self.assertEqual(calls, [203])
        # A PDF device is named as such: neither « transmitted » nor « printed ».
        self.assertEqual(qr.status.text(), f"Fichier PDF écrit (203 ppp, QR de {ui_qr._mm(qr.last_device_plan.qr_mm)} mm) : {path}. Ce n’est pas une impression.")
        media = [float(v) for v in re.search(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)", path.read_bytes()).groups()]
        self.assertTrue(all(abs(v * 25.4 / 72 - 50) <= 0.2 for v in media), media)
        plan = qr.last_device_plan
        self.assertEqual((plan.dpi, plan.status), (203, "ready"))
        document = QPdfDocument(); document.load(str(path))
        size = document.pagePointSize(0)
        pixels = QSize(round(size.width() / 72 * 203), round(size.height() / 72 * 203))
        image = document.render(0, pixels)
        paint = printer.pageLayout().paintRectPixels(203)
        x0, y0 = paint.x() + plan.qr_rect[0], paint.y() + plan.qr_rect[1]
        m = plan.dots_per_module
        for y, row in enumerate(qr.symbol.modules):
            for x, dark in enumerate(row):
                value = image.pixelColor(x0 + (x + 4) * m + m // 2, y0 + (y + 4) * m + m // 2).value()
                self.assertEqual(value < 128, dark, (x, y))
        for i in range(4 * m):  # Quiet zone stays white
            self.assertGreater(image.pixelColor(x0 + i, y0 + plan.qr_rect[2] // 2).value(), 200)

    def test_print_cancel_no_printer_refused_format_and_painter_errors(self):
        # Cancel: nothing written, no success.
        printer, path = self.pdf_printer("cancel.pdf")
        qr = self.printable_window(lambda p, parent: False, printer)
        self.assertFalse(qr._print()); self.assertFalse(path.exists())
        self.assertEqual(qr.status.text(), "Impression annulée : rien n’a été envoyé.")
        # No printer in the system: the dialog is not even opened.
        opened = []
        qr = self.open_qr(print_dialog=lambda p, parent: opened.append(p) or True, printer_names=lambda: [])
        qr.support.setCurrentIndex(qr.support.findData("label-50x50"))
        self.assertFalse(qr._print()); self.assertEqual(opened, [])
        self.assertIn("Aucune imprimante", qr.status.text())
        # Driver (or user) switched to another format: refused before any page.
        printer, path = self.pdf_printer("a4.pdf")
        qr = self.printable_window(lambda p, parent: p.setPageSize(QPageSize(QPageSize.A4)) or True, printer)
        self.assertFalse(qr._print()); self.assertFalse(path.exists())
        self.assertIn("n’a pas accepté le format 50 × 50 mm", qr.status.text())
        # QPainter cannot start on the device.
        printer = QPrinter(QPrinter.HighResolution); printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(Path(core.DATA_HOME) / "missing" / "dir" / "x.pdf"))
        qr = self.printable_window(lambda p, parent: True, printer)
        with patch("spoolscribe.ui_qr.QPainter.begin", return_value=False):
            self.assertFalse(qr._print())
        self.assertIn("n’a pas démarré", qr.status.text())
        self.assertEqual(self.warnings.call_count, 3)

    def test_driver_resolution_is_used_and_too_dense_is_never_sent(self):
        printer, path = self.pdf_printer("300.pdf")
        qr = self.printable_window(lambda p, parent: p.setResolution(300) or True, printer)
        self.assertTrue(qr._print())
        self.assertEqual(qr.last_device_plan.dpi, 300)
        self.assertEqual(qr.last_device_plan.dots_per_module, min(qr.last_device_plan.fitting_dots, 11))
        # D101 profile: the essential OpenSpool QR is refused, before any dialog.
        cfg = core.load_config(); cfg["qr_label"] = {}; core.save_config(cfg)
        opened = []
        qr = self.open_qr(printer_factory=lambda: self.pdf_printer("dense.pdf")[0], print_dialog=lambda p, parent: opened.append(1) or True)
        self.assertEqual(qr.support.currentData(), "screen")
        self.assertIsNone(qr.plan())
        self.assertFalse(qr.btn_print.isEnabled())
        self.assertFalse(qr._print()); self.assertEqual(opened, [])
        self.assertIn("support", qr.status.text())
        self.assertFalse((Path(core.DATA_HOME) / "dense.pdf").exists())
        # A driver lowering the resolution after the dialog makes the same label too dense.
        printer, path = self.pdf_printer("low.pdf")
        qr = self.printable_window(lambda p, parent: p.setResolution(100) or True, printer)
        self.assertFalse(qr._print()); self.assertFalse(path.exists())
        self.assertIn("(100 ppp)", qr.status.text())

    def test_small_format_is_an_explicit_choice(self):
        self.select_opentag()
        qr = self.open_qr()
        qr.support.setCurrentIndex(qr.support.findData('custom'))
        for key,value in [('width_mm',25),('height_mm',50),('margin',1)]:qr.custom_fields[key].setValue(value)
        qr.custom_dpi.setValue(203)
        self.assertEqual((qr.symbol.version, qr.plan().status, qr.plan().reason), (8, "refused", "needs_small"))
        self.assertIn("petit format", qr.result.text().lower())
        qr.small.setChecked(True)
        self.assertEqual((qr.plan().status, qr.plan().dots_per_module), ("small", 3))
        self.assertIn("Essai de lecture requis", qr.result.text())
        self.assertTrue(qr.btn_print.isEnabled())
        qr.error.setCurrentIndex(qr.error.findData("Q"))
        self.assertEqual((qr.symbol.error, qr.symbol.version, qr.plan().status), ("Q", 10, "refused"))
        self.assertEqual(qr.snap.ndef, qr_transfer.decode(qr.symbol.text).ndef)  # Same message, no field removed

    # ── QR-09: window behaviour, languages and themes ──
    def test_resizable_keyboard_and_folded_details(self):
        qr = self.open_qr(); qr.show(); qr.app = self.window.app
        self.assertTrue(qr.details.isHidden())
        qr.details_toggle.click(); self.assertFalse(qr.details.isHidden())
        sizes = []
        for size in ((440, 560), (900, 1000)):
            qr.resize(*size); self.window.app.processEvents()
            sizes.append(qr.canvas.scale())
        self.assertLess(sizes[0], sizes[1])
        self.assertGreaterEqual(sizes[0], 1)
        for button in (qr.btn_png, qr.btn_svg, qr.btn_print, qr.details_toggle):
            self.assertEqual(button.height(), CONTROL_HEIGHT)
            self.assertNotEqual(button.focusPolicy(), Qt.NoFocus)
        self.assertEqual(qr.canvas.focusPolicy(), Qt.StrongFocus)
        QTest.keyClick(qr, Qt.Key_Escape)
        self.assertFalse(qr.isVisible())  # Deleted on the next event loop turn

    def test_four_languages_and_a_white_code_in_dark_theme(self):
        texts = {}
        for language in ("fr", "en", "es", "zh_CN"):
            i18n.set_language(language)
            qr = self.open_qr()
            texts[language] = (qr.btn_png.text(), qr.btn_print.text(), qr.details_toggle.text(), qr.result.text(), qr.companion.text())
            self.assertIn(qr.snap.format_label.split(" · ")[0], qr.subtitle.text())
            qr.close()
        for language in ("en", "es", "zh_CN"):
            for french, translated in zip(texts["fr"], texts[language]):
                self.assertNotEqual(french, translated, language)
        i18n.set_language("fr")
        with patch("spoolscribe.app_gui.is_dark_theme", return_value=True):
            self.window._apply_theme()
        qr = self.open_qr(); qr.resize(500, 700); qr.show(); self.window.app.processEvents()
        image = qr.canvas.grab().toImage()
        self.assertEqual(image.pixelColor(2, 2).name(), "#ffffff")
        self.assertLess(qr.palette().window().color().value(), 128)  # The window itself follows the dark theme

    def test_every_qr_string_is_translated(self):
        messages = i18n.catalogue()
        for filename in ("ui_qr.py",):
            for node in ast.walk(ast.parse((ROOT / "src/spoolscribe" / filename).read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args and isinstance(node.args[0], ast.Constant):
                    self.assertIn(node.args[0].value, messages, f"{filename}:{node.lineno}")
        for name, _ in qr_layout.PRESETS.values():
            self.assertIn(name, messages)
        for source in ("Afficher le QR Code…", "Disponible lorsque l’export NFC est possible.", "Les marges ne laissent aucune zone imprimable.",
                       "Message trop volumineux pour un seul QR Code à ce niveau de correction."):
            self.assertEqual(set(messages[source]), {"en", "es", "zh_CN"})

    # ── QR-10: dedicated, persistent and importable settings ──
    def test_paper_settings_persist_and_follow_settings_files(self):
        before = core.load_config()
        qr = self.open_qr()
        qr.support.setCurrentIndex(qr.support.findData("a4")); qr.small.setChecked(True)
        saved = core.load_config()
        self.assertEqual(saved["qr_label"], {"preset": "a4", "small_format": True, "error": "M"})
        self.assertEqual({k: v for k, v in saved.items() if k != "qr_label"}, {k: v for k, v in before.items() if k != "qr_label"})
        again = self.open_qr()
        self.assertEqual((again.support.currentData(), again.small.isChecked()), ("screen", True))  # Paper settings survive; a new transfer always opens digitally.
        target = Path(core.DATA_HOME) / "settings.json"
        core.export_settings(target)
        cfg = core.load_config(); cfg["qr_label"] = {}; core.save_config(cfg)
        core.import_settings(target)
        self.assertEqual(core.load_config()["qr_label"]["preset"], "a4")
        document = json.loads(target.read_text(encoding="utf-8"))
        document["settings"]["qr_label"] = {"preset": "custom", "custom": {"width_mm": 1}}
        target.write_text(json.dumps(document), encoding="utf-8")
        raw = Path(core.CONFIG_PATH).read_bytes()
        with self.assertRaises(ValueError):
            core.import_settings(target)
        self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), raw)
        cfg = core.load_config(); cfg["qr_label"] = {"preset": "elsewhere"}; core.save_config(cfg)
        self.assertEqual(self.open_qr().support.currentData(), "screen")  # Invalid stored section: safe default

    def test_custom_support_is_bounded(self):
        qr = self.open_qr()
        qr.support.setCurrentIndex(qr.support.findData("custom"))
        self.assertFalse(qr.custom.isHidden())
        qr.custom_fields["width_mm"].setValue(60); qr.custom_fields["height_mm"].setValue(80); qr.custom_dpi.setValue(300)
        self.assertEqual(core.load_config()["qr_label"]["custom"]["width_mm"], 60)
        self.assertEqual(qr.plan().status, "ready")
        qr.custom_fields["margin"].setValue(40)  # Leaves no printable area
        self.assertIsNone(qr.plan())
        self.assertIn("Support invalide", qr.result.text())
        self.assertFalse(qr.btn_print.isEnabled())
        self.assertEqual(core.load_config()["qr_label"]["custom"]["margins_mm"][0], qr_layout.profile_to_dict(qr_layout.LabelProfile(60, 80, (1.0,) * 4, 300))["margins_mm"][0])


if __name__ == "__main__":
    unittest.main()
