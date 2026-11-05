"""QR geometry and files (SPOOLSCRIBE-QR-2026-001): whole printer dots, quiet zone, exact PNG/SVG."""
import json
import math
import re
import unittest
import xml.etree.ElementTree as ET

import tests.support  # noqa: F401  (network refused for the whole suite)
from tests.support import ROOT
from spoolscribe import qr_layout as L

VECTORS = json.loads((ROOT / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))["vectors"]
D101 = L.PRESETS["d101-25x50"][1]

try:
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    HAS_QT = True
except ImportError:  # pragma: no cover
    HAS_QT = False


def symbol(name, error="M"):
    entry = VECTORS[name]
    return L.make_symbol(entry["protocol"], bytes.fromhex(entry["hex"]), error)


def total(version):
    return 17 + 4 * version + 8


class D101GeometryTests(unittest.TestCase):
    """QR-05: thresholds computed from dots, not from a favourable rounding."""

    def test_dot_pitch_and_usable_width(self):
        self.assertEqual(L.dots(24, 203), 191)          # 191.81: never 192
        self.assertEqual(L.dots(23, 203), 183)
        self.assertAlmostEqual(L.dots_to_mm(1, 203), 25.4 / 203)
        plan = L.plan_label(total(5), D101)
        self.assertEqual(plan.area[2], 183)              # 1 mm margins: 0.5 mm paper + 0.5 mm kept

    def test_four_and_three_dots_per_module_on_the_d101_preset(self):
        cases = {5: ("ready", 4), 6: ("refused", 0), 9: ("refused", 0), 10: ("refused", 0)}
        for version, (status, dots) in cases.items():
            with self.subTest(version=version):
                plan = L.plan_label(total(version), D101)
                self.assertEqual((plan.status, plan.dots_per_module), (status, dots))
        self.assertEqual(L.plan_label(total(6), D101).reason, "needs_small")
        self.assertEqual(L.plan_label(total(10), D101).reason, "too_dense")
        for version, status in ((6, "small"), (9, "small"), (10, "refused")):
            with self.subTest(version=version, small=True):
                plan = L.plan_label(total(version), D101, small_format=True)
                self.assertEqual(plan.status, status)
                self.assertEqual(plan.dots_per_module, 3 if status == "small" else 0)

    def test_the_191_dot_width_without_extra_margin(self):
        tight = L.LabelProfile(25, 50, (0.5, 0.5, 0.5, 0.5), 203)
        plan = L.plan_label(total(9), tight, small_format=True)
        self.assertEqual((plan.area[2], plan.status, plan.qr_rect[2]), (191, "small", 183))
        self.assertEqual(L.plan_label(total(10), tight, small_format=True).status, "refused")  # 65 × 3 = 195 > 191
        self.assertEqual(L.plan_label(total(5), tight).status, "ready")
        self.assertEqual(L.plan_label(total(6), tight).status, "refused")                     # 49 × 4 = 196 > 191

    def test_measured_widths_of_the_framing_cases(self):
        for name, version, width in (("catalogue-essential", 11, 25.901), ("catalogue-full", 15, 31.906),
                                     ("opentag-real-explicit", 8, 21.396)):
            with self.subTest(vector=name):
                code = symbol(name)
                self.assertEqual(code.version, version)
                # 01 shows widths rounded from a 0.125123 mm pitch (25.9005 mm is displayed 25.901).
                self.assertAlmostEqual(L.minimum_width_mm(code.total_modules, 203, 3), width, delta=0.001)
        self.assertEqual(L.plan_label(symbol("opentag-real-explicit").total_modules, D101, small_format=True).status, "small")
        self.assertEqual(L.plan_label(symbol("catalogue-essential").total_modules, D101, small_format=True).status, "refused")

    def test_rotation_and_length_do_not_widen_the_label(self):
        landscape = L.LabelProfile(25, 50, (1, 1, 1, 1), 203, "landscape")
        for version in (5, 9, 10):
            self.assertEqual(L.plan_label(total(version), landscape, small_format=True).status,
                             L.plan_label(total(version), D101, small_format=True).status)
        self.assertEqual(L.plan_label(total(10), L.LabelProfile(25, 200, (1, 1, 1, 1), 203), small_format=True).status, "refused")

    def test_other_resolutions_and_wider_labels(self):
        self.assertEqual(L.plan_label(total(10), L.LabelProfile(25, 50, (1, 1, 1, 1), 300)).dots_per_module, 4)  # 271 dots
        self.assertEqual(L.plan_label(total(15), L.LabelProfile(25, 50, (1, 1, 1, 1), 300)).status, "refused")
        self.assertEqual(L.plan_label(total(15), L.LabelProfile(25, 50, (1, 1, 1, 1), 600)).status, "ready")
        wide = L.plan_label(total(15), L.PRESETS["label-50x50"][1])
        self.assertEqual((wide.status, wide.dots_per_module), ("ready", 4))
        page = L.plan_label(total(10), L.PRESETS["a4"][1])
        self.assertEqual(page.dots_per_module, math.floor(300 / 25.4))  # Capped at 1 mm modules on a large page

    def test_invalid_parameters_are_refused(self):
        bad = [L.LabelProfile(float("nan"), 50), L.LabelProfile(25, float("inf")), L.LabelProfile(-25, 50),
               L.LabelProfile(25, 50, (1, 1, 1)), L.LabelProfile(25, 50, (13, 1, 13, 1)), L.LabelProfile(25, 50, (1, 1, 1, -1)),
               L.LabelProfile(25, 50, dpi=50), L.LabelProfile(25, 50, dpi=203.0), L.LabelProfile(25, 50, dpi=True),
               L.LabelProfile(True, 50), L.LabelProfile(25, 50, orientation="diagonal"), L.LabelProfile(4, 50)]
        for profile in bad:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                L.plan_label(total(5), profile)
        for modules in (0, 28, 186, 45.0, None):
            with self.subTest(modules=modules), self.assertRaises(ValueError):
                L.plan_label(modules, D101)

    def test_driver_area_and_resolution_replace_the_requested_ones(self):
        # A driver accepting 300 dpi with an extra non-printable band on the left.
        page = (L.dots(25, 300), L.dots(50, 300))
        plan = L.plan_label(total(10), D101, device=(300, (40, 0, page[0] - 40, page[1]), page))
        self.assertEqual(plan.dpi, 300)
        self.assertEqual(plan.area[0], 0)  # Origin of the drawing is the driver's paint rectangle.
        self.assertEqual(plan.area[2], page[0] - 40 - math.ceil(300 / 25.4))
        self.assertEqual(plan.status, "refused")
        for device in ((50, (0, 0, 10, 10), (10, 10)), (203, (0, 0, 0, 10), (10, 10)), (203.0, (0, 0, 10, 10), (10, 10))):
            with self.subTest(device=device), self.assertRaises(ValueError):
                L.plan_label(total(5), D101, device=device)


