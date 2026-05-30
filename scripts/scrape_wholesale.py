#!/usr/bin/env python3
"""scrape_wholesale.py — Download Polymaker US wholesale catalogue,
extract SKU+hex+color data, and update polymaker_db.json.

Usage:
    python scrape_wholesale.py [--dry-run]

Options:
    --dry-run   Show what would change without writing to DB.
"""
import json
import os
import re
import sys
import time
import urllib.error
from datetime import datetime
import urllib.request
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")
DB_FILE = os.path.join(DATA_DIR, "polymaker_db.json")
RAW_OUT = os.path.join(DATA_DIR, "wholesale_raw.json")
WHOLESALE_BASE = "https://us-wholesale.polymaker.com/products.json?limit=250&page={}"

# ── Product-title → _products key mapping ──────────────────────────────────
# Keys are normalized (lowercase, regular spaces); values are exact _products keys.
# The matcher checks if ANY key is a substring of the normalized product title.
# Sorted by length descending so more specific keys match first.
TITLE_MAP = {
    # ── Panchroma line (PLA) ──────────────────────────────────────
    "panchroma™ uv shift pla":          "Panchroma PLA UV Shift",
    "panchroma™ dual silk pla":         "Panchroma PLA Silk",
    "panchroma™ gradient silk pla":     "Panchroma PLA Silk",
    "panchroma™ gradient starlight":    "Panchroma PLA Starlight",
    "panchroma™ gradient celestial":    "Panchroma PLA Celestial",
    "panchroma™ gradient matte pla":    "PolyTerra PLA",
    "panchroma™ gradient galaxy":       "Panchroma PLA Galaxy",
    "panchroma™ gradient neon":         "Panchroma PLA Neon",
    "panchroma™ gradient satin pla":    "PolyTerra PLA+",
    "panchroma™ gradient translucent":  "Panchroma PLA",
    "panchroma™ gradient crystal":      "Panchroma PLA",
    "panchroma™ dual matte pla":        "PolyTerra PLA",
    "panchroma™ dual special pla":      "Panchroma PLA",
    "panchroma™ luminous pla":          "Panchroma PLA Glow",
    "panchroma™ satin pla":             "PolyTerra PLA+",    # formerly PolyTerra PLA+
    "panchroma™ matte pla":             "PolyTerra PLA",     # formerly PolyTerra PLA
    "panchroma™ marble pla":            "PolyTerra PLA",
    "panchroma™ metallic pla":          "Polymaker PLA Pro Metallic",
    "panchroma™ starlight pla":         "Panchroma PLA Starlight",
    "panchroma™ celestial pla":         "Panchroma PLA Celestial",
    "panchroma™ galaxy pla":            "Panchroma PLA Galaxy",
    "panchroma™ silk pla":              "Panchroma PLA Silk",
    "panchroma™ glow pla":              "Panchroma PLA Glow",
    "panchroma™ neon pla":              "Panchroma PLA Neon",
    "panchroma™ translucent pla":       "Panchroma PLA",
    "panchroma™ pla refill":            "Panchroma PLA",
    "panchroma™ pla":                   "Panchroma PLA",
    "panchroma™ cope":                  "Panchroma CoPE",
    # ── PolyTerra ──────────────────────────────────────────────────
    "polyterra™ pla+":  "PolyTerra PLA+",
    "polyterra™ pla":   "PolyTerra PLA",
    # ── PolyLite ───────────────────────────────────────────────────
    "polylite™ metallic pla pro": "Polymaker PLA Pro Metallic",
    "polylite™ pla pro":          "Polymaker PLA Pro",    # PolyLite PLA Pro = Polymaker PLA Pro
    "polylite™ translucent petg": "PolyLite PETG",
    "polylite™ galaxy abs":       "PolyLite ABS",
    "polylite™ neon abs":         "PolyLite ABS",
    "polylite™ cospla":           "PolyLite CosPLA",
    "polylite™ lw-pla":           "PolyLite LW-PLA",
    "polylite™ pla-cf":           "PolyLite PLA-CF",
    "polylite™ abs":              "PolyLite ABS",
    "polylite™ petg":             "PolyLite PETG",
    "polylite™ pla":              "PolyLite PLA",
    "polylite™ pc":               "PolyLite PC",
    # ── Polymaker HT-PLA ────────────────────────────────────────────
    "polymaker ht-pla-gf":        "Polymaker HT-PLA-GF",
    "polymaker ht-pla":           "Polymaker HT-PLA",
    # ── PolySonic ───────────────────────────────────────────────────
    "polysonic™ pla":             "PolySonic PLA",
    # ── Polymaker PLA/PETG/ASA ──────────────────────────────────────
    "polymaker™ galaxy asa":      "Polymaker ASA",
    "polymaker™ asa":             "Polymaker ASA",        # formerly PolyLite ASA
    "polymaker™ petg":            "Polymaker PETG",
    "polymaker™ pla pro":         "Polymaker PLA Pro",
    "polymaker pc-abs":           "Polymaker PC-ABS",
    "polymaker pc-pbt":           "Polymaker PC-PBT",
    # ── PolyFlex TPU ────────────────────────────────────────────────
    "polyflex™ tpu95-hf":         "PolyFlex TPU95-HF",
    "polyflex™ tpu95":            "PolyFlex TPU95",
    "polyflex™ tpu90":            "PolyFlex TPU90",
    # ── PolyMax ─────────────────────────────────────────────────────
    "polymax™ petg-esd":          "PolyMax PETG-ESD",
    "polymax™ pc-fr":             "PolyMax PC-FR",
    "polymax™ petg":              "PolyMax PETG",
    "polymax™ pla":               "PolyMax PLA",
    "polymax™ pc":                "PolyMax PC",
    # ── PolyMide (Nylon) ────────────────────────────────────────────
    "polymide™ pa12-cf":          "PolyMide PA12-CF",
    "polymide™ pa6-cf":           "PolyMide PA6-CF",
    "polymide™ pa6-gf":           "PolyMide PA6-GF",
    "polymide™ pa612-cf":         "PolyMide PA612-CF",
    "polymide™ copa":             "PolyMide CoPA",
    # ── PolySmooth / PolyDissolve / PolyWood ────────────────────────
    "polysmooth™":                "PolySmooth",
    "polydissolve™":              "PolyDissolve S1",
    "polywood":                   "PolyWood",
    # ── PolySupport ─────────────────────────────────────────────────
    "polysupport™ for pa12":      "PolySupport PA12",
    "polysupport™ for pla":       "PolySupport PLA",
    # ── Fiberon ─────────────────────────────────────────────────────
    "fiberon™ pa12-cf10":         "Fiberon PA12-CF10",
    "fiberon™ pa6-cf20":          "Fiberon PA6-CF20",
    "fiberon™ pa6-gf25":          "Fiberon PA6-GF25",
    "fiberon™ pa612-cf15":        "Fiberon PA612-CF15",
    "fiberon™ pa612-esd":         "Fiberon PA612-ESD",
    "fiberon™ pet-cf17":          "Fiberon PET-CF17",
    "fiberon™ pet-gf15":          "Fiberon PET-GF15",
    "fiberon™ petg-esd":          "Fiberon PETG-ESD",
    "fiberon™ petg-rcf08":        "Fiberon PETG-rCF08",
    "fiberon™ asa-cf08":          "Fiberon ASA-CF08",
    "fiberon™ pps-cf10":          "Fiberon PPS-CF10",
    "fiberon™ pps-gf20":          "Fiberon PPS-GF20",
    "fiberon™ pps-cf20":          "Fiberon PPS-CF20",
}

