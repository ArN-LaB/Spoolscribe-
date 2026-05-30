"""
sync_multibrand_assets.py — Synchronise les logos et métadonnées de marque
pour Prusament et ROSA3D dans polymaker_db.json.

Source : OpenFilamentCollective/open-filament-database (brand.json + logo.png)

Usage:
    python sync_multibrand_assets.py              # met à jour la DB
    python sync_multibrand_assets.py --dry-run    # prévisualise sans modifier
    python sync_multibrand_assets.py --force      # retélécharge les logos
"""

import json
import os
import sys
import urllib.request
from datetime import datetime

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")

_OFD = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/data"

# (db_brand_key, ofd_slug, local_filename)
BRANDS = [
    ("Prusament", "prusament",       "prusament_logo.png"),
    ("ROSA3D",    "rosa3d_filaments", "rosa3d_logo.png"),
]


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
    force   = "--force"   in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)

    db.setdefault("_brands", {})

    for db_key, ofd_slug, logo_filename in BRANDS:
        brand_url = f"{_OFD}/{ofd_slug}/brand.json"
        logo_url  = f"{_OFD}/{ofd_slug}/logo.png"
        logo_file = os.path.join(DATA_DIR, logo_filename)
        logo_path = f"data/{logo_filename}"

        try:
            brand = _fetch_json(brand_url)
        except Exception as exc:
            print(f"[WARN] {db_key}: impossible de récupérer brand.json — {exc}")
            brand = {}

        logo_ok = os.path.exists(logo_file)
        if force or not logo_ok:
            try:
                logo_bytes = _fetch_bytes(logo_url)
                if not dry_run:
                    with open(logo_file, "wb") as f:
                        f.write(logo_bytes)
                logo_ok = True
                print(f"  {db_key}: logo téléchargé → {logo_file}")
            except Exception as exc:
                print(f"[WARN] {db_key}: impossible de télécharger le logo — {exc}")
                logo_path = ""

        db["_brands"][db_key] = {
            "id":          brand.get("id",      ofd_slug),
            "name":        brand.get("name",     db_key),
            "website":     brand.get("website",  ""),
            "origin":      brand.get("origin",   ""),
            "source":      brand.get("source",   "openprinttag"),
            "logo":        brand.get("logo",     "logo.png"),
            "logo_path":   logo_path if logo_ok else "",
            "logo_source": "OpenFilamentCollective/open-filament-database",
            "logo_url":    logo_url,
            "updated_at":  datetime.now().isoformat(),
        }
        status = "OK" if logo_ok else "absent"
        print(f"  {db_key}: métadonnées {'simulées' if dry_run else 'mises à jour'} — logo {status}")

    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"DB sauvegardée : {DB_FILE}")
    else:
        print("[DRY RUN] Aucune modification écrite.")


if __name__ == "__main__":
    main()
