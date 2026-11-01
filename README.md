<p align="center">
  <img src="data/spoolscribe_logo_animated.svg" alt="SpoolScribe" width="128" height="128">
</p>

<h1 align="center">SpoolScribe</h1>

<p align="center">
  <a href="https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml"><img src="https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml/badge.svg" alt="Build multiplatform"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/status-for%20fun%20%C2%B7%20free%20time-blueviolet" alt="Status: for fun">
</p>

> Prepare [OpenSpool](https://github.com/spuder/OpenSpool) data for NFC spool tags, so a printer with an
> OpenSpool-capable reader — such as the **[Snapmaker U1](https://snapmaker.com/snapmaker-u1)** with the
> [paxx12 firmware fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) — recognizes the
> filament loaded from a [PolyDryer](https://polymaker.com/product/polydryer/) + [PolyBox](https://polymaker.com/product/polybox/)
> or an AMS-style feeder.

**SpoolScribe** is a small desktop app (Windows / macOS / Linux) with a CLI. It downloads a
multi-manufacturer filament catalogue from public sources, shows each reference's colour,
temperatures, diameter and density, and generates the **OpenSpool JSON payload** that a
separate writer (for example [SpoolFlux](https://spoolflux.dingdongclick.de/?lang=us)) programs
onto an **NTAG215 or NTAG216** tag.

Made by [@ArN-LaB](https://github.com/ArN-LaB) — a **for-fun, free-time** hobby project.
It is **not affiliated with any filament manufacturer or with Snapmaker**; see
[docs/TRADEMARKS.md](docs/TRADEMARKS.md).

## Quick start

1. **Download** the archive for your system from the
   [Releases](https://github.com/ArN-LaB/Spoolscribe-/releases) page, unzip it and open
   SpoolScribe. The binaries are not code-signed: see [Windows SmartScreen](#windows-unknown-publisher--smartscreen)
   and [macOS Gatekeeper](#macos-gatekeeper) below.
2. **First launch**: choose the data sources you want and click *Synchroniser maintenant*.
   The installer contains no catalogue; the download builds it in your user folder. Later
   launches refresh it once a day by default.
3. **Tell it what you own**, once: *⚙ → Mon matériel* (my hardware) — your printer or
   reader, its firmware when that matters (a stock Snapmaker U1 does not read OpenSpool, the
   paxx12 firmware does) and the tag you bought (NTAG216 or NTAG215).
4. **Export a tag**: pick a filament in the list, then *Exporter pour NFC*. Write the JSON
   file with SpoolFlux (or another NDEF writer), read the tag back, and check that the printer
   shows the expected brand, material and colour.

## Status

v0.3.0 is in development on the `feature/universal-catalogue` branch. The published stable
release is [v0.2.2](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.2.2).
The 31 October 2026 audit, the review on real data of 1 November 2026 and their fixes are
recorded in [docs/VALIDATION-RETOURS-v0.3.0.md](docs/VALIDATION-RETOURS-v0.3.0.md) (latest screen feedback) and [docs/VALIDATION-AUDIT-v0.3.0.md](docs/VALIDATION-AUDIT-v0.3.0.md) (test build)
and in [CHANGELOG.md](CHANGELOG.md); earlier reports are in [docs/archive/](docs/archive/).

## Download

Each release ships three archives with a SHA-256 checksum file next to each one:

| Archive | Content | Notes |
|---|---|---|
| `SpoolScribe-windows.zip` | `SpoolScribe.exe`, single file | Windows 10/11, x64 |
| `SpoolScribe-macos.zip` | `SpoolScribe.app` bundle | **Apple Silicon (arm64) only**; built on `macos-latest` |
| `SpoolScribe-linux.zip` | `SpoolScribe`, single file | Built on `ubuntu-latest`; needs a recent glibc and Qt runtime libraries (`libegl1`, `libxkbcommon0`, `libdbus-1-3`) |

Verify a download before running it:

```sh
shasum -a 256 SpoolScribe-macos.zip      # macOS / Linux: sha256sum
Get-FileHash .\SpoolScribe-windows.zip -Algorithm SHA256   # Windows PowerShell
```

The database, settings and exports live in your user folder, not next to the application:
`%APPDATA%\SpoolScribe` (Windows), `~/Library/Application Support/SpoolScribe` (macOS),
`~/.config/SpoolScribe` (Linux).

### macOS Gatekeeper

The `.app` has an ad-hoc signature, not a Developer ID, so macOS blocks the first launch.
Either right-click (Control-click) the app and choose **Open**, then **Open** again in the
dialog, or remove the quarantine attribute once:

```sh
xattr -dr com.apple.quarantine SpoolScribe.app
```

### Windows: "Unknown publisher" / SmartScreen

SpoolScribe is **free, open-source software** and the binaries are **not code-signed**
(a signing certificate costs money this hobby project doesn't spend). Windows SmartScreen
may show a blue *"Windows protected your PC"* prompt the first time you run it. This is
expected for any unsigned app — it is **not** a virus warning. Click **More info** →
**Run anyway**, or verify the SHA-256 first. The executable embeds version metadata, so its
**Properties → Details** show *SpoolScribe* by *ArN-LaB*. Prefer not to trust a binary?
Run from source (below).

## Features

- Catalogue downloaded from selected public sources: Open Filament Database, SpoolmanDB,
  Polymaker, Bambu Lab (Bambu Studio profiles) and SUNLU, about 24,000 references from
  170+ manufacturers. Nothing is bundled; nothing is contacted without your consent.
- Manufacturer values outrank community values and also correct records of unknown origin
  (older installations); your own corrections outrank everything and survive every refresh.
  Uncertain cross-source matches are held aside, never merged.
- One row per filament: the spool sizes, refills and diameters of the same manufacturer,
  product and colour are grouped, and the card lists each reference with its state. Product
  lines listed as brands by some sources (PolyLite, Panchroma, Fiberon, PrimaSelect…) are
  shown under their manufacturer.
- Values that contradict themselves (a black HEX for "White", a 7.2 g/cm³ density…) are
  flagged **to be checked** (« À vérifier ») and cannot reach a tag until you confirm them.
- Refresh cadence of your choice (every launch, daily, weekly, manual); sources answer
  "not modified" when nothing changed; a running refresh can be cancelled.
- Sidebar with manufacturers (explicit favorites pinned), material families and data state
  (« État des données »), plus search, two-level sorting from the column headers, a column
  chooser, list and grid views and 250 rows per page.
- Manufacturer logos with a transparent background (checked by a test), a name fallback and
  light/dark themes.
- A data-driven list of printers and readers (`data/printers.json`, refreshable from the
  repository) says, per firmware, whether the machine reads an OpenSpool tag at all. No Bambu
  RFID, Creality/Anycubic/QIDI tag or OpenPrintTag is generated; see
  [Printers and readers](docs/wiki/Printers-and-Readers.md).
- NTAG215 / NTAG216 capacity check with the exact NDEF framing; the inspector shows the
  byte-identical JSON that will be exported.
- Explicit local editing of temperatures, diameter, density and colour; atomic saves,
  backups and restore.
- Persistent workspace (filters, columns, layout, printer, tag), settings import/export,
  keyboard shortcuts (Ctrl+F search, Ctrl+E export, Ctrl+U synchronise, Esc deselect).
- A synchronisation report (references, ready filaments, manufacturers, conserved values,
  pending matches, result per source) after every manual refresh.
- Release check on demand only (*⚙ → Vérifier une mise à jour de l'application*).

Internal `OFD-…` / `SMDB-…` identifiers name source records; they are **not manufacturer
SKUs**. The optional *Référence* column shows the manufacturer article number when the
source provides one (`+n` when several packagings share it) and `n cond.` otherwise; the
card lists source details behind **Détails et sources**. Select the exact packaging in the card before exporting; conflicting hues require an explicit choice.

### Interface

The catalogue toolbar contains the **list/grid** switch and column controls.
The grid shows a spool, actual product name, colour, diameter and favorite star.
The filament card uses the selected source HEX for its spool illustration; unknown
or conflicting colours stay neutral until an explicit choice is made. No artwork
writes or invents catalogue values.

Manufacturer favorite stars appear on hover; saved favorites retain their star.
Matching **Fabricants** and **Filaments** buttons in the Favorites row filter saved
favorites. **Effacer**
clears searches, filters and selection while retaining both favorite lists.

The card groups nozzle/bed temperatures, diameter and density into four tiles.
**Détails et sources** expands provenance. Its footer has a full-width NFC export
button with **Voir le JSON** and **Dossier d’export** visible underneath. Shared
control heights and content edges keep the main commands aligned.

**Paramètres → Bobines** stores a preferred spool weight (initially 1 kg) and
spool/refill preference. Selection uses existing source references only, falls
back visibly when a weight is unavailable, and never resolves conflicting hues.
A manual packaging choice wins for that group during the session.

**Synchroniser** uses saved sources after consent. **Paramètres → Catalogue**
contains source selection and refresh cadence. Source details expand on demand.
**Mon matériel** offers searchable printer names, concise documented descriptions
and reviewed manufacturer images for U1, X1 Carbon and QIDI Plus4; other entries
stay textual. Compatibility checks and firmware questions remain mandatory.
See the [French UX guide](docs/UX-v0.3.0.md) and
[printer visual sources](docs/PRINTER_VISUALS.md).

### Writing NTAG215 or NTAG216 tags

SpoolScribe generates the data; a separate writer, such as
[SpoolFlux](https://spoolflux.dingdongclick.de/?lang=us), writes the physical tag.
The chip choice changes the capacity check, not the OpenSpool 1.0 protocol.

| Chip | User memory | Standard CC-declared NDEF area |
|---|---:|---:|
| NTAG215 | 504 bytes | 496 bytes |
| NTAG216 | 888 bytes | 872 bytes |

These are the [NXP documented capacities](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf).
The estimate counts the UTF-8 JSON, one MIME `application/json` NDEF record and the Type 2
TLV/terminator.

The recommended profile is **essential**: protocol, type, brand, colour (HEX, optional
alpha and additional colours), nozzle and bed ranges, diameter, density and subtype —
everything a reader uses. It fits every reference on an NTAG215. The **full** profile adds
the SKU, product and colour names and brand metadata (website, logo URL); it is an explicit
choice under *Réglages avancés* (advanced settings) or with `--nfc-profile full`. Unknown
metadata is omitted, never written as `null`. Nothing is silently truncated; oversized
exports are refused before writing.

The tag, profile and reserve you pick apply to the current session. Click
**Définir par défaut** (set as default) next to the tag selector to keep them for later
exports and launches; the CLI uses the same saved default and stores a new one with
`--save-nfc-default` (for example `--tag-type NTAG215 --save-nfc-default`).

A byte reserve accounts for records your writer may add. SpoolScribe never programs tags
or modifies their Capability Container; unknown colours require an explicit representative
HEX. See [the NFC guide](docs/wiki/Writing-RFID-Tags.md).

```sh
python convert_profile.py --list --brand "bambu lab" --material PLA --sort1 color_name --sort2 weight
python convert_profile.py --tag-type NTAG215 --nfc-profile auto --reserve-bytes 32
```

## Install (from source)

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
under `Contents/`, which starts faster than a self-extracting file and stays compatible with
PyInstaller 7). CI in [`.github/workflows/build.yml`](.github/workflows/build.yml) runs the
offline tests on four configurations, builds the three archives, checks them and attaches
them with SHA-256 checksums to a GitHub Release when a `v*` tag is pushed.

## Tests and local data

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
[docs/DATA_FORMAT.md](docs/DATA_FORMAT.md).

## Privacy & data

- Network access only after you select sources; the dialog lists the exact hosts.
  Deselecting a source stops future requests without deleting its records. Settings can
  revoke the authorization; imported settings never grant it.
- Only one instance runs per data folder. A refresh can be cancelled; an offline launch
  keeps the cached database untouched.
- Sources and licences: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).
  Network behaviour: [docs/PRIVACY.md](docs/PRIVACY.md).

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

## Documentation

- [docs/PRIVACY.md](docs/PRIVACY.md) — network transparency and consent
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — sources, licences and merge rules
- [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md) — identifiers, JSON validation, settings keys
- [docs/UX-v0.3.0.md](docs/UX-v0.3.0.md) — interface behaviour and the two user reviews (French)
- [docs/wiki/Printers-and-Readers.md](docs/wiki/Printers-and-Readers.md) — which printers read which tags
- [docs/TRADEMARKS.md](docs/TRADEMARKS.md) — trademarks and non-affiliation
- [docs/ROADMAP.md](docs/ROADMAP.md) — done and remaining work
- [docs/archive/](docs/archive/) — superseded validation reports
- [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) — how to help
- [.github/SECURITY.md](.github/SECURITY.md) — reporting issues
- [CHANGELOG.md](CHANGELOG.md) — version history
- Wiki — starter pages in [`docs/wiki/`](docs/wiki/) (copy into the GitHub Wiki)

## Acknowledgements

- [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) (MIT)
- [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) (MIT)
- [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) (MIT)
- [TheFilamentDB](https://thefilamentdb.issou.best/) (CC-BY 4.0)
- [Bambu Studio](https://github.com/bambulab/BambuStudio) profiles (factual values only)
- [OpenSpool](https://github.com/spuder/OpenSpool) format
- [SpoolFlux](https://spoolflux.dingdongclick.de/?lang=us) — separate iPhone app for programming NFC tags
- The [**paxx12**](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) Snapmaker U1 firmware fork that makes the RFID reader usable

## License

Source code: **MIT** — see [LICENSE](LICENSE). Datasets and brand assets keep their own
licences and trademark rights (see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) and
[docs/TRADEMARKS.md](docs/TRADEMARKS.md)).
