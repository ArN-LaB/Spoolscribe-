"""QR phase D (SPOOLSCRIBE-QR-2026-001, 06): reproductions of F1–F5 found by QA 05.

F1 checks what the window really shows (visible region and a capture of the whole
window), not a grab of the canvas alone, which also paints pixels hidden by its parent.
"""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from spoolscribe import core, i18n, qr_layout, qr_transfer
from tests import test_gui as fixture
from tests.support import ROOT

VECTORS = json.loads((ROOT / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))["vectors"]

if fixture.HAS_QT:
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QMessageBox, QPushButton, QStyle, QStyleOptionButton, QToolButton
    from spoolscribe import ui_qr


def large_compressible_message():
    """Valid OpenSpool NDEF of 3 243 bytes: raw text above 4 296 characters, zlib text far below."""
    raw = bytes.fromhex(VECTORS["catalogue-essential"]["hex"])
    payload = json.loads(raw[3 + 16:])
    text = json.dumps(dict(payload, product="X" * 3000), separators=(",", ":"), ensure_ascii=False)
    return qr_transfer.openspool_ndef(text.encode("utf-8"))


class CompressedCandidateTests(unittest.TestCase):
    """F5: a raw candidate above its bound must not stop the compressed one."""

    def test_compressed_only_message_gets_a_symbol(self):
        message = large_compressible_message()
        self.assertEqual(len(message), 3243)
        with self.assertRaises(qr_transfer.TransferError):
            qr_transfer.envelope(qr_transfer.OPENSPOOL, message, qr_transfer.RAW)
        self.assertLess(len(qr_transfer.envelope(qr_transfer.OPENSPOOL, message, qr_transfer.ZLIB)), 400)
        import segno
        for error in ("M", "Q"):
            with self.subTest(error=error):
                symbol = qr_layout.make_symbol(qr_transfer.OPENSPOOL, message, error)
                self.assertEqual(symbol.codec, qr_transfer.ZLIB)
                self.assertEqual(qr_transfer.decode(symbol.text).ndef, message)
                expected = segno.make(qr_transfer.envelope(qr_transfer.OPENSPOOL, message, qr_transfer.ZLIB), error=error.lower(),
                                      mode="alphanumeric", micro=False, boost_error=False).version
                self.assertEqual(symbol.version, expected)

    def test_business_errors_and_bounds_are_still_raised(self):
        wrong = qr_transfer.mime_record(b"application/opentag3d", b"{}")
        with self.assertRaises(qr_transfer.TransferError) as caught:
            qr_layout.make_symbol(qr_transfer.OPENSPOOL, wrong)
        self.assertIn("MIME", str(caught.exception))  # Not hidden behind a size message
        raw = bytes.fromhex(VECTORS["catalogue-essential"]["hex"])
        payload = json.loads(raw[3 + 16:])
        for size, refused in ((4096, False), (4097, True)):
            body = json.dumps(dict(payload, product=""), separators=(",", ":")).encode()
            body = json.dumps(dict(payload, product="Y" * (size - 6 - 16 - len(body))), separators=(",", ":")).encode()
            message = qr_transfer.openspool_ndef(body)
            self.assertEqual(len(message), size)
            with self.subTest(size=size):
                if refused:
                    with self.assertRaises(qr_transfer.TransferError):
                        qr_layout.make_symbol(qr_transfer.OPENSPOOL, message)
                else:
                    self.assertEqual(qr_transfer.decode(qr_layout.make_symbol(qr_transfer.OPENSPOOL, message).text).ndef, message)
        import random
        rng = random.Random(5)
        noise = "".join(chr(rng.randrange(0x4E00, 0x9FFF)) for _ in range(1200))
        message = qr_transfer.openspool_ndef(json.dumps(dict(payload, product=noise), ensure_ascii=False).encode())
        with self.assertRaises(qr_transfer.TransferError) as caught:
            qr_layout.make_symbol(qr_transfer.OPENSPOOL, message)
        self.assertIn("trop volumineux", str(caught.exception))
        for name, entry in VECTORS.items():  # Tie rule and versions of the normative vectors unchanged
            symbol = qr_layout.make_symbol(entry["protocol"], bytes.fromhex(entry["hex"]))
            self.assertEqual(symbol.codec, qr_transfer.ZLIB, name)


class SettingsTypeTests(unittest.TestCase):
    """F3: wrong JSON types are refused as ValueError, never TypeError."""

    def test_wrong_types_are_value_errors(self):
        bad = [None, [], "d101-25x50", True, 3, {"preset": []}, {"preset": {}}, {"preset": None}, {"preset": True},
               {"preset": 1}, {"error": []}, {"error": {}}, {"error": None}, {"small_format": []}, {"small_format": "yes"},
               {"preset": "custom", "custom": []}, {"preset": "custom", "custom": None},
               {"preset": "custom", "custom": {"width_mm": [], "height_mm": 50, "margins_mm": [1, 1, 1, 1], "dpi": 203, "orientation": "portrait"}},
               {"preset": "custom", "custom": {"width_mm": 25, "height_mm": 50, "margins_mm": [1, 1, 1, 1], "dpi": 203, "orientation": []}},
               {"preset": "custom", "custom": {"width_mm": 25, "height_mm": 50, "margins_mm": {}, "dpi": 203, "orientation": "portrait"}},
               {"preset": "custom", "custom": {"width_mm": 25, "height_mm": 50, "margins_mm": [[], 1, 1, 1], "dpi": 203, "orientation": "portrait"}}]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    qr_layout.validate_settings(value)
                self.assertEqual(qr_layout.settings_profile(value), qr_layout.PRESETS[qr_layout.DEFAULT_PRESET][1])


