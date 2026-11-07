"""macOS Developer ID/notarisation procedure with simulated Apple commands.

Every Apple tool (codesign, notarytool, stapler, spctl, ditto, lipo, otool, security) is
simulated: these are simulated proofs of the orchestrator's decisions, never a signature,
an Apple acceptance or a Gatekeeper result. Git runs for real on a temporary repository.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tests.support import ROOT

TOOL = ROOT / "packaging/macos_notarize.py"
_spec = importlib.util.spec_from_file_location("macos_notarize", TOOL)
mn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mn)  # volontairement sans inscription dans sys.modules (R5)

POSIX = os.name == "posix"
GIT = shutil.which("git")
DEV_ID = "A" * 40
APPLE_DEV = "B" * 40
INSTALLER = "C" * 40
DISTRIBUTION = "D" * 40
SUBMISSION = "2f0c3c1e-8d4b-4c11-9a6e-0f6a1b2c3d4e"
IDENTITIES = (
    f'  1) {APPLE_DEV} "Apple Development: Private Person (PERSONAL01)"\n'
    f'  2) {DEV_ID} "Developer ID Application: Private Person (TEAMFAKE01)"\n'
    f'  3) {INSTALLER} "Developer ID Installer: Private Person (TEAMFAKE01)"\n'
    f'  4) {DISTRIBUTION} "Apple Distribution: Private Person (TEAMFAKE01)"\n'
    "     4 valid identities found\n")
HOLDER = "QA_SYNTHETIC_HOLDER_ONLY"  # marqueurs fictifs, jamais une identité réelle
TEAM = "QAFAKETEAM1"
LEAK = f"The signing certificate is invalid: Developer ID Application: {HOLDER} ({TEAM})."
ONLY_APPLE_DEV = f'  1) {APPLE_DEV} "Apple Development: Private Person (PERSONAL01)"\n     1 valid identities found\n'


def macho(filetype=mn.MH_DYLIB, cputype=0x0100000C):
    return struct.pack("<IiII", 0xFEEDFACF, cputype, 0, filetype) + b"\0" * 48


def fat_macho(*cputypes, filetype=mn.MH_DYLIB):
    header = struct.pack(">II", 0xCAFEBABE, len(cputypes))
    offset = 4096
    table, slices = b"", b""
    for cputype in cputypes:
        body = macho(filetype, cputype)
        table += struct.pack(">iIIII", cputype, 0, offset + len(slices), len(body), 12)
        slices += body + b"\0" * (4096 - len(body))
    return (header + table).ljust(offset, b"\0") + slices


def write(path, data=b"", mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    os.chmod(path, mode)
    return path


def framework(lib, name, versions=("A",)):
    root = lib / f"{name}.framework"
    for version in versions:
        write(root / "Versions" / version / name, macho())
        write(root / "Versions" / version / "Resources/Info.plist",
              plistlib.dumps({"CFBundleExecutable": name, "CFBundleIdentifier": "org.qt-project." + name}))
    os.symlink(versions[-1], root / "Versions/Current")
    os.symlink(f"Versions/Current/{name}", root / name)
    os.symlink("Versions/Current/Resources", root / "Resources")
    return root


def make_app(dist, source, *, version=None, helper=False, multi_version=False, links=None):
    """A synthetic PyInstaller-like onedir bundle (not a real executable)."""
    app = Path(dist) / mn.APP_DIR
    version = version or mn.read_app_version(source)
    write(app / "Contents/Info.plist", plistlib.dumps({
        "CFBundleExecutable": "SpoolScribe", "CFBundleIdentifier": mn.BUNDLE_ID,
        "CFBundleShortVersionString": version, "CFBundleVersion": version}))
    write(app / "Contents/MacOS/SpoolScribe", macho(mn.MH_EXECUTE), 0o755)
    frameworks = app / "Contents/Frameworks"
    write(frameworks / "libpython3.12.dylib", macho())
    write(frameworks / "PySide6/QtCore.abi3.so", macho(mn.MH_BUNDLE), 0o755)
    write(frameworks / "PySide6/Qt/plugins/platforms/libqcocoa.dylib", macho())
    write(frameworks / "PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib", macho())
    lib = frameworks / "PySide6/Qt/lib"
    framework(lib, "QtCore", ("A", "B") if multi_version else ("A",))
    framework(lib, "QtQml")
    framework(lib, "QtQuick")
    if helper:
        nested = frameworks / "Helper.app"
        write(nested / "Contents/Info.plist", plistlib.dumps({"CFBundleExecutable": "Helper"}))
        write(nested / "Contents/MacOS/Helper", macho(mn.MH_EXECUTE), 0o755)
        write(nested / "Contents/Frameworks/libhelper.dylib", macho())
    for top in ("data", "scripts"):
        for path in sorted((Path(source) / top).rglob("*")):
            if path.is_file() and path.suffix != ".md":
                write(app / "Contents/Resources" / path.relative_to(source), path.read_bytes())
    os.symlink("../Resources/data", frameworks / "data")
    for name, target in (links or {}).items():
        os.symlink(target, frameworks / name)
    write(app / "Contents/Resources/base_library.zip", b"PK\x05\x06" + b"\0" * 18)
    return app


OTOOL = """{path}:
Load command 9
      cmd LC_BUILD_VERSION
  cmdsize 32
 platform 1
    minos 13.0
      sdk 15.0
Load command 12
          cmd LC_LOAD_DYLIB
      cmdsize 56
         name /usr/lib/libSystem.B.dylib (offset 24)
