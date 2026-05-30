"""
scrape_wiki_hex.py — Enrichit polymaker_db.json avec les codes HEX
officiels depuis la page Wiki Polymaker (codes-hex-et-distances-de-transmission).

Usage:
    python scrape_wiki_hex.py              # remplit les hex manquants
    python scrape_wiki_hex.py --force      # remplace aussi les hex existants (wholesale)
    python scrape_wiki_hex.py --dry-run    # prévisualise sans modifier
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

WIKI_URL = (
    "https://wiki.polymaker.com/polymaker-wiki/polymaker-wiki-fr/"
    "produits-polymaker/en-savoir-plus-sur-nos-produits/"
    "codes-hex-et-distances-de-transmission"
)

_RESOURCE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_HOME = os.environ.get("SPOOLSCRIBE_DATA_HOME") or _RESOURCE
DATA_DIR   = os.path.join(_DATA_HOME, "data")
DB_FILE    = os.path.join(DATA_DIR, "polymaker_db.json")


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_wiki_hex() -> dict[str, str]:
    """
    Download the wiki HEX page and return a {SKU: HEX} dict.
    HEX values are 6-char uppercase strings (no leading #).
    """
    print("Fetching wiki HEX page…", end=" ", flush=True)
    req = urllib.request.Request(
        WIKI_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"FAILED ({e})")
        return {}

    print(f"{len(html):,} bytes")

    # Each table row has 5 cells: SKU | ProductLine | ColorName | #HexCode | TD
    # Cell text is inside: role="cell" ... <p ...>TEXT</p>
    cell_re   = re.compile(r'role="cell"[^>]*>.*?<p[^>]*>(.*?)</p>', re.DOTALL)
    sku_re    = re.compile(r'^[CP][A-Z0-9]\d{5}$')
    hex_re    = re.compile(r'^#?([0-9A-Fa-f]{6})$')

    raw_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cell_re.findall(html)]

    results: dict[str, str] = {}
    i = 0
    while i < len(raw_cells) - 2:
        if sku_re.match(raw_cells[i]):
            sku = raw_cells[i]
            # Hex can be at offset 2, 3, or 4 (depending on whether product/color cols merge)
            for offset in (2, 3, 4):
                if i + offset >= len(raw_cells):
                    break
                hm = hex_re.match(raw_cells[i + offset])
                if hm:
                    results[sku] = hm.group(1).upper()
                    break
            i += 5  # advance a full row
        else:
            i += 1

    print(f"  {len(results)} SKU→HEX pairs extracted from wiki")
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    force   = "--force"   in sys.argv

    # 1. Load DB
    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    skus_dict: dict = db["_skus"]

    # 2. Fetch wiki data
    wiki_hex = fetch_wiki_hex()
    if not wiki_hex:
        print("Nothing to do (fetch failed).")
        return

    # 3. Apply
    stats = {"filled": 0, "overridden": 0, "skipped": 0, "unknown_sku": 0}

    for sku, hex_code in wiki_hex.items():
        if sku not in skus_dict:
            stats["unknown_sku"] += 1
            continue

        entry    = skus_dict[sku]
        existing = entry.get("hex")

        if not existing:
            # Fill missing hex
            if not dry_run:
                entry["hex"] = hex_code
            stats["filled"] += 1
        elif existing.upper() != hex_code:
            if force:
                if not dry_run:
                    entry["hex"] = hex_code
                stats["overridden"] += 1
            else:
                stats["skipped"] += 1

    # 4. Save
    if not dry_run:
        db["_last_updated"] = datetime.now().isoformat()
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"\nDB saved: {DB_FILE}")

    # 5. Report
    print("\n── Stats ─────────────────────────────────────────")
    print(f"  Hex filled (was missing)    : {stats['filled']}")
    print(f"  Hex overridden (--force)    : {stats['overridden']}")
    print(f"  Conflicts skipped (no force): {stats['skipped']}")
    print(f"  SKUs in wiki but not in DB  : {stats['unknown_sku']}")
    total_missing = sum(1 for v in skus_dict.values() if not v.get("hex"))
    print(f"  Total SKUs still missing hex: {total_missing}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
    if stats["skipped"] and not force:
        print(f"\n  Tip: re-run with --force to override {stats['skipped']} conflicting values.")


if __name__ == "__main__":
    main()
