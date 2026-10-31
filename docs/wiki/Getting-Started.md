# Getting Started

## 1. Install

### Option A — standalone app (no Python)

Download the build for your OS from the **[Releases](https://github.com/ArN-LaB/Spoolscribe-/releases)** page (produced by CI), unzip,
and run `SpoolScribe` (`.exe` on Windows, `.app` on macOS, binary on Linux).

### Option B — from source

```sh
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
python app_gui.py
```

## 2. First run

- First launch asks you to choose and authorize data sources, then downloads the catalogue. Later authorized launches refresh the selected sources; the local cache survives failures.
- Browse or search filaments by SKU, product, or color.
- Select a filament to see its details and color swatch.

## 3. Generate a tag payload

1. Select a SKU.
2. (Optional) Click **Inspect JSON** to review the [OpenSpool](https://github.com/spuder/OpenSpool) payload.
3. Click **Exporter pour NFC**. If HEX is missing, explicitly enter a representative color or cancel.
4. Use **Dossier d’export** to find the file. Both packaged and source apps use the per-user data directory, outside the application.
5. For a readable archive, use the **⋯** menu. No physical tag is written by SpoolScribe.

Next: [[Writing RFID Tags|Writing-RFID-Tags]].


## Universal catalogue (v0.3.0 development)

The repository regression fixture contains 24,521 references across 174 brand
labels; it is not bundled. The live catalogue depends on selected sources. Use the manufacturer/material/completeness filters together with the
search box. Click a column header for ascending/descending order; right-click
for primary/secondary sorting and visible columns. Both views
show 250 results per page, while filters/search operate on the entire catalogue.

Internal OFD/SMDB references are distinct from a manufacturer SKU. Unknown
physical data can be filled using **Compléter / corriger les caractéristiques…**;
these edits affect the product's variants and are preserved during updates.
Logos are local reviewed assets; a readable manufacturer name replaces an
unsuitable or unavailable image.

Choose **NTAG215** or **NTAG216** before export. Complete exports retain metadata;
the automatic choice uses the essential profile when required, omitting descriptives/logos while preserving printing
values and colors. The inspector shows the exact exported JSON. See the
[NFC guide](Writing-RFID-Tags.md), [data contract](../DATA_FORMAT.md) and
[roadmap](../ROADMAP.md). These development changes are not a published v0.3.0 release.

The latest interaction and printer guidance is in [UX v0.3.0](../UX-v0.3.0.md).
Settings persist; logos have no added rectangular plate; the automatic NFC profile
chooses what fits. Technical overrides are under **Réglages avancés**.