Load command 13
          cmd LC_RPATH
      cmdsize 32
         path @loader_path/.. (offset 12)
{extra}"""

CODESIGN_DETAILS = """Executable={path}
Identifier=com.github.arn-lab.spoolscribe
Format=app bundle with Mach-O thin (arm64)
CodeDirectory v=20500 size=1000 flags=0x10000(runtime) hashes=20+7 location=embedded
Signature size=9000
Authority={authority}: Private Person (TEAMFAKE01)
Authority=Developer ID Certification Authority
Authority=Apple Root CA
{time}
TeamIdentifier={team}
Runtime Version=15.0.0
"""


def zip_tree(source, destination):
    source = Path(source)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        root = zipfile.ZipInfo(source.name + "/")
        root.external_attr = (stat.S_IFDIR | stat.S_IMODE(os.lstat(source).st_mode)) << 16
        archive.writestr(root, b"")
        for rel, entry in sorted(mn.tree_manifest(source).items()):
            name = f"{source.name}/{rel}"
            if entry[0] == "dir":
                info = zipfile.ZipInfo(name + "/")
                info.external_attr = (stat.S_IFDIR | entry[1]) << 16
                archive.writestr(info, b"")
            elif entry[0] == "link":
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFLNK | 0o755) << 16
                archive.writestr(info, entry[1])
            else:
                info = zipfile.ZipInfo(name)
                info.external_attr = (stat.S_IFREG | entry[1]) << 16
                archive.writestr(info, (source / rel).read_bytes())


def unzip_tree(source, destination):
    modes = []
    with zipfile.ZipFile(source) as archive:
        for info in archive.infolist():
            mode = info.external_attr >> 16
            target = Path(destination) / info.filename.rstrip("/")
            if info.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                modes.append((target, stat.S_IMODE(mode)))
            elif stat.S_ISLNK(mode):
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(archive.read(info).decode(), target)
            else:
                write(target, archive.read(info), stat.S_IMODE(mode))
    for target, mode in sorted(modes, key=lambda item: -len(item[0].parts)):
        os.chmod(target, mode)


class FakeXattrs:
    def __init__(self):
        self.names = {}

    def list(self, path):
        return sorted(self.names.get(os.path.realpath(os.path.dirname(path)) + "/" + os.path.basename(path), ()))

    def add(self, path, name):
        key = os.path.realpath(os.path.dirname(path)) + "/" + os.path.basename(path)
        self.names.setdefault(key, set()).add(name)

    def remove(self, path, name):
        key = os.path.realpath(os.path.dirname(path)) + "/" + os.path.basename(path)
        self.names[key].discard(name)


class Result(mn.Result):
    pass


class FakeMac:
    """Simulated macOS tools; git is real. Records every call for order assertions."""

    def __init__(self, base):
        self.base = Path(base)
        self.calls = []
        self.python = write(self.base / "bin/python3.12", "#!fake\n", 0o755)
        self.identities = IDENTITIES
        self.python_version = [3, 12, 13]
        self.authority = "Developer ID Application"
        self.signed_time = False
        self.fail_sign = None
        self.otool_extra = {}
        self.entitlements = ""
        self.submit = lambda: Result(0, json.dumps({"id": SUBMISSION, "message": "Successfully uploaded file"}), "")
        self.wait = lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Accepted"}), "")
        self.info = [lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Accepted"}), "")]
        self.log = {}
        self.submitted = None
        self.staple_extra = None
        self.extracted_validate = 0
        self.app_options = {}

    def names(self):
        return [os.path.basename(c[0]) + " " + " ".join(c[1:3]) for c in self.calls]

    def count(self, *prefix):
        return sum(1 for c in self.calls if [os.path.basename(c[0])] + c[1:len(prefix)] == list(prefix))

    def run(self, args, *, cwd=None, env=None, timeout=600):
        args = [str(a) for a in args]
        self.calls.append(args)
        name = os.path.basename(args[0])
        handler = getattr(self, "_" + name.replace("-", "_").replace(".", "_"), None)
        if args[0].endswith("venv/bin/python"):
            return self._venv(args, cwd)
        if args[0] == str(self.python):
            return self._base_python(args)
        if name == "git":
            done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
            return Result(done.returncode, done.stdout, done.stderr)
        if handler is None:
            raise AssertionError("unexpected command " + " ".join(args))
        return handler(args)

    def _base_python(self, args):
        if args[1:3] == ["-I", "-c"]:
            return Result(0, json.dumps({"version": self.python_version, "machine": "arm64"}), "")
        if args[1:3] == ["-m", "venv"]:
            write(Path(args[3]) / "bin/python", "#!fake\n", 0o755)
            return Result(0, "", "")
        raise AssertionError(args)

    def _venv(self, args, cwd):
        if args[1:4] == ["-m", "pip", "install"]:
            return Result(0, "", "")
        if args[1:4] == ["-m", "pip", "freeze"]:
            return Result(0, "pyinstaller==6.22.3\npip==25.0\n", "")
        if args[1:3] == ["-m", "PyInstaller"]:
            make_app(Path(cwd) / "dist", cwd, **self.app_options)
            return Result(0, "", "")
        if args[1] == "-B" and args[2].endswith("verify_archive.py"):
            done = subprocess.run([sys.executable, "-B", *args[2:]], capture_output=True, text=True)
            return Result(done.returncode, done.stdout, done.stderr)
        if args[1] == "-B" and "check_frozen_" in args[2]:
            return Result(0, "FROZEN_SIMULATED_OK {}\n", "")
        raise AssertionError(args)

    def _xcode_select(self, args):
        return Result(0, "/Applications/Xcode.app/Contents/Developer\n", "")

    def _xcodebuild(self, args):
        return Result(0, "Xcode 27.2\nBuild version 27B52\n", "")

    def _security(self, args):
        return Result(0, self.identities, "")

    def _lipo(self, args):
        return Result(0, " ".join(mn.macho_info(args[-1])["archs"]) + "\n", "")

    def _otool(self, args):
        path = args[-1]
        extra = next((v for k, v in self.otool_extra.items() if path.endswith(k)), "")
        return Result(0, OTOOL.format(path=path, extra=extra), "")

    def _codesign(self, args):
        path = Path(args[-1])
        if "--sign" in args:
            if self.fail_sign and str(path).endswith(self.fail_sign):
                return Result(1, "", "The timestamp service is not available.")
            if path.is_dir():
                folder = path / "Contents" if (path / "Contents").is_dir() else path
                write(folder / "_CodeSignature/CodeResources", "sealed")
            else:
                with open(path, "ab") as stream:
                    stream.write(b"SIGNED")
            return Result(0, "", f"{path}: signed\n")
        if "--verify" in args:
            return Result(0, "", f"{path}: valid on disk\n")
        if "-dvvv" in args:
            time = "Signed Time=Nov 7, 2026" if self.signed_time else "Timestamp=Nov 7, 2026 at 10:00:00"
            return Result(0, "", CODESIGN_DETAILS.format(path=path, authority=self.authority, time=time,
                                                         team="TEAMFAKE01"))
        if "--entitlements" in args:
            return Result(0, self.entitlements, "")
        raise AssertionError(args)

    def _ditto(self, args):
        if args[1:3] == ["-c", "-k"]:
            self.ditto_flags = args[3:-2]
            zip_tree(args[-2], args[-1])
        elif args[1:3] == ["-x", "-k"]:
            unzip_tree(args[-2], args[-1])
        else:
            raise AssertionError(args)
        return Result(0, "", "")

    def _xcrun(self, args):
        if args[1] == "--find":
            return Result(0, f"/Applications/Xcode.app/bin/{args[2]}\n", "")
        if args[1:3] == ["notarytool", "--version"]:
            return Result(0, "1.1.4 (43)\n", "")
        if args[1] == "notarytool":
            self.assert_no_secret(args)
            action = args[2]
            if action == "submit":
                self.submitted = args[3]
                return self.submit()
            if action == "wait":
                return self.wait()
            if action == "info":
                return (self.info.pop(0) if len(self.info) > 1 else self.info[0])()
            if action == "log":
                write(args[-1], json.dumps(dict(self.apple_log(), **self.log)))
                return Result(0, "", "")
        if args[1] == "stapler":
            app = Path(args[-1])
            if args[2] == "staple":
                write(app / "Contents/CodeResources", "ticket")
                if self.staple_extra:
                    write(app / self.staple_extra, "unexpected")
                return Result(0, "The staple and validate action worked!\n", "")
            if args[2] == "validate":
                extracted = "extracted-" in str(app)
                if extracted and self.extracted_validate:
                    return Result(65, "", "does not have a ticket stapled to it")
                return Result(0, "The validate action worked!\n", "")
        raise AssertionError(args)

    def _spctl(self, args):
        return Result(0, "", f"{args[-1]}: accepted\nsource=Notarized Developer ID\n"
                             "origin=Developer ID Application: Private Person (TEAMFAKE01)\n")

    def apple_log(self):
        """What Apple would describe for the archive actually submitted (simulated)."""
        tickets = []
        with zipfile.ZipFile(self.submitted) as archive:
            for info in archive.infolist():
                if not info.filename.endswith("/") and not stat.S_ISLNK(info.external_attr >> 16):
                    if archive.read(info)[:4] in mn.THIN_MAGIC or archive.read(info)[:4] in mn.FAT_MAGIC:
                        tickets.append({"path": f"{mn.SUBMISSION_ZIP}/{info.filename}", "arch": "arm64"})
        return {"jobId": SUBMISSION, "status": "Accepted", "issues": None,
                "sha256": mn.sha256_file(self.submitted), "ticketContents": tickets}

    @staticmethod
    def assert_no_secret(args):
        forbidden = {"--password", "-p", "--apple-id", "--key", "--key-id", "--issuer", "--team-id"}
        assert not forbidden & set(args) and args[args.index("--keychain-profile") + 1], args


def identity_cases():
    return mn.parse_identities(IDENTITIES)


class PureDecisionTests(unittest.TestCase):
    def test_identity_selection_accepts_only_explicit_developer_id_application(self):
        identities = identity_cases()
        self.assertEqual(mn.select_identity(identities, DEV_ID.lower())["type"], "Developer ID Application")
        for reference, reason in ((None, "non fournie"), ("-", "ad hoc"), ("Developer ID Application", "ambiguë"),
                                  ("Private Person", "ambiguë"), ("E" * 40, "introuvable")):
            with self.subTest(reference=reference), self.assertRaisesRegex(mn.ProcedureError, reason):
                mn.select_identity(identities, reference)
        # Le type refusé reste un détail privé ; le libellé public est fixe (reprise R2 du 10).
        for reference, kind in ((APPLE_DEV, "Apple Development"), (INSTALLER, "Developer ID Installer"),
                                (DISTRIBUTION, "Apple Distribution")):
            with self.subTest(reference=reference):
                with self.assertRaisesRegex(mn.ProcedureError, "type d'identité refusé") as caught:
                    mn.select_identity(identities, reference)
                self.assertEqual(caught.exception.detail, kind)
                self.assertNotIn(kind, str(caught.exception))
                self.assertNotIn("Private Person", str(caught.exception))
        doubled = mn.parse_identities(IDENTITIES + f'  5) {DEV_ID} "Developer ID Application: Private Person (TEAMFAKE01)"\n')
        with self.assertRaisesRegex(mn.ProcedureError, "ambiguë"):
            mn.select_identity(doubled, DEV_ID)
        revoked = mn.parse_identities(f'  1) {DEV_ID} "Developer ID Application: X (T)" (CSSMERR_TP_CERT_REVOKED)\n')
        with self.assertRaisesRegex(mn.ProcedureError, "introuvable"):
            mn.select_identity(revoked, DEV_ID)

    def test_macho_is_detected_by_header_not_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(mn.macho_info(write(root / "plugin", macho()))["archs"], ["arm64"])
            self.assertIsNone(mn.macho_info(write(root / "fake.dylib", b"not a binary at all", 0o755)))
            self.assertIsNone(mn.macho_info(write(root / "Main.class", b"\xca\xfe\xba\xbe\x00\x00\x00\x34" + b"\0" * 40)))
            fat = mn.macho_info(write(root / "universal", fat_macho(0x0100000C, 0x01000007)))
            self.assertEqual((fat["archs"], fat["fat"], fat["filetype"]), (["arm64", "x86_64"], True, mn.MH_DYLIB))
            self.assertEqual(mn.macho_info(write(root / "x.o", macho(1)))["filetype"], 1)

    def test_otool_dependencies_minos_and_rpaths_are_parsed(self):
        text = OTOOL.format(path="x", extra="""Load command 14
          cmd LC_LOAD_WEAK_DYLIB
         name @rpath/QtQml.framework/Versions/A/QtQml (offset 24)
Load command 15
          cmd LC_ID_DYLIB
         name @rpath/libfoo.dylib (offset 24)
