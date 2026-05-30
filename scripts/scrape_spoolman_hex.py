"""
scrape_spoolman_hex.py — Enrichit polymaker_db.json avec les codes HEX
depuis SpoolmanDB (Donkie/SpoolmanDB, MIT License).

Matching par normalisation du nom produit + couleur.

Usage:
    python scrape_spoolman_hex.py              # remplit les hex manquants
    python scrape_spoolman_hex.py --force      # remplace aussi les hex existants
    python scrape_spoolman_hex.py --dry-run    # prévisualise sans modifier
    python scrape_spoolman_hex.py --verbose    # affiche les matchs trouvés
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

SPOOLMAN_URL = (
    "https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/polymaker.json"
)

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, remove punctuation/symbols."""
    s = s.lower()
    # Remove trademark symbols and common suffixes
    s = re.sub(r'[™®©\u2122\u00ae\u00a9]', '', s)
    # Remove punctuation except spaces
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    # Collapse whitespace
    return re.sub(r"\s+", " ", s).strip()


def _product_key(name: str) -> str:
    """
    Extract a comparable product key from a SpoolmanDB filament name.
    E.g. 'PolyLite™ PLA {color_name}' → 'polylite pla'
         'Panchroma™ Matte (Formerly PolyTerra™) {color_name}' → 'panchroma matte'
    """
    # Remove the {color_name} placeholder and parenthetical notes
    s = re.sub(r'\{color_name\}', '', name)
    s = re.sub(r'\(.*?\)', '', s)
    return _norm(s)


# Map SpoolmanDB product keys → list of (color_name_norm, hex)
def build_spoolman_index(data: dict) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = {}
    for fil in data.get("filaments", []):
        prod_key = _product_key(fil.get("name", ""))
        for color in fil.get("colors", []):
            color_norm = _norm(color.get("name", ""))
            # Single hex
            hex_val = color.get("hex", "").lstrip("#").upper()
            if hex_val and len(hex_val) == 6 and all(c in "0123456789ABCDEF" for c in hex_val):
                index.setdefault(prod_key, []).append((color_norm, hex_val))
            # Multi-color: take the first hex
            hexes = color.get("hexes", [])
            if hexes:
                h = hexes[0].lstrip("#").upper()
                if len(h) == 6:
                    index.setdefault(prod_key, []).append((color_norm, h))
    return index


# ── DB product name → SpoolmanDB key mapping ─────────────────────────────────
# SpoolmanDB uses "Panchroma™ Matte (Formerly PolyTerra™)" for PolyTerra entries.
# We try direct norm match first, then these aliases.

ALIASES: list[tuple[str, str]] = [
    # (DB product norm pattern, SpoolmanDB product key norm)
    ("polyterra pla",           "panchroma matte formerly polyterra"),
    ("polylite pla pro",        "polylite pla pro"),
    ("polylite pla",            "polylite pla"),
    ("polymax pla",             "polymax pla"),
    ("polysonic pla pro",       "polysonic pla pro"),
    ("polysonic pla",           "polysonic pla"),
    ("polylite petg",           "polylite petg"),
    ("polymax petg",            "polymax petg"),
    ("polylite pc",             "polylite pc"),
    ("polymax pc",              "polymax pc"),
    ("polylite abs",            "polylite abs"),
    ("polylite asa",            "polylite asa"),
    ("polylite lw pla",         "polylite lw pla"),
    ("polyflexTPU90",           "polyflex tpu90"),
    ("polyflex tpu90",          "polyflex tpu90"),
    ("polyflex tpu95 hf",       "polyflex tpu95 hf"),
    ("polyflex tpu95",          "polyflex tpu95"),
    ("polysmooth",              "polysmooth"),
    ("polylite copla",          "polylite copla"),
    ("panchroma pla glow",      "panchroma formerly polylite luminous"),
    ("panchroma luminous",      "panchroma formerly polylite luminous"),
    ("panchroma pla luminous",  "panchroma formerly polylite luminous"),
    ("polylite pla",            "panchroma regular"),  # fallback for luminous colors
    ("panchroma pla",           "panchroma regular"),
    ("panchroma regular",       "panchroma regular"),
    ("panchroma mat",           "panchroma matte formerly polyterra"),
    ("panchroma matte",         "panchroma matte formerly polyterra"),
    ("panchroma marble",        "panchroma marble formerly polyterra marble"),
    ("panchroma dual mat",      "panchroma dual"),
    ("panchroma dual matte",    "panchroma dual"),
    ("panchroma dual",          "panchroma dual"),
    ("panchroma satin",         "panchroma satin"),
    ("polymax pc fr",           "polymax pc fr"),
    ("polymaker pc abs",        "polymaker pc abs"),
    ("polymaker pc pbt",        "polymaker pc pbt"),
    ("polymaker petg",          "polylite petg"),
    ("polylite pla cf",         "polylite pla cf"),
    ("polymide copa",           "polymide copa"),
    ("polywood",                "polywood"),
    ("polycast",                "polycast"),
    ("polydissolve s1",         "polydissolve s1 pva"),
]


