# Real interface captures — SpoolScribe v0.8.0

Generated on 5 November 2026 from the actual v0.8.0 application source. Application
modules/resources match the published v0.8.0 tag; only documentation/maintenance
files differ in this help follow-up. Python 3.12, PySide6/Qt 6.11.3, English,
application light palette, offscreen Qt rendering. No AI or composited controls.

The [manifest](captures.json) records version, checkout base, dimensions, SHA-256
and scenario metadata. Images with QR data carry their expected NDEF digest.
The public fixture catalogues are merged in memory and loaded into temporary user
folders. A Python audit hook blocks network requests. Counts are demonstration
data, not live source coverage. Lab values, device settings, CSV rows and update
statuses are synthetic examples, not instrument readings or real network results.

Every illustration in the current README/help has a short title and caption, and
is centred. Clicking opens the full-size file. Native OS file and print dialogs
vary by platform and are explained rather than passed off as universal screenshots.

| Capture | Demonstrated screen |
| --- | --- |
| [catalogue.png](catalogue.png) | list catalogue with selected Polymaker filament |
| [qr-transfer.png](qr-transfer.png) | Complete SSQR1 QR and digital PNG/SVG save actions |
| [collection.png](collection.png) | grid catalogue with selected Bambu Lab filament |
| [colour-search.png](colour-search.png) | PLA colour proximity with declared HEX and actual Delta E scores |
| [hardware.png](hardware.png) | Compose a real printer, reader and tag setup |
| [printers.png](printers.png) | Visual printer browser with photographs, search and compatibility categories |
| [catalogue-status.png](catalogue-status.png) | Local fixture catalogue status; no update performed |
| [update-report.png](update-report.png) | Example partial-update report using synthetic statuses, no live requests |
| [export-details.png](export-details.png) | Current NFC export readiness, capacity and next steps |
| [sources.png](sources.png) | Choose catalogue sources before any download |
| [settings-catalogue.png](settings-catalogue.png) | Settings: catalogue |
| [settings-spools.png](settings-spools.png) | Settings: spools |
| [settings-export.png](settings-export.png) | Settings: export |
| [settings-interface.png](settings-interface.png) | Settings: interface |
| [settings-colours.png](settings-colours.png) | Settings: colours |
| [favourites.png](favourites.png) | Saved filament favourites filter; clearing filters keeps the favourites |
| [filament-details.png](filament-details.png) | Selected filament values and their provenance |
| [personal-copy.png](personal-copy.png) | Personal copy editor; source reference stays unchanged |
| [colour-list.png](colour-list.png) | Contextual Delta E column, visible only during colour comparison |
| [columns-menu.png](columns-menu.png) | Column visibility choices rendered from the real menu without opening the native menu loop |
| [colour-lab.png](colour-lab.png) | Enter documented Lab D65/2 degree example values |
| [colour-saved.png](colour-saved.png) | Saved reference values, associations and backup actions |
| [device-preset.png](device-preset.png) | User-declared device entry preset, explicitly applied |
| [colour-paste.png](colour-paste.png) | Interpret labelled colour values copied from an application |
| [colour-import.png](colour-import.png) | Review file settings, columns and parsed rows before importing |
| [opentag-temperatures.png](opentag-temperatures.png) | Review OpenTag3D temperature proposals before explicit confirmation |
| [qr-companion.png](qr-companion.png) | Offline QR transfer, Companion availability and optional paper choices |
| [qr-details.png](qr-details.png) | QR technical cards, protection level and integrity digest |
| [qr-paper.png](qr-paper.png) | Optional print geometry and product reference; not a physical print test |
| [paper-references.png](paper-references.png) | A4 sheets and label rolls: commercial references and external templates |

## Reproduce

Run `python .github/scripts/render_readme_screenshots.py` in the documented build
environment, then visually inspect the results and check every manifest hash.
Modal dialogs are shown without committing their drafts. The column menu is
rendered from the actual widget without entering the native menu event loop.
The documented QR transfer is independently decoded; screenshot generation alone
does not establish physical phone/print/NFC or native-desktop acceptance.

## Artwork and animation

The animated logo `spoolscribe-animated.gif` is retained. It is a deterministic
export of `data/app/spoolscribe_logo_animated.svg` (75 frames, 3-second loop),
regenerated with `render_readme_logo.py`. No remote image dependency is added.

Source/mark credits: [data sources](../DATA_SOURCES.md), [trademarks](../TRADEMARKS.md),
[printer photographs](../PRINTER_VISUALS.md). Documentation captures and scan oracles
are excluded from application resources. No catalogue or personal data is bundled.