class TemplateTests(unittest.TestCase):
    """QR-06: QR square first, quiet zone white, identity lines outside it."""

    def test_layout_of_the_25_by_50_template(self):
        code = symbol("opentag-real-explicit")
        plan = L.plan_label(code.total_modules, D101, small_format=True)
        x, y, side, _ = plan.qr_rect
        self.assertEqual(side, code.total_modules * 3)
        ax, ay, aw, ah = plan.area
        self.assertTrue(ax <= x and x + side <= ax + aw and ay == y)
        tx, ty, tw, th = plan.text_rect
        self.assertGreaterEqual(ty, y + side)                 # Text never enters the quiet zone
        self.assertLessEqual(ty + th, ay + ah)
        self.assertEqual(plan.text_lines, 3)
        rects = L.module_rects(code, (x, y), 3)
        quiet = 4 * 3
        for rx, ry, rw, rh in rects:
            self.assertTrue(all(isinstance(v, int) for v in (rx, ry, rw, rh)))
            self.assertTrue(x + quiet <= rx and rx + rw <= x + side - quiet and y + quiet <= ry and ry + rh <= y + side - quiet)
        self.assertEqual(sum(w * h for _, _, w, h in rects), 9 * sum(map(sum, code.modules)))

    def test_square_label_keeps_only_the_code(self):
        plan = L.plan_label(total(5), L.LabelProfile(25, 25, (1, 1, 1, 1), 203))
        self.assertEqual((plan.status, plan.text_lines, plan.text_rect), ("ready", 0, (0, 0, 0, 0)))