@unittest.skipUnless(fixture.HAS_QT, "PySide6 non installé : fenêtre QR non mesurée")
class QrWindowCorrectionTests(unittest.TestCase):
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

    def open_qr(self):
        qr = ui_qr.QrWindow(ui_qr.snapshot(self.window), self.window)
        self.addCleanup(self.close_quietly, qr)
        return qr

    @staticmethod
    def close_quietly(widget):
        try:
            widget.close()
        except RuntimeError:
            pass

    # ── F1: the code the user sees ──
    def assert_whole_code_visible(self, qr, label):
        canvas = qr.canvas
        self.assertTrue(canvas.isVisible(), label)
        self.assertEqual(canvas.visibleRegion().boundingRect(), canvas.rect(), label)
        scale = canvas.scale()
        self.assertGreaterEqual(scale, 2, label)
        side = qr.symbol.total_modules * scale
        origin = canvas.mapTo(qr, QPoint((canvas.width() - side) // 2, (canvas.height() - side) // 2))
        image = qr.grab().toImage()  # The whole window, as composed on screen
        self.assertTrue(0 <= origin.x() and origin.x() + side <= image.width() and 0 <= origin.y() and origin.y() + side <= image.height(), label)
        rows = [[False] * qr.symbol.total_modules for _ in range(qr.symbol.total_modules)]
        for y, row in enumerate(qr.symbol.modules):
            for x, dark in enumerate(row):
                rows[y + 4][x + 4] = dark
        for y, row in enumerate(rows):
            for x, dark in enumerate(row):
                value = image.pixelColor(origin.x() + x * scale + scale // 2, origin.y() + y * scale + scale // 2).value()
                self.assertEqual(value < 128, dark, f"{label}: module {x},{y}")

    def assert_labels_fit(self, qr, label):
        for button in qr.findChildren(QPushButton):
            if not button.isVisible():
                continue
            option = QStyleOptionButton(); option.initFrom(button); option.text = button.text()
            content = button.style().subElementRect(QStyle.SE_PushButtonContents, option, button)
            self.assertGreaterEqual(content.width(), button.fontMetrics().horizontalAdvance(button.text()), f"{label}: {button.text()}")
        for button in qr.findChildren(QToolButton):
            if button.isVisible():
                self.assertGreaterEqual(button.width(), button.sizeHint().width(), f"{label}: {button.text()}")

    def test_code_and_labels_visible_at_minimum_and_default_sizes(self):
        for language, dark in (("fr", False), ("en", True), ("es", False), ("zh_CN", True)):
            i18n.set_language(language)
            with patch("spoolscribe.app_gui.is_dark_theme", return_value=dark):
                self.window._apply_theme()
            qr = self.open_qr(); qr.show()
            available = qr.screen().availableGeometry()
            for size, details in (((420, 520), False), ((420, 520), True), ((560, 720), False), ((560, 720), True)):
                qr.details_toggle.setChecked(details); qr.resize(*size); self.window.app.processEvents(); self.window.app.processEvents()
                label = f"{language} {size} details={details}"
                # Never forced beyond the screen; only as tall as the legible code needs.
                self.assertLessEqual(qr.minimumHeight(), available.height(), label)
                self.assertEqual(qr.height(), max(size[1], qr.minimumHeight()), label)
                self.assertEqual(qr.width(), size[0], label)
                self.assert_whole_code_visible(qr, label)
                self.assert_labels_fit(qr, label)
            self.assertFalse(qr.details.isVisible() and not qr.details_toggle.isChecked())
            qr.close()

    def test_details_are_folded_by_default_and_never_shrink_the_code(self):
        qr = self.open_qr(); qr.show(); self.window.app.processEvents()
        self.assertGreaterEqual(qr.canvas.scale(), 3)
        qr.resize(420, 520); qr.details_toggle.setChecked(True); self.window.app.processEvents(); self.window.app.processEvents()
        self.assertFalse(qr.details_toggle.visibleRegion().isEmpty())  # Opened details are scrolled into view
        self.assertFalse(qr.details.visibleRegion().isEmpty())
        self.assert_whole_code_visible(qr, "minimum, details open")
        qr.details_toggle.setChecked(False)
        qr.resize(560, 720); self.window.app.processEvents()
        self.assertFalse(qr.details_toggle.isChecked())
        closed = qr.canvas.scale()
        qr.details_toggle.setChecked(True); self.window.app.processEvents()
        self.assertEqual(qr.canvas.scale(), closed)
        self.assert_whole_code_visible(qr, "details open")

    # ── F2: final destination after the suffix is added ──
    def test_suffix_added_after_the_dialog_never_replaces_silently(self):
        root = Path(core.DATA_HOME); root.mkdir(parents=True, exist_ok=True)
        qr = self.open_qr()
        for kind in ("png", "svg"):
            existing = root / f"existing.{kind}"
            existing.write_bytes(b"witness bytes")
            with self.subTest(kind=kind, answer="no"), \
                    patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=(str(root / "existing"), "")), \
                    patch("spoolscribe.ui_qr.QMessageBox.question", return_value=QMessageBox.No) as ask:
                self.assertIsNone(qr._save(kind))
                self.assertEqual(ask.call_count, 1)
                self.assertIn(str(existing), ask.call_args[0][2])
                self.assertEqual(existing.read_bytes(), b"witness bytes")
                self.assertNotIn("enregistrée", qr.status.text())
            with self.subTest(kind=kind, answer="yes"), \
                    patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=(str(root / "existing"), "")), \
                    patch("spoolscribe.ui_qr.QMessageBox.question", return_value=QMessageBox.Yes):
                self.assertEqual(qr._save(kind), str(existing))
                self.assertEqual(existing.read_bytes(), qr.file_data(kind))
            with self.subTest(kind=kind, case="new file"), \
                    patch("spoolscribe.ui_qr.QFileDialog.getSaveFileName", return_value=(str(root / f"fresh-{kind}"), "")), \
                    patch("spoolscribe.ui_qr.QMessageBox.question") as ask:
                self.assertEqual(qr._save(kind), str(root / f"fresh-{kind}.{kind}"))
                self.assertEqual(ask.call_count, 0)  # The native dialog already handled this path

    # ── F3: corrupted stored section ──
    def test_corrupted_stored_section_opens_with_defaults_and_import_is_refused(self):
        for value in ({"preset": []}, {"preset": {}}, [], None, {"error": []}):
            with self.subTest(value=value):
                cfg = core.load_config(); cfg["qr_label"] = value; core.save_config(cfg)
                qr = self.open_qr()
                self.assertEqual(qr.support.currentData(), qr_layout.DEFAULT_PRESET)
                qr.close()
                target = Path(core.DATA_HOME) / "settings.json"
                core.export_settings(target)
                cfg = core.load_config(); cfg["qr_label"] = {"preset": "a4"}; core.save_config(cfg)
                raw = Path(core.CONFIG_PATH).read_bytes()
                with self.assertRaises(ValueError):
                    core.import_settings(target)
                self.assertEqual(Path(core.CONFIG_PATH).read_bytes(), raw)
        # Settings exported by v0.5.0 have no qr_label: they import and keep the current section.
        document = {"format": "spoolscribe-settings", "version": 1, "settings": {k: v for k, v in core.load_config().items()
                    if k not in ("qr_label", "network_consent", "network_sources_revision", "last_update")}}
        old = Path(core.DATA_HOME) / "v050.json"; old.write_text(json.dumps(document), encoding="utf-8")
        core.import_settings(old)
        self.assertEqual(core.load_config()["qr_label"], {"preset": "a4"})

    # ── F4: every accepted profile can be saved as PNG ──
    def test_png_for_every_accepted_profile_keeps_whole_modules_and_size(self):
        qr = self.open_qr()
        qr.support.setCurrentIndex(qr.support.findData("custom"))
        cases = [(210, 297, 10, 2400), (210, 297, 10, 1200), (50, 50, 1.5, 96), (25, 50, 1, 203), (60, 80, 1, 600),
                 (5, 5, 1.5, 2400), (40, 60, 1, 1500)]
        checked = 0
        for width, height, margin, dpi in cases:
            for small in (False, True):
                qr.custom_fields["width_mm"].setValue(width); qr.custom_fields["height_mm"].setValue(height)
                qr.custom_fields["margin"].setValue(margin); qr.custom_dpi.setValue(dpi); qr.small.setChecked(small)
                plan = qr.plan()
                if plan is None or not plan.printable:
                    continue
                label = f"{width}x{height} m{margin} {dpi} ppp small={small}"
                image = QImage.fromData(qr.file_data("png"))
                self.assertFalse(image.isNull(), label)
                scale = image.width() // qr.symbol.total_modules
                self.assertEqual(image.width(), qr.symbol.total_modules * scale, label)
                self.assertTrue(1 <= scale <= qr_layout.PNG_MAX_SCALE, label)
                physical = image.width() / image.dotsPerMeterX() * 1000
                self.assertAlmostEqual(physical, plan.qr_mm, delta=0.01, msg=label)
                colours = {image.pixel(x, y) & 0xFFFFFF for y in range(0, image.height(), max(1, scale // 2)) for x in range(0, image.width(), max(1, scale // 2))}
                self.assertEqual(colours, {0, 0xFFFFFF}, label)
                self.assertTrue(qr.file_data("svg").startswith(b"<?xml"), label)
                checked += 1
        self.assertGreaterEqual(checked, 8)


if __name__ == "__main__":
    unittest.main()
