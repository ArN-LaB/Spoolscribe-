"""Run inside the frozen app: offline colour-measurement journeys on an isolated data folder.

No instrument, no network, no catalogue download. The registry is written in the
QA data folder given by SPOOLSCRIBE_DATA_HOME; the catalogue stays empty apart
from one synthetic reference, exactly like the catalogue probe.
"""
import json
import os
from pathlib import Path
import sys


def offline(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise AssertionError("Frozen measurement probe must stay offline")


sys.addaudithook(offline)
assert getattr(sys, "frozen", False)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from spoolscribe import app_gui, colour_import, colour_measurements as cm, colour_targets, core, measurement_store

app = QApplication.instance() or QApplication([])
app_gui.configure_application(app)
core.save_config(dict(core.load_config(), network_consent=False))
db = core.load_db()
assert not db["_skus"], "Installer must start without catalogue data"
db["_products"]["Probe PLA"] = dict(brand="Probe", type="PLA", min_temp=190, max_temp=230, bed_min_temp=50, bed_max_temp=60, diameter=1.75, density=1.24)
db["_skus"]["PROBE"] = dict(product="Probe PLA", color_name="Teal", hex="74CABF")
core.save_db(db)
window = app_gui.MainWindow()
dialog = window._open_measurements()
registry_path = Path(core.DB_PATH).with_name("colour_measurements.json")
assert not registry_path.exists(), "Opening the window must not create the registry"
# Manual Lab D65/2° → indicative ranking against the single catalogue colour.
dialog.space.setCurrentIndex(dialog.space.findData("CIELAB"))
for key, text in (("L", "73,2"), ("a", "-25,6"), ("b", "-12,4")):
    dialog.lab_edits[key].setText(text)
dialog.illuminant.setCurrentIndex(dialog.illuminant.findData("D65")); dialog.observer.setCurrentIndex(dialog.observer.findData(2))
assert dialog.btn_search.isEnabled()
dialog.btn_save.click(); app.processEvents()
assert registry_path.exists()
dialog.btn_search.click(); app.processEvents()
assert window._colour_query["kind"] == "measurement" and "lab" in window._colour_query
assert [r["sku"] for r in window._filtered_rows] == ["PROBE"]
delta = window._colour_deltas["PROBE"]["delta"]
# Paste with conflicting HEX/RGB and D50 conditions: a decision is required, nothing is ranked.
dialog = window._open_measurements(); dialog.tabs.setCurrentIndex(1)
dialog.paste_edit.setPlainText("HEX #74CABF RGB 10 20 30 L*=60 a*=1 b*=2 D50 10°"); dialog.btn_interpret.click(); app.processEvents()
assert dialog.paste_candidates.count() == 3 and not dialog.btn_search.isEnabled()
dialog.paste_candidates.setCurrentRow(2); app.processEvents()
assert dialog.level_tile.value.text() and not dialog.btn_search.isEnabled()
dialog.reject()
# Registry: link/detach/delete/restore through the store used by the window.
registry = measurement_store.MeasurementRegistry(registry_path); registry.load()
identifier = next(iter(registry.measurements))
registry.associate(identifier, "PROBE"); registry.detach(identifier); registry.delete(identifier); registry.restore()
assert identifier in registry.load()["measurements"]
assert core.load_db()["_skus"]["PROBE"]["hex"] == "74CABF"
# CSV mapping on an in-memory synthetic document (no fixture bundled).
preview = colour_import.preview_csv("Sample;L*;a*;b*;Illuminant;Observer\n probe;73,2;-25,6;-12,4;D65;2\n".encode("utf-8"))
mapping = colour_import.propose_mapping(preview["header"])["mapping"]
report = colour_import.validate_rows(colour_import.read_records(colour_import.decode_text("Sample;L*;a*;b*;Illuminant;Observer\n probe;73,2;-25,6;-12,4;D65;2\n".encode())[0], ";")[1:], mapping, decimal=",")
assert len(report["valid"]) == 1 and not report["errors"]
result = dict(version=core.APP_VERSION, registry=str(registry_path.name), measurements=len(registry.measurements), delta=delta,
              paste_candidates=3, csv_valid=len(report["valid"]), catalogue_untouched=True, offline=True)
Path(os.environ["SPOOLSCRIBE_MEASUREMENTS_REPORT"]).write_text(json.dumps(result), encoding="utf-8")
