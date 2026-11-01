# Development and command-line use

[Back to SpoolScribe](../README.md) · [Contributor guide](../.github/CONTRIBUTING.md)

Run commands from the repository root. Use Python 3.10+ for source use and
Python 3.12 with the recorded dependency set for packaging.

## Run from source

```sh
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt

python app_gui.py          # graphical app
python convert_profile.py  # terminal app
```

## Build a standalone app

One PyInstaller spec builds all three systems (run it on the target OS):

```sh
python -m pip install -r requirements-build.txt  # pinned Python 3.12 build set
python -B -m unittest discover -s tests -t . -v
pyinstaller spoolscribe.spec --noconfirm
```

Output lands in `dist/`: a **single file** on Windows (`SpoolScribe.exe`) and Linux
(`SpoolScribe`), and a regular **`SpoolScribe.app` bundle** on macOS (one-directory layout
under `Contents/`, which starts faster than a self-extracting file and avoids the deprecated onefile-plus-bundle layout). CI in [`.github/workflows/build.yml`](../.github/workflows/build.yml) runs the
offline tests on four configurations, builds the three archives, checks them and attaches
them with SHA-256 checksums to a GitHub Release when a `v*` tag is pushed.

## Tests and local data

For a personal macOS installation with provenance checks, backups and an interactive
approval, use [the shared local installer](LOCAL_MACOS_INSTALL.md). It is developer
tooling, excluded from the distributed app, and leaves Gatekeeper enabled.

```sh
python -B -m unittest discover -s tests -t . -v
```

Core tests need Python 3.10+ and `certifi`; GUI tests need PySide6 and are skipped
otherwise. Tests block network access, use temporary data folders and never touch a
printer or a personal Spoolman server. The repository snapshots in `data/`
(`polymaker_db.json`, `catalogue_ofd.json`, `catalogue_spoolman.json`) are regression
fixtures, excluded from installers; `data/catalogue_*_audit.json` record their counts and
hashes. The 1,008 historical Polymaker exports are checked byte for byte
(`tests/fixtures/legacy_catalogue_contract.json`).

Database writes are validated and atomic; the previous revision is kept in
`polymaker_db.json.bak` and a full update also keeps `polymaker_db.json.pre-update.bak`.
`python convert_profile.py --restore-db [backup]` restores explicitly; the packaged GUI
offers restoration when its database is unreadable. See
[docs/DATA_FORMAT.md](DATA_FORMAT.md).


## Project layout

| Path | Role |
|---|---|
| `core.py` | Pure business logic (no terminal I/O), shared by CLI and GUI. |
| `app_gui.py`, `ui_catalogue.py` | PySide6 interface and saved catalogue workspace. |
| `printer_profiles.py`, `data/printers.json` | Printers and readers (reader technology, firmwares, "reads OpenSpool" flag, field guidance); the JSON can be refreshed from the repository into the user folder. |
| `packaging_rules.py` | Which resources go into installers (code, artwork, licences; never a catalogue). |
| `convert_profile.py` | Command-line interface. |
| `scripts/` | Source adapters and update workers (standard library only), plus legacy scrapers kept for reference. |
| `.github/scripts/` | Offline snapshot preparation, logo import with transparent background (`import_brand_logos.py`) and packaged-build checks. |
| `data/` | Regression snapshots, audit reports, reviewed logos (`brand_logos/manifest.json`, checked by `tests/test_logos.py`), printer list and licences. |
| `orca_profiles/` | Official [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) OrcaSlicer profiles for the Snapmaker U1 (temperature overrides). |
| `docs/` | Documentation; `docs/archive/` holds superseded validation reports. |


## UI languages

The v0.3.5 interface uses [bundled translations](../translations/README.md). Add display text with `i18n.tr`, keeping catalogue identities and payloads outside translation. The standard test suite checks locale fallback, placeholders, language persistence and crossed manufacturer/material filters. The existing frozen-app probe now renders all four languages.
