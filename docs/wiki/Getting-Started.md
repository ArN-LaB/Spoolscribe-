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

- The app opens **offline**. A fresh install makes no network call; later startup updates need saved consent and a separate opt-in.
- Browse or search filaments by SKU, product, or color.
- Select a filament to see its details and color swatch.

## 3. Generate a tag payload

1. Select a SKU.
2. (Optional) Click **Inspect JSON** to review the [OpenSpool](https://github.com/spuder/OpenSpool) payload.
3. Click **Exporter pour NFC**. If HEX is missing, explicitly enter a representative color or cancel.
4. Use **Dossier d’export** to find the file. The packaged app uses its per-user data directory; source mode uses the repository `output/` folder.
5. For a readable archive, use the **⋯** menu. No physical tag is written by SpoolScribe.

Next: [[Writing RFID Tags|Writing-RFID-Tags]].
