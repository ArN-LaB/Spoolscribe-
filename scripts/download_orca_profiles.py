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

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCA_DIR   = os.path.join(SCRIPT_DIR, "orca_profiles")

INDEX_URL  = "https://raw.githubusercontent.com/polymaker3d/Polymaker-Preset/main/index.json"
RAW_BASE   = "https://raw.githubusercontent.com/polymaker3d/Polymaker-Preset/main/"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "polymaker-db/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "polymaker-db/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def local_filename(material):
    """Nom de fichier local : '{material} @Snapmaker U1 - OrcaSlicer.json'"""
    return f"{material} @Snapmaker U1 - OrcaSlicer.json"


def main():
    parser = argparse.ArgumentParser(description="Télécharge les profils Orca Snapmaker U1")
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche ce qui serait téléchargé sans rien écrire")
    parser.add_argument("--force", action="store_true",
                        help="Re-télécharge même les fichiers déjà présents")
    args = parser.parse_args()

    os.makedirs(ORCA_DIR, exist_ok=True)

    print("Téléchargement de l'index...")
    try:
        index = fetch_json(INDEX_URL)
    except Exception as e:
        print(f"Erreur lors du téléchargement de l'index : {e}", file=sys.stderr)
        sys.exit(1)

    # Filtrer les profils Snapmaker U1 / OrcaSlicer
    snapmaker_presets = [
        p for p in index.get("presets", [])
        if p.get("brand") == "Snapmaker"
        and p.get("model") == "U1"
        and p.get("slicer") in ("OrcaSlicer", "Orcaslicer")
    ]

    if not snapmaker_presets:
        print("Aucun profil Snapmaker U1 trouvé dans l'index.")
        sys.exit(0)

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

        url = RAW_BASE + path
        action = "Mise à jour" if exists else "Nouveau"
        print(f"  [{action}] {material}  ({updated})")

        if args.dry_run:
            downloaded += 1
            continue

        try:
            data = fetch_bytes(url)
            with open(dest, "wb") as f:
                f.write(data)
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


if __name__ == "__main__":
    main()