# Products to skip entirely (accessories, devices, non-filament)
SKIP_PRODUCTS = {
    "matte pla for production",
    "polybox™",
    "polydryer™",
    "polybox™ edition",
    "polysher™",
    "polycast™",           # Lost-PLA casting; not a standard filament profile
}

# ── New product definitions (added to _products if key missing) ────────────
# Format: { product_key: { ...fields... } }
NEW_PRODUCTS: dict[str, dict] = {
    "PolySonic PLA": {
        "type": "PLA", "subtype": "HighSpeed", "brand": "Polymaker",
        "min_temp": 220, "max_temp": 260, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.23,
    },
    "Polymaker ASA": {
        "type": "ASA", "subtype": None, "brand": "Polymaker",
        "min_temp": 220, "max_temp": 260, "bed_min_temp": 90, "bed_max_temp": 105,
        "diameter": 1.75, "density": 1.07,
    },
    "Panchroma CoPE": {
        "type": "PLA", "subtype": "CoPE", "brand": "Polymaker",
        "min_temp": 190, "max_temp": 230, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.17,
    },
    "PolyLite PC": {
        "type": "PC", "subtype": None, "brand": "Polymaker",
        "min_temp": 245, "max_temp": 280, "bed_min_temp": 90, "bed_max_temp": 115,
        "diameter": 1.75, "density": 1.20,
    },
    "PolyLite LW-PLA": {
        "type": "PLA", "subtype": "LW", "brand": "Polymaker",
        "min_temp": 200, "max_temp": 240, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 0.64,
    },
    "PolyLite PLA-CF": {
        "type": "PLA-CF", "subtype": None, "brand": "Polymaker",
        "min_temp": 190, "max_temp": 230, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.30,
    },
    "PolyFlex TPU90": {
        "type": "TPU", "subtype": "Shore90A", "brand": "Polymaker",
        "min_temp": 195, "max_temp": 230, "bed_min_temp": 35, "bed_max_temp": 45,
        "diameter": 1.75, "density": 1.22,
    },
    "PolyFlex TPU95-HF": {
        "type": "TPU", "subtype": "HighFlow", "brand": "Polymaker",
        "min_temp": 210, "max_temp": 250, "bed_min_temp": 35, "bed_max_temp": 35,
        "diameter": 1.75, "density": 1.22,
    },
    "PolyMax PLA": {
        "type": "PLA", "subtype": "MaxStrength", "brand": "Polymaker",
        "min_temp": 190, "max_temp": 230, "bed_min_temp": 35, "bed_max_temp": 65,
        "diameter": 1.75, "density": 1.17,
    },
    "PolyMax PETG": {
        "type": "PETG", "subtype": "MaxStrength", "brand": "Polymaker",
        "min_temp": 230, "max_temp": 260, "bed_min_temp": 65, "bed_max_temp": 80,
        "diameter": 1.75, "density": 1.25,
    },
    "PolyMax PETG-ESD": {
        "type": "PETG", "subtype": "ESD", "brand": "Polymaker",
        "min_temp": 230, "max_temp": 260, "bed_min_temp": 65, "bed_max_temp": 80,
        "diameter": 1.75, "density": 1.28,
    },
    "PolyMax PC": {
        "type": "PC", "subtype": "MaxStrength", "brand": "Polymaker",
        "min_temp": 260, "max_temp": 290, "bed_min_temp": 100, "bed_max_temp": 120,
        "diameter": 1.75, "density": 1.20,
    },
    "PolyMax PC-FR": {
        "type": "PC", "subtype": "FlameRetardant", "brand": "Polymaker",
        "min_temp": 260, "max_temp": 290, "bed_min_temp": 90, "bed_max_temp": 110,
        "diameter": 1.75, "density": 1.40,
    },
    "PolyMide CoPA": {
        "type": "PA", "subtype": "CoPA", "brand": "Polymaker",
        "min_temp": 235, "max_temp": 275, "bed_min_temp": 70, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.06,
    },
    "PolyMide PA12-CF": {
        "type": "PA-CF", "subtype": None, "brand": "Polymaker",
        "min_temp": 250, "max_temp": 270, "bed_min_temp": 80, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.08,
    },
    "PolyMide PA6-CF": {
        "type": "PA6-CF", "subtype": None, "brand": "Polymaker",
        "min_temp": 250, "max_temp": 280, "bed_min_temp": 80, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.13,
    },
    "PolyMide PA6-GF": {
        "type": "PA-GF", "subtype": None, "brand": "Polymaker",
        "min_temp": 250, "max_temp": 280, "bed_min_temp": 90, "bed_max_temp": 100,
        "diameter": 1.75, "density": 1.28,
    },
    "PolyMide PA612-CF": {
        "type": "PA-CF", "subtype": None, "brand": "Polymaker",
        "min_temp": 250, "max_temp": 280, "bed_min_temp": 85, "bed_max_temp": 100,
        "diameter": 1.75, "density": 1.09,
    },
    "PolySmooth": {
        "type": "PVOH", "subtype": None, "brand": "Polymaker",
        "min_temp": 190, "max_temp": 210, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.23,
    },
    "PolyDissolve S1": {
        "type": "PVA", "subtype": None, "brand": "Polymaker",
        "min_temp": 200, "max_temp": 220, "bed_min_temp": 40, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.23,
    },
    "PolySupport PLA": {
        "type": "PLA", "subtype": "Support", "brand": "Polymaker",
        "min_temp": 215, "max_temp": 240, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.22,
    },
    "PolySupport PA12": {
        "type": "PA", "subtype": "Support", "brand": "Polymaker",
        "min_temp": 270, "max_temp": 290, "bed_min_temp": 80, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.10,
    },
    "Polymaker PC-ABS": {
        "type": "PC-ABS", "subtype": None, "brand": "Polymaker",
        "min_temp": 240, "max_temp": 260, "bed_min_temp": 90, "bed_max_temp": 105,
        "diameter": 1.75, "density": 1.18,
    },
    "Polymaker PC-PBT": {
        "type": "PC", "subtype": "PC-PBT", "brand": "Polymaker",
        "min_temp": 260, "max_temp": 280, "bed_min_temp": 100, "bed_max_temp": 110,
        "diameter": 1.75, "density": 1.22,
    },
    "Fiberon PA612-ESD": {
        "type": "PA-CF", "subtype": "ESD", "brand": "Polymaker",
        "min_temp": 250, "max_temp": 300, "bed_min_temp": 100, "bed_max_temp": 100,
        "diameter": 1.75, "density": 1.10,
    },
    "Fiberon PET-GF15": {
        "type": "PET-GF", "subtype": None, "brand": "Polymaker",
        "min_temp": 270, "max_temp": 300, "bed_min_temp": 70, "bed_max_temp": 70,
        "diameter": 1.75, "density": 1.42,
    },
    "Fiberon PPS-CF20": {
        "type": "PPS", "subtype": "CF20", "brand": "Polymaker",
        "min_temp": 300, "max_temp": 340, "bed_min_temp": 105, "bed_max_temp": 105,
        "diameter": 1.75, "density": 1.30,
    },
    "PolyWood": {
        "type": "PLA", "subtype": "Wood", "brand": "Polymaker",
        "min_temp": 190, "max_temp": 230, "bed_min_temp": 35, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.18,
    },
}

