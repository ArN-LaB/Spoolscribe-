#!/usr/bin/env python3
"""Local read-only documentation check, without external dependencies.

Example: python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
Options : --all-docs (empty folders throughout docs), --strict (nonzero exit on error).
Never modifies, creates or deletes files; never follows symlinks.
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
    ap = argparse.ArgumentParser(description="Read-only universal trace verification")
    ap.add_argument("--root", default=".", help="Open project root")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on documentation errors")
    ap.add_argument("--all-docs", action="store_true", help="Empty folders throughout docs/ (otherwise UNIVERSAL + agent-runs)")
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
        print("ERROR : docs/ is missing or is a symlink.")
        return 1 if args.strict else 0

    entry = docs / "UNIVERSAL.md"
    if not entry.is_file() or entry.is_symlink():
        note("ERROR", "docs/UNIVERSAL.md missing or invalid")
    for filename in ("01-NORME.md", "02-MISSION-ADOPTION.md", "03-MODELES.md", "04-ESSAIS-ET-NETTOYAGE.md"):
        p = common / filename
        if not p.is_file() or p.is_symlink():
            note("ERROR", f"Missing universal file : {relative(p, root)}")

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
                note("WARNING", f"Inaccessible directory : {relative(folder, root)} ({e})")
                continue
            if not entries or all(e.name == ".DS_Store" for e in entries):
                note("ERROR", f"Empty documentation folder or .DS_Store only : {relative(folder, root)}")
            for p in entries:
                if p.is_symlink():
                    note("WARNING", f"Symlink not followed : {relative(p, root)}")
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

    # Lightweight structure check: no placeholder file required.
    if not trace.is_dir():
        note("INFO", "No docs/agent-runs/: no phase exists yet")
    elif trace.is_symlink():
        note("ERROR", "docs/agent-runs must not be a symlink")
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
                note("WARNING", f"Noncanonical/historical top-level folder : {relative(item, root)}")
                continue
            if m.group(1) != "DATE-INCONNUE":
                try:
                    date.fromisoformat(m.group(1))
                except ValueError:
                    note("ERROR", f"Invalid phase date : {relative(item, root)}")
            phase_dirs.append(item)
            totals["phases"] += 1
            if not (item / "00-PHASE.md").is_file():
                note("ERROR", f"Missing 00-PHASE.md : {relative(item, root)}")
            for boucle in sorted(item.iterdir(), key=lambda p: p.name):
                if boucle.is_symlink() or not boucle.is_dir() or not BOUCLE_RE.fullmatch(boucle.name):
                    continue
                totals["boucles"] += 1
                if not (boucle / "00-BOUCLE.md").is_file():
                    note("ERROR", f"Missing 00-BOUCLE.md : {relative(boucle, root)}")
                preuves = boucle / "PREUVES"
                if preuves.is_dir() and not (preuves / "MANIFESTE.csv").is_file():
                    note("ERROR", f"PREUVES without MANIFESTE.csv : {relative(preuves, root)}")
        if phase_dirs and not (trace / "INDEX.md").is_file():
            note("ERROR", "docs/agent-runs/INDEX.md missing despite existing phases")
        if not phase_dirs:
            note("INFO", "No canonical phase found; determine whether adoption is needed")

    # Direct local Markdown links; never read external targets or follow symlinks.
    totals["markdown"] = len(set(files_to_check))
    for path in sorted(set(files_to_check)):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            note("WARNING", f"Unreadable Markdown : {relative(path, root)} ({e})")
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
                target = target.split(" ", 1)[0]  # optional Markdown link title
            link_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not link_path:
                continue
            totals["liens_locaux"] += 1
            # Record external absolute references without opening them.
            if link_path.startswith("/"):
                note("INFO", f"Unverified absolute path : {relative(path, root)} → {link_path}")
                continue
            destination = path.parent / link_path
            try:
                resolved = destination.resolve(strict=False)
            except (OSError, RuntimeError):
                note("WARNING", f"Unresolvable link : {relative(path, root)} → {target}")
                continue
            if not inside(resolved, root):
                note("WARNING", f"Out-of-project link not followed : {relative(path, root)} → {target}")
                continue
            if not resolved.exists():
                note("ERROR", f"Missing local link : {relative(path, root)} → {target}")
            # No target content access; rendered anchors and dynamic links are not checked.

    print("UNIVERSAL CHECK — READ ONLY")
    print(f"Project checked : {root}")
    print(f"Phases : {totals['phases']} | Loops: {totals['boucles']} | Markdown read: {totals['markdown']} | Local links: {totals['liens_locaux']}")
    for level in ("ERROR", "WARNING", "INFO"):
        selected = [msg for lvl, msg in issues if lvl == level]
        print(f"{level} : {len(selected)}")
        for msg in selected[:80]:
            print(f"  - {msg}")
        if len(selected) > 80:
            print(f"  ... and {len(selected) - 80} more items at this level")
    print("Limits: no application tests, network URLs, rendered anchors or script-generated links.")
    print("No file deleted, modified or created.")
    return 1 if args.strict and any(level == "ERROR" for level, _ in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
