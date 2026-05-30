#!/usr/bin/env python3
"""seed_rosa3d.py — Ajoute la marque ROSA3D à la DB SpoolScribe.

Source : table interne **hors-ligne** (aucun accès réseau). Les valeurs
(température, densité, diamètre) reprennent les plages d'impression
recommandées par ROSA3D (ROSA PLAST Sp. z o.o., Pologne) telles que publiées
sur leurs fiches produit / catalogue. Les codes SKU sont des identifiants
**internes** namespacés `R3-…` (et non des références exactes du catalogue
ROSA3D), afin de ne rien inventer comme numéro officiel tout en gardant la
recherche-par-SKU.

Le script est **idempotent** : il fusionne sans écraser les entrées déjà
présentes (on n'efface jamais un HEX ou un produit existant).

Modèle interne réutilisé tel quel (cf. core.py) :
  _products[<nom>] = {type, subtype, brand, min_temp, max_temp,
                      bed_min_temp, bed_max_temp, diameter, density}
  _skus[<sku>]     = {product, color_name, hex}
  _brands[<marque>]= {id, name, website, origin, source, …}

Usage :
    python seed_rosa3d.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")

BRAND = "ROSA3D"

# ── Marque ────────────────────────────────────────────────────────────────
BRAND_META = {
    "id": "rosa3d",
    "name": "ROSA3D",
    "website": "https://www.rosa3d.pl/en/",
    "origin": "PL",
    "source": "curated-offline",
    # Pas de logo embarqué (marque déposée ROSA PLAST) : l'UI dégrade
    # proprement si `logo_path` est absent.
    "logo_path": "",
}

# ── Produits (plages d'impression publiées par ROSA3D) ─────────────────────
# diameter 1.75 mm partout (offre standard ROSA3D).
PRODUCTS: dict[str, dict] = {
    "ROSA3D PLA Starter": {
        "type": "PLA", "subtype": "Starter", "brand": BRAND,
        "min_temp": 200, "max_temp": 220, "bed_min_temp": 0, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "ROSA3D PLA High Speed": {
        "type": "PLA", "subtype": "HighSpeed", "brand": BRAND,
        "min_temp": 190, "max_temp": 230, "bed_min_temp": 45, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "ROSA3D PLA Silk": {
        "type": "PLA", "subtype": "Silk", "brand": BRAND,
        "min_temp": 210, "max_temp": 230, "bed_min_temp": 50, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "ROSA3D PLA Pastel": {
        "type": "PLA", "subtype": "Pastel", "brand": BRAND,
        "min_temp": 200, "max_temp": 220, "bed_min_temp": 0, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "ROSA3D R-PLA": {
        "type": "PLA", "subtype": "Recycled", "brand": BRAND,
        "min_temp": 200, "max_temp": 220, "bed_min_temp": 0, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "ROSA3D PETG Standard HS": {
        "type": "PETG", "subtype": "HighSpeed", "brand": BRAND,
        "min_temp": 220, "max_temp": 250, "bed_min_temp": 70, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.27,
    },
    "ROSA3D R-PET-G": {
        "type": "PETG", "subtype": "Recycled", "brand": BRAND,
        "min_temp": 220, "max_temp": 250, "bed_min_temp": 70, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.27,
    },
    "ROSA3D PCTG": {
        "type": "PCTG", "subtype": None, "brand": BRAND,
        "min_temp": 250, "max_temp": 270, "bed_min_temp": 70, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.23,
    },
    "ROSA3D ASA": {
        "type": "ASA", "subtype": None, "brand": BRAND,
        "min_temp": 240, "max_temp": 260, "bed_min_temp": 90, "bed_max_temp": 100,
        "diameter": 1.75, "density": 1.07,
    },
    "ROSA3D ABS+": {
        "type": "ABS", "subtype": "Plus", "brand": BRAND,
        "min_temp": 230, "max_temp": 260, "bed_min_temp": 90, "bed_max_temp": 110,
        "diameter": 1.75, "density": 1.04,
    },
}

# ── Couleurs (nom → HEX si connu de façon fiable, sinon None) ──────────────
# HEX laissé à None quand la valeur exacte n'est pas certaine : l'UI affiche
# « HEX inconnu » et la pipeline hex existante pourra l'enrichir plus tard.
PLA_STARTER_COLORS: list[tuple[str, str | None]] = [
    ("Black",          "1A1A1A"),
    ("White",          "F5F5F0"),
    ("Red",            "C8102E"),
    ("Orange",         "F26522"),
    ("Yellow",         "F5C518"),
    ("Juicy Green",    "5CB531"),
    ("Hunter Green",   "2E5E32"),
    ("Blue Sky",       "3FA9F5"),
    ("Pink",           "E0218A"),
    ("Violet Dynamic", "6A2C91"),
    ("Mocha Mousse",   "8C6A4A"),
]

PLA_PASTEL_COLORS: list[tuple[str, str | None]] = [
    ("Pastel Blue",     "AEC6E4"),
    ("Pastel Green",    "B7DBA7"),
    ("Pastel Lavender", "C9B8E0"),
    ("Pastel Mint",     "AEE3D0"),
    ("Pastel Peach",    "F4C9A8"),
    ("Pastel Pink",     "F4C2D0"),
    ("Pastel Yellow",   "F5E6A8"),
]

PLA_SILK_COLORS: list[tuple[str, str | None]] = [
    ("Silk Gold",          "D4AF37"),
    ("Silk Silver",        "C7C9CB"),
    ("Silk White",         "F0F0EC"),
    ("Silk Emerald Green", "1FA974"),
    ("Silk Fuchsia",       "C2185B"),
]

PLA_GENERIC_COLORS: list[tuple[str, str | None]] = [
    ("Black", "1A1A1A"),
    ("White", "F5F5F0"),
    ("Grey",  "808588"),
]

PETG_COLORS: list[tuple[str, str | None]] = [
    ("Black",                "1A1A1A"),
    ("White",                "F5F5F0"),
    ("Aluminium",            "9AA0A6"),
    ("Red Transparent",      None),
    ("Blue Ice Transparent", None),
    ("Ultramarine Blue Transparent", None),
    ("Transparent Yellow",   None),
    ("Transparent",          None),
]

ASA_COLORS: list[tuple[str, str | None]] = [
    ("Black", "1A1A1A"),
    ("White", "F5F5F0"),
    ("Grey",  "808588"),
    ("Natural", None),
]

ABS_COLORS: list[tuple[str, str | None]] = [
    ("Black", "1A1A1A"),
    ("White", "F5F5F0"),
    ("Grey",  "808588"),
]

# Quels produits reçoivent quelles palettes.
PALETTES: list[tuple[str, list[tuple[str, str | None]]]] = [
    ("ROSA3D PLA Starter",     PLA_STARTER_COLORS),
    ("ROSA3D PLA High Speed",  PLA_GENERIC_COLORS),
    ("ROSA3D PLA Silk",        PLA_SILK_COLORS),
    ("ROSA3D PLA Pastel",      PLA_PASTEL_COLORS),
    ("ROSA3D R-PLA",           PLA_GENERIC_COLORS),
    ("ROSA3D PETG Standard HS", PETG_COLORS),
    ("ROSA3D R-PET-G",         PETG_COLORS),
    ("ROSA3D PCTG",            PETG_COLORS),
    ("ROSA3D ASA",             ASA_COLORS),
    ("ROSA3D ABS+",            ABS_COLORS),
]

# Préfixe de matériau pour des SKU internes lisibles et stables.
_MAT_CODE = {
    "ROSA3D PLA Starter":      "PLAST",
    "ROSA3D PLA High Speed":   "PLAHS",
    "ROSA3D PLA Silk":         "PLASILK",
    "ROSA3D PLA Pastel":       "PLAPAST",
    "ROSA3D R-PLA":            "RPLA",
    "ROSA3D PETG Standard HS": "PETG",
    "ROSA3D R-PET-G":          "RPETG",
    "ROSA3D PCTG":             "PCTG",
    "ROSA3D ASA":              "ASA",
    "ROSA3D ABS+":             "ABSP",
}


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", s).upper()


def _internal_sku(product: str, color: str) -> str:
    return f"R3-{_MAT_CODE[product]}-{_slug(color)}"


def _norm_hex(h: str | None) -> str | None:
    if not h:
        return None
    h = h.strip().lstrip("#")
    return h.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", h) else None


def build_entries() -> tuple[dict, dict]:
    """Retourne (products, skus) à fusionner."""
    products = {name: dict(data) for name, data in PRODUCTS.items()}
    skus: dict[str, dict] = {}
    for product, palette in PALETTES:
        for color_name, hexv in palette:
            sku = _internal_sku(product, color_name)
            skus[sku] = {
                "product": product,
                "color_name": color_name,
                "hex": _norm_hex(hexv),
            }
    return products, skus


def main() -> int:
    dry = "--dry-run" in sys.argv

    if os.path.exists(DB_FILE):
        with open(DB_FILE, encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {"_products": {}, "_skus": {}, "_brands": {}}
    db.setdefault("_products", {})
    db.setdefault("_skus", {})
    db.setdefault("_brands", {})

    products, skus = build_entries()

    added_p = added_s = 0

    # Marque (toujours rafraîchie, c'est de la métadonnée stable).
    db["_brands"].setdefault(BRAND, {})
    db["_brands"][BRAND].update(BRAND_META)
    db["_brands"][BRAND]["updated_at"] = datetime.now().isoformat()

    # Produits : on ne réécrit pas un produit déjà présent.
    for name, data in products.items():
        if name not in db["_products"]:
            db["_products"][name] = data
            added_p += 1

    # SKUs : idempotent. Si le SKU existe déjà, on préserve un HEX non vide.
    for sku, entry in skus.items():
        cur = db["_skus"].get(sku)
        if cur is None:
            db["_skus"][sku] = entry
            added_s += 1
        else:
            if not cur.get("hex") and entry.get("hex"):
                cur["hex"] = entry["hex"]
            cur.setdefault("product", entry["product"])
            cur.setdefault("color_name", entry["color_name"])

    print(f"ROSA3D : +{added_p} produits, +{added_s} SKUs "
          f"(total SKUs ROSA3D : {len(skus)})")

    if dry:
        print("--dry-run : aucune écriture.")
        return 0

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    print(f"écrit : {DB_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