# ── Helpers ────────────────────────────────────────────────────────────────

HEX_RE = re.compile(r'(?:#|⌗|#)\s*([0-9A-Fa-f]{6})\b')

def extract_hex(text: str) -> str | None:
    """Return 6-char uppercase hex from a color title, or None."""
    m = HEX_RE.search(text)
    return m.group(1).upper() if m else None


def clean_color_name(text: str) -> str:
    """Strip the '(HEX Code - #XXXXXX)' suffix and trim."""
    cleaned = re.sub(r'\s*\(HEX Code\s*[-–]\s*[⌗#][0-9A-Fa-f]*\)', '', text)
    return cleaned.strip()


def normalize_title(title: str) -> str:
    """Lowercase and collapse all whitespace (incl. non-breaking spaces)."""
    return " ".join(title.lower().split())


def map_product_title(title: str) -> str | None:
    """Map a wholesale product title to a _products key, or None."""
    normalized = normalize_title(title)
    # Try longest-match first (sort by key length descending)
    for key in sorted(TITLE_MAP, key=len, reverse=True):
        if key in normalized:
            return TITLE_MAP[key]
    return None


def is_skip(title: str) -> bool:
    normalized = normalize_title(title)
    return any(s in normalized for s in SKIP_PRODUCTS)


def fetch_page(page: int) -> list:
    url = WHOLESALE_BASE.format(page)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("products", [])
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} on page {page}")
        return []
    except Exception as e:
        print(f"  Error on page {page}: {e}")
        return []


