# Getting Started

Three steps: install, download the catalogue, export a tag.

## 1. Install

### Option A — standalone app (no Python)

Download the archive for your system from the
**[Releases](https://github.com/ArN-LaB/Spoolscribe-/releases)** page and unzip it:
`SpoolScribe.exe` (Windows), `SpoolScribe.app` (macOS, Apple Silicon only) or the
`SpoolScribe` binary (Linux, recent glibc). Each archive has a `.sha256` file to
verify the download.

The binaries are not code-signed:

- **Windows** — SmartScreen shows *"Windows protected your PC"*: click **More
  info** → **Run anyway**.
- **macOS** — Gatekeeper blocks the first launch: right-click the app → **Open**
  → **Open**, or run `xattr -dr com.apple.quarantine SpoolScribe.app` once.

### Option B — from source

```sh
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
python app_gui.py
```

## 2. First run: download the catalogue

The app starts empty. The **Sources du catalogue** dialog lists the sources and
the hosts they use; tick the ones you want and click **Télécharger et enregistrer**.
This records your consent and downloads the data into your user folder
(`%APPDATA%\SpoolScribe`, `~/Library/Application Support/SpoolScribe` or
`~/.config/SpoolScribe`).

Later launches refresh the selected sources once a day by default (change the
cadence in **⋯ → Paramètres**); **Mettre à jour** forces a refresh at any time,
and **Annuler** stops one. Offline, the cached catalogue stays usable. See
[[Updating the Database|Updating-the-Database]].

Then browse: type in the search box (Ctrl+F), filter by manufacturer, material
or data state, click a column header to sort (second click reverses, Shift-click
or right-click adds a secondary sort), and select a row to open its card.

## 3. Export a tag payload

1. Select a reference. The card shows its colour, temperatures, diameter,
   density and the data state. Fill in missing values with **Compléter /
   corriger les caractéristiques…** if needed; values flagged *À vérifier* must
   be confirmed before export.
2. Choose your printer/reader (**Utiliser ce filament avec**) and the tag you
   bought (**Étiquette achetée**: NTAG216 or NTAG215). The recommended
   *essential* profile fits every reference on both chips; the *full* profile is
   under **Réglages avancés**.
3. (Optional) **Inspecter le JSON** shows the exact bytes that will be exported.
4. Click **Exporter pour NFC** (Ctrl+E). If the colour is unknown, enter a
   representative HEX or cancel. **Dossier d'export** opens the output folder.
5. Write the JSON onto the tag with a separate writer (for example SpoolFlux),
   read the tag back, and check what the printer reports. SpoolScribe never
   writes a tag itself. See [[Writing RFID Tags|Writing-RFID-Tags]].

For Bambu Lab and Prusa printers the card is a reference sheet for your slicer
profile; no proprietary RFID tag or OpenPrintTag is generated.