@unittest.skipUnless(HAS_QT, "Qt indisponible : rendu PNG/SVG non relu")
class FileTests(unittest.TestCase):
    """QR-06: integer scale, pure black and white, quiet zone of four modules."""

    def matrix_of(self, image, scale):
        n = image.width() // scale
        return [[image.pixelColor(x * scale + scale // 2, y * scale + scale // 2).value() < 128 for x in range(n)] for y in range(n)]

    def expected(self, code):
        size = code.total_modules
        rows = [[False] * size for _ in range(size)]
        for y, row in enumerate(code.modules):
            for x, dark in enumerate(row):
                rows[y + 4][x + 4] = dark
        return rows

    def test_png_pixels_scale_and_resolution(self):
        code = symbol("catalogue-full")
        for scale, dpi in ((3, 203), (4, 203), (15, 1015)):
            with self.subTest(scale=scale):
                image = QImage.fromData(L.png_bytes(code, scale, dpi=dpi))
                self.assertEqual((image.width(), image.height()), (code.total_modules * scale,) * 2)
                self.assertEqual(round(image.dotsPerMeterX() * 0.0254), dpi)
                colours = {image.pixel(x, y) & 0xFFFFFF for y in range(image.height()) for x in range(image.width())}
                self.assertEqual(colours, {0x000000, 0xFFFFFF})
                for y in range(image.height()):  # Every module is a whole block of pixels
                    for x in range(image.width()):
                        self.assertEqual(image.pixel(x, y), image.pixel(x - x % scale, y - y % scale))
                self.assertEqual(self.matrix_of(image, scale), self.expected(code))
        with self.assertRaises(ValueError):
            L.png_bytes(code, 0)

    def test_svg_is_exact_in_modules_and_millimetres(self):
        code = symbol("openspool-utf8")
        data = L.svg_bytes(code, 0.5, "Titre <&>", "Café 测试")
        root = ET.fromstring(data)
        ns = "{http://www.w3.org/2000/svg}"
        self.assertEqual(root.get("viewBox"), f"0 0 {code.total_modules} {code.total_modules}")
        self.assertEqual(root.get("width"), f"{code.total_modules * 0.5:g}mm")
        self.assertEqual((root.find(ns + "title").text, root.find(ns + "desc").text), ("Titre <&>", "Café 测试"))
        self.assertEqual(root.find(ns + "rect").get("fill"), "#fff")
        rows = [[False] * code.total_modules for _ in range(code.total_modules)]
        for x, y, n in re.findall(r"M(\d+) (\d+)h(\d+)v1h-\3z", root.find(ns + "path").get("d")):
            for i in range(int(n)):
                rows[int(y)][int(x) + i] = True
        self.assertEqual(rows, self.expected(code))
        renderer = QSvgRenderer(QByteArray(data))
        scale = 4
        image = QImage(code.total_modules * scale, code.total_modules * scale, QImage.Format_RGB32)
        image.fill(Qt.red)
        painter = QPainter(image); renderer.render(painter); painter.end()
        self.assertEqual(self.matrix_of(image, scale), self.expected(code))
        for bad in (0, float("nan"), 11):
            with self.assertRaises(ValueError):
                L.svg_bytes(code, bad)


class SettingsTests(unittest.TestCase):
    """QR-10: bounded configuration section, refused when invalid."""

    def test_valid_and_invalid_sections(self):
        custom = L.profile_to_dict(L.LabelProfile(40, 60, (1.5, 1.5, 1.5, 1.5), 300, "landscape"))
        for value in ({}, {"preset": "a4"}, {"preset": "custom", "custom": custom, "small_format": True, "error": "Q"}):
            self.assertEqual(L.validate_settings(value), value)
        for value in (None, [], {"preset": "unknown"}, {"preset": "custom"}, {"error": "L"}, {"small_format": 1},
                      {"extra": 1}, {"preset": "custom", "custom": dict(custom, dpi=10)},
                      {"preset": "custom", "custom": dict(custom, margins_mm=[30, 30, 30, 30])}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                L.validate_settings(value)
        self.assertEqual(L.settings_profile({"preset": "custom", "custom": custom}), L.profile_from_dict(custom))
        self.assertIsNone(L.settings_profile({"preset": "bogus"}))


if __name__ == "__main__":
    unittest.main()
