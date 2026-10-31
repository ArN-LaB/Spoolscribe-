"""
sync_polymaker_brand_assets.py — Synchronise le logo Polymaker et les
métadonnées de marque dans polymaker_db.json.

Source des métadonnées:
- OpenFilamentCollective/open-filament-database (brand.json + logo.svg)

Usage:
    python sync_polymaker_brand_assets.py              # met à jour la DB
    python sync_polymaker_brand_assets.py --dry-run    # prévisualise sans modifier
    python sync_polymaker_brand_assets.py --force      # retélécharge le logo
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The worker also runs standalone; expose the project namespace to its helper.
if _RESOURCE not in sys.path:
    sys.path.insert(0, _RESOURCE)
from scripts.db_io import (
    load_db, save_db, atomic_write, run_step
)
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")
BRAND_URL  = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/data/polymaker/brand.json"
LOGO_URL   = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/data/polymaker/logo.svg"
LOGO_FILE   = os.path.join(DATA_DIR, "polymaker_logo.svg")


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv

    db = load_db(DB_FILE)

    brand = _fetch_json(BRAND_URL)

    logo_exists = os.path.exists(LOGO_FILE)
    if force or not logo_exists:
        logo_bytes = _fetch_bytes(LOGO_URL)
        if not dry_run:
            atomic_write(LOGO_FILE, logo_bytes)

    incoming = {
        "id": brand.get("id", "polymaker"),
        "name": brand.get("name", "Polymaker"),
        "website": brand.get("website", "https://polymaker.com/"),
        "origin": brand.get("origin", "CN"),
        "source": brand.get("source", "openprinttag"),
        "logo": brand.get("logo", "logo.svg"),
        "logo_path": "data/polymaker_logo.svg",
        "logo_source": "OpenFilamentCollective/open-filament-database",
        "logo_url": LOGO_URL,
        "updated_at": datetime.now().isoformat(),
    }

    current = db.setdefault("_brands", {}).setdefault("Polymaker", {})
    for field, value in incoming.items():
        if field == "updated_at":
            continue
        if not current.get(field):
            current[field] = value
        elif current[field] != value:
            print(f"CONFLIT marque : {field}, valeur locale conservée.")

    if not dry_run:
        save_db(db, DB_FILE)
        print(f"DB saved: {DB_FILE}")

    print("Polymaker brand metadata updated")
    print(f"Logo file: {LOGO_FILE} ({'present' if os.path.exists(LOGO_FILE) else 'missing'})")
    if dry_run:
        print("[DRY RUN] No changes written.")


if __name__ == "__main__":
    run_step(main, DB_FILE)
