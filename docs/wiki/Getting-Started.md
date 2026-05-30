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

- The app opens **offline**. No network call happens on startup.
- Browse or search filaments by SKU, product, or color.
- Select a filament to see its details and color swatch.

## 3. Generate a tag payload

1. Select a SKU.
2. (Optional) Click **Inspect JSON** to review the [OpenSpool](https://github.com/spuder/OpenSpool) payload.
3. Click **Generate NFC JSON**. The file is written to the `output/` folder.

Next: [[Writing RFID Tags|Writing-RFID-Tags]].