""")
        info = mn.parse_otool_load_commands(text)
        self.assertEqual((info["minos"], info["sdk"]), ("13.0", "15.0"))
        self.assertEqual(info["rpaths"], ["@loader_path/.."])
        self.assertEqual(info["dylibs"], ["/usr/lib/libSystem.B.dylib"])
        self.assertEqual(info["weak"], ["@rpath/QtQml.framework/Versions/A/QtQml"])
        self.assertEqual(info["id"], "@rpath/libfoo.dylib")

    def test_codesign_details_distinguish_secure_timestamp_from_signed_time(self):
        good = mn.parse_codesign_details(CODESIGN_DETAILS.format(
            path="x", authority="Developer ID Application", time="Timestamp=Nov 7, 2026", team="T"))
        self.assertEqual(good["authority_type"], "Developer ID Application")
        self.assertTrue(good["runtime"] and good["secure_timestamp"] and not good["signed_time_only"])
        weak = mn.parse_codesign_details(CODESIGN_DETAILS.format(
            path="x", authority="Apple Development", time="Signed Time=Nov 7, 2026", team="T")
            .replace("flags=0x10000(runtime)", "flags=0x2(adhoc)"))
        self.assertFalse(weak["runtime"] or weak["secure_timestamp"])
        self.assertTrue(weak["signed_time_only"])

    def test_entitlements_default_to_none_and_forbid_get_task_allow(self):
        self.assertEqual(mn.parse_entitlements(mn.Result(0, "", "")), {})
        mn.check_entitlements({}, {})
        with self.assertRaisesRegex(mn.ProcedureError, "get-task-allow"):
            mn.check_entitlements({"com.apple.security.get-task-allow": True}, {})
        with self.assertRaisesRegex(mn.ProcedureError, "différents"):
            mn.check_entitlements({"com.apple.security.cs.allow-jit": True}, {})
        with tempfile.TemporaryDirectory() as directory:
            for value, reason in (({"com.apple.security.get-task-allow": True}, "interdit"),
                                  ({"com.apple.security.app-sandbox": True}, "non prévu"),
                                  ({"com.apple.security.cs.allow-jit": False}, "inattendue"), ({}, "vide")):
                path = write(Path(directory) / "e.plist", plistlib.dumps(value))
                with self.subTest(value=value), self.assertRaisesRegex(mn.ProcedureError, reason):
                    mn.load_entitlements(path)

    def test_notary_responses_and_log_review(self):
        with self.assertRaisesRegex(mn.ProcedureError, "non JSON"):
            mn.parse_notary_json("Error: HTTP status code: 401", need=("id",))
        with self.assertRaisesRegex(mn.ProcedureError, "inattendue"):
            mn.parse_notary_json(json.dumps({"message": "x"}), need=("id",))
        with self.assertRaisesRegex(mn.ProcedureError, "identifiant"):
            mn.parse_notary_json(json.dumps({"id": "../../x"}), need=("id",))
        log = {"jobId": SUBMISSION, "status": "Accepted", "sha256": "ab" * 32, "issues": [
            {"severity": "warning", "message": "The binary uses an SDK older than the 10.9 SDK."}],
            "ticketContents": [{"path": "SpoolScribe-submission.zip/SpoolScribe.app/Contents/MacOS/SpoolScribe"}]}
        review = mn.examine_notary_log(log, submission_id=SUBMISSION, zip_sha256="ab" * 32,
                                       macho_paths=["Contents/MacOS/SpoolScribe", "Contents/Frameworks/x.dylib"])
        self.assertEqual(review["errors"], [])
        self.assertEqual(review["warnings"], ["issue-warning", "uncovered-macho"])
        self.assertEqual((review["uncovered"], review["issue_warnings"]), (1, 1))
        self.assertNotIn("SDK", json.dumps(review))
        bad = mn.examine_notary_log(dict(log, status="Invalid", sha256="cd" * 32), submission_id=SUBMISSION,
                                    zip_sha256="ab" * 32, macho_paths=[])
        self.assertEqual(bad["errors"], ["sha256-mismatch", "status-not-accepted"])
        self.assertEqual(mn.examine_notary_log(dict(log, jobId="other"), submission_id=SUBMISSION,
                                               zip_sha256="ab" * 32, macho_paths=[])["errors"], ["job-mismatch"])

    def test_pins_are_checked_against_the_darwin_python312_snapshot(self):
        snapshot = (ROOT / "requirements/requirements-build.txt").read_text(encoding="utf-8")
        wanted = {line.split("==")[0]: line.split("==")[1].split(";")[0].strip() for line in snapshot.splitlines()
                  if "==" in line and not line.lstrip().startswith("#")
                  and ("win32" not in line and "< '3.11'" not in line)}
        freeze = "\n".join(f"{name}=={version}" for name, version in wanted.items())
        self.assertEqual(mn._pin_mismatches(snapshot, freeze), [])
        self.assertTrue(mn._pin_mismatches(snapshot, freeze.replace("pyinstaller==6.22.3", "pyinstaller==6.0")))

    def test_timeouts_are_bounded(self):
        self.assertEqual(mn.parse_timeout("30m"), 1800)
        for value in ("", "0m", "forever", "10d", "-1h"):
            with self.subTest(value=value), self.assertRaises(mn.ProcedureError):
                mn.parse_timeout(value)

    def test_tool_contains_no_identity_or_secret_material(self):
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\b[0-9A-Fa-f]{40}\b")
        self.assertNotRegex(source, r"Developer ID Application: \w")
        for word in ("--password", "--apple-id", "--key ", "xattr -cr", "--preserve-metadata"):
            self.assertNotIn(word, source)
        self.assertIn('"--options", "runtime", "--timestamp"', source)


class NonMacTests(unittest.TestCase):
    def test_other_os_gets_diagnostic_without_any_tool_or_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = FakeMac(directory)
            out = io.StringIO()
            code = mn.main(["preflight", "--python", str(fake.python)], runner=fake, platform="linux", out=out,
                           xattrs=FakeXattrs(), which=lambda name: name)
            self.assertEqual(code, mn.EXIT_BLOCKED)
            self.assertIn("macOS uniquement", out.getvalue())
            target = Path(directory) / "ws"
            for argv in (["prepare", "--workspace", str(target), "--commit", "a" * 40, "--python", str(fake.python)],
                         ["sign", "--workspace", str(target), "--identity", DEV_ID, "--confirm-signing"],
                         ["notarize", "--workspace", str(target), "--profile", "p", "--confirm-submission"]):
                self.assertEqual(mn.main(argv, runner=fake, platform="win32", out=io.StringIO(),
                                         xattrs=FakeXattrs()), mn.EXIT_BLOCKED)
            self.assertEqual(fake.calls, [])
            self.assertFalse(target.exists())


@unittest.skipUnless(POSIX, "macOS-like file system (symlinks, POSIX modes) required")
class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fake = FakeMac(self.tmp.name)

    def preflight(self, *extra):
        out = io.StringIO()
        code = mn.main(["preflight", "--python", str(self.fake.python), *extra], runner=self.fake,
                       platform="darwin", machine="arm64", out=out, xattrs=FakeXattrs(), which=lambda name: name)
        return code, out.getvalue()

    def test_missing_developer_id_is_ready_to_notarize_without_leaking_identity(self):
        self.fake.identities = ONLY_APPLE_DEV
        code, text = self.preflight("--identity", APPLE_DEV)
        self.assertEqual(code, mn.EXIT_READY_MISSING)
        self.assertIn(mn.VERDICT_READY, text)
        self.assertIn("Apple Development ×1", text)
        self.assertIn("type d'identité refusé : Apple Development", text)
        for private in ("Private Person", "PERSONAL01", APPLE_DEV):
            self.assertNotIn(private, text)
        actions = {tuple(c[1:3]) for c in self.fake.calls}
        self.assertFalse({("notarytool", "submit"), ("notarytool", "history"), ("notarytool", "store-credentials")}
                         & actions)
        self.assertFalse(any(os.path.basename(c[0]) == "codesign" for c in self.fake.calls))

    def test_complete_prerequisites_are_reported_without_contacting_apple(self):
        code, text = self.preflight("--identity", DEV_ID, "--profile", "spoolscribe-notary-local")
        self.assertEqual(code, mn.EXIT_OK)
        self.assertIn("NON VÉRIFIÉ", text)
        self.assertNotIn("TEAMFAKE01", text)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 0)

    def test_first_identity_is_never_chosen_implicitly(self):
        code, text = self.preflight("--profile", "p")
        self.assertEqual(code, mn.EXIT_READY_MISSING)
        self.assertIn("identité de signature non fournie", text)

    def test_wrong_python_is_an_environment_blocker(self):
        self.fake.python_version = [3, 14, 10]
        code, text = self.preflight("--identity", DEV_ID, "--profile", "p")
        self.assertEqual(code, mn.EXIT_BLOCKED)
        self.assertIn("Python 3.12 requis", text)
        self.assertIn("--python /chemin/python3.12", text)


@unittest.skipUnless(POSIX and GIT, "POSIX file system and git required")
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.fake = FakeMac(self.base)
        self.xattrs = FakeXattrs()
        self.ws = self.base / "private" / "ws"
        self.ws.parent.mkdir()
        self.commit = self.make_repo()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=QA", "-c", "user.email=qa@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def make_repo(self):
        write(self.repo / "src/spoolscribe/core.py", 'APP_NAME = "SpoolScribe"\nAPP_VERSION = "9.9.9"\n')
        write(self.repo / "src/spoolscribe/packaging_rules.py",
              "def include_resource(name):\n    return name.startswith(('data/', 'scripts/'))"
              " and name.endswith(('.json', '.py'))\n")
        write(self.repo / "data/printers.json", '{"printers": []}\n')
        write(self.repo / "data/notes.md", "not bundled\n")
        write(self.repo / "scripts/worker.py", "print('worker')\n")
        write(self.repo / "requirements/requirements-build.txt", "pyinstaller==6.22.3\n")
        write(self.repo / "packaging/spoolscribe.spec", "# unchanged spec\n")
        write(self.repo / ".github/scripts/verify_archive.py", (ROOT / ".github/scripts/verify_archive.py").read_bytes())
        for probe in mn.FROZEN_PROBES:
            write(self.repo / ".github/scripts" / probe, "print('probe')\n")
        subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q", str(self.repo)], check=True)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = mn.main(list(argv), runner=self.fake, platform="darwin", machine="arm64", out=out,
                           xattrs=self.xattrs, which=lambda name: name, checkout=self.repo, tool_path=TOOL)
        self.output = out.getvalue()
        self.errors_output = err.getvalue()
        self.transcript = getattr(self, "transcript", "") + self.output + self.errors_output
        return code

    def prepare(self):
        self.assertEqual(self.main("prepare", "--workspace", str(self.ws), "--commit", self.commit,
                                   "--python", str(self.fake.python)), mn.EXIT_OK, self.output)

    def through_sign(self):
        self.prepare()
        for step in ("build", "inspect", "probes", "sanitize"):
            self.assertEqual(self.main(step, "--workspace", str(self.ws)), mn.EXIT_OK, (step, self.output))
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_OK, self.output)

    def state(self):
        return json.loads((self.ws / mn.STATE_FILE).read_text(encoding="utf-8"))

    @property
    def app(self):
        return self.ws / "source/dist" / mn.APP_DIR

    def test_destination_must_be_new_private_and_outside_checkout_and_sync(self):
        cloud = self.base / "Library/CloudStorage/ProtonDrive-x"
        cloud.mkdir(parents=True)
        provider = self.base / "provider"
        provider.mkdir()
        self.xattrs.add(provider, "com.apple.fileprovider.dir#N")
        existing = self.base / "existing"
        existing.mkdir()
        link = self.base / "link"
        os.symlink(self.base / "private", link)
        for target, reason in ((self.repo / "out", "hors du checkout"), (cloud / "ws", "synchronisé"),
                               (provider / "ws", "File Provider"), (existing, "préexistante"),
                               (link, "préexistante"), (Path("relative/ws"), "absolu"),
                               (self.base / "missing/ws", "parent doit exister")):
            with self.subTest(target=target):
                code = self.main("prepare", "--workspace", str(target), "--commit", self.commit,
                                 "--python", str(self.fake.python))
                self.assertEqual(code, mn.EXIT_BLOCKED)
                self.assertIn(reason, self.output)
        named = self.base / "-Users-x-Library-CloudStorage-ProtonDrive-copy"
        named.mkdir()
        self.assertEqual(self.main("prepare", "--workspace", str(named / "ws"), "--commit", self.commit,
                                   "--python", str(self.fake.python)), mn.EXIT_OK, self.output)
        self.assertEqual(sorted(p.name for p in existing.iterdir()), [])
        self.assertFalse((self.repo / "out").exists() or (cloud / "ws").exists())
        self.assertEqual(self.main("prepare", "--workspace", str(self.ws), "--commit", "HEAD",
                                   "--python", str(self.fake.python)), mn.EXIT_BLOCKED)
        self.assertIn("empreinte complète", self.output)

    def test_export_of_approved_commit_keeps_refs_and_excludes_uncommitted_changes(self):
        refs = self.git("for-each-ref")
        write(self.repo / "data/printers.json", '{"uncommitted": true}\n')
        write(self.repo / "untracked.txt", "local\n")
        self.prepare()
        self.assertEqual(self.git("for-each-ref"), refs)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.commit)
        self.assertEqual((self.ws / "source/data/printers.json").read_text(), '{"printers": []}\n')
        self.assertFalse((self.ws / "source/untracked.txt").exists())
        self.assertEqual((self.repo / "data/printers.json").read_text(), '{"uncommitted": true}\n')
        self.assertEqual(stat.S_IMODE(os.lstat(self.ws).st_mode), 0o700)
        state = self.state()
        tool = state["steps"]["prepare"]["tool"]
        self.assertEqual(tool["sha256"], mn.sha256_file(TOOL))
        self.assertFalse(tool["matches_commit"])
        self.assertIn("diffère de sa version", self.output)
        self.assertEqual(self.main("prepare", "--workspace", str(self.ws), "--commit", self.commit,
                                   "--python", str(self.fake.python)), mn.EXIT_BLOCKED)

    def test_mutating_commands_require_a_workspace_owned_by_the_procedure(self):
        plain = self.base / "plain"
        plain.mkdir(mode=0o700)
        self.assertEqual(self.main("build", "--workspace", str(plain)), mn.EXIT_BLOCKED)
        self.assertIn("marqueur absent", self.output)
        self.prepare()
        link = self.base / "alias"
        os.symlink(self.ws, link)
        self.assertEqual(self.main("build", "--workspace", str(link)), mn.EXIT_BLOCKED)
        self.assertIn("pas un lien", self.output)
        copy = self.base / "private" / "copy"
        shutil.copytree(self.ws, copy, symlinks=True)
        os.chmod(copy, 0o700)
        self.assertEqual(self.main("build", "--workspace", str(copy)), mn.EXIT_BLOCKED)
        self.assertIn("incohérent", self.output)
        os.chmod(self.ws, 0o755)
        self.assertEqual(self.main("build", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertIn("0700", self.output)
        self.assertEqual(self.fake.count("venv/bin/python", "-m", "PyInstaller"), 0)

    def test_signing_plan_is_inside_out_through_real_files_with_framework_versions_and_helpers(self):
        self.fake.app_options = dict(helper=True, multi_version=True)
        self.prepare()
        self.assertEqual(self.main("build", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.assertEqual(self.main("inspect", "--workspace", str(self.ws)), mn.EXIT_OK, self.output)
        report = self.state()["steps"]["inspect"]
        plan = [item["path"] for item in report["plan"]]
        self.assertEqual(plan[-1], ".")
        for index, path in enumerate(plan):
            for later in plan[index + 1:]:
                self.assertFalse(later != "." and path != "." and later.startswith(path + "/"),
                                 f"{later} after its container {path}")
        lib = "Contents/Frameworks/PySide6/Qt/lib/"
        self.assertIn(lib + "QtCore.framework/Versions/A", plan)
        self.assertIn(lib + "QtCore.framework/Versions/B", plan)
        self.assertNotIn(lib + "QtCore.framework/QtCore", plan)
        self.assertNotIn(lib + "QtCore.framework/Versions/Current", plan)
        self.assertNotIn("Contents/MacOS/SpoolScribe", plan)
        helper = plan.index("Contents/Frameworks/Helper.app")
        self.assertLess(plan.index("Contents/Frameworks/Helper.app/Contents/Frameworks/libhelper.dylib"), helper)
        self.assertNotIn("Contents/Frameworks/Helper.app/Contents/MacOS/Helper", plan)
        self.assertNotIn("Contents/Resources/base_library.zip", plan)
        self.assertEqual(report["qml_frameworks"], ["QtQml", "QtQuick"])
        self.assertEqual(report["archs_common"], ["arm64"])
        self.assertEqual(report["resources_verified"], 2)

    def test_broken_outgoing_and_looping_links_and_external_dependencies_are_refused(self):
        self.fake.app_options = dict(links={"escape": "../../../../outside", "absolute": "/usr/lib",
                                            "broken": "missing.dylib", "loop-a": "loop-b", "loop-b": "loop-a"})
        self.prepare()
        self.assertEqual(self.main("build", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.fake.otool_extra = {"libqcocoa.dylib": "          cmd LC_LOAD_DYLIB\n         name /opt/homebrew/lib/libz.dylib (offset 24)\n"}
        self.assertEqual(self.main("inspect", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        for reason in ("escape : sort du candidat", "absolute : cible absolue", "broken : lien cassé",
                       "loop-a : boucle de liens", "dépendance hors candidat (external)"):
            self.assertIn(reason, self.output)
        self.assertEqual(self.main("sanitize", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_BLOCKED)
        self.assertIn("inspection en échec", self.output)
        self.assertEqual(self.fake.count("codesign", "--force"), 0)

    def test_resolver_never_leaves_the_candidate(self):
        root = self.base / "tree"
        write(root / "a/file", "x")
        os.symlink("a", root / "dir")
        os.symlink("dir/file", root / "chain")
        os.symlink("../../tree/a/file", root / "a/up")
        self.assertEqual(mn.resolve_inside(root, "chain"), ("a/file", None))
        self.assertEqual(mn.resolve_inside(root, "a/up"), (None, "sort du candidat"))
        self.assertEqual(mn.resolve_inside(root, "dir/../a/file"), ("a/file", None))

    def test_full_simulated_pipeline_orders_stapling_before_final_zip_and_hash(self):
        checkout_file = self.repo / "data/printers.json"
        self.xattrs.add(checkout_file, "com.apple.FinderInfo")
        self.prepare()
        self.assertEqual(self.main("build", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.xattrs.add(self.app / "Contents/Info.plist", "com.apple.FinderInfo")
        self.xattrs.add(self.app / "Contents/Resources/data", "com.apple.ResourceFork")
        self.xattrs.add(self.app / "Contents/MacOS/SpoolScribe", "com.apple.provenance")
        self.assertEqual(self.main("inspect", "--workspace", str(self.ws)), mn.EXIT_OK, self.output)
        self.assertEqual(self.main("probes", "--workspace", str(self.ws)), mn.EXIT_OK, self.output)
        pyinstaller = next(i for i, c in enumerate(self.fake.calls) if "PyInstaller" in c)
        oracles = next(i for i, c in enumerate(self.fake.calls) if "zxing-cpp==2.3.0" in c)
        self.assertLess(pyinstaller, oracles)
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_BLOCKED)
        self.assertIn("sanitize manquant", self.output)
        self.assertEqual(self.main("sanitize", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.assertEqual(self.xattrs.list(self.app / "Contents/Info.plist"), [])
        self.assertEqual(self.xattrs.list(self.app / "Contents/MacOS/SpoolScribe"), ["com.apple.provenance"])
        self.assertEqual(self.xattrs.list(checkout_file), ["com.apple.FinderInfo"])
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_OK, self.output)
        signs = [c for c in self.fake.calls if os.path.basename(c[0]) == "codesign" and "--sign" in c]
        self.assertEqual(len(signs), len(self.state()["steps"]["inspect"]["plan"]))
        for call in signs:
            self.assertEqual(call[1:8], ["--force", "--sign", DEV_ID, "--options", "runtime", "--timestamp",
                                         call[7]])
            self.assertNotIn("--deep", call)
            self.assertNotIn("--entitlements", call)
        self.assertEqual(signs[-1][-1], os.path.realpath(self.app))
        self.assertEqual(self.main("probes", "--workspace", str(self.ws)), mn.EXIT_OK)
        self.assertIn("signed", self.state()["steps"]["probes"])
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "spoolscribe-notary-local",
                                   "--confirm-submission"), mn.EXIT_OK, self.output)
        submission = self.state()["submission"]
        self.assertEqual(submission["status"], "Accepted")
        self.assertEqual(submission["zip_sha256"], mn.sha256_file(self.ws / "submission" / mn.SUBMISSION_ZIP))
        self.assertEqual(self.fake.count("xcrun", "notarytool", "log"), 1)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_OK)
        self.assertEqual(self.main("package", "--workspace", str(self.ws)), mn.EXIT_OK, self.output)
        names = self.fake.names()
        staple = names.index("xcrun stapler staple")
        final_zip = max(i for i, c in enumerate(self.fake.calls) if c[-1].endswith(mn.FINAL_ZIP)
                        and os.path.basename(c[0]) == "ditto")
        self.assertLess(staple, final_zip)
        self.assertFalse(any("stapler" in c and c[-1].endswith(".zip") for c in self.fake.calls))
        self.assertEqual(self.fake.ditto_flags, ["--norsrc", "--noextattr", "--keepParent"])
        archive = self.ws / "release" / mn.FINAL_ZIP
        self.assertEqual((self.ws / "release" / (mn.FINAL_ZIP + ".sha256")).read_text(),
                         f"{mn.sha256_file(archive)}  {mn.FINAL_ZIP}\n")
        resigns_after_staple = [c for c in self.fake.calls[staple:] if "--sign" in c]
        self.assertEqual(resigns_after_staple, [])
        self.assertEqual(self.main("assess", "--workspace", str(self.ws), "--confirm-assessment"), mn.EXIT_OK)
        self.assertIn("NON MESURÉ", self.output)
        summary = (self.ws / "summary.md").read_text(encoding="utf-8")
        for private in ("Private Person", "TEAMFAKE01", DEV_ID, str(self.base)):
            self.assertNotIn(private, summary)
        self.assertIn("ESSAI UTILISATEUR STANDARD NON MESURÉ", summary)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 1)

    def test_confirmations_are_required_for_each_apple_or_signing_step(self):
        self.prepare()
        for step in ("build", "inspect", "sanitize"):
            self.main(step, "--workspace", str(self.ws))
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p"), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("notary-status", "--workspace", str(self.ws), "--profile", "p"), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("assess", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("codesign", "--force"), 0)
        self.assertFalse(any(c[1:2] in (["notarytool"], ["stapler"]) and c[2] != "--version" for c in self.fake.calls))
        self.assertEqual(self.fake.count("spctl"), 0)

    def test_signing_or_timestamp_error_blocks_every_following_step(self):
        self.prepare()
        for step in ("build", "inspect", "sanitize"):
            self.main(step, "--workspace", str(self.ws))
        self.fake.fail_sign = "libqcocoa.dylib"
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_BLOCKED)
        self.assertIn("timestamp", self.output)
        failed = [i for i, c in enumerate(self.fake.calls) if c[-1].endswith("libqcocoa.dylib") and "--sign" in c][0]
        self.assertFalse(any("--sign" in c or "--verify" in c for c in self.fake.calls[failed + 1:]))
        self.fake.fail_sign = None
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_BLOCKED)
        self.assertIn("déjà été tentée", self.output)
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertEqual(self.main("probes", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("ditto"), 0)
        self.assertIn("SIGNATURE EN ÉCHEC", mn.overall_verdict(self.state()))

    def test_non_developer_id_or_untimestamped_signature_fails_verification(self):
        for attribute, value, reason in (("authority", "Apple Development", "autorité"),
                                         ("signed_time", True, "timestamp sécurisé")):
            with self.subTest(attribute=attribute):
                self.ws = self.base / "private" / f"ws-{attribute}"
                self.fake = FakeMac(self.base / attribute)
                setattr(self.fake, attribute, value)
                self.prepare()
                for step in ("build", "inspect", "sanitize"):
                    self.main(step, "--workspace", str(self.ws))
                self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID,
                                           "--confirm-signing"), mn.EXIT_BLOCKED)
                self.assertIn(reason, self.output)
                self.assertNotIn("signed", self.state()["candidate"])

    def test_embedded_get_task_allow_is_refused(self):
        self.fake.entitlements = plistlib.dumps({"com.apple.security.get-task-allow": True}).decode()
        self.prepare()
        for step in ("build", "inspect", "sanitize"):
            self.main(step, "--workspace", str(self.ws))
        self.assertEqual(self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing"),
                         mn.EXIT_BLOCKED)
        self.assertIn("get-task-allow", self.output)

    def test_modified_signed_candidate_cannot_be_submitted(self):
        self.through_sign()
        write(self.app / "Contents/Resources/data/printers.json", "tampered")
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("candidat modifié", self.output)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 0)

    def test_invalid_status_blocks_stapling(self):
        self.through_sign()
        self.fake.info = [lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Invalid"}), "")]
        self.fake.log = {"jobId": SUBMISSION, "status": "Invalid", "issues": [
            {"severity": "error", "message": "The signature does not include a secure timestamp."}]}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "log"), 1)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("xcrun", "stapler"), 0)

    def test_interrupted_wait_is_pending_and_resumes_without_new_submission(self):
        self.through_sign()
        self.fake.wait = lambda: Result(None, "", "", timed_out=True)
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_PENDING)
        self.assertIn("PENDING", self.output)
        self.assertEqual(self.state()["submission"]["id"], SUBMISSION)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("jamais un nouvel envoi", self.output)
        self.fake.info = [lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "In Progress"}), ""),
                          lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Accepted"}), "")]
        self.assertEqual(self.main("notary-status", "--workspace", str(self.ws), "--profile", "p",
                                   "--confirm-apple-query"), mn.EXIT_PENDING)
        self.assertEqual(self.main("notary-status", "--workspace", str(self.ws), "--profile", "p",
                                   "--confirm-apple-query"), mn.EXIT_OK)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 1)
        self.assertEqual(self.state()["submission"]["status"], "Accepted")

    def test_unexpected_json_or_unknown_status_blocks(self):
        self.through_sign()
        self.fake.submit = lambda: Result(0, "Successfully uploaded", "")
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertEqual(self.state()["submission"]["status"], "UNKNOWN")
        self.assertEqual(self.main("notary-status", "--workspace", str(self.ws), "--profile", "p",
                                   "--confirm-apple-query"), mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 1)

    def test_unknown_status_and_auth_error(self):
        self.through_sign()
        self.fake.info = [lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Mystery"}), "")]
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("statut Apple inattendu", self.output)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        other = self.base / "auth"
        self.fake = FakeMac(other)
        self.fake.submit = lambda: Result(1, "", "Error: HTTP status code: 401. Unable to authenticate.")
        self.ws = self.base / "private" / "ws-auth"
        self.through_sign()
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertNotIn("401", self.output)
        self.assertEqual(self.state()["submission"]["status"], "SUBMIT_FAILED")

    def test_log_is_examined_before_stapling(self):
        self.through_sign()
        self.fake.log = {"jobId": SUBMISSION, "status": "Accepted", "sha256": "0" * 64, "issues": None}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("empreinte", self.output)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.ws = self.base / "private" / "ws-warn"
        self.fake = FakeMac(self.base / "warn")
        self.fake.log = {"jobId": SUBMISSION, "status": "Accepted",
                         "issues": [{"severity": "warning", "message": "deprecated SDK"}]}
        self.through_sign()
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_OK)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertIn("--acknowledge-log-warnings", self.output)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling",
                                   "--acknowledge-log-warnings"), mn.EXIT_OK)

    def test_stapling_may_only_add_the_ticket(self):
        self.through_sign()
        self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission")
        self.fake.staple_extra = "Contents/Resources/extra.txt"
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertIn("Contents/CodeResources", self.output)

    def test_lost_ticket_after_extraction_stops_for_packaging_decision(self):
        self.through_sign()
        self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission")
        self.main("staple", "--workspace", str(self.ws), "--confirm-stapling")
        self.fake.extracted_validate = 1
        self.assertEqual(self.main("package", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertIn("Décision de packaging requise", self.output)
        self.assertNotIn("package", self.state()["steps"])

    def test_probes_never_run_on_a_stapled_candidate_and_cannot_change_it(self):
        self.prepare()
        self.main("build", "--workspace", str(self.ws))
        original = self.fake._venv

        def mutating(args, cwd):
            if "check_frozen_" in " ".join(args):
                write(self.app / "Contents/Resources/cache.pyc", "x")
            return original(args, cwd)

        self.fake._venv = mutating
        self.assertEqual(self.main("probes", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        self.assertIn("modifié le candidat", self.output)

    # ── Régressions R2 (05-CODEX-QA) : mêmes injections que le harness historique, contrat corrigé ──
    def ready_to_sign(self):
        self.prepare()
        for step in ("build", "inspect", "sanitize"):
            self.assertEqual(self.main(step, "--workspace", str(self.ws)), mn.EXIT_OK, (step, self.output))

    def sign(self, *extra):
        return self.main("sign", "--workspace", str(self.ws), "--identity", DEV_ID, "--confirm-signing", *extra)

    def replace_entitlement_reads(self, answer):
        original = self.fake._codesign
        reads = []

        def codesign(args):
            if "--entitlements" in args and "--sign" not in args:
                reads.append(args[-1])
                return answer(len(reads), Path(args[-1]))
            return original(args)

        self.fake._codesign = codesign
        return reads

    def assert_not_verified(self):
        state = self.state()
        self.assertNotIn("signed", state["candidate"])
        self.assertNotIn("verified", state["steps"]["sign"])
        self.assertIn("SIGNATURE EN ÉCHEC", mn.overall_verdict(state))
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 0)
        self.assertEqual(self.fake.count("ditto"), 0)
        self.assertNotIn("Traceback", self.transcript)

    def test_r1_failed_entitlement_extraction_never_counts_as_verified(self):
        self.ready_to_sign()
        reads = self.replace_entitlement_reads(
            lambda n, path: Result(23, "", "SYNTHETIC: entitlement extraction failed"))
        self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
        self.assertIn("lecture des entitlements en échec", self.output)
        self.assertEqual(len(reads), 1)  # arrêt au premier échec
        self.assertNotIn("SYNTHETIC", self.transcript)
        logs = "".join(p.read_text(encoding="utf-8") for p in (self.ws / "logs").glob("*-entitlements.txt"))
        self.assertIn("SYNTHETIC: entitlement extraction failed", logs)
        self.assert_not_verified()

    def test_r1_failure_after_a_first_nominal_read_blocks(self):
        self.ready_to_sign()
        reads = self.replace_entitlement_reads(
            lambda n, path: Result(0, "", "") if n == 1 else Result(23, "", "SYNTHETIC: second read failed"))
        self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
        self.assertEqual(len(reads), 2)
        self.assert_not_verified()

    def test_r1_timeout_or_error_code_is_refused_even_with_plausible_output(self):
        plist = plistlib.dumps({}).decode()
        for name, answer in (("timeout-empty", Result(0, "", "", timed_out=True)),
                             ("timeout-plist", Result(0, plist, "", timed_out=True)),
                             ("nonzero-plist", Result(1, plist, "SYNTHETIC")),
                             ("none-code", Result(None, "", ""))):
            with self.subTest(name=name):
                self.ws = self.base / "private" / f"ws-{name}"
                self.fake = FakeMac(self.base / name)
                self.ready_to_sign()
                self.replace_entitlement_reads(lambda n, path, answer=answer: answer)
                self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
                self.assertIn("lecture des entitlements en échec", self.output)
                self.assert_not_verified()

    def test_r1_malformed_entitlement_output_is_a_controlled_block(self):
        partial = '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict><key>'
        for name, text in (("partial", partial), ("array", plistlib.dumps(["x"]).decode()),
                           ("prefixed", "junk" + plistlib.dumps({}).decode()),
                           ("broken", '<?xml version="1.0"?><plist><dict><key>a</key></plist>'),
                           ("garbage", "SYNTHETIC not a plist")):
            with self.subTest(name=name):
                self.ws = self.base / "private" / f"ws-{name}"
                self.fake = FakeMac(self.base / name)
                self.ready_to_sign()
                self.replace_entitlement_reads(lambda n, path, text=text: Result(0, text, ""))
                self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
                self.assertIn("entitlements", self.output)
                self.assertNotIn("SYNTHETIC", self.transcript)
                self.assert_not_verified()

    def test_r1_signature_display_failure_blocks(self):
        self.ready_to_sign()
        original = self.fake._codesign
        self.fake._codesign = lambda args: Result(1, "", "SYNTHETIC display failure") if "-dvvv" in args \
            else original(args)
        self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
        self.assertIn("lecture de la signature en échec", self.output)
        self.assert_not_verified()

    def test_r1_nominal_and_forbidden_entitlements_keep_their_contract(self):
        self.ready_to_sign()
        reads = self.replace_entitlement_reads(lambda n, path: Result(0, "", ""))
        self.assertEqual(self.sign(), mn.EXIT_OK, self.output)
        self.assertEqual(self.state()["steps"]["sign"]["verified"]["entitlements"], "aucun")
        self.assertEqual(len(reads), self.state()["steps"]["sign"]["verified"]["objects"])
        self.assertEqual(len(reads), 12)  # les 12 lectures possibles de la fixture du 05
        for name, value in (("forbidden", {"com.apple.security.get-task-allow": True}),
                            ("unexpected", {"com.apple.security.cs.allow-jit": True})):
            with self.subTest(name=name):
                self.ws = self.base / "private" / f"ws-{name}"
                self.fake = FakeMac(self.base / name)
                self.ready_to_sign()
                self.replace_entitlement_reads(lambda n, path, v=value: Result(0, plistlib.dumps(v).decode(), ""))
                self.assertEqual(self.sign(), mn.EXIT_BLOCKED)
                self.assertNotIn("signed", self.state()["candidate"])

    def shareable_outputs(self):
        self.main("status", "--workspace", str(self.ws))
        return {"stdout+stderr": self.transcript, "status": self.output,
                "summary.md": (self.ws / "summary.md").read_text(encoding="utf-8"),
                "state.json": (self.ws / mn.STATE_FILE).read_text(encoding="utf-8")}

    def assert_markers_private_only(self):
        for name, text in self.shareable_outputs().items():
            for marker in (HOLDER, TEAM):
                self.assertNotIn(marker, text, name)
        private = "".join(p.read_text(encoding="utf-8") for p in (self.ws / "private").glob("notary-log*.json"))
        self.assertIn(HOLDER, private)
        self.assertNotIn("Traceback", self.transcript)

    def leaky_notary(self):
        """Commandes notarytool simulées dont stderr contient aussi les marqueurs fictifs."""
        original = self.fake._xcrun

        def xcrun(args):
            result = original(args)
            if args[1] == "notarytool":
                return Result(result.returncode, result.stdout, result.stderr + LEAK)
            return result

        self.fake._xcrun = xcrun

    def test_r2_invalid_log_with_synthetic_identity_stays_private(self):
        self.through_sign()
        self.leaky_notary()
        self.fake.info = [lambda: Result(0, json.dumps({"id": SUBMISSION, "status": "Invalid"}), "")]
        self.fake.log = {"status": "Invalid", "issues": [{"severity": "error", "message": LEAK}]}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("issue-error", self.output)
        self.assertIn("private/notary-log.json", self.output)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assert_markers_private_only()

    def test_r2_accepted_warning_with_synthetic_identity_stays_private(self):
        self.through_sign()
        self.leaky_notary()
        self.fake.log = {"issues": [{"severity": "warning", "message": LEAK}]}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_OK)
        self.assertIn("issue-warning", self.output)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling",
                                   "--acknowledge-log-warnings"), mn.EXIT_OK)
        self.assert_markers_private_only()

    def test_r2_external_text_in_schema_severity_or_status_is_never_echoed(self):
        cases = (("schema", {}, {"issues": LEAK}),
                 ("severity", {}, {"issues": [{"severity": LEAK, "message": LEAK}]}),
                 ("log-status", {}, {"status": LEAK, "issues": [{"severity": "warning", "message": LEAK}]}),
                 ("info-status", {"status": LEAK}, {"issues": [{"severity": "error", "message": LEAK}]}))
        for name, info, log in cases:
            with self.subTest(name=name):
                self.ws = self.base / "private" / f"ws-{name}"
                self.fake = FakeMac(self.base / name)
                self.transcript = ""
                self.through_sign()
                self.leaky_notary()
                response = dict({"id": SUBMISSION, "status": "Accepted"}, **info)
                self.fake.info = [lambda r=response: Result(0, json.dumps(r), "")]
                self.fake.log = log
                self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p",
                                           "--confirm-submission"), mn.EXIT_BLOCKED)
                self.assertNotEqual(self.state()["submission"]["status"], "Accepted")
                for text in self.shareable_outputs().values():
                    self.assertNotIn(HOLDER, text)
                    self.assertNotIn(TEAM, text)

    def test_r2_unexpected_internal_exception_is_reported_without_its_text(self):
        self.through_sign()
        original = mn.examine_notary_log

        def explode(*args, **kwargs):
            raise RuntimeError(LEAK)

        mn.examine_notary_log = explode
        try:
            self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p",
                                       "--confirm-submission"), mn.EXIT_BLOCKED)
        finally:
            mn.examine_notary_log = original
        self.assertIn("erreur interne RuntimeError", self.output)
        traces = "".join(p.read_text(encoding="utf-8") for p in (self.ws / "private").glob("internal-error-*.txt"))
        self.assertIn(HOLDER, traces)
        for text in self.shareable_outputs().values():
            self.assertNotIn(HOLDER, text)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling",
                                   "--acknowledge-log-warnings"), mn.EXIT_BLOCKED)

    def test_r3_empty_issues_object_blocks_accepted_and_stapling(self):
        self.through_sign()
        self.fake.log = {"issues": {}}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        submission = self.state()["submission"]
        self.assertNotEqual(submission["status"], "Accepted")
        self.assertIn("schema:issues", submission["review"]["errors"])
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling",
                                   "--acknowledge-log-warnings"), mn.EXIT_BLOCKED)
        self.assertEqual(self.fake.count("xcrun", "stapler"), 0)

    def test_r3_malformed_ticket_contents_blocks_through_the_workflow(self):
        self.through_sign()
        self.fake.log = {"ticketContents": {}}
        self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission"),
                         mn.EXIT_BLOCKED)
        self.assertIn("schema:ticketContents", self.state()["submission"]["review"]["errors"])
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling",
                                   "--acknowledge-log-warnings"), mn.EXIT_BLOCKED)

    def approved_plist(self):
        return write(self.base / "synthetic-approved.plist", plistlib.dumps({"com.apple.security.cs.allow-jit": True}))

    def test_r4_approved_exception_applies_to_app_and_its_main_executable_only(self):
        self.ready_to_sign()
        app = Path(os.path.realpath(self.app))
        main = app / "Contents/MacOS/SpoolScribe"
        approved = plistlib.dumps({"com.apple.security.cs.allow-jit": True}).decode()
        reads = self.replace_entitlement_reads(
            lambda n, path: Result(0, approved if path in (app, main) else "", ""))
        self.assertEqual(self.sign("--entitlements", str(self.approved_plist())), mn.EXIT_OK, self.output)
        self.assertEqual(self.state()["steps"]["sign"]["verified"]["entitlements"],
                         ["com.apple.security.cs.allow-jit"])
        self.assertIn(str(app), reads)
        self.assertIn(str(main), reads)
        signs = [c for c in self.fake.calls if "--sign" in c]
        self.assertEqual([c[-1] for c in signs if "--entitlements" in c], [str(app)])

    def test_r4_exception_on_unapproved_library_or_divergent_views_is_refused(self):
        approved = plistlib.dumps({"com.apple.security.cs.allow-jit": True}).decode()
        for name in ("library", "divergent"):
            with self.subTest(name=name):
                self.ws = self.base / "private" / f"ws-r4-{name}"
                self.fake = FakeMac(self.base / f"r4-{name}")
                self.ready_to_sign()
                app = Path(os.path.realpath(self.app))
                main = app / "Contents/MacOS/SpoolScribe"
                if name == "library":
                    wanted = {app, main, app / "Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib"}
                else:
                    wanted = {app}
                self.replace_entitlement_reads(lambda n, path, w=wanted: Result(0, approved if path in w else "", ""))
                self.assertEqual(self.sign("--entitlements", str(self.approved_plist())), mn.EXIT_BLOCKED)
                self.assertIn("différents des entitlements approuvés", self.output)
                self.assertNotIn("signed", self.state()["candidate"])

    # ── Reprise R2 (10-CODEX-POUR-CLAUDE-R3) : ProcedureError et RuntimeError, même scénario, mêmes marqueurs ──
    PRIVATE_PATH = "/Users/QA_SYNTHETIC_HOLDER_ONLY/Library/private-synthetic"
    FAMILIES = (
        ("RuntimeError", lambda: RuntimeError(LEAK), "erreur interne RuntimeError"),
        ("ProcedureError", lambda: mn.ProcedureError(LEAK), mn.UNLISTED_REFUSAL),
        ("ProcedureError-09", lambda: mn.ProcedureError(f"Developer ID Application: {HOLDER} ({TEAM})"),
         mn.UNLISTED_REFUSAL),
        ("ProcedureError-path", lambda: mn.ProcedureError(f"{LEAK} {WorkflowTests.PRIVATE_PATH}"),
         mn.UNLISTED_REFUSAL),
        ("ProcedureError-detail", lambda: mn.ProcedureError("autorité de signature inattendue",
                                                            detail=f"{LEAK} {WorkflowTests.PRIVATE_PATH}"),
         "autorité de signature inattendue"),
    )

    def inject_parser_failure(self, factory):
        original = mn.examine_notary_log

        def explode(*args, **kwargs):
            raise factory()

        mn.examine_notary_log = explode
        try:
            return self.main("notarize", "--workspace", str(self.ws), "--profile", "p", "--confirm-submission")
        finally:
            mn.examine_notary_log = original

    def assert_nothing_shareable_leaks(self, *texts, paths=True):
        workspace = (str(self.ws), os.path.realpath(self.ws), str(self.base), os.path.realpath(self.base))
        for text in texts:
            for forbidden in (HOLDER, TEAM, "Developer ID Application: ", self.PRIVATE_PATH, "Traceback",
                              *(workspace if paths else ())):
                self.assertNotIn(forbidden, text)

    def test_r2_procedure_error_and_runtime_error_stay_private_through_main(self):
        for name, factory, label in self.FAMILIES:
            with self.subTest(family=name):
                self.ws = self.base / "private" / f"ws-{name}"
                self.fake = FakeMac(self.base / name)
                self.transcript = ""
                self.through_sign()
                self.transcript = ""  # sorties produites à partir de l'erreur (prepare affiche son WS choisi)
                self.assertEqual(self.inject_parser_failure(factory), mn.EXIT_BLOCKED)
                stdout, stderr = self.output, self.errors_output
                self.assertIn(f"BLOQUÉ [notarize] : {label}", stdout)
                self.assertRegex(stdout, r"détail privé : private/(refusal|internal-error)-[0-9T+-]+-\d{3}\.txt")
                self.assertEqual(stderr, "")
                submission = self.state()["submission"]
                self.assertNotEqual(submission["status"], "Accepted")
                # Parseur restauré : aucune étape protégée ne devient possible à cause du traitement d'erreur.
                for step in (("staple", "--confirm-stapling", "--acknowledge-log-warnings"), ("package",),
                             ("assess", "--confirm-assessment")):
                    self.assertEqual(self.main(step[0], "--workspace", str(self.ws), *step[1:]), mn.EXIT_BLOCKED)
                self.assertEqual(self.main("notarize", "--workspace", str(self.ws), "--profile", "p",
                                           "--confirm-submission"), mn.EXIT_BLOCKED)
                self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 1)
                self.assertEqual(self.fake.count("xcrun", "stapler"), 0)
                shareable = self.shareable_outputs()
                self.assert_nothing_shareable_leaks(stdout, stderr, self.transcript, shareable["status"],
                                                    shareable["summary.md"])
                # state.json est privé (0600) et porte par conception le chemin du marqueur : marqueurs seulement.
                self.assert_nothing_shareable_leaks(shareable["state.json"], paths=False)
                self.assertNotIn("private/", shareable["summary.md"])
                traces = sorted((self.ws / "private").glob("*-*-[0-9][0-9][0-9].txt"))
                first = next(t for t in traces if t.name.startswith(("refusal-", "internal-error-")))
                self.assertEqual(stat.S_IMODE(os.lstat(first).st_mode), 0o600)
                body = first.read_text(encoding="utf-8")
                self.assertIn(HOLDER, body)
                self.assertIn(TEAM, body)
                self.assertIn("command: 'notarize'", body)
                self.assertIn("Traceback", body)
                if name != "RuntimeError":
                    self.assertIn("raw:", body)
                self.assertFalse(any("refusal-" in p or "internal-error-" in p
                                     for p in mn.tree_manifest(self.app)))

    def test_r2_procedure_traces_never_overwrite_previous_evidence(self):
        self.through_sign()
        self.assertEqual(self.inject_parser_failure(lambda: mn.ProcedureError(LEAK)), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("staple", "--workspace", str(self.ws), "--confirm-stapling"), mn.EXIT_BLOCKED)
        self.assertEqual(self.main("package", "--workspace", str(self.ws)), mn.EXIT_BLOCKED)
        traces = sorted(p.name for p in (self.ws / "private").glob("refusal-*.txt"))
        self.assertEqual(len(traces), 3)
        self.assertIn(HOLDER, (self.ws / "private" / traces[0]).read_text(encoding="utf-8")
                      + "".join((self.ws / "private" / t).read_text(encoding="utf-8") for t in traces))

    def test_r2_procedure_unavailable_private_trace_stays_blocked_without_leak(self):
        before = sorted(str(p) for p in self.base.rglob("*"))
        original = mn.Procedure.require_macos

        def leak(proc):
            raise mn.ProcedureError(f"{LEAK} {self.PRIVATE_PATH}")

        mn.Procedure.require_macos = leak
        try:
            code = self.main("build", "--workspace", str(self.ws))
        finally:
            mn.Procedure.require_macos = original
        self.assertEqual(code, mn.EXIT_BLOCKED)
        self.assertIn("détail privé indisponible", self.output)
        self.assert_nothing_shareable_leaks(self.output, self.errors_output)
        self.assertEqual(sorted(str(p) for p in self.base.rglob("*")), before)
        # Espace signé dont private/ est remplacé par un lien : refus, aucune écriture à travers le lien.
        self.through_sign()
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        private = self.ws / "private"
        os.rename(private, self.ws / "private-moved")
        os.symlink(elsewhere, private)
        self.assertEqual(self.inject_parser_failure(lambda: mn.ProcedureError(LEAK)), mn.EXIT_BLOCKED)
        self.assertIn("espace privé altéré", self.output)
        self.assertIn("détail privé indisponible", self.output)
        self.assert_nothing_shareable_leaks(self.output, self.errors_output)
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertNotIn("submission", self.state())
        self.assertEqual(self.fake.count("xcrun", "notarytool", "submit"), 0)
        # Même avec un espace déjà ouvert, _private_trace refuse d'écrire à travers un lien.
        proc = mn.Procedure(runner=self.fake, platform="darwin", out=io.StringIO(), xattrs=self.xattrs,
                            checkout=self.repo, tool_path=TOOL)
        proc.workspace, proc.state = Path(os.path.realpath(self.ws)), self.state()
        self.assertIsNone(mn._private_trace(proc, "refusal", "notarize", {"raw": LEAK}))
        self.assertEqual(list(elsewhere.iterdir()), [])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignore les droits")
    def test_r2_procedure_unwritable_private_folder_reports_unavailable_trace(self):
        self.through_sign()
        private = self.ws / "private"
        os.chmod(private, 0o500)
        try:
            self.assertEqual(self.inject_parser_failure(lambda: mn.ProcedureError(LEAK)), mn.EXIT_BLOCKED)
        finally:
            os.chmod(private, 0o700)
        self.assertIn("détail privé indisponible", self.output)
        self.assert_nothing_shareable_leaks(self.output, self.errors_output)
        self.assertFalse(list(private.glob("refusal-*.txt")))


class RefusalCatalogueTests(unittest.TestCase):
    """Le vocabulaire public est fermé : exactement les littéraux du code, sans interpolation."""

    def test_every_refusal_is_a_literal_of_the_closed_catalogue(self):
        import ast
        literals, others = set(), []
        for node in ast.walk(ast.parse(TOOL.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ProcedureError":
                first = node.args[0] if node.args else None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    literals.add(first.value)
                else:
                    others.append(node.lineno)
        self.assertEqual(others, [])
        self.assertEqual(literals, set(mn.PUBLIC_REFUSALS))
        for label in mn.PUBLIC_REFUSALS:
            self.assertNotRegex(label, r"\{|\}|%s|/Users/")

    def test_uncatalogued_text_is_never_the_public_form(self):
        exc = mn.ProcedureError(LEAK, detail=LEAK)
        for text in (str(exc), repr(exc), " ".join(map(str, exc.args))):
            self.assertNotIn(HOLDER, text)
            self.assertNotIn(TEAM, text)
        self.assertEqual((exc.public, exc.raw, exc.detail), (None, LEAK, LEAK))
        known = mn.ProcedureError("Hardened Runtime absent", detail=LEAK)
        self.assertEqual(str(known), "Hardened Runtime absent")
        self.assertNotIn(HOLDER, repr(known))


class NotaryLogSchemaTests(unittest.TestCase):
    """R3 : types bruts validés avant normalisation ; formes vides trompeuses refusées."""

    def review(self, **fields):
        log = {"jobId": SUBMISSION, "status": "Accepted", "sha256": "ab" * 32, "issues": None,
               "ticketContents": [{"path": "x.zip/SpoolScribe.app/Contents/MacOS/SpoolScribe"}]}
        log.update(fields)
        for key in [k for k, v in fields.items() if v is KeyError]:
            del log[key]
        return mn.examine_notary_log(log, submission_id=SUBMISSION, zip_sha256="ab" * 32,
                                     macho_paths=["Contents/MacOS/SpoolScribe"])

    def test_misleading_empty_or_wrong_types_are_schema_errors(self):
        for field, code, values in (
                ("issues", "schema:issues", ({}, False, True, 0, 1, "", "x", {"a": 1})),
                ("issues", "schema:issue", (["x"], [1], [None], [{}], [{"message": "m"}], [{"severity": 3}],
                                            [{"severity": "warning", "message": 5}])),
                ("ticketContents", "schema:ticketContents", ({}, False, True, 0, "", "x")),
                ("ticketContents", "schema:ticket", (["x"], [{}], [{"path": 3}], [None])),
                ("jobId", "schema:jobId", (None, 5, [], {})),
                ("status", "schema:status", (None, 0, False, [])),
                ("sha256", "schema:sha256", (5, "", "zz", ["ab"], False))):
            for value in values:
                with self.subTest(field=field, value=value):
                    review = self.review(**{field: value})
                    self.assertIn(code, review["errors"])

    def test_admitted_nominal_forms(self):
        self.assertEqual(self.review()["errors"], [])
        self.assertEqual(self.review(issues=[])["errors"], [])
        self.assertEqual(self.review(issues=KeyError)["errors"], [])
        structured = self.review(issues=[{"severity": "warning", "message": "deprecated SDK", "path": "x"}])
        self.assertEqual((structured["errors"], structured["warnings"]), ([], ["issue-warning"]))
        self.assertEqual(self.review(ticketContents=None)["warnings"], ["ticket-absent", "uncovered-macho"])
        self.assertEqual(self.review(ticketContents=[])["warnings"], ["uncovered-macho"])
        self.assertEqual(self.review(sha256=None)["warnings"], ["sha256-absent"])
        invalid = self.review(status="Invalid", issues=[{"severity": "error", "message": LEAK}])
        self.assertEqual(invalid["errors"], ["issue-error", "status-not-accepted"])
        self.assertEqual(invalid["status"], "Invalid")
        self.assertEqual(self.review(status=LEAK)["status"], "inattendu")
        self.assertNotIn(HOLDER, json.dumps(invalid))

    def test_categories_are_a_closed_vocabulary(self):
        review = self.review(status=LEAK, issues=[{"severity": LEAK, "message": LEAK}], ticketContents=LEAK)
        for code in review["errors"] + review["warnings"]:
            self.assertIn(code, mn.LOG_CATEGORIES)
        self.assertNotIn(HOLDER, json.dumps(review))
        self.assertNotIn(HOLDER, " ".join(mn.describe_categories(review["errors"])))

    def test_parse_entitlements_requires_a_successful_complete_read(self):
        nominal = plistlib.dumps({"com.apple.security.cs.allow-jit": True}).decode()
        self.assertEqual(mn.parse_entitlements(mn.Result(0, nominal, "")), {"com.apple.security.cs.allow-jit": True})
        for result in (mn.Result(23, "", "x"), mn.Result(0, "", "", timed_out=True), mn.Result(1, nominal, ""),
                       mn.Result(0, nominal[:-10], ""), mn.Result(0, "junk" + nominal, ""),
                       mn.Result(0, plistlib.dumps([1]).decode(), ""), "", None):
            with self.subTest(result=repr(result)), self.assertRaises(mn.ProcedureError):
                mn.parse_entitlements(result)


class UnregisteredLoadingTests(unittest.TestCase):
    """R5 : chargement importlib sans inscription préalable dans sys.modules, processus isolé."""

    SNIPPET = """
import importlib.util, sys
tool_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("qa_r2_unregistered", tool_path)
module = importlib.util.module_from_spec(spec)
assert spec.name not in sys.modules
spec.loader.exec_module(module)
assert spec.name not in sys.modules
assert module.Result(0, "", "").ok
assert not module.Result(0, "", "", timed_out=True).ok
assert module.Result(1, "o", "e").returncode == 1 and module.Result(0, "o", "e") == module.Result(0, "o", "e")
print("UNREGISTERED_OK", sys.version_info[:2])
"""

    def test_fresh_process_loads_tool_outside_sys_modules(self):
        done = subprocess.run([sys.executable, "-B", "-I", "-c", self.SNIPPET, str(TOOL)],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("UNREGISTERED_OK", done.stdout)

    def test_this_test_module_did_not_register_the_tool(self):
        self.assertNotIn("macos_notarize", sys.modules)
        self.assertTrue(mn.Result(0, "", "").ok)

    def test_cli_still_starts(self):
        done = subprocess.run([sys.executable, "-B", str(TOOL), "--help"], capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("preflight", done.stdout)


if __name__ == "__main__":
    unittest.main()
