"""Supplement uncovered manufacturers from the public SpoolmanDB catalogue."""
import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import catalogue_sources as sources, db_io, catalogue_merge

DB_FILE = db_io.default_db_path()


def fetch_catalogue(etag=None):
    from scripts import official_sources
    return official_sources.fetch(sources.SPOOLMAN_URL, 32 * 1024 * 1024, etag=etag, timeout=60)


def main():
    from scripts import official_sources
    db = db_io.load_db(DB_FILE)
    previous = (db.get("_source_snapshots") or {}).get("spoolman") or {}
    try:
        raw = fetch_catalogue(previous.get("etag"))
        rows = db_io.parse_json(raw)
    except official_sources.NotModified:
        print("SpoolmanDB : catalogue inchangé depuis la dernière synchronisation (ETag).")
        return "unchanged"
    except Exception as exc:
        raise db_io.SourceUnavailable(f"SpoolmanDB indisponible : {exc}") from exc
    covered = [name for name, meta in db["_brands"].items() if meta.get("source") != "SpoolmanDB"]
    incoming, report = sources.adapt_spoolman(rows, source_digest=hashlib.sha256(raw).hexdigest(), covered_brands=covered)
    db_io.check_source_shrink(db, "spoolman", len(incoming["_skus"]), "SpoolmanDB")
    merged, conflicts = catalogue_merge.merge_catalogue(db, incoming, "SpoolmanDB", 10)
    db.update(merged)
    snapshot = dict(incoming["_source_snapshot"])
    etag = getattr(official_sources.fetch, "last_etag", None)
    if isinstance(etag, str) and etag:
        snapshot["etag"] = etag
    db.setdefault("_source_snapshots", {})["spoolman"] = snapshot
    db.setdefault("_source_conflicts_by_source", {})["spoolman"] = conflicts
    db_io.save_db(db, DB_FILE)
    print(f"SpoolmanDB : {report['references']} références, {report['brands_imported']} fabricants supplémentaires.")
    if report["rejected"]:
        raise db_io.PartialUpdate(f"SpoolmanDB : {len(report['rejected'])} références rejetées ; "
                                  f"première anomalie : {report['rejected'][0]}")


if __name__ == "__main__":
    db_io.run_step(main, DB_FILE)
