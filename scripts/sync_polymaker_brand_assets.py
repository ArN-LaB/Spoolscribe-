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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")
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

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)

    brand = _fetch_json(BRAND_URL)

    logo_exists = os.path.exists(LOGO_FILE)
    if force or not logo_exists:
        logo_bytes = _fetch_bytes(LOGO_URL)
        if not dry_run:
            with open(LOGO_FILE, "wb") as f:
                f.write(logo_bytes)

    db.setdefault("_brands", {})["Polymaker"] = {
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

    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"DB saved: {DB_FILE}")

    print("Polymaker brand metadata updated")
    print(f"Logo file: {LOGO_FILE} ({'present' if os.path.exists(LOGO_FILE) else 'missing'})")
    if dry_run:
        print("[DRY RUN] No changes written.")


if __name__ == "__main__":
    main()
