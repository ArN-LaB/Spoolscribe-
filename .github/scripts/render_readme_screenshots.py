"""Capture the current UI using public fixtures and temporary, offline settings."""
import json
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
        from PySide6.QtWidgets import QApplication
        database = json.loads((ROOT / 'tests/fixtures/catalogues/polymaker_db.json').read_text(encoding='utf-8'))
        for name, source, rank in [('catalogue_ofd.json', 'Open Filament Database', 20),
                                   ('catalogue_spoolman.json', 'SpoolmanDB', 10)]:
            incoming = json.loads((ROOT / 'tests/fixtures/catalogues' / name).read_text(encoding='utf-8'))
            database, _ = merge_catalogue(database, incoming, source, rank)
        core.save_db(database)
        core.save_config(dict(core.DEFAULT_CONFIG, language='en', network_consent=False,
                              printer='u1', printer_firmware='paxx12', nfc_tag_type='NTAG216',
                              favorite_brands=['Polymaker', 'Bambu Lab', 'Prusament']))
        app = QApplication.instance() or QApplication([])
        app_gui.configure_application(app)
        with patch.object(app_gui.MainWindow, '_maybe_auto_update'):
            window = app_gui.MainWindow()
            try:
                window.resize(1480, 920)
                window.show()
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
                    target = ROOT / 'docs/images' / filename
                    assert window.grab().save(str(target)), target
                    print(f'{filename}: {core.APP_VERSION}, {brand}, {choice["sku"]}, 1480x920')
            finally:
                window.close()


if __name__ == '__main__':
    main()
