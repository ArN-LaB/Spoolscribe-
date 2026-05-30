#!/usr/bin/env python3
"""seed_prusament.py — Ajoute la marque Prusament à la DB SpoolScribe.

Source : table interne **hors-ligne** (aucun accès réseau). Les valeurs
(température, densité, diamètre) proviennent des fiches matériaux publiques
de Prusa Research ; les codes SKU sont des identifiants **internes** namespacés
`PM-…` (et non les références exactes du catalogue Prusa), afin de ne rien
inventer comme numéro officiel tout en gardant la recherche-par-SKU.

Le script est **idempotent** : il fusionne sans écraser les entrées déjà
présentes (on n'efface jamais un HEX ou un produit existant).

Modèle interne réutilisé tel quel (cf. core.py) :
  _products[<nom>] = {type, subtype, brand, min_temp, max_temp,
                      bed_min_temp, bed_max_temp, diameter, density}
  _skus[<sku>]     = {product, color_name, hex}
  _brands[<marque>]= {id, name, website, origin, source, …}

Usage :
    python seed_prusament.py [--dry-run]
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

BRAND = "Prusament"

# ── Marque ────────────────────────────────────────────────────────────────
BRAND_META = {
    "id": "prusament",
    "name": "Prusament",
    "website": "https://prusament.com/",
    "origin": "CZ",
    "source": "curated-offline",
    # Pas de logo embarqué (marque déposée Prusa Research) : l'UI dégrade
    # proprement si `logo_path` est absent.
    "logo_path": "",
}

# ── Produits (fiches matériaux publiques Prusa Research) ───────────────────
# diameter 1.75 mm partout (offre standard Prusament).
PRODUCTS: dict[str, dict] = {
    "Prusament PLA": {
        "type": "PLA", "subtype": None, "brand": BRAND,
        "min_temp": 215, "max_temp": 225, "bed_min_temp": 60, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "Prusament PLA Refill": {
        "type": "PLA", "subtype": "Refill", "brand": BRAND,
        "min_temp": 215, "max_temp": 225, "bed_min_temp": 60, "bed_max_temp": 60,
        "diameter": 1.75, "density": 1.24,
    },
    "Prusament PETG": {
        "type": "PETG", "subtype": None, "brand": BRAND,
        "min_temp": 240, "max_temp": 260, "bed_min_temp": 85, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.27,
    },
    "Prusament PETG Refill": {
        "type": "PETG", "subtype": "Refill", "brand": BRAND,
        "min_temp": 240, "max_temp": 260, "bed_min_temp": 85, "bed_max_temp": 90,
        "diameter": 1.75, "density": 1.27,
    },
    "Prusament ASA": {
        "type": "ASA", "subtype": None, "brand": BRAND,
        "min_temp": 260, "max_temp": 280, "bed_min_temp": 100, "bed_max_temp": 110,
        "diameter": 1.75, "density": 1.07,
    },
    "Prusament PC Blend": {
        "type": "PC", "subtype": "Blend", "brand": BRAND,
        "min_temp": 270, "max_temp": 285, "bed_min_temp": 110, "bed_max_temp": 115,
        "diameter": 1.75, "density": 1.22,
    },
}

# ── Couleurs (nom officiel → HEX si connu de façon fiable, sinon None) ─────
# HEX laissé à None quand la valeur exacte n'est pas certaine : l'UI affiche
# « HEX inconnu » et la pipeline hex existante pourra l'enrichir plus tard.
PLA_COLORS: list[tuple[str, str | None]] = [
    ("Jet Black",       "1A1A1A"),
    ("Galaxy Black",    "2B2C30"),
    ("Vanilla White",   "F3F0E6"),
    ("Prusa Orange",    "FA6831"),
    ("Lipstick Red",    "B3122A"),
    ("Azure Blue",      "1F6FB2"),
    ("Pineapple Yellow", "F5C518"),
    ("Army Green",      "4B5320"),
    ("Gravity Grey",    "5A5E63"),
    ("Ms. Pink",        "E0218A"),
    ("Galaxy Silver",   None),
    ("Opal Green",      None),
    ("Mystic Brown",    None),
]

PETG_COLORS: list[tuple[str, str | None]] = [
    ("Jet Black",       "1A1A1A"),
    ("Anthracite Grey", "3A3D40"),
    ("Signal White",    "F5F5F0"),
    ("Prusa Orange",    "FA6831"),
    ("Carmine Red",     "9B1B2E"),
    ("Ocean Blue",      "1A5C8A"),
    ("Neon Green",      "39FF14"),
    ("Clear",           None),
]

ASA_COLORS: list[tuple[str, str | None]] = [
    ("Jet Black",   "1A1A1A"),
    ("Sapphire Blue", "1C3F94"),
    ("Signal White", "F5F5F0"),
    ("Prusa Orange", "FA6831"),
]

PC_COLORS: list[tuple[str, str | None]] = [
    ("Jet Black",  "1A1A1A"),
    ("Transparent", None),
    ("Urban Grey", "6B6F74"),
]

# Quels produits reçoivent quelles palettes (bobine + recharge partagent la
# même couleur ; seul le `subtype` Refill les distingue).
PALETTES: list[tuple[str, list[tuple[str, str | None]]]] = [
    ("Prusament PLA",         PLA_COLORS),
    ("Prusament PLA Refill",  PLA_COLORS),
    ("Prusament PETG",        PETG_COLORS),
    ("Prusament PETG Refill", PETG_COLORS),
    ("Prusament ASA",         ASA_COLORS),
    ("Prusament PC Blend",    PC_COLORS),
]

# Préfixe de matériau pour des SKU internes lisibles et stables.
_MAT_CODE = {
    "Prusament PLA": "PLA",
    "Prusament PLA Refill": "PLAR",
    "Prusament PETG": "PETG",
    "Prusament PETG Refill": "PETGR",
    "Prusament ASA": "ASA",
    "Prusament PC Blend": "PCB",
}


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", s).upper()


def _internal_sku(product: str, color: str) -> str:
    return f"PM-{_MAT_CODE[product]}-{_slug(color)}"


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

    print(f"Prusament : +{added_p} produits, +{added_s} SKUs "
          f"(total SKUs Prusament : {len(skus)})")

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