def find_spoolman_hex(
    db_product: str,
    db_color: str,
    index: dict[str, list[tuple[str, str]]],
) -> str | None:
    """
    Try to find a hex in the SpoolmanDB index for the given DB product + color.
    Returns 6-char uppercase hex or None.
    """
    prod_norm  = _norm(db_product)
    color_norm = _norm(db_color)

    # Candidate product keys to try (in order)
    candidates: list[str] = []

    # 1. Direct norm match
    candidates.append(prod_norm)

    # 2. Alias lookup
    for db_pat, spool_key in ALIASES:
        if db_pat in prod_norm or prod_norm in db_pat:
            candidates.append(spool_key)

    # 3. Also try just the first two words (e.g. "polylite pla" from "polylite pla pro")
    words = prod_norm.split()
    if len(words) >= 2:
        candidates.append(" ".join(words[:2]))

    for prod_key in candidates:
        colors = index.get(prod_key)
        if not colors:
            continue
        # Exact color match
        for cn, hx in colors:
            if cn == color_norm:
                return hx
        # Partial color match (one is a substring of the other)
        for cn, hx in colors:
            if color_norm in cn or cn in color_norm:
                return hx

    return None


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_spoolman() -> dict:
    print("Fetching SpoolmanDB polymaker.json…", end=" ", flush=True)
    req = urllib.request.Request(
        SPOOLMAN_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"FAILED ({e})")
        return {}
    fil_count = len(data.get("filaments", []))
    print(f"{fil_count} filament groups")
    return data


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force   = "--force"   in sys.argv
    verbose = "--verbose" in sys.argv

    # 1. Load DB
    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    skus_dict: dict = db["_skus"]

    # 2. Fetch & index SpoolmanDB
    data = fetch_spoolman()
    if not data:
        print("Nothing to do (fetch failed).")
        return

    index = build_spoolman_index(data)
    if verbose:
        print(f"  SpoolmanDB index: {len(index)} product keys")
        for k, v in sorted(index.items()):
            print(f"    {k!r}: {len(v)} colors")

    # 3. Only target SKUs missing hex (or all if --force)
    stats = {"filled": 0, "overridden": 0, "skipped": 0, "no_match": 0}

    for sku, entry in skus_dict.items():
        existing = entry.get("hex")
        if existing and not force:
            continue

        product    = entry.get("product", "")
        color_name = entry.get("color_name", "")
        if not product or not color_name:
            continue

        hex_found = find_spoolman_hex(product, color_name, index)
        if hex_found is None:
            stats["no_match"] += 1
            continue

        if not existing:
            if verbose:
                print(f"  FILL  {sku}  {product} / {color_name}  ->  #{hex_found}")
            if not dry_run:
                entry["hex"] = hex_found
            stats["filled"] += 1
        elif existing.upper() != hex_found:
            if force:
                if verbose:
                    print(f"  OVERRIDE  {sku}  {product} / {color_name}  {existing} -> #{hex_found}")
                if not dry_run:
                    entry["hex"] = hex_found
                stats["overridden"] += 1
            else:
                stats["skipped"] += 1

    # 4. Save
    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nDB saved: {DB_FILE}")

    # 5. Report
    still_missing = sum(1 for v in skus_dict.values() if not v.get("hex"))
    print("\n-- Stats -----------------------------------------")
    print(f"  Hex filled (was missing)    : {stats['filled']}")
    print(f"  Hex overridden (--force)    : {stats['overridden']}")
    print(f"  Conflicts skipped (no force): {stats['skipped']}")
    print(f"  No match in SpoolmanDB      : {stats['no_match']}")
    print(f"  Total SKUs still missing hex: {still_missing}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
    if stats["skipped"] and not force:
        print(f"\n  Tip: re-run with --force to override {stats['skipped']} conflicting values.")


if __name__ == "__main__":
    main()
