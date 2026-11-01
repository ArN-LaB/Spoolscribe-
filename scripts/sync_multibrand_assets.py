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
# The worker also runs standalone; expose the project namespace to its helper.
if _RESOURCE not in sys.path:
    sys.path.insert(0, _RESOURCE)
from scripts.db_io import (
    load_db, save_db, atomic_write, run_step, PartialUpdate, SourceUnavailable
)
from scripts.resource_paths import user_data_home
from scripts.resource_paths import canonical_resource_path
_DATA_HOME = user_data_home()
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")

_OFD = "https://raw.githubusercontent.com/OpenFilamentCollective/open-filament-database/main/data"

# (db_brand_key, ofd_slug, local_filename, curated)
# curated=True : on garde un asset vectoriel soigné, fourni avec le dépôt
# (l'entrée OFD est de mauvaise qualité — ici un simple « R » rouge), et on
# ne le télécharge pas.
BRANDS = [
    ("Prusament", "prusament",       "prusament_logo.png", False),
    ("ROSA3D",    "rosa3d_filaments", "rosa3d_logo.png",     True),
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

    db = load_db(DB_FILE)

    db.setdefault("_brands", {})

    failures = []
    checked = 0
    for db_key, ofd_slug, logo_filename, curated in BRANDS:
        brand_url = f"{_OFD}/{ofd_slug}/brand.json"
        logo_url  = f"{_OFD}/{ofd_slug}/logo.png"
        logo_file = os.path.join(DATA_DIR, logo_filename)
        logo_path = f"data/{logo_filename}"

        try:
            brand = _fetch_json(brand_url)
            if not isinstance(brand, dict) or not any(
                isinstance(brand.get(key), str) and brand[key].strip() for key in ("id", "name")
            ):
                raise SourceUnavailable("Métadonnées de marque vides ou inexploitables.")
        except Exception as exc:
            print(f"[WARN] {db_key}: impossible de récupérer brand.json — {exc}")
            failures.append(f"{db_key} : {exc}")
            continue

        checked += 1
        logo_ok = os.path.exists(logo_file)
        if curated and not logo_ok:
            # Curated artwork remains in read-only resources, not the user database.
            relative = canonical_resource_path(logo_path)
            bundled = os.path.join(_RESOURCE, relative)
            if os.path.isfile(bundled):
                logo_file, logo_path, logo_ok = bundled, relative, True
        if curated:
            # Asset soigné fourni avec le dépôt : pas de téléchargement.
            if not logo_ok:
                print(f"[WARN] {db_key}: asset soigné absent ({logo_file})")
                failures.append(f"{db_key} : logo indisponible.")
                logo_path = ""
            else:
                print(f"  {db_key}: asset vectoriel soigné conservé ({logo_filename})")
        elif force or not logo_ok:
            try:
                logo_bytes = _fetch_bytes(logo_url)
                if not dry_run:
                    atomic_write(logo_file, logo_bytes)
                logo_ok = True
                print(f"  {db_key}: logo téléchargé → {logo_file}")
            except Exception as exc:
                print(f"[WARN] {db_key}: impossible de télécharger le logo — {exc}")
                failures.append(f"{db_key} : logo indisponible.")
                logo_path = ""

        incoming = {
            "id":          brand.get("id",      ofd_slug),
            "name":        brand.get("name",     db_key),
            "website":     brand.get("website",  ""),
            "origin":      brand.get("origin",   ""),
            "source":      brand.get("source",   "openprinttag"),
            "logo":        logo_filename,
            "logo_path":   logo_path if logo_ok else "",
            "logo_source": ("soigné (fourni avec SpoolScribe)" if curated
                            else "OpenFilamentCollective/open-filament-database"),
            "logo_url":    "" if curated else logo_url,
            "updated_at":  datetime.now().isoformat(),
        }
        current = db.setdefault("_brands", {}).setdefault(db_key, {})
        for field, value in incoming.items():
            if field == "updated_at":
                continue
            if not current.get(field):
                current[field] = value
            elif current[field] != value:
                print(f"CONFLIT marque : {field}, valeur locale conservée.")

        status = "OK" if logo_ok else "absent"
        print(f"  {db_key}: métadonnées {'simulées' if dry_run else 'mises à jour'} — logo {status}")

    if not checked:
        raise SourceUnavailable(" ; ".join(failures) or "Aucune marque vérifiée.")
    if not dry_run:
        save_db(db, DB_FILE)
        print(f"DB sauvegardée : {DB_FILE}")
    else:
        print("[DRY RUN] Aucune modification écrite.")
    if failures:
        raise PartialUpdate(" ; ".join(failures))


if __name__ == "__main__":
    run_step(main, DB_FILE)
