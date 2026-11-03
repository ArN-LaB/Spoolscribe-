"""Reviewed product cutouts: identity, provenance, native alpha and UI coverage."""
import hashlib
import json
from pathlib import Path
import unittest

from tests.support import ROOT
from tests import test_gui as fixture

PHOTO_PROFILES = {
    'u1', 'bambu', 'bambu_openspool', 'prusa', 'prusa_core', 'prusa_mk4',
    'anycubic_ace', 'qidi_box', 'creality_k2', 'creality_klipper',
    'flashforge_ad5x', 'flashforge_creator5', 'elegoo_cc2', 'ultimaker_s',
    'raise3d_pro3', 'makerbot_method', 'xyz_davinci',
}
GENERIC_PROFILES = {'openspool', 'opentag3d', 'klipper_diy', 'prusa_generic', 'no_reader'}


class PrinterPhotoTests(unittest.TestCase):
    def test_named_printer_choices_have_photos_and_generic_choices_stay_explicit(self):
        from spoolscribe import printer_profiles
        from spoolscribe.printer_presentations import presentation
        self.assertEqual(set(printer_profiles.PROFILES), PHOTO_PROFILES | GENERIC_PROFILES)
        for key in PHOTO_PROFILES:
            info = presentation(printer_profiles.PROFILES[key])
            self.assertTrue(Path(info.get('photo', '')).is_file(), key)
            self.assertTrue(info.get('photo_model'), key)
            self.assertTrue(info.get('photo_source', '').startswith('https://'), key)
        for key in GENERIC_PROFILES:
            self.assertNotIn('photo', presentation(printer_profiles.PROFILES[key]), key)

    def test_original_files_match_provenance_and_no_photo_is_orphaned(self):
        folder = ROOT / 'data/printers/photos'
        entries = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual({p.name for p in folder.iterdir() if p.is_file()},
                         {'manifest.json'} | {e['file'] for e in entries.values()})
        for key, entry in entries.items():
            with self.subTest(profile=key):
                raw = (folder / entry['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
                self.assertEqual(len(raw), entry['bytes'])
                self.assertTrue(entry['url'].startswith('https://'))
                self.assertTrue(entry['page_url'].startswith('https://'))
                self.assertTrue(entry['model']); self.assertTrue(entry['caption'])
                self.assertEqual(entry['transformation'], 'none')

    def test_native_transparency_dimensions_and_render_crop_are_measured(self):
        from PIL import Image
        folder = ROOT / 'data/printers/photos'
        for key, entry in json.loads((folder / 'manifest.json').read_text()).items():
            with self.subTest(profile=key), Image.open(folder / entry['file']) as image:
                self.assertEqual(list(image.size), entry['dimensions'])
                alpha = image.convert('RGBA').getchannel('A')
                share = alpha.histogram()[0] / (image.width * image.height)
                self.assertGreater(share, .02)  # actual transparent pixels, not just RGBA mode
                self.assertEqual(list(alpha.getbbox()), entry['bounds'])
                self.assertGreater(min(entry['dimensions']), 150)


@unittest.skipUnless(fixture.HAS_QT, 'Qt unavailable')
class PrinterPhotoGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): fixture.GuiTests.setUpClass()

    def test_photo_render_is_bounded_and_cached_without_changing_original(self):
        from spoolscribe import printer_profiles
        from spoolscribe.printer_presentations import presentation
        from spoolscribe.ui_widgets import printer_visual
        for key in PHOTO_PROFILES:
            info = presentation(printer_profiles.PROFILES[key]); path = Path(info['photo'])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            for size in (40, 64, 80):
                pixmap = printer_visual(info, size, True)
                self.assertFalse(pixmap.isNull(), key)
                self.assertLessEqual(max(pixmap.width(), pixmap.height()), size * 2)
                self.assertTrue(pixmap.hasAlphaChannel(), key)
                self.assertEqual(pixmap.cacheKey(), printer_visual(info, size, False).cacheKey())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
