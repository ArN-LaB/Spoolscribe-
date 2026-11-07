"""Capture the current UI using public fixtures and temporary, offline settings."""
import json
import hashlib
import subprocess
import os
from pathlib import Path
import sys
import tempfile
import time
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
        from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QFileDialog, QLineEdit, QInputDialog, QMenu
        from PySide6.QtCore import QRect, QPoint
        from spoolscribe.ui_widgets import PrinterBrowser
        from spoolscribe.ui_surfaces import fit_dialog, ReadingTabs
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
                    for _ in range(6):
                        app.processEvents(); time.sleep(.02)
                    target = ROOT / 'docs/images' / filename
                    pixmap = widget.grab(region) if region is not None else widget.grab()
                    assert pixmap.save(str(target)), target
                    captures.append(dict(file=filename, description=description, version=core.APP_VERSION,
                                         width=pixmap.width(), height=pixmap.height(),
                                         sha256=hashlib.sha256(target.read_bytes()).hexdigest(), **metadata))
                    print(f'{filename}: {core.APP_VERSION}, {pixmap.width()}x{pixmap.height()}', flush=True)

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
                # Help screenshots: the actual widgets, with public/synthetic demo values.
                # No successful network update, physical measurement or NFC write is staged.
                def modal_capture(action, callback):
                    def review(dialog):
                        dialog.show(); app.processEvents()
                        fit_dialog(dialog, preferred_width=820, available=QRect(0, 0, 1600, 1120))
                        callback(dialog)
                        dialog.reject()
                        return QDialog.Rejected
                    with patch.object(QDialog, 'exec', new=review): action()

                modal_capture(window._database_details, lambda d: capture(d, 'catalogue-status.png', 'Local fixture catalogue status; no update performed'))
                stats = window._snapshot_stats()
                results = [core.StepResult('Polymaker officiel', True, status='unchanged'), core.StepResult('Catalogue multi-fabricants OFD', False, stderr='Demonstration: source temporarily unavailable.', status='unavailable')]
                previous_dialogs = set(window.findChildren(QDialog))
                window._show_sync_report(results, stats, stats)
                report = next(d for d in window.findChildren(QDialog) if d not in previous_dialogs and d.isVisible())
                capture(report, 'update-report.png', 'Example partial-update report using synthetic statuses, no live requests', source_results='synthetic demonstration, not an executed network update')
                report.close()
                window._open_export_explanation()
                capture(window.export_details, 'export-details.png', 'Current NFC export readiness, capacity and next steps')
                window.export_details.close()
                modal_capture(window._choose_sources, lambda d: capture(d, 'sources.png', 'Choose catalogue sources before any download', network_action='none'))
                def settings_pages(dialog):
                    tabs = dialog.findChild(ReadingTabs)
                    for index, name in enumerate(('catalogue', 'spools', 'export', 'colours', 'interface', 'backups')):
                        tabs.setCurrentIndex(index); app.processEvents()
                        fit_dialog(dialog, preferred_width=860, available=QRect(0, 0, 1600, 1120))
                        if name == 'export':
                            # A documentation-only empty draft; nothing is saved.
                            for field in dialog.findChildren(QLineEdit):
                                if field.text().startswith(directory): field.setText('')
                        capture(dialog, 'settings-' + name + '.png', 'Settings: ' + name)
                modal_capture(window._open_settings, settings_pages)
                window._stop_colour_search(); window._reset_filters(); window._choose_brand('Polymaker', remember=False)
                choice = next(row for row in window._rows if row.get('hex') and row.get('hex_variants', 0) <= 1 and row.get('material') == 'PLA' and row.get('color_name') == 'Aqua Blue')
                window.current_sku = choice['sku']; window._show_detail(choice['sku'])
                window._toggle_filament_favorite(choice['sku']); window.favorites_only.setChecked(True)
                window._set_view_mode('grid')
                capture(window, 'favourites.png', 'Saved filament favourites filter; clearing filters keeps the favourites')
                window.favorites_only.setChecked(False)
                window.resize(1580, 1020); window.splitter.setSizes([250, 550, 780]); app.processEvents()
                window.provenance_toggle.setChecked(True)
                capture(window.comparison_card, 'filament-details.png', 'Selected filament values and their provenance')
                window.provenance_toggle.setChecked(False); window._edit_physical()
                capture(window.draft_editor, 'personal-copy.png', 'Personal copy editor; source reference stays unchanged', write_action='none')
                window._cancel_draft()
                window.resize(1480, 920)
                window._start_colour_search('C8E6A0'); window._set_view_mode('list')
                capture(window, 'colour-list.png', 'Contextual Delta E column, visible only during colour comparison')
                menu = QMenu(window); window._add_column_choices(menu)
                menu.ensurePolished(); menu.resize(menu.sizeHint())
                capture(menu, 'columns-menu.png', 'Column visibility choices rendered from the real menu without opening the native menu loop')
                menu.deleteLater()
                window._stop_colour_search()
                measure = window._open_measurements(); measure.space.setCurrentIndex(measure.space.findData('CIELAB'))
                for key, value in [('L', '73.2'), ('a', '-25.6'), ('b', '-12.4')]: measure.lab_edits[key].setText(value)
                measure.illuminant.setCurrentIndex(measure.illuminant.findData('D65')); measure.observer.setCurrentIndex(measure.observer.findData(2))
                fit_dialog(measure, preferred_width=860, available=QRect(0, 0, 1600, 1120))
                capture(measure, 'colour-lab.png', 'Enter documented Lab D65/2 degree example values', measurement='synthetic example, not an instrument reading')
                measure.btn_save.click(); measure.tabs.setCurrentIndex(3); app.processEvents()
                capture(measure, 'colour-saved.png', 'Saved reference values, associations and backup actions', measurement='synthetic local entry')
                measure.tabs.setCurrentIndex(0); measure.details_toggle.setChecked(True)
                measure.device_manufacturer.setText('Example'); measure.device_model.setText('Demo meter')
                with patch.object(QInputDialog, 'getText', return_value=('My device settings', True)): measure.btn_profile_save.click()
                measure.tabs.currentWidget().ensureWidgetVisible(measure.device_profile, 0, 120)
                capture(measure, 'device-preset.png', 'User-declared device entry preset, explicitly applied', device='synthetic example, not a supported hardware claim')
                measure.close(); measure.deleteLater(); window.measurement_window = None
                measure = window._open_measurements(); measure.tabs.setCurrentIndex(1)
                measure.paste_edit.setPlainText('HEX #74CABF RGB 116 202 191'); measure.btn_interpret.click(); measure.paste_candidates.setCurrentRow(0)
                fit_dialog(measure, preferred_width=860, available=QRect(0, 0, 1600, 1120))
                capture(measure, 'colour-paste.png', 'Interpret labelled colour values copied from an application')
                measure.tabs.setCurrentIndex(2)
                csv = Path(directory) / 'example-colours.csv'
                csv.write_text('Name;HEX\nTeal sample;74CABF\nBlue sample;2274D3\n', encoding='utf-8')
                with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(csv), 'CSV')): measure._choose_file()
                measure._check_rows()
                fit_dialog(measure, preferred_width=900, available=QRect(0, 0, 1600, 1120))
                capture(measure, 'colour-import.png', 'Review file settings, columns and parsed rows before importing', input_file='synthetic CSV, not a personal file')
                measure.close()
                window._reset_filters(); window._choose_brand('Polymaker', remember=False)
                window.current_sku = choice['sku']; window._show_detail(choice['sku'])
                window.printer.setCurrentIndex(window.printer.findData('opentag3d'))
                modal_capture(window._complete_opentag_settings, lambda d: capture(d, 'opentag-temperatures.png', 'Review OpenTag3D temperature proposals before explicit confirmation', confirmed=False))
                window.printer.setCurrentIndex(window.printer.findData('u1')); window.firmware.setCurrentIndex(window.firmware.findData('paxx12'))
                qr = window._open_qr(); assert qr is not None
                fit_dialog(qr, preferred_width=720, available=QRect(0, 0, 1600, 1260))
                capture(qr, 'qr-companion.png', 'Offline QR transfer, Companion availability and optional paper choices', ndef_sha256=qr.snap.sha256)
                qr.details_toggle.setChecked(True)
                fit_dialog(qr, preferred_width=820, available=QRect(0, 0, 1600, 1260))
                capture(qr, 'qr-details.png', 'QR technical cards, protection level and integrity digest', ndef_sha256=qr.snap.sha256)
                qr.details_toggle.setChecked(False); qr.support.setCurrentIndex(qr.support.findData('label-62x100'))
                fit_dialog(qr, preferred_width=720, available=QRect(0, 0, 1600, 1260))
                capture(qr, 'qr-paper.png', 'Optional print geometry and product reference; not a physical print test', ndef_sha256=qr.snap.sha256)
                qr._paper_help(); qr._paper_guide.tabs.setCurrentIndex(1)
                capture(qr._paper_guide, 'paper-references.png', 'A4 sheets and label rolls: commercial references and external templates')
                qr._paper_guide.close(); qr.close()
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
