"""Validate the user-facing layout and native executable of a distribution ZIP."""
import argparse
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import zipfile


def verify_archive(path: Path, expected_version: str | None = None) -> dict:
    platform = {
        "SpoolScribe-windows.zip": "windows",
        "SpoolScribe-linux.zip": "linux",
        "SpoolScribe-macos.zip": "macos",
    }.get(path.name)
    if platform is None:
        raise ValueError(f"Unexpected archive name: {path.name}")
    root = {"windows": "SpoolScribe.exe", "linux": "SpoolScribe", "macos": "SpoolScribe.app"}[platform]
    binary = root + "/Contents/MacOS/SpoolScribe" if platform == "macos" else root

    def require(condition, message):
        if not condition:
            raise ValueError(f"{path.name}: {message}")

    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(bool(names) and len(names) == len(set(names)), "empty or duplicate ZIP entries")
        require(all(not PurePosixPath(n).is_absolute() and ".." not in PurePosixPath(n).parts
                    and "\\" not in n for n in names), "unsafe ZIP path")
        require({n.split("/")[0] for n in names} == {root}, f"expected only {root} at archive root")
        if platform != "macos":
            require(names == [binary], "unexpected extra files")
        require(binary in names, "native executable missing")
        require(archive.testzip() is None, "ZIP CRC failure")
        with archive.open(binary) as stream:
            magic = stream.read(4)
        require({"windows": magic[:2] == b"MZ", "linux": magic == b"\x7fELF",
                 "macos": magic in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
                                    b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                                    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")}[platform],
                "wrong native executable format")
        if platform in ("linux", "macos"):
            require(archive.getinfo(binary).external_attr >> 16 & stat.S_IXUSR, "executable permission missing")
        if platform == "macos":
            info = plistlib.loads(archive.read(root + "/Contents/Info.plist"))
            require(info.get("CFBundleExecutable") == "SpoolScribe", "wrong bundle executable")
            if expected_version:
                require(info.get("CFBundleShortVersionString") == expected_version
                        and info.get("CFBundleVersion") == expected_version, "wrong bundle version")
    return {"archive": path.name, "platform": platform, "root": root, "binary": binary, "entries": len(names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--version")
    args = parser.parse_args()
    version = args.version
    if version is None:
        core = (Path(__file__).resolve().parents[2] / "src/spoolscribe/core.py").read_text(encoding="utf-8")
        version = re.search(r'^APP_VERSION = "([^"]+)"$', core, re.M).group(1)
    for path in args.archives:
        print(json.dumps(verify_archive(path, version)))


if __name__ == "__main__":
    main()
