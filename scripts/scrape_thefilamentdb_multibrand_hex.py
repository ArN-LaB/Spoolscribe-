#!/usr/bin/env python3
"""
scrape_thefilamentdb_multibrand_hex.py — Enrichit polymaker_db.json avec les
codes HEX de **Prusament** et **ROSA3D** depuis le dump local TheFilamentDB
(issou.best, CC-BY 4.0 — attribution requise) : data/thefilamentdb.jsonl.gz.

Dans le dump, le champ ``name`` porte le matériau (PLA, PETG, …), ``colorName``
le nom de couleur et ``colorHex`` la valeur. Le rapprochement se fait par
**matériau (type) + nom de couleur**.

Le script est idempotent : par défaut il ne remplit que les HEX manquants et
n'écrase jamais une valeur existante (sauf --force). Si une marque est absente
du dump, elle est simplement ignorée sans erreur.

Usage :
    python scrape_thefilamentdb_multibrand_hex.py           # remplit les manquants
    python scrape_thefilamentdb_multibrand_hex.py --force   # remplace l'existant
    python scrape_thefilamentdb_multibrand_hex.py --dry-run # prévisualise
    python scrape_thefilamentdb_multibrand_hex.py --verbose # affiche les matchs
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")
THEFILE    = os.path.join(DATA_DIR, "thefilamentdb.jsonl.gz")

# Marque interne (DB) → nom de marque tel qu'écrit dans TheFilamentDB (normalisé)
BRANDS: dict[str, str] = {
    "Prusament": "prusament",
    "ROSA3D":    "rosa3d",
}

MATERIAL_MAP: dict[str, set[str]] = {
    "PLA":  {"pla"},
    "PETG": {"petg"},
    "PCTG": {"pctg", "petg"},
    "ASA":  {"asa"},
    "ABS":  {"abs"},
    "PC":   {"pc", "pccf", "pcblend"},
    "TPU":  {"tpu95a", "tpu", "tpu90"},
    "PVB":  {"pvb"},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _norm(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = re.sub(r"[™®©]", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _mat_norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _strip_accents(s or "").lower())


def _color_norm(s: str) -> str:
    s = _norm(s)
    s = re.sub(r"\b(blend|nfc)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _valid_hex(h: str) -> str | None:
    h = (h or "").lstrip("#").upper()
    if len(h) == 6 and all(c in "0123456789ABCDEF" for c in h):
        return h
    return None


# ── Index TheFilamentDB ───────────────────────────────────────────────────────

def build_index(path: str, brand_norms: set[str]) -> dict[str, dict[str, dict[str, str]]]:
    """Retourne {brand_norm: {material_norm: {color_norm: hex}}}."""
    index: dict[str, dict[str, dict[str, str]]] = {}
    if not os.path.isfile(path):
        print(f"Dump introuvable: {path}")
        return index
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            bn = _norm(row.get("brand", ""))
            if bn not in brand_norms:
                continue
            hx = _valid_hex(row.get("colorHex", ""))
            if not hx:
                continue
            mat = _mat_norm(row.get("name", ""))
            cn = _color_norm(row.get("colorName", ""))
            if not mat or not cn:
                continue
            index.setdefault(bn, {}).setdefault(mat, {}).setdefault(cn, hx)
    return index


def find_hex(db_type: str, db_color: str, brand_index: dict[str, dict[str, str]]) -> str | None:
    materials = MATERIAL_MAP.get((db_type or "").upper(), {_mat_norm(db_type)})
    target = _color_norm(db_color)
    if not target:
        return None
    for mat in materials:
        bucket = brand_index.get(mat)
        if bucket and target in bucket:
            return bucket[target]
    for mat in materials:
        bucket = brand_index.get(mat) or {}
        for cn, hx in bucket.items():
            if target == cn or target in cn or cn in target:
                return hx
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force   = "--force"   in sys.argv
    verbose = "--verbose" in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    products: dict = db["_products"]
    skus: dict = db["_skus"]

    brand_norms = set(BRANDS.values())
    print("Lecture du dump TheFilamentDB…", end=" ", flush=True)
    index = build_index(THEFILE, brand_norms)
    print(", ".join(f"{b}={sum(len(c) for c in m.values())} couleurs" for b, m in index.items()) or "aucune marque cible")

    stats = {"filled": 0, "overridden": 0, "skipped": 0, "no_match": 0}

    for brand, brand_norm in BRANDS.items():
        brand_index = index.get(brand_norm)
        if not brand_index:
            continue
        for sku, entry in skus.items():
            product = entry.get("product", "")
            prod = products.get(product)
            if not prod or prod.get("brand") != brand:
                continue
            existing = entry.get("hex")
            if existing and not force:
                continue
            color = entry.get("color_name", "")
            if not color:
                continue
            hx = find_hex(prod.get("type", ""), color, brand_index)
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
                if force:
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

    print("\n-- Stats (TheFilamentDB multibrand) --------------")
    print(f"  Hex filled (was missing)    : {stats['filled']}")
    print(f"  Hex overridden (--force)    : {stats['overridden']}")
    print(f"  Conflicts skipped (no force): {stats['skipped']}")
    print(f"  No match in TheFilamentDB   : {stats['no_match']}")
    if dry_run:
        print("\n[DRY RUN] No changes written.")


if __name__ == "__main__":
    main()
