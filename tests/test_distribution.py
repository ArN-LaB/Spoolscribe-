import importlib.util
from pathlib import Path
import plistlib
import stat
import tempfile
import unittest
import zipfile

from tests.support import ROOT

spec = importlib.util.spec_from_file_location("verify_archive", ROOT / ".github/scripts/verify_archive.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def archive(self, platform, *, extra=None, magic=None, executable=True, version="0.2.2"):
        path = Path(self.tmp.name) / f"SpoolScribe-{platform}.zip"
        binary = {"windows": "SpoolScribe.exe", "linux": "SpoolScribe",
                  "macos": "SpoolScribe.app/Contents/MacOS/SpoolScribe"}[platform]
        with zipfile.ZipFile(path, "w") as archive:
            entry = zipfile.ZipInfo(binary)
            entry.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
            archive.writestr(entry, magic or {"windows": b"MZ00", "linux": b"\x7fELF", "macos": b"\xcf\xfa\xed\xfe"}[platform])
            if platform == "macos":
                archive.writestr("SpoolScribe.app/Contents/Info.plist", plistlib.dumps({
                    "CFBundleExecutable": "SpoolScribe", "CFBundleVersion": version,
                    "CFBundleShortVersionString": version}))
            if extra:
                archive.writestr(extra, b"unwanted")
        return path

    def test_windows_contains_only_native_exe(self):
        self.assertEqual(checker.verify_archive(self.archive("windows"))["root"], "SpoolScribe.exe")

    def test_linux_contains_only_native_executable(self):
        self.assertEqual(checker.verify_archive(self.archive("linux"))["root"], "SpoolScribe")

    def test_macos_contains_only_app(self):
        self.assertEqual(checker.verify_archive(self.archive("macos"), "0.2.2")["root"], "SpoolScribe.app")

    def test_macos_duplicate_raw_executable_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected only"):
            checker.verify_archive(self.archive("macos", extra="SpoolScribe"))

    def test_wrong_native_format_is_rejected(self):
        for platform in ("windows", "linux", "macos"):
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "wrong native"):
                checker.verify_archive(self.archive(platform, magic=b"oops"))

    def test_extra_files_are_rejected(self):
        for platform in ("windows", "linux", "macos"):
            with self.subTest(platform=platform), self.assertRaises(ValueError):
                checker.verify_archive(self.archive(platform, extra="temporary.log"))

    def test_wrong_mac_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "wrong bundle version"):
            checker.verify_archive(self.archive("macos", version="0.2.1"), "0.2.2")

    def test_missing_execute_permission_is_rejected(self):
        for platform in ("linux", "macos"):
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, "permission"):
                checker.verify_archive(self.archive(platform, executable=False))
