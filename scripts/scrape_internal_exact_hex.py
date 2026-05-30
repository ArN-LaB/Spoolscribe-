"""
scrape_internal_exact_hex.py — Remplit les HEX manquants par correspondance
exacte interne: même product + même color_name déjà présent ailleurs dans la DB
avec un unique HEX.

Usage:
    python scrape_internal_exact_hex.py
    python scrape_internal_exact_hex.py --dry-run
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR = os.path.join(_DATA_HOME, "data")
DB_FILE = os.path.join(DATA_DIR, "polymaker_db.json")


def _key(entry: dict) -> tuple[str, str]:
    return (
        (entry.get("product") or "").strip().lower(),
        (entry.get("color_name") or "").strip().lower(),
    )


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)

    skus = db.get("_skus", {})
    known_hex = defaultdict(set)

    for entry in skus.values():
        hex_val = (entry.get("hex") or "").strip().upper()
        if hex_val:
            known_hex[_key(entry)].add(hex_val)

    filled = 0
    ambiguous = 0

    for entry in skus.values():
        if entry.get("hex"):
            continue
        key = _key(entry)
        candidates = known_hex.get(key, set())
        if len(candidates) == 1:
            if not dry_run:
                entry["hex"] = next(iter(candidates))
            filled += 1
        elif len(candidates) > 1:
            ambiguous += 1

    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"DB saved: {DB_FILE}")

    still_missing = sum(1 for v in skus.values() if not v.get("hex"))
    print("\n-- Stats -----------------------------------------")
    print(f"  Hex filled (exact internal) : {filled}")
    print(f"  Ambiguous exact matches     : {ambiguous}")
    print(f"  Total SKUs still missing    : {still_missing}")
    if dry_run:
        print("\n[DRY RUN] No changes written.")


if __name__ == "__main__":
    main()
