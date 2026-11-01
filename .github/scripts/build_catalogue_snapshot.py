"""Build a reviewed offline OFD extension and logo contact sheets from an archive.

Development tool only. Requires the existing build dependencies Pillow/PySide6.
No downloads: the caller supplies the source archive and its verified commit.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image, ImageChops, ImageDraw, ImageStat
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt, QRectF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import catalogue_sources, db_io


def prepare_logo(raw, suffix):
    if suffix == ".svg":
        tree = ET.fromstring(raw)
        for element in tree.iter():
            if element.tag.split("}")[-1] in ("script", "foreignObject", "image"):
                raise ValueError("Contenu SVG externe/non vectoriel")
            for key, value in element.attrib.items():
                if key.lower().startswith("on") or key.endswith("href") and not value.startswith("#"):
                    raise ValueError("Référence SVG externe")
        if re.search(rb"<!DOCTYPE|<!ENTITY|@import|url\s*\(\s*['\"]?(?:https?:|file:|data:)", raw, re.I):
            raise ValueError("Référence SVG externe")
        renderer = QSvgRenderer(raw)
        if not renderer.isValid():
            raise ValueError("SVG illisible")
        box = renderer.viewBoxF()
        if box.width() <= 0 or box.height() <= 0:
            raise ValueError("Dimensions SVG invalides")
        scale = min(640 / box.width(), 208 / box.height())
        width, height = max(1, round(box.width() * scale)), max(1, round(box.height() * scale))
        image = QImage(width, height, QImage.Format_RGBA8888)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, width, height))
        painter.end()
        preview = Image.frombytes("RGBA", (width, height), bytes(image.constBits()), "raw", "RGBA", image.bytesPerLine())
        if preview.getbbox() is None:
            raise ValueError("SVG vide")
        # Remove transparent viewBox padding without changing vector artwork.
        bounds = preview.getbbox()
        if bounds != (0, 0, width, height):
            left, top, right, bottom = bounds
            tree.set("viewBox", f"{box.x()+left/scale} {box.y()+top/scale} {(right-left)/scale} {(bottom-top)/scale}")
            raw = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
            preview = preview.crop(bounds)
        # Normalize indentation-only empty lines, preserving all artwork/text.
        raw = re.sub(rb"(?m)^[ \t]+(?=\r?$)", b"", raw)
        return raw, ".svg", preview
    if suffix not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Format d'image non pris en charge")
    with Image.open(io.BytesIO(raw)) as src:
        if src.width * src.height > 25000000:
            raise ValueError("Image trop grande")
        src.load()
        image = src.convert("RGBA")
    bounds = image.getbbox()
    if bounds:
        image = image.crop(bounds)
    # Trim only truly uniform outer margins; preserve the artwork and colors.
    rgb = image.convert("RGB")
    corner = rgb.getpixel((0, 0))
    if all(rgb.getpixel(p) == corner for p in ((rgb.width-1, 0), (0, rgb.height-1), (rgb.width-1, rgb.height-1))):
        bounds = ImageChops.difference(rgb, Image.new("RGB", rgb.size, corner)).getbbox()
        if bounds:
            image = image.crop(bounds)
    w, h = image.size
    ratio = min(320 / w, 104 / h, 1)
    if w * ratio < 60 or h * ratio < 24:
        raise ValueError(f"Logo trop petit/étroit pour un affichage lisible ({w}×{h})")
    if max(ImageStat.Stat(image).stddev) < 3:
        raise ValueError("Image quasiment uniforme")
    # Limit unnecessary multi-megapixel assets, never upscale.
    image.thumbnail((1280, 416), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream, "PNG", optimize=True)
    return stream.getvalue(), ".png", image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--spoolman", type=Path, help="Optional downloaded SpoolmanDB filaments.json")
    parser.add_argument("--spoolman-license", type=Path)
    args = parser.parse_args()
    if args.spoolman and not args.spoolman_license:
        parser.error("--spoolman-license is required with --spoolman")
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("Commit SHA-1 attendu")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use an empty output directory; review before copying into the repository")
    app = QApplication.instance() or QApplication([])
    raw = args.archive.read_bytes()
    files = catalogue_sources.read_ofd_archive(raw)
    digest = hashlib.sha256(raw).hexdigest()
    initial, _ = catalogue_sources.adapt_ofd(files, source_digest=digest)
    asset_dir = args.output / "data/brands/logos"
    catalogues = args.output / "tests/fixtures/catalogues"
    audits = catalogues / "audits"
    licenses = args.output / "data/licenses"
    for directory in (catalogues, audits, licenses):directory.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    args.review.mkdir(parents=True, exist_ok=True)
    manifest, rejected, previews = {}, [], []
    unique_artwork = {}
    exclusions = json.loads((Path(__file__).resolve().parents[1] / "catalogue-logo-exclusions.json").read_text())
    for name, meta in sorted(initial["_brands"].items(), key=lambda pair: pair[0].casefold()):
        slug = meta["source_slug"]
        source = db_io.parse_json(files[f"data/{slug}/brand.json"])
        logo_name = source.get("logo") or ""
        path = f"data/{slug}/{logo_name}"
        try:
            if slug in exclusions:
                raise ValueError("Revue visuelle : " + exclusions[slug])
            if Path(logo_name).name != logo_name or not logo_name:
                raise ValueError("Chemin de logo invalide ou absent")
            original = files[path]
            content, suffix, preview = prepare_logo(original, Path(path).suffix.lower())
            asset_hash = hashlib.sha256(content).hexdigest()
            target = unique_artwork.get(asset_hash)
            if target is None:
                target = asset_dir / (slug + suffix)
                target.write_bytes(content)
                unique_artwork[asset_hash] = target
            manifest[meta["source_id"]] = {"name": name, "path": f"data/brands/logos/{target.name}",
                "source_path": path, "source_commit": args.commit,
                "source_sha256": hashlib.sha256(original).hexdigest(),
                "sha256": hashlib.sha256(content).hexdigest(), "width": preview.width, "height": preview.height}
            previews.append((name, preview))
        except (ValueError, KeyError, OSError, ET.ParseError) as exc:
            rejected.append({"brand": name, "reason": str(exc)})
    (asset_dir.parent / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (licenses / "OFD-LICENSE.txt").write_bytes(files["LICENSE"])
    db, report = catalogue_sources.adapt_ofd(files, source_digest=digest, logos=manifest)
    report.update(source_commit=args.commit, logos_approved=len(manifest), logos_rejected=rejected)
    db["_source_snapshot"]["source_commit"] = args.commit
    (catalogues / "catalogue_ofd.json").write_text(json.dumps(db, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (audits / "catalogue_ofd_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.spoolman:
        spoolman_raw = args.spoolman.read_bytes()
        existing = db_io.load_db(Path(__file__).resolve().parents[2] / "tests/fixtures/catalogues/polymaker_db.json")
        supplement, supplement_report = catalogue_sources.adapt_spoolman(
            db_io.parse_json(spoolman_raw), source_digest=hashlib.sha256(spoolman_raw).hexdigest(),
            covered_brands=set(db["_brands"]) | set(existing["_brands"]))
        (catalogues / "catalogue_spoolman.json").write_text(json.dumps(supplement, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (audits / "catalogue_spoolman_audit.json").write_text(json.dumps(supplement_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (licenses / "SpoolmanDB-LICENSE.txt").write_bytes(args.spoolman_license.read_bytes())
    for offset in range(0, len(previews), 40):
        sheet = Image.new("RGB", (1200, 1400), "#eeeeee")
        draw = ImageDraw.Draw(sheet)
        for i, (name, image) in enumerate(previews[offset:offset+40]):
            x, y = (i % 4) * 300, (i // 4) * 140
            draw.text((x+8, y+4), name, fill="black")
            for j, background in enumerate(("#ffffff", "#262626")):
                tile = Image.new("RGBA", (292, 52), background)
                logo = image.copy()
                logo.thumbnail((276, 46), Image.Resampling.LANCZOS)
                tile.alpha_composite(logo, ((292-logo.width)//2, (52-logo.height)//2))
                sheet.paste(tile.convert("RGB"), (x+4, y+22+j*55))
        sheet.save(args.review / f"logos-{offset//40+1}.png")
    print(json.dumps({k:v for k,v in report.items() if k not in ("rejected", "logos_rejected")}, indent=2))
    print("Logos non retenus :", json.dumps(rejected, ensure_ascii=False))


if __name__ == "__main__":
    main()
