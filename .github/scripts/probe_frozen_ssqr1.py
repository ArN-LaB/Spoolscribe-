"""Run inside the frozen app: offline QR outputs from external normative fixtures.

Fixtures and scan libraries are provided by CI, never bundled with the app.
No print dialog, printer discovery, network request or tag write is performed.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


def offline(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise AssertionError("Frozen SSQR1 probe must stay offline")


sys.addaudithook(offline)
assert getattr(sys, "frozen", False)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from spoolscribe import app_gui, core, i18n, ui_qr
import segno

out = Path(os.environ["SPOOLSCRIBE_SSQR1_OUTPUT"])
out.mkdir(parents=True, exist_ok=True)
vectors = json.loads(Path(os.environ["SPOOLSCRIBE_SSQR1_VECTORS"]).read_text(encoding="utf-8"))["vectors"]
app = QApplication.instance() or QApplication([])
app_gui.configure_application(app)
core.save_config(dict(core.load_config(), network_consent=False))
parent = app_gui.MainWindow()
rows = []
cases = (("catalogue-essential", "essential", "M"), ("catalogue-full", "full", "Q"),
         ("opentag-real-explicit", "", "M"))
for name, profile, error in cases:
    entry = vectors[name]
    message = bytes.fromhex(entry["hex"])
    for language in ("fr", "en", "es", "zh_CN"):
        i18n.set_language(language)
        for dark in (False, True):
            app_gui.is_dark_theme = lambda *_args, _dark=dark: _dark
            parent._apply_theme()
            core.save_config(dict(core.load_config(), qr_label={"error": error, "preset": "label-62x100"}))
            snap = ui_qr.QrSnapshot("QA", "QA", False, "QR offline", "Reference", "QA", entry["protocol"],
                                     "OpenSpool 1.0" if entry["protocol"] == 1 else "OpenTag3D 2.004",
                                     "NTAG216", 0, profile, (), message, "00:00")
            qr = ui_qr.QrWindow(snap, parent)
            assert qr.details.isHidden()
            qr.resize(420, 520)
            qr.show()
            qr.details_toggle.setChecked(True)
            app.processEvents()
            app.processEvents()
            assert qr.canvas.visibleRegion().boundingRect() == qr.canvas.rect()
            assert qr.canvas.scale() >= 2
            stem = f"{name}-{language}-{'dark' if dark else 'light'}"
            image = out / (stem + "-screen.png")
            assert qr.grab().save(str(image))
            row = dict(case=name, language=language, dark=dark, protocol=entry["protocol"],
                       ndef_hex=message.hex(), text=qr.symbol.text, version=qr.symbol.version,
                       modules=qr.symbol.total_modules, error=error, screen=image.name,
                       canvas_visible=True, size=list(qr.size().toTuple()), pixels_per_module=qr.canvas.scale())
            if language == "fr" and not dark:
                for kind in ("png", "svg"):
                    path = out / (name + "." + kind)
                    path.write_bytes(qr.file_data(kind))
                    row[kind] = path.name
            rows.append(row)
            qr.close()
            app.processEvents()
parent.close()
resource = Path(core.RESOURCE_DIR)
missing = {name: importlib.util.find_spec(name) is None for name in ("qrcode", "zxingcpp", "base45", "ndef")}
assert all(missing.values()), "QA oracle must not be shipped in the app"
assert not (resource / "tests").exists()
result = dict(frozen=True, offline=True, version=core.APP_VERSION, segno=segno.__version__,
              license_sha256=hashlib.sha256((resource / "data/licenses/Segno-LICENSE.txt").read_bytes()).hexdigest(),
              oracles_absent=missing, fixtures_absent=True, rows=rows)
(out / "frozen-ssqr1.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
