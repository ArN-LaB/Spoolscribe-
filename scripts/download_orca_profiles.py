"""
download_orca_profiles.py
Télécharge les profils Orca Snapmaker U1 depuis le repo GitHub Polymaker.
Index: https://raw.githubusercontent.com/polymaker3d/Polymaker-Preset/main/index.json
"""

import json
import os
import sys
import argparse
import urllib.request
import urllib.parse

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The worker also runs standalone; expose the project namespace to its helper.
if _RESOURCE not in sys.path:
    sys.path.insert(0, _RESOURCE)
from scripts.db_io import (
    atomic_write, parse_json, run_step, SourceUnavailable, PartialUpdate, orca_values
)
from scripts.resource_paths import user_data_home
_DATA_HOME = user_data_home()
ORCA_DIR   = os.path.join(_DATA_HOME, "orca_profiles")

INDEX_URL  = "https://raw.githubusercontent.com/polymaker3d/Polymaker-Preset/main/index.json"
RAW_BASE   = "https://raw.githubusercontent.com/polymaker3d/Polymaker-Preset/main/"


def fetch_json(url):
    from scripts import official_sources
    return json.loads(official_sources.fetch(url, 2 * 1024 * 1024).decode("utf-8"))


def fetch_bytes(url):
    from scripts import official_sources
    return official_sources.fetch(url, 2 * 1024 * 1024)


def local_filename(material):
    """Nom de fichier local : '{material} @Snapmaker U1 - OrcaSlicer.json'"""
    # Only a plain material name: no path separators, drive letters, NTFS
    # streams, control characters or relative segments.
    if (not isinstance(material, str) or not material.strip() or len(material) > 120
            or any(c in material for c in ("/", "\\", ":", "\x00")) or any(ord(c) < 32 for c in material)
            or material.strip() in (".", "..") or material != material.strip()):
        raise ValueError("Nom de matériau invalide pour un fichier Orca.")
    return f"{material} @Snapmaker U1 - OrcaSlicer.json"


def main():
    parser = argparse.ArgumentParser(description="Télécharge les profils Orca Snapmaker U1")
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche ce qui serait téléchargé sans rien écrire")
    parser.add_argument("--force", action="store_true",
                        help="Re-télécharge même les fichiers déjà présents")
    args = parser.parse_args()

    print("Téléchargement de l'index...")
    try:
        index = fetch_json(INDEX_URL)
    except Exception as e:
        raise SourceUnavailable(f"Index Orca indisponible : {e}") from e

    # Filtrer les profils Snapmaker U1 / OrcaSlicer
    snapmaker_presets = [
        p for p in index.get("presets", [])
        if p.get("brand") == "Snapmaker"
        and p.get("model") == "U1"
        and p.get("slicer") in ("OrcaSlicer", "Orcaslicer")
    ]

    if not snapmaker_presets:
        raise SourceUnavailable("Aucun profil Snapmaker U1 trouvé dans l'index.")

    print(f"{len(snapmaker_presets)} profils Snapmaker U1 trouvés dans l'index.")
    print(f"  Index mis à jour le : {index.get('updatedAt', '?')}\n")

    downloaded = 0
    skipped    = 0
    errors     = 0

    for preset in snapmaker_presets:
        material = preset["material"]
        path     = preset["path"]          # ex: "preset/Fiberon ASA-CF08/Snapmaker/U1/OrcaSlicer/..."
        updated  = preset.get("updatedAt", "")

        dest = os.path.join(ORCA_DIR, local_filename(material))
        exists = os.path.isfile(dest)

        if exists and not args.force:
            skipped += 1
            continue

        url = RAW_BASE + urllib.parse.quote(path)
        action = "Mise à jour" if exists else "Nouveau"
        print(f"  [{action}] {material}  ({updated})")

        if args.dry_run:
            downloaded += 1
            continue

        try:
            data = fetch_bytes(url)
            orca_values(parse_json(data))
            atomic_write(dest, data)
            downloaded += 1
        except Exception as e:
            print(f"    ERREUR : {e}", file=sys.stderr)
            errors += 1

    print()
    if args.dry_run:
        print(f"Mode dry-run : {downloaded} fichier(s) seraient téléchargé(s), {skipped} déjà présents.")
    else:
        print(f"Terminé : {downloaded} téléchargé(s), {skipped} ignoré(s) (déjà présents), {errors} erreur(s).")
        if downloaded > 0:
            print("\nLancez scripts/import_orca_profiles.py pour synchroniser la DB.")
    if errors:
        if not downloaded and not skipped:
            raise ValueError(f"Orca : aucun profil valide téléchargé ({errors} erreur(s)).")
        raise PartialUpdate(f"Orca : {errors} téléchargement(s) ou profil(s) invalide(s).")
    if downloaded and not args.dry_run:
        return "changed"


if __name__ == "__main__":
    run_step(main)
