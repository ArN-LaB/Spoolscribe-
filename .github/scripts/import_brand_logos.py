"""Import reviewed manufacturer logos with a transparent background.

Development tool. Input: a sources.json produced during logo review (list of
{"slug", "brand", "file", "url", "source_kind", ...}) plus the downloaded files.
Each logo is normalised (SVG sanitised and cropped to its artwork, raster
converted to RGBA with a uniform background made transparent, trimmed and
bounded), written to data/brands/logos/<slug>.<ext> and recorded in
data/brands/manifest.json with its provenance. ``--retouch-existing``
reprocesses the raster logos already listed so every one has a transparent
background. Nothing is downloaded here.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
from scripts.catalogue_sources import brand_key  # noqa: E402
import build_catalogue_snapshot as snapshot  # noqa: E402

LOGO_DIR = ROOT / "data" / "brands" / "logos"
MANIFEST = LOGO_DIR.parent / "manifest.json"
TOLERANCE = 34  # per-channel distance accepted as "same background"


def make_transparent(image: Image.Image) -> tuple[Image.Image, int]:
    """Flood the uniform outer background from the edges and make it transparent.

    Only edge-connected pixels close to the corner colour are affected, so the
    artwork (including white or black strokes inside it) is untouched. Returns
    the new image and the number of pixels made transparent.
    """
    image = image.convert("RGBA")
    if image.getpixel((0, 0))[3] == 0:
        return image, 0  # already transparent
    rgb = image.convert("RGB")
    w, h = rgb.size
    # The background is the dominant colour along the border (quantised), not
    # necessarily the top-left pixel: artwork may touch one or two corners.
    border = [rgb.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + [rgb.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
    buckets = {}
    for c in border:
        key = tuple(v // 24 for v in c)
        buckets[key] = buckets.get(key, 0) + 1
    dominant = max(buckets, key=buckets.get)
    share = buckets[dominant] / len(border)
    members = [c for c in border if tuple(v // 24 for v in c) == dominant]
    reference = tuple(sum(c[i] for c in members) // len(members) for i in range(3))
    if share < 0.45:
        return image, 0  # no uniform background around the artwork: leave it alone
    if max(reference) - min(reference) > 40:
        return image, 0  # a coloured border is artwork (a filled logo), not a background
    sentinel = (1, 254, 1) if reference != (1, 254, 1) else (254, 1, 254)
    work = rgb.copy()
    seeds = [(x, y) for x in range(0, w, max(1, w // 24)) for y in (0, h - 1)] + [(x, y) for y in range(0, h, max(1, h // 12)) for x in (0, w - 1)]
    for seed in seeds:
        if work.getpixel(seed) != sentinel and max(abs(a - b) for a, b in zip(work.getpixel(seed), reference)) <= TOLERANCE:
            ImageDraw.floodfill(work, seed, sentinel, thresh=TOLERANCE)
    alpha = image.getchannel("A")
    removed = 0
    pixels, mask = work.load(), alpha.load()
    for y in range(h):
        for x in range(w):
            if pixels[x, y] == sentinel:
                mask[x, y] = 0
                removed += 1
    if removed >= w * h * 0.98:
        return image, 0  # the "background" was the whole image: nothing meaningful left
    image.putalpha(alpha)
    bounds = image.getbbox()
    if bounds:
        image = image.crop(bounds)
    return image, removed


def process_raster(raw: bytes) -> tuple[bytes, Image.Image, int]:
    with Image.open(io.BytesIO(raw)) as src:
        if src.width * src.height > 40_000_000:
            raise ValueError("Image trop grande")
        src.load()
        image = src.convert("RGBA")
    image, removed = make_transparent(image)
    if image.width < 60 or image.height < 24:
        raise ValueError(f"Logo trop petit ({image.width}×{image.height})")
    image.thumbnail((1600, 520), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream, "PNG", optimize=True)
    return stream.getvalue(), image, removed


def record(manifest: dict, key: str, name: str, path: Path, data: bytes, image, source: dict) -> None:
    entry = manifest.get(key, {})
    entry.update({"name": name, "path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
                  "width": image.width, "height": image.height, "transparent_background": True})
    if source:
        entry["logo_source"] = {k: source[k] for k in ("url", "source_kind", "licence_note", "retrieved") if source.get(k)}
    manifest[key] = entry
    for other_key, other in manifest.items():
        if other_key != key and other.get("path") == entry["path"]:
            for field in ("sha256", "width", "height", "transparent_background"):
                other[field] = entry[field]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, help="sources.json of the logo review")
    parser.add_argument("--retouch-existing", action="store_true", help="make every listed raster logo transparent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_brand = {brand_key(v["name"]): k for k, v in manifest.items() if isinstance(v, dict) and v.get("name")}
    report = {"imported": [], "retouched": [], "skipped": []}

    if args.retouch_existing:
        for key, entry in manifest.items():
            path = ROOT / entry["path"]
            if path.suffix.lower() != ".png" or not path.is_file():
                continue
            data, image, removed = process_raster(path.read_bytes())
            if removed:
                if not args.dry_run:
                    path.write_bytes(data)
                    record(manifest, key, entry["name"], path, data, image, entry.get("logo_source"))
                report["retouched"].append(f"{entry['name']} ({removed} px)")
            else:
                report["skipped"].append(entry["name"])

    if args.sources:
        base = args.sources.parent
        for source in json.loads(args.sources.read_text(encoding="utf-8")):
            if not source.get("file") or not source.get("verified", True):
                report["skipped"].append(f"{source.get('brand')} : pas de fichier vérifié")
                continue
            raw_path = base / source["file"]
            raw = raw_path.read_bytes()
            try:
                suffix = raw_path.suffix.lower()
                if suffix == ".svg":
                    data, ext, preview = snapshot.prepare_logo(raw, ".svg")
                    image = preview
                else:
                    data, image, _ = process_raster(raw)
                    ext = ".png"
            except Exception as exc:
                report["skipped"].append(f"{source['brand']} : {exc}")
                continue
            slug = source["slug"]
            key = by_brand.get(brand_key(source["brand"]), slug)
            target = LOGO_DIR / f"{slug}{ext}"
            old = manifest.get(key, {}).get("path")
            if not args.dry_run:
                target.write_bytes(data)
                if old and (ROOT / old) != target and (ROOT / old).is_file():
                    (ROOT / old).unlink()
                record(manifest, key, source["brand"], target, data, image, dict(source, retrieved=source.get("retrieved", "")))
            report["imported"].append(f"{source['brand']} → {target.name} ({image.width}×{image.height})")
    if not args.dry_run:
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
