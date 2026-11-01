"""Every bundled raster logo keeps a transparent background; the manifest matches the files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from tests.support import ROOT

HAS_PIL = importlib.util.find_spec("PIL") is not None
MANIFEST = ROOT / "data/brands/manifest.json"


class LogoTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_entries_match_the_bundled_files(self):
        for key, entry in self.manifest.items():
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"], entry["path"])
            self.assertTrue(entry.get("name"))

    @unittest.skipUnless(HAS_PIL, "Pillow absent : transparence non mesurée")
    def test_raster_logos_have_a_transparent_background(self):
        from PIL import Image
        opaque = []
        for entry in self.manifest.values():
            path = ROOT / entry["path"]
            if path.suffix.lower() != ".png" or entry.get("filled_shape"):
                continue  # a filled square/round logo legitimately covers its corners
            with Image.open(path) as image:
                image = image.convert("RGBA")
                w, h = image.size
                corners = [image.getpixel(p)[3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
            # Artwork may touch a corner; an opaque frame touches all four with one colour.
            if all(a > 8 for a in corners):
                opaque.append(entry["path"])
        self.assertEqual(opaque, [], f"Logos à fond opaque : {opaque}")

    def test_svg_logos_have_no_full_background_rectangle(self):
        for entry in self.manifest.values():
            path = ROOT / entry["path"]
            if path.suffix.lower() != ".svg":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn('width="100%" height="100%"', text, entry["path"])


if __name__ == "__main__":
    unittest.main()
