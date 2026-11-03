"""Capture the current UI using public fixtures and temporary, offline settings."""
import json
import hashlib
import subprocess
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def offline(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError('README captures must stay offline')


def main():
    sys.addaudithook(offline)
    with tempfile.TemporaryDirectory(prefix='spoolscribe-readme-') as directory:
        os.environ['SPOOLSCRIBE_DATA_HOME'] = directory
        os.environ['SPOOLSCRIBE_CONFIG_PATH'] = str(Path(directory) / 'config.json')
        from spoolscribe import core, app_gui
        from scripts.catalogue_merge import merge_catalogue
        from PySide6.QtWidgets import QApplication, QAbstractItemView
        from PySide6.QtCore import QRect, QPoint
        from spoolscribe.ui_widgets import PrinterBrowser
        captures = []
        database = json.loads((ROOT / 'tests/fixtures/catalogues/polymaker_db.json').read_text(encoding='utf-8'))
        for name, source, rank in [('catalogue_ofd.json', 'Open Filament Database', 20),
                                   ('catalogue_spoolman.json', 'SpoolmanDB', 10)]:
            incoming = json.loads((ROOT / 'tests/fixtures/catalogues' / name).read_text(encoding='utf-8'))
            database, _ = merge_catalogue(database, incoming, source, rank)
        core.save_db(database)
        core.save_config(dict(core.DEFAULT_CONFIG, language='en', network_consent=False,
                              printer_profile='u1', printer_firmware='paxx12', nfc_tag_type='NTAG216',
                              colour_delta_max=10.0,
                              favorite_brands=['Polymaker', 'Bambu Lab', 'Prusament']))
        app = QApplication.instance() or QApplication([])
        app_gui.configure_application(app)
        with patch.object(app_gui.MainWindow, '_maybe_auto_update'):
            window = app_gui.MainWindow()
            try:
                window.resize(1480, 920)
                window.show()
                def capture(widget, filename, description, *, region=None, **metadata):
                    app.processEvents()
                    target = ROOT / 'docs/images' / filename
                    pixmap = widget.grab(region) if region is not None else widget.grab()
                    assert pixmap.save(str(target)), target
                    captures.append(dict(file=filename, description=description, version=core.APP_VERSION,
                                         width=pixmap.width(), height=pixmap.height(),
                                         sha256=hashlib.sha256(target.read_bytes()).hexdigest(), **metadata))
                    print(f'{filename}: {core.APP_VERSION}, {pixmap.width()}x{pixmap.height()}')

                for brand, view, filename in [('Polymaker', 'list', 'catalogue.png'),
                                               ('Bambu Lab', 'grid', 'collection.png')]:
                    window._reset_filters()
                    window._choose_brand(brand, remember=False)
                    index = window.material_filter.findData('PLA')
                    window.material_filter.setCurrentIndex(index)
                    window._set_view_mode(view)
                    candidates = [row for row in window._rows if row.get('hex') and row.get('hex_variants', 0) <= 1]
                    assert candidates, brand
                    choice = next((row for row in candidates if 'blue' in row.get('color_name', '').lower()), candidates[0])
                    window.current_sku = choice['sku']
                    window._show_detail(choice['sku'])
                    index = next(i for i, row in enumerate(window._rows) if row['sku'] == choice['sku'])
                    for widget in (window.table, window.grid):
                        previous = widget.blockSignals(True)
                        if widget is window.table:
                            widget.selectRow(index)
                        else:
                            widget.setCurrentRow(index)
                        widget.blockSignals(previous)
                    app.processEvents()
                    capture(window, filename, f'{view} catalogue with selected {brand} filament',
                            sku=choice['sku'], view=view)
                    if filename == 'catalogue.png':
                        assert window.btn_qr.isEnabled(), 'The genuine selected export must be available'
                        qr = window._open_qr()
                        assert qr is not None
                        qr.resize(660, 800)
                        capture(qr, 'qr-transfer.png', 'Complete SSQR1 QR and digital PNG/SVG save actions',
                                region=QRect(0, 0, qr.width(), qr.btn_png.mapTo(qr, QPoint(0, 0)).y() + qr.btn_png.height() + 12),
                                crop='Top of the real QR window through digital save actions; printing band omitted',
                                sku=qr.snap.sku, protocol='OpenSpool 1.0',
                                ndef_sha256=qr.snap.sha256)
                        qr.close()
                window._reset_filters()
                window.material_filter.setCurrentIndex(window.material_filter.findData('PLA'))
                window._set_view_mode('grid')
                window._start_colour_search('C8E6A0')
                assert window._colour_deltas, 'Colour ranking must actually be active'
                colour_choice = window._rows[0]
                window.current_sku = colour_choice['sku']
                window._show_detail(colour_choice['sku'])
                app.processEvents()
                capture(window, 'colour-search.png', 'PLA colour proximity with declared HEX and actual Delta E scores',
                        target_hex='C8E6A0', maximum_delta_e=core.colour_delta_limit(), results=len(window._rows))
                window._open_hardware()
                window.hardware_dialog.resize(780, 740)
                capture(window.hardware_dialog, 'hardware.png', 'Compose a real printer, reader and tag setup')
                browser = PrinterBrowser(window.printer, window.hardware_dialog)
                browser.show()
                browser.resize(840, 800)
                app.processEvents()
                browser.list.scrollToItem(browser.list.currentItem(), QAbstractItemView.PositionAtCenter)
                capture(browser, 'printers.png', 'Visual printer browser with photographs, search and compatibility categories')
                browser.close()
                window.hardware_dialog.close()
                manifest = dict(version=core.APP_VERSION,
                                source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                                language='en', theme='application light palette', network='blocked by Python audit hook',
                                provenance='public regression fixtures merged in memory, isolated temporary user/config folders',
                                captures=captures)
                (ROOT / 'docs/images/captures.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
            finally:
                window.close()


if __name__ == '__main__':
    main()
