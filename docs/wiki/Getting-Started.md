# Getting Started

Four steps: install, download the catalogue, describe your hardware, export a tag.

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
the hosts they use; tick the ones you want and click **Synchroniser maintenant**.
This records your consent and downloads the data into your user folder
(`%APPDATA%\SpoolScribe`, `~/Library/Application Support/SpoolScribe` or
`~/.config/SpoolScribe`). A report window then summarises what was added.

Later launches refresh the selected sources once a day by default (change the
cadence in **⚙ → Paramètres**); **Synchroniser** (Ctrl+U) forces a refresh at
any time, and **Annuler** stops one. Offline, the cached catalogue stays usable.
See [[Updating the Database|Updating-the-Database]].

Then browse: the sidebar lists manufacturers (recent ones pinned at the top; a
field filters the list), material families and data states; the search box
(Ctrl+F) matches product, colour, reference, manufacturer and material; a column
header click sorts (second click reverses, Shift-click or right-click adds a
secondary sort). Each row is one filament; its spool sizes are listed in the
card. Select a row to open its card.

## 3. Describe your hardware, once

**⚙ → Mon matériel** (or **Modifier…** in the card) asks for the printer or
reader that will read the tag, its firmware when several exist, and the tag you
bought (**Étiquette achetée**: NTAG216 or NTAG215). The list says, per
firmware, whether the machine reads an OpenSpool tag at all — a Snapmaker U1
does so with the paxx12 firmware, not with the stock one; Bambu AMS, Prusa
OpenPrintTag, Creality CFS and the like never do (see
[[Printers and Readers|Printers-and-Readers]]). The recommended *essential*
profile fits every reference on both chips; the *full* profile and the writer
reserve are under **Réglages avancés**. **Définir par défaut** keeps the tag
choice for later launches. The card then shows a one-line summary
(*Pour : …*).

## 4. Export a tag payload

1. Select a filament. The card shows its colour, temperatures, diameter,
   density, the references of every packaging and the data state. Fill in
   missing values with **Corriger…** if needed; values flagged *À vérifier* must
   be confirmed before export.
2. (Optional) **Inspecter le JSON** shows the exact bytes that will be exported.
3. Click **Exporter pour NFC** (Ctrl+E). If the colour is unknown, enter a
   representative HEX or cancel. **Dossier d'export** opens the output folder.
4. Write the JSON onto the tag with a separate writer (for example SpoolFlux),
   read the tag back, and check what the printer reports. SpoolScribe never
   writes a tag itself. See [[Writing RFID Tags|Writing-RFID-Tags]].

When the chosen hardware cannot read an OpenSpool tag, the tag controls are
hidden and the card is a reference sheet for your slicer profile; no proprietary
RFID tag or OpenPrintTag is generated.
