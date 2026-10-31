"""Offline native smoke check of the packaged universal catalogue and exports."""
import hashlib
import json
import os
from pathlib import Path
import sys


def offline(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise AssertionError("Packaged catalogue checks must stay offline")


sys.addaudithook(offline)
assert getattr(sys, "frozen", False)
import core
from scripts import catalogue_sources, db_io

db = core.load_db()
assert not db["_skus"], "Installer must start without catalogue data"
assert not (Path(core.RESOURCE_DIR) / "data/polymaker_db.json").exists()
assert not (Path(core.RESOURCE_DIR) / "data/catalogue_ofd.json").exists()
assert not (Path(core.RESOURCE_DIR) / "orca_profiles").exists()
assert "ofd" in catalogue_sources.SOURCE_ADAPTERS
from scripts import catalogue_merge, official_sources, app_updates
# Synthetic offline fixture tests the packaged write/export path, not a shipped database.
p = dict(brand="Test", type="PLA", min_temp=190, max_temp=230, bed_min_temp=50,
         bed_max_temp=60, diameter=1.75, density=1.24)
e = dict(product="Test PLA", color_name="Red", hex="FF0000")
db["_products"]["Test PLA"] = p
db["_skus"]["TEST"] = e
core.save_db(db)
payload = core.build_openspool(dict(e,sku="TEST"),p)
for tag in core.NFC_CAPACITIES:
    options=core.recommended_nfc(payload,tag)
    text=core.serialize_openspool(payload,**options)
    output=core.write_openspool("TEST",e,p,**options)
    assert Path(output).read_text(encoding="utf-8")==text
    assert core.nfc_size(text,tag_type=tag).fits
assert core.load_db()["_skus"]["TEST"]==e
manifest = db_io.parse_json((Path(core.RESOURCE_DIR) / "data/brand_logos/manifest.json").read_bytes())
for item in manifest.values():
    assert hashlib.sha256((Path(core.RESOURCE_DIR) / item["path"]).read_bytes()).hexdigest() == item["sha256"]
result = {"version": core.APP_VERSION, "empty_first_install": True, "fixture_references": len(db["_skus"]),
          "approved_new_logos": len(manifest), "tag_exports": list(core.NFC_CAPACITIES), "offline": True}
Path(os.environ["SPOOLSCRIBE_CATALOGUE_REPORT"]).write_text(json.dumps(result), encoding="utf-8")
