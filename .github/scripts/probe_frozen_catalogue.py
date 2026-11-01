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
from spoolscribe import core
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
    assert core.logo_abs_path(db, item['name']), f"Bundled logo path rejected: {item['name']}"
# Render in the real frozen resource layout, not only the source checkout.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QRectF
app = QApplication.instance() or QApplication([])
rendered = []
for brand in ('Polymaker', 'Prusament', 'ROSA3D'):
    path = core.logo_abs_path(db, brand)
    if path.lower().endswith('.svg'):
        renderer = QSvgRenderer(path)
        assert renderer.isValid(), f"Invalid SVG: {brand}"
        pixmap = QPixmap(216, 96);pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap);renderer.render(painter,QRectF(0,0,216,96));painter.end()
    else:
        pixmap = QPixmap(path).scaled(216,96,Qt.KeepAspectRatio,Qt.SmoothTransformation)
    pixmap.setDevicePixelRatio(2.0)
    assert not pixmap.isNull(), f"Logo not rendered: {brand}"
    assert any(pixmap.toImage().pixelColor(x,y).alpha() for x in range(pixmap.width()) for y in range(pixmap.height())), brand
    assert pixmap.deviceIndependentSize().width() <= 108
    rendered.append(brand)
from spoolscribe.printer_presentations import presentation
from spoolscribe import printer_profiles
photo_manifest=json.loads((Path(core.RESOURCE_DIR)/'data/printer_photos/manifest.json').read_text())
for key,info in photo_manifest.items():
    path=Path(core.RESOURCE_DIR)/'data/printer_photos'/info['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==info['sha256']
    assert not QPixmap(str(path)).isNull(), f'Printer photo not decoded: {key}'
    assert presentation(printer_profiles.PROFILES[key]).get('photo')
from spoolscribe.ui_widgets import spool_icon
assert not spool_icon('008899',112,2).isNull()
assert not spool_icon(None,112,2).isNull()
# Construct the actual UI from the frozen imports, with synthetic data only.
# No startup consent dialog or source refresh can run in this smoke check.
core.save_config(dict(core.load_config(),network_consent=False,printer_firmware='paxx12'))
# PyInstaller's entry script is __main__, not an importable app_gui module;
# runpy temporarily owns __main__ here. Use the entry frame already on the stack.
entry_frame = sys._getframe()
while entry_frame is not None and 'MainWindow' not in entry_frame.f_globals:
    entry_frame = entry_frame.f_back
assert entry_frame is not None, 'Frozen entry point not found'
entry_frame.f_globals['configure_application'](app)
window_class = entry_frame.f_globals['MainWindow']
del entry_frame
from spoolscribe import i18n
languages=[]
for code in ('auto',*i18n.LANGUAGES):
    settings=core.load_config();settings['language']=code;core.save_config(settings)
    window=window_class()
    try:
        window.resize(1100,800)
        window.show()
        window._show_detail('TEST')
        app.processEvents()
        assert window.isVisible() and window.current_sku == 'TEST'
        assert window.btn_generate.isEnabled(), 'Fixture export must be available'
        assert window.update_btn.text() == i18n.tr('Actualiser le catalogue')
        assert not window.grab().isNull(), 'Frozen UI must render'
        if code=='auto':
            expected=i18n.resolve_language('auto',i18n.system_ui_languages())
            assert i18n.language()==expected
            automatic_language=expected
        else:
            assert i18n.language() == code
            languages.append(code)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
result = {"version": core.APP_VERSION, "empty_first_install": True, "fixture_references": len(db["_skus"]),
          "approved_new_logos": len(manifest), "rendered_logos": rendered,
          "printer_photos":len(photo_manifest),"spool_artwork":True,"main_window_rendered":True,
          "automatic_language":automatic_language,"interface_languages":languages,"tag_exports": list(core.NFC_CAPACITIES), "offline": True}
Path(os.environ["SPOOLSCRIBE_CATALOGUE_REPORT"]).write_text(json.dumps(result), encoding="utf-8")
