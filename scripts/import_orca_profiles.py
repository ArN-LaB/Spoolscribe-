#!/usr/bin/env python3
"""import_orca_profiles.py — Sync Orca filament profiles into polymaker_db.json.

Reads every *@Snapmaker U1 - OrcaSlicer.json in orca_profiles/, extracts the
official temps/density from Polymaker, and:
  - Updates existing _products entries (min_temp, max_temp, bed temps, density)
  - Adds missing sub-variant entries (e.g. "PolyLite PLA Galaxy")

Usage:
    python import_orca_profiles.py [--dry-run]
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE    = os.path.join(SCRIPT_DIR, "data", "polymaker_db.json")
ORCA_DIR   = os.path.join(SCRIPT_DIR, "orca_profiles")


# ── Helpers ───────────────────────────────────────────────────────────────

def first(obj, key, default=None):
    """Return the first element of an Orca array field, or default."""
    v = obj.get(key, [default])
    return v[0] if v else default


def read_orca_data(path):
    """Extract the relevant fields from an Orca profile JSON."""
    with open(path, encoding="utf-8") as f:
        p = json.load(f)

    # Gather all plate temps; ignore 0 (= "not applicable for this plate type")
    plate_keys = ["cool_plate_temp", "eng_plate_temp", "hot_plate_temp", "textured_plate_temp"]
    bed_temps = [int(first(p, k, 0)) for k in plate_keys]
    bed_temps_nonzero = [t for t in bed_temps if t > 0]
    bed_min = min(bed_temps_nonzero) if bed_temps_nonzero else 0
    bed_max = max(bed_temps_nonzero) if bed_temps_nonzero else 0

    return {
        "type":     first(p, "filament_type",            "PLA"),
        "min_temp": int(first(p, "nozzle_temperature_range_low",  190)),
        "max_temp": int(first(p, "nozzle_temperature_range_high", 230)),
        "bed_min":  bed_min,
        "bed_max":  bed_max,
        "density":  float(first(p, "filament_density",            1.24)),
        "diameter": float(first(p, "filament_diameter",           1.75)),
    }


def find_base_product(name, products_dict):
    """
    Find the longest existing product key that is a prefix of *name*.
    e.g. 'Panchroma PLA Luminous' -> 'Panchroma PLA'
    """
    parts = name.split()
    for i in range(len(parts) - 1, 0, -1):
        candidate = " ".join(parts[:i])
        if candidate in products_dict:
            return candidate
    return None


def derive_subtype(name, base_name):
    """
    Derive subtype from what remains after the base name.
    e.g. 'PolyLite PLA Galaxy', base='PolyLite PLA' -> 'Galaxy'
    """
    suffix = name[len(base_name):].strip()
    return suffix if suffix else None


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv

    with open(DB_FILE, encoding="utf-8") as f:
        db = json.load(f)
    products = db["_products"]

    stats = {"updated": 0, "added": 0, "skipped": 0}
    update_log = []
    added_log  = []

    for fname in sorted(os.listdir(ORCA_DIR)):
        if not fname.endswith(".json"):
            continue
        if "@Snapmaker" not in fname:
            continue

        product_name = fname.split(" @Snapmaker")[0]
        orca = read_orca_data(os.path.join(ORCA_DIR, fname))

        if product_name in products:
            # ── Update existing entry ──────────────────────────────────────
            entry = products[product_name]
            changes = {}
            for field, new_val in [
                ("min_temp",    orca["min_temp"]),
                ("max_temp",    orca["max_temp"]),
                ("bed_min_temp", orca["bed_min"]),
                ("bed_max_temp", orca["bed_max"]),
                ("density",     orca["density"]),
                ("diameter",    orca["diameter"]),
            ]:
                old_val = entry.get(field)
                if old_val != new_val:
                    changes[field] = (old_val, new_val)

            if changes:
                if not dry_run:
                    for field, (_, new_val) in changes.items():
                        entry[field] = new_val
                update_log.append((product_name, changes))
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

        else:
            # ── Add new sub-variant entry ──────────────────────────────────
            base = find_base_product(product_name, products)
            if base:
                base_entry = products[base]
                subtype    = derive_subtype(product_name, base)
                new_entry  = {
                    "type":         base_entry.get("type", orca["type"]),
                    "subtype":      subtype,
                    "brand":        base_entry.get("brand", "Polymaker"),
                    "min_temp":     orca["min_temp"],
                    "max_temp":     orca["max_temp"],
                    "bed_min_temp": orca["bed_min"],
                    "bed_max_temp": orca["bed_max"],
                    "diameter":     orca["diameter"],
                    "density":      orca["density"],
                }
            else:
                new_entry = {
                    "type":         orca["type"],
                    "subtype":      None,
                    "brand":        "Polymaker",
                    "min_temp":     orca["min_temp"],
                    "max_temp":     orca["max_temp"],
                    "bed_min_temp": orca["bed_min"],
                    "bed_max_temp": orca["bed_max"],
                    "diameter":     orca["diameter"],
                    "density":      orca["density"],
                }

            if not dry_run:
                products[product_name] = new_entry
            added_log.append((product_name, new_entry))
            stats["added"] += 1

    # ── Save ──────────────────────────────────────────────────────────────
    if not dry_run:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print(f"DB saved: {DB_FILE}")

    # ── Report ────────────────────────────────────────────────────────────
    print("\n── Stats ─────────────────────────────────────────")
    print(f"  Products updated   : {stats['updated']}")
    print(f"  Products added     : {stats['added']}")
    print(f"  Already up-to-date : {stats['skipped']}")

    if update_log:
        print("\n── Updates ───────────────────────────────────────")
        for name, changes in update_log:
            print(f"  {name}")
            for field, (old, new) in changes.items():
                print(f"    {field}: {old} → {new}")

    if added_log:
        print("\n── Added to _products ────────────────────────────")
        for name, entry in added_log:
            print(f"  + {name}  (type={entry['type']}, subtype={entry['subtype']}, "
                  f"nozzle={entry['min_temp']}-{entry['max_temp']}, "
                  f"bed={entry['bed_min_temp']}-{entry['bed_max_temp']}, density={entry['density']})")

    if dry_run:
        print("\n[DRY RUN] No changes written.")


if __name__ == "__main__":
    main()
