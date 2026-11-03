"""Scan the native binary's QR outputs with a separate, CI-only decoder."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib


ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


def source_version(root):
    """Read version metadata without importing application code or its scripts package."""
    tree = ast.parse((root / "src/spoolscribe/core.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets))


def decode_transfer(text):
    """Independent Base45/zlib/SHA/NDEF oracle; no production decoder import."""
    if not isinstance(text, str) or not text.startswith("SSQR1:") or len(text) > 4296:
        raise ValueError("SSQR1 prefix/size")
    encoded = text[6:]
    raw = bytearray()
    for start in range(0, len(encoded), 3):
        group = encoded[start:start + 3]
        if len(group) == 1 or any(c not in ALPHABET for c in group):
            raise ValueError("Base45 characters/length")
        value = sum(ALPHABET.index(c) * 45 ** i for i, c in enumerate(group))
        if value >= (65536 if len(group) == 3 else 256):
            raise ValueError("Base45 overflow")
        raw.extend(value.to_bytes(2 if len(group) == 3 else 1, "big"))
    if len(raw) < 37 or raw[0] not in (1, 2) or raw[1] not in (0, 1):
        raise ValueError("SSQR1 header")
    length = int.from_bytes(raw[2:4], "big")
    if not 1 <= length <= 4096:
        raise ValueError("NDEF size")
    if raw[1]:
        decoder = zlib.decompressobj()
        message = decoder.decompress(bytes(raw[36:]), length + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("zlib stream")
    else:
        message = bytes(raw[36:])
    if len(message) != length or hashlib.sha256(message).digest() != raw[4:36]:
        raise ValueError("NDEF length/digest")
    if len(message) < 3:
        raise ValueError("NDEF header")
    flags, type_length = message[:2]
    if flags not in (0xD2, 0xC2):
        raise ValueError("NDEF TNF/flags/ID/record count")
    offset = 3 if flags == 0xD2 else 6
    size = message[2] if flags == 0xD2 else int.from_bytes(message[2:6], "big")
    mime = message[offset:offset + type_length]
    payload = message[offset + type_length:]
    if mime != {1: b"application/json", 2: b"application/opentag3d"}[raw[0]] or len(payload) != size:
        raise ValueError("NDEF MIME/payload")
    return bytes(message), dict(tnf=2, mime=mime.decode("ascii"), identifier="", records=1,
                               payload_sha256=hashlib.sha256(payload).hexdigest())


def verify_outputs(folder, root):
    # These packages are installed after packaging, in CI only.
    from PIL import Image
    import zxingcpp
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    result = json.loads((folder / "frozen-ssqr1.json").read_text(encoding="utf-8"))
    assert result["frozen"] and result["offline"] and result["fixtures_absent"]
    assert all(result["oracles_absent"].values())
    assert result["license_sha256"] == hashlib.sha256((root / "data/licenses/Segno-LICENSE.txt").read_bytes()).hexdigest()
    assert result["version"] == source_version(root)
    vectors = json.loads((root / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))["vectors"]
    assert len(result["rows"]) == 24
    scans = []
    for row in result["rows"]:
        expected = bytes.fromhex(vectors[row["case"]]["hex"])
        message, metadata = decode_transfer(row["text"])
        assert message == expected == bytes.fromhex(row["ndef_hex"])
        images = [(row["screen"], Image.open(folder / row["screen"]))]
        if "png" in row:
            image = Image.open(folder / row["png"])
            scale, remainder = divmod(image.width, row["modules"])
            assert not remainder and scale >= 1 and image.mode == "1" and image.width == image.height
            assert image.crop((0, 0, image.width, 4 * scale)).getextrema() == (255, 255)
            assert image.crop((0, 0, 4 * scale, image.height)).getextrema() == (255, 255)
            images.append((row["png"], image))
            renderer = QSvgRenderer(str(folder / row["svg"]))
            assert renderer.isValid()
            side = row["modules"] * 4
            raster = QImage(side, side, QImage.Format_RGB32)
            raster.fill(Qt.white)
            painter = QPainter(raster)
            renderer.render(painter)
            painter.end()
            path = folder / (row["svg"] + ".png")
            assert raster.save(str(path))
            images.append((row["svg"], Image.open(path)))
        for name, image in images:
            codes = zxingcpp.read_barcodes(image)
            assert len(codes) == 1 and codes[0].text == row["text"], name
            decoded, record = decode_transfer(codes[0].text)
            assert decoded == expected and record == metadata, name
            scans.append(dict(file=name, exact=True, **metadata))
    summary = dict(version=result["version"], segno=result["segno"], cases=len(result["rows"]),
                   independent_scans=len(scans), scans=scans, offline=True)
    (folder / "verified-ssqr1.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("FROZEN_SSQR1_OK", json.dumps(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    relative = ("SpoolScribe.exe" if sys.platform == "win32" else
                "SpoolScribe.app/Contents/MacOS/SpoolScribe" if sys.platform == "darwin" else "SpoolScribe")
    binary = args.binary or root / "dist" / relative
    with tempfile.TemporaryDirectory(prefix="ssqr1-native-") as directory:
        folder = args.output or Path(directory) / "outputs"
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SPOOLSCRIBE_RUN_SCRIPT_ALLOW=str(root / ".github/scripts"),
                   SPOOLSCRIBE_SSQR1_OUTPUT=str(folder), SPOOLSCRIBE_SSQR1_VECTORS=str(root / "tests/fixtures/qr/ssqr1_vectors.json"),
                   SPOOLSCRIBE_DATA_HOME=str(Path(directory) / "user"), SPOOLSCRIBE_CONFIG_PATH=str(Path(directory) / "config.json"))
        subprocess.run([str(binary), "--run-script", str(root / ".github/scripts/probe_frozen_ssqr1.py")],
                       env=env, check=True, timeout=180)
        verify_outputs(folder, root)


if __name__ == "__main__":
    main()