def fetch_all_products() -> list:
    """Fetch all pages; stop when a page returns 0 products."""
    all_products = []
    page = 1
    while True:
        print(f"  Fetching page {page}…", end=" ", flush=True)
        prods = fetch_page(page)
        print(f"{len(prods)} products")
        if not prods:
            break
        all_products.extend(prods)
        if len(prods) < 250:
            break  # Last page
        page += 1
        time.sleep(0.5)  # Be polite
    return all_products


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv

    # 1. Load DB
    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    products_dict = db["_products"]
    skus_dict = db["_skus"]

    # 2. Fetch wholesale data (or reuse cached raw if available)
    if "--cached" in sys.argv:
        print("Using cached wholesale_raw.json…")
        with open(RAW_OUT, encoding="utf-8") as f:
            all_products = json.load(f)
    else:
        print("Fetching wholesale catalogue…")
        all_products = fetch_all_products()
        print(f"Total products fetched: {len(all_products)}")
        with open(RAW_OUT, "w", encoding="utf-8") as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)
        print(f"Raw data saved to {RAW_OUT}")

    # 3. Auto-add missing products to _products
    added_products = []
    for key, data in NEW_PRODUCTS.items():
        if key not in products_dict:
            if not dry_run:
                products_dict[key] = data
            added_products.append(key)

    # 4. Parse variants
    stats = {
        "seen": 0,
        "new_sku": 0,
        "hex_added": 0,
        "no_map": 0,
        "skipped_variants": 0,
    }
    unmapped_titles: dict[str, set] = defaultdict(set)

    for prod in all_products:
        title = prod.get("title", "")

        if is_skip(title):
            continue

        product_key = map_product_title(title)

        for variant in prod.get("variants", []):
            sku = variant.get("sku", "").strip()
            if not sku:
                continue
            stats["seen"] += 1

            option3 = variant.get("option3") or ""
            variant_title = variant.get("title") or ""
            color_source = option3 if option3 else variant_title

            hex_code = extract_hex(color_source)
            color_name = clean_color_name(option3) if option3 else ""

            if product_key is None:
                stats["no_map"] += 1
                unmapped_titles[title].add(sku)
                continue

            if sku in skus_dict:
                entry = skus_dict[sku]
                if hex_code and not entry.get("hex"):
                    if not dry_run:
                        entry["hex"] = hex_code
                    stats["hex_added"] += 1
            else:
                new_entry = {
                    "product": product_key,
                    "color_name": color_name or "Unknown",
                    "hex": hex_code,
                }
                if not dry_run:
                    skus_dict[sku] = new_entry
                stats["new_sku"] += 1

    # 5. Save updated DB
    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nDB saved: {DB_FILE}")

    # 6. Report
    print("\n── Stats ─────────────────────────────────────────")
    print(f"  New products added : {len(added_products)}")
    print(f"  Variants seen      : {stats['seen']}")
    print(f"  New SKUs added     : {stats['new_sku']}")
    print(f"  Hex codes added    : {stats['hex_added']}")
    print(f"  Unmapped variants  : {stats['no_map']}")
    print(f"  Total SKUs in DB   : {len(skus_dict)}")
    print(f"  Total products     : {len(products_dict)}")

    if added_products:
        print(f"\n── New products added to _products ──────────────")
        for p in sorted(added_products):
            print(f"  + {p}")

    if unmapped_titles:
        print(f"\n── Still-unmapped titles ({len(unmapped_titles)}) ──────────────")
        for t, skus_set in sorted(unmapped_titles.items()):
            sku_sample = ", ".join(sorted(skus_set)[:4])
            print(f"  {normalize_title(t)[:70]:70s} [{sku_sample}]")

    if dry_run:
        print("\n[DRY RUN] No changes written.")

if __name__ == "__main__":
    main()
