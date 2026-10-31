"""Supplement uncovered manufacturers from the public SpoolmanDB catalogue."""
import hashlib
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import catalogue_sources as sources, db_io, catalogue_merge

DB_FILE = str(Path(os.environ.get("SPOOLSCRIBE_DATA_HOME") or ROOT) / "data/polymaker_db.json")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise db_io.SourceUnavailable("Redirection SpoolmanDB inattendue.")


def fetch_catalogue():
    request = urllib.request.Request(sources.SPOOLMAN_URL, headers={"User-Agent": "SpoolScribe/0.3 catalogue update"})
    with urllib.request.build_opener(_NoRedirect()).open(request, timeout=60) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise db_io.SourceUnavailable("Catalogue SpoolmanDB trop volumineux.")
    return raw


def main():
    try:
        raw = fetch_catalogue()
        rows = db_io.parse_json(raw)
    except Exception as exc:
        raise db_io.SourceUnavailable(f"SpoolmanDB indisponible : {exc}") from exc
    db = db_io.load_db(DB_FILE)
    covered = [name for name, meta in db["_brands"].items() if meta.get("source") != "SpoolmanDB"]
    incoming, report = sources.adapt_spoolman(rows, source_digest=hashlib.sha256(raw).hexdigest(), covered_brands=[])
    merged, conflicts = catalogue_merge.merge_catalogue(db, incoming, "SpoolmanDB", 10)
    db.update(merged)
    db.setdefault("_source_snapshots", {})["spoolman"] = incoming["_source_snapshot"]
    db.setdefault("_source_conflicts_by_source", {})["spoolman"] = conflicts
    db_io.save_db(db, DB_FILE)
    print(f"SpoolmanDB : {report['references']} références, {report['brands_imported']} fabricants supplémentaires.")
    if report["rejected"]:
        raise db_io.PartialUpdate(f"SpoolmanDB : {len(report['rejected'])} références rejetées ; "
                                  f"première anomalie : {report['rejected'][0]}")


if __name__ == "__main__":
    db_io.run_step(main, DB_FILE)
