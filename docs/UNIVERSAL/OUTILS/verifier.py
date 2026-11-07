#!/usr/bin/env python3
"""Audit documentaire local, en lecture seule, sans dépendance externe.

Exemple : python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
Options : --all-docs (dossiers vides dans tout docs), --strict (code != 0 sur erreur).
Ne modifie, ne crée et ne supprime aucun fichier. Ne suit pas les liens symboliques.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
import re
import sys
from urllib.parse import unquote

PHASE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|DATE-INCONNUE)-([A-Z0-9]+(?:-[A-Z0-9]+)*)$")
BOUCLE_RE = re.compile(r"^B\d{2,3}-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(\s*(<[^>]+>|[^)\n]+)\s*\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def main() -> int:
    ap = argparse.ArgumentParser(description="Vérification en lecture seule des traces universelles")
    ap.add_argument("--root", default=".", help="Racine du projet ouvert")
    ap.add_argument("--strict", action="store_true", help="Code 1 si erreurs documentaires")
    ap.add_argument("--all-docs", action="store_true", help="Dossiers vides sous tout docs/ (sinon UNIVERSAL + agent-runs)")
    args = ap.parse_args()

    root = Path(args.root).expanduser().absolute()
    docs = root / "docs"
    trace = docs / "agent-runs"
    common = docs / "UNIVERSAL"
    issues: list[tuple[str, str]] = []
    totals = Counter()

    def note(level: str, message: str) -> None:
        issues.append((level, message))

    if not docs.is_dir() or docs.is_symlink():
        print("ERREUR : docs/ est absent ou est un lien symbolique.")
        return 1 if args.strict else 0

    entry = docs / "UNIVERSAL.md"
    if not entry.is_file() or entry.is_symlink():
        note("ERREUR", "docs/UNIVERSAL.md absent ou invalide")
    for filename in ("01-NORME.md", "02-MISSION-ADOPTION.md", "03-MODELES.md", "04-ESSAIS-ET-NETTOYAGE.md"):
        p = common / filename
        if not p.is_file() or p.is_symlink():
            note("ERREUR", f"Fichier universel manquant : {relative(p, root)}")

    files_to_check: list[Path] = []
    visited_dirs: set[Path] = set()

    def walk(start: Path) -> None:
        if not start.exists() or start.is_symlink() or not start.is_dir():
            return
        stack = [start]
        while stack:
            folder = stack.pop()
            if folder in visited_dirs:
                continue
            visited_dirs.add(folder)
            try:
                entries = sorted(folder.iterdir(), key=lambda p: p.name)
            except OSError as e:
                note("AVERTISSEMENT", f"Répertoire inaccessible : {relative(folder, root)} ({e})")
                continue
            if not entries or all(e.name == ".DS_Store" for e in entries):
                note("ERREUR", f"Dossier documentaire vide ou .DS_Store seul : {relative(folder, root)}")
            for p in entries:
                if p.is_symlink():
                    note("AVERTISSEMENT", f"Lien symbolique non suivi : {relative(p, root)}")
                elif p.is_dir():
                    stack.append(p)
                elif p.is_file() and p.suffix.lower() == ".md":
                    files_to_check.append(p)

    if args.all_docs:
        walk(docs)
    else:
        walk(common)
        walk(trace)
        if entry.is_file() and not entry.is_symlink():
            files_to_check.append(entry)

    # Vérification légère de l'organisation courante : aucun fichier factice requis.
    if not trace.is_dir():
        note("INFO", "Pas de docs/agent-runs/ : aucune phase créée à ce stade")
    elif trace.is_symlink():
        note("ERREUR", "docs/agent-runs ne doit pas être un lien symbolique")
    else:
        phase_dirs: list[Path] = []
        try:
            top = sorted(trace.iterdir(), key=lambda p: p.name)
        except OSError:
            top = []
        for item in top:
            if item.is_symlink() or not item.is_dir():
                continue
            m = PHASE_RE.fullmatch(item.name)
            if not m:
                note("AVERTISSEMENT", f"Dossier de premier niveau non conforme / historique : {relative(item, root)}")
                continue
            if m.group(1) != "DATE-INCONNUE":
                try:
                    date.fromisoformat(m.group(1))
                except ValueError:
                    note("ERREUR", f"Date de phase invalide : {relative(item, root)}")
            phase_dirs.append(item)
            totals["phases"] += 1
            if not (item / "00-PHASE.md").is_file():
                note("ERREUR", f"00-PHASE.md absent : {relative(item, root)}")
            for boucle in sorted(item.iterdir(), key=lambda p: p.name):
                if boucle.is_symlink() or not boucle.is_dir() or not BOUCLE_RE.fullmatch(boucle.name):
                    continue
                totals["boucles"] += 1
                if not (boucle / "00-BOUCLE.md").is_file():
                    note("ERREUR", f"00-BOUCLE.md absent : {relative(boucle, root)}")
                preuves = boucle / "PREUVES"
                if preuves.is_dir() and not (preuves / "MANIFESTE.csv").is_file():
                    note("ERREUR", f"PREUVES sans MANIFESTE.csv : {relative(preuves, root)}")
        if phase_dirs and not (trace / "INDEX.md").is_file():
            note("ERREUR", "docs/agent-runs/INDEX.md absent alors que des phases existent")
        if not phase_dirs:
            note("INFO", "Aucune phase canonique identifiée ; vérifier si une adoption est nécessaire")

    # Liens directs locaux dans les Markdown analysés (sans lire fichiers externes ni symlinks).
    totals["markdown"] = len(set(files_to_check))
    for path in sorted(set(files_to_check)):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            note("AVERTISSEMENT", f"Markdown non lisible : {relative(path, root)} ({e})")
            continue
        is_fenced = False
        clean_lines = []
        for line in content.splitlines():
            if FENCE_RE.match(line):
                is_fenced = not is_fenced
                continue
            if not is_fenced:
                clean_lines.append(line)
        for match in LINK_RE.finditer("\n".join(clean_lines)):
            target = match.group(1).strip().strip("<>")
            if not target or target.startswith(("#", "http:", "https:", "mailto:", "data:", "file:")):
                continue
            if " " in target and "?" not in target and "%20" not in target:
                target = target.split(" ", 1)[0]  # titre optionnel du lien Markdown
            link_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not link_path:
                continue
            totals["liens_locaux"] += 1
            # Les références absolues externes sont consignées, jamais ouvertes.
            if link_path.startswith("/"):
                note("INFO", f"Chemin absolu non vérifié : {relative(path, root)} → {link_path}")
                continue
            destination = path.parent / link_path
            try:
                resolved = destination.resolve(strict=False)
            except (OSError, RuntimeError):
                note("AVERTISSEMENT", f"Lien non résoluble : {relative(path, root)} → {target}")
                continue
            if not inside(resolved, root):
                note("AVERTISSEMENT", f"Lien hors projet non parcouru : {relative(path, root)} → {target}")
                continue
            if not resolved.exists():
                note("ERREUR", f"Lien local absent : {relative(path, root)} → {target}")
            # Aucun accès à la cible ; les ancres / liens dynamiques ne sont pas validés ici.

    print("VÉRIFICATION UNIVERSAL — LECTURE SEULE")
    print(f"Projet analysé : {root}")
    print(f"Phases : {totals['phases']} | Boucles : {totals['boucles']} | Markdown lus : {totals['markdown']} | Liens locaux : {totals['liens_locaux']}")
    for level in ("ERREUR", "AVERTISSEMENT", "INFO"):
        selected = [msg for lvl, msg in issues if lvl == level]
        print(f"{level} : {len(selected)}")
        for msg in selected[:80]:
            print(f"  - {msg}")
        if len(selected) > 80:
            print(f"  ... et {len(selected) - 80} autres éléments du même niveau")
    print("Limites : pas de tests applicatifs, d'URLs réseau, d'ancres rendues ni de liens construits par script.")
    print("Aucune suppression, modification ou création de fichier effectuée.")
    return 1 if args.strict and any(level == "ERREUR" for level, _ in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
