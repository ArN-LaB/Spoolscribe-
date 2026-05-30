#!/usr/bin/env python3
"""
scrape_spoolman_multibrand_hex.py — Enrichit polymaker_db.json avec les codes
HEX de **Prusament** et **ROSA3D** depuis SpoolmanDB (Donkie/SpoolmanDB, MIT).

Contrairement au scraper Polymaker (scrape_spoolman_hex.py), pour ces marques
le nom de produit SpoolmanDB est souvent juste « {color_name} » : la famille de
matériau est portée par le champ ``material``. Le rapprochement se fait donc par
**matériau (type) + nom de couleur**, pas par nom de produit.

Sources (un fichier JSON par marque) :
  - https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/prusament.json
  - https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/rosa3d.json

Le script est idempotent : par défaut il ne remplit que les HEX manquants et
n'écrase jamais une valeur existante (sauf --force).

Usage :
    python scrape_spoolman_multibrand_hex.py            # remplit les hex manquants
    python scrape_spoolman_multibrand_hex.py --force    # remplace aussi l'existant
    python scrape_spoolman_multibrand_hex.py --dry-run  # prévisualise
    python scrape_spoolman_multibrand_hex.py --verbose  # affiche les matchs
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")

SPOOLMAN_BASE = "https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/{file}.json"

# Marque interne (telle qu'écrite dans la DB) → fichier SpoolmanDB
BRANDS: dict[str, str] = {
    "Prusament": "prusament",
    "ROSA3D":    "rosa3d",
}

# Marques dont SpoolmanDB est considéré comme **source faisant autorité** :
# les nuanciers y sont les valeurs officielles publiées (cas Prusament), donc
# on remplace même les HEX déjà présents (approximations de la table interne).
# Pour les autres (ex. ROSA3D, dont rosa3d.json contient des approximations CSS
# pour certaines familles PLA), on se contente de combler les HEX manquants.
AUTHORITATIVE_OVERRIDE_BRANDS: set[str] = {"Prusament"}

# Type de produit interne → matériaux SpoolmanDB acceptés (normalisés)
MATERIAL_MAP: dict[str, set[str]] = {
    "PLA":  {"pla"},
    "PETG": {"petg"},
    "PCTG": {"pctg", "petg"},
    "ASA":  {"asa"},
    "ABS":  {"abs"},
    "PC":   {"pc", "pccf"},
    "TPU":  {"tpu95a", "tpu", "tpu90"},
    "PVB":  {"pvb"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[™®©\u2122\u00ae\u00a9]", "", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _mat_norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _color_norm(s: str) -> str:
    s = _norm(s)
    # « Pearl White (Blend) » et « Neon Green Transparent » → on garde les mots
    # signifiants mais on retire le bruit générique de finition.
    s = re.sub(r"\b(blend|nfc)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _valid_hex(h: str) -> str | None:
    h = (h or "").lstrip("#").upper()
    if len(h) == 6 and all(c in "0123456789ABCDEF" for c in h):
        return h
    return None


# ── Index SpoolmanDB ──────────────────────────────────────────────────────────

def build_index(data: dict) -> dict[str, dict[str, str]]:
    """Retourne {material_norm: {color_norm: hex}} pour une marque."""
    index: dict[str, dict[str, str]] = {}
    for fil in data.get("filaments", []):
        mat = _mat_norm(fil.get("material", ""))
        if not mat:
            continue
        bucket = index.setdefault(mat, {})
        for color in fil.get("colors", []):
            hx = _valid_hex(color.get("hex", "")) or (
                _valid_hex(color.get("hexes", [""])[0]) if color.get("hexes") else None
            )
            if not hx:
                continue
            cn = _color_norm(color.get("name", ""))
            if cn:
                bucket.setdefault(cn, hx)
    return index


def find_hex(db_type: str, db_color: str, index: dict[str, dict[str, str]]) -> str | None:
    materials = MATERIAL_MAP.get((db_type or "").upper(), {_mat_norm(db_type)})
    target = _color_norm(db_color)
    if not target:
        return None
    # 1) Correspondance exacte de couleur dans un matériau accepté.
    for mat in materials:
        bucket = index.get(mat)
        if bucket and target in bucket:
            return bucket[target]
    # 2) Correspondance partielle (sous-chaîne) dans un matériau accepté.
    for mat in materials:
        bucket = index.get(mat) or {}
        for cn, hx in bucket.items():
            if target == cn or target in cn or cn in target:
                return hx
    return None


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_brand(file_slug: str) -> dict:
    url = SPOOLMAN_BASE.format(file=file_slug)
    print(f"Fetching SpoolmanDB {file_slug}.json…", end=" ", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:  # noqa: BLE001
        print(f"FAILED ({e})")
        return {}
    print(f"{len(data.get('filaments', []))} filament groups")
    return data


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force   = "--force"   in sys.argv
    verbose = "--verbose" in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    products: dict = db["_products"]
    skus: dict = db["_skus"]

    stats = {"filled": 0, "overridden": 0, "skipped": 0, "no_match": 0}

    for brand, slug in BRANDS.items():
        data = fetch_brand(slug)
        if not data:
            continue
        index = build_index(data)
        if verbose:
            print(f"  [{brand}] index: " + ", ".join(
                f"{m}={len(c)}" for m, c in sorted(index.items())
            ))

        brand_force = force or (brand in AUTHORITATIVE_OVERRIDE_BRANDS)

        for sku, entry in skus.items():
            product = entry.get("product", "")
            prod = products.get(product)
            if not prod or prod.get("brand") != brand:
                continue
            existing = entry.get("hex")
            if existing and not brand_force:
                continue
            color = entry.get("color_name", "")
            if not color:
                continue
            hx = find_hex(prod.get("type", ""), color, index)
            if hx is None:
                stats["no_match"] += 1
                continue
            if not existing:
                if verbose:
                    print(f"  FILL  {sku}  {product} / {color}  ->  #{hx}")
                if not dry_run:
                    entry["hex"] = hx
                stats["filled"] += 1
            elif existing.upper() != hx:
                if brand_force:
                    if verbose:
                        print(f"  OVERRIDE  {sku}  {product} / {color}  {existing} -> #{hx}")
                    if not dry_run:
                        entry["hex"] = hx
                    stats["overridden"] += 1
                else:
                    stats["skipped"] += 1

    if not dry_run and (stats["filled"] or stats["overridden"]):
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nDB saved: {DB_FILE}")

    print("\n-- Stats (SpoolmanDB multibrand) -----------------")
    print(f"  Hex filled (was missing)    : {stats['filled']}")
    print(f"  Hex overridden (--force)    : {stats['overridden']}")
    print(f"  Conflicts skipped (no force): {stats['skipped']}")
    print(f"  No match in SpoolmanDB      : {stats['no_match']}")
    if dry_run:
        print("\n[DRY RUN] No changes written.")


if __name__ == "__main__":
    main()
