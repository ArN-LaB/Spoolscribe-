"""Update all compatible OFD manufacturers after the application's network consent."""
import hashlib
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import catalogue_sources, db_io, catalogue_merge

DB_FILE = db_io.default_db_path()


class _ArchiveRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urllib.parse.urlsplit(newurl)
        if url.scheme != "https" or url.hostname != "codeload.github.com" or url.username or url.port not in (None, 443):
            raise db_io.SourceUnavailable("Redirection OFD hors de l'hôte HTTPS déclaré.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class NotModified(Exception):
    """The archive endpoint confirmed the cached snapshot is current."""


def fetch_archive(etag=None):
    headers = {"User-Agent": "SpoolScribe/0.3 (+https://github.com/ArN-LaB/Spoolscribe-; catalogue update)"}
    if etag:
        headers["If-None-Match"] = etag
    request = urllib.request.Request(catalogue_sources.OFD_ARCHIVE_URL, headers=headers)
    try:
        with urllib.request.build_opener(_ArchiveRedirect()).open(request, timeout=120) as response:
            if not response.url.startswith("https://codeload.github.com/"):
                raise db_io.SourceUnavailable("Redirection OFD inattendue.")
            raw = response.read(catalogue_sources.MAX_ARCHIVE_BYTES + 1)
            fetch_archive.last_etag = response.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304 and etag:
            raise NotModified()
        raise
    return raw


fetch_archive.last_etag = None


def main():
    db = db_io.load_db(DB_FILE)
    previous = (db.get("_source_snapshots") or {}).get("ofd") or {}
    try:
        raw = fetch_archive(previous.get("etag"))
        files = catalogue_sources.read_ofd_archive(raw)
    except NotModified:
        print("OFD : archive inchangée depuis la dernière synchronisation (ETag).")
        return "unchanged"
    except Exception as exc:
        raise db_io.SourceUnavailable(f"Catalogue OFD indisponible : {exc}") from exc
    manifest = ROOT / "data/brands/manifest.json"
    logos = db_io.parse_json(manifest.read_bytes()) if manifest.is_file() else {}
    incoming, report = catalogue_sources.adapt_ofd(files, source_digest=hashlib.sha256(raw).hexdigest(), logos=logos, preserve_curated=False)
    # These three reviewed legacy logos remain artwork resources even though
    # the historical filament database is no longer installed.
    legacy_logos = {"polymaker": "brands/logos/polymaker-lines.svg", "prusament": "brands/logos/prusament.svg", "rosa3d": "brands/logos/rosa3d.png"}
    for name, meta in incoming["_brands"].items():
        logo = legacy_logos.get(catalogue_sources.brand_key(name))
        if logo and (ROOT / "data" / logo).is_file():
            meta.setdefault("logo_path", "data/" + logo)
    db_io.check_source_shrink(db, "ofd", len(incoming["_skus"]), "OFD")
    merged, conflicts = catalogue_merge.merge_catalogue(db, incoming, "Open Filament Database", 20)
    db.update(merged)
    snapshot = dict(incoming["_source_snapshot"])
    etag = getattr(fetch_archive, "last_etag", None)
    if isinstance(etag, str) and etag:
        snapshot["etag"] = etag
    db.setdefault("_source_snapshots", {})["ofd"] = snapshot
    db["_source_conflicts"] = conflicts
    db_io.save_db(db, DB_FILE)
    print(f"OFD : {report['references']} références, {report['brands_imported']} fabricants ; "
          f"{len(conflicts)} valeurs locales conservées.")
    if report["rejected"]:
        raise db_io.PartialUpdate(f"OFD : {len(report['rejected'])} variantes rejetées ; "
                                  f"première anomalie : {report['rejected'][0]}")


if __name__ == "__main__":
    db_io.run_step(main, DB_FILE)
