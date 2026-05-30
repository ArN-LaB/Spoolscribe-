"""
scrape_thefilamentdb_hex.py — Enrichit polymaker_db.json avec les codes HEX
depuis TheFilamentDB (issou.best, CC-BY 4.0).

Ce script lit le dump local data/thefilamentdb.jsonl.gz, filtre Polymaker,
et tente de rapprocher les entrées par nom de produit + couleur.

Usage:
    python scrape_thefilamentdb_hex.py              # remplit les hex manquants
    python scrape_thefilamentdb_hex.py --force      # remplace aussi les hex existants
    python scrape_thefilamentdb_hex.py --dry-run    # prévisualise sans modifier
    python scrape_thefilamentdb_hex.py --verbose    # affiche les matchs trouvés
"""

import gzip
import difflib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")
THEFILE    = os.path.join(DATA_DIR, "thefilamentdb.jsonl.gz")


# ── Normalization helpers ─────────────────────────────────────────────────────

def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _norm(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = text.replace("™", " ").replace("®", " ").replace("©", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\btm\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _color_norm(text: str) -> str:
    text = _norm(text)
    # collapse common noise that appears in DB and TheFilamentDB names
    text = text.replace("the filament db", "")
    text = re.sub(r"\bfilament\b", "", text)
    text = re.sub(r"\bformerly\b.*$", "", text).strip()
    return re.sub(r"\s+", " ", text).strip()


def _color_tokens(text: str) -> tuple[str, ...]:
    tokens = [token for token in _color_norm(text).split() if token]
    stopwords = {
        "panchroma", "polyterra", "polylite", "polymax", "polysonic",
        "polysmooth", "polymide", "polyflex", "polywood", "polycast",
        "pla", "petg", "abs", "asa", "pc", "pva", "pvb", "tpu",
        "cope", "cf", "gf", "esd", "hf", "fr", "dual", "gradient",
        "matte", "silk", "starlight", "celestial", "galaxy", "glow",
        "luminous", "rainbow", "transparent", "clear", "former",
        "formerly", "unknown",
    }
    return tuple(token for token in tokens if token not in stopwords)


# ── TheFilamentDB index ───────────────────────────────────────────────────────

def _product_key(name: str) -> str:
    s = _norm(name)
    # Drop brand-ish boilerplate and keep the product family + series.
    s = re.sub(r"\b(formerly|aka|new packaging)\b.*$", "", s).strip()
    return s


def build_index(path: str) -> dict[str, list[dict[str, str]]]:
    """Return {product_key: [{color, hex, name, diameter, blended}, ...]}"""
    index: dict[str, list[dict[str, str]]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if _norm(row.get("brand", "")) != "polymaker":
                continue
            product_key = _product_key(row.get("name", ""))
            color_name = _color_norm(row.get("colorName", ""))
            color_hex = (row.get("colorHex") or "").strip().lstrip("#").upper()
            if len(color_hex) != 6:
                continue
            index.setdefault(product_key, []).append(
                {
                    "color": color_name,
                    "tokens": " ".join(_color_tokens(color_name)),
                    "hex": color_hex,
                    "name": row.get("name", ""),
                    "diameter": str(row.get("diameter", "")),
                    "blended": str(bool(row.get("isColorBlended"))),
                }
            )
    return index


# ── Matching heuristics ───────────────────────────────────────────────────────

def _candidate_keys(product: str) -> list[str]:
    p = _norm(product)
    candidates = [p]

    # Canonicalize common series names.
    alias_map = [
        ("polylite pla", ["panchroma regular pla", "panchroma pla", "polyterra pla"]),
        ("polyterra pla", ["panchroma matte pla", "panchroma dual matte pla", "panchroma gradient matte pla", "panchroma marble pla"]),
        ("panchroma pla glow", ["panchroma glow pla", "panchroma luminous pla"]),
        ("panchroma pla starlight", ["panchroma starlight pla"]),
        ("panchroma pla silk", ["panchroma dual silk pla", "panchroma silk pla", "panchroma gradient silk"]),
        ("panchroma pla celestial", ["panchroma celestial pla"]),
        ("panchroma pla galaxy", ["panchroma galaxy pla"]),
        ("panchroma pla luminous", ["panchroma luminous pla"]),
        ("polysonic pla pro", ["polysonic pla pro"]),
        ("polysonic pla", ["polysonic pla"]),
        ("polyflex tpu95 hf", ["polyflex tpu95 hf"]),
        ("polyflex tpu90", ["polyflex tpu90"]),
        ("polysmooth", ["polysmooth pvb"]),
        ("polylite pc", ["polylite pc"]),
        ("polylite petg", ["polylite petg", "polylite translucent petg"]),
        ("polymax pla", ["polymax pla"]),
        ("polymax petg", ["polymax petg"]),
        ("polymax pc", ["polymax pc", "polymax pc fr"]),
        ("polymaker pc abs", ["polymaker pc abs"]),
        ("polymaker pc pbt", ["polymaker pc pbt"]),
        ("polymide copa", ["polymide copa"]),
        ("polylite abs", ["polylite abs"]),
        ("polylite asa", ["polylite asa"]),
        ("polylite lw pla", ["polylite lw pla"]),
        ("polywood", ["polywood"]),
        ("polycast", ["polycast"]),
        ("polydissolve s1", ["polydissolve s1 pva", "polydissolve s1"]),
    ]
    for needle, repls in alias_map:
        if needle in p:
            candidates.extend(repls)

    # Also try reduced two-word keys for variants like "polylite pla pro".
    words = p.split()
    if len(words) >= 2:
        candidates.append(" ".join(words[:2]))
    if len(words) >= 3:
        candidates.append(" ".join(words[:3]))

    # De-duplicate while preserving order.
    seen = set()
    ordered = []
    for c in candidates:
        c = re.sub(r"\s+", " ", c).strip()
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def match_hex(product: str, color_name: str, index: dict[str, list[dict[str, str]]]) -> str | None:
    color = _color_norm(color_name)
    product_candidates = _candidate_keys(product)

    best_hex = None
    best_score = 0.0

    color_tokens = set(_color_tokens(color_name))

    for pk in product_candidates:
        entries = index.get(pk)
        if not entries:
            continue

        # 1) exact color match
        for entry in entries:
            if entry["color"] == color:
                return entry["hex"]
            if entry["tokens"] == " ".join(_color_tokens(color_name)):
                return entry["hex"]

        # 2) substring / fuzzy match
        for entry in entries:
            if color and (color in entry["color"] or entry["color"] in color):
                return entry["hex"]

            entry_tokens = set(entry["tokens"].split())
            if entry_tokens and color_tokens:
                overlap = len(entry_tokens & color_tokens) / len(entry_tokens | color_tokens)
            else:
                overlap = 0.0
            ratio = difflib.SequenceMatcher(None, entry["color"], color).ratio()
            score = max(overlap, ratio)
            if score > best_score:
                best_score = score
                best_hex = entry["hex"]

    if best_hex and best_score >= 0.78:
        return best_hex

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    verbose = "--verbose" in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    skus_dict: dict = db["_skus"]

    if not os.path.exists(THEFILE):
        print(f"Missing file: {THEFILE}")
        return

    print("Loading TheFilamentDB…", end=" ", flush=True)
    index = build_index(THEFILE)
    print(f"{len(index)} product keys")
    if verbose:
        print(f"  total products indexed: {sum(len(v) for v in index.values())}")

    stats = {"filled": 0, "overridden": 0, "skipped": 0, "no_match": 0}

    for sku, entry in skus_dict.items():
        existing = entry.get("hex")
        if existing and not force:
            continue

        product = entry.get("product", "")
        color_name = entry.get("color_name", "")
        if not product or not color_name:
            continue

        hex_found = match_hex(product, color_name, index)
        if not hex_found:
            stats["no_match"] += 1
            continue

        if not existing:
            if verbose:
                print(f"FILL  {sku}  {product} / {color_name} -> #{hex_found}")
            if not dry_run:
                entry["hex"] = hex_found
            stats["filled"] += 1
        elif existing.upper() != hex_found:
            if force:
                if verbose:
                    print(f"OVERRIDE  {sku}  {product} / {color_name} {existing} -> #{hex_found}")
                if not dry_run:
                    entry["hex"] = hex_found
                stats["overridden"] += 1
            else:
                stats["skipped"] += 1

    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nDB saved: {DB_FILE}")

    still_missing = sum(1 for v in skus_dict.values() if not v.get("hex"))
    print("\n-- Stats -----------------------------------------")
    print(f"  Hex filled (was missing)    : {stats['filled']}")
    print(f"  Hex overridden (--force)    : {stats['overridden']}")
    print(f"  Conflicts skipped (no force): {stats['skipped']}")
    print(f"  No match in TheFilamentDB   : {stats['no_match']}")
    print(f"  Total SKUs still missing hex: {still_missing}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
    if stats["skipped"] and not force:
        print(f"\n  Tip: re-run with --force to override {stats['skipped']} conflicting values.")


if __name__ == "__main__":
    main()
