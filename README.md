# SpoolScribe

[![Build multiplatform](https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml/badge.svg)](https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: for fun](https://img.shields.io/badge/status-for%20fun%20%C2%B7%20free%20time-blueviolet)

> Write OpenSpool / NFC spool tags for the **[open-firmware Snapmaker U1](https://snapmaker.com/snapmaker-u1)**, so
> your printer auto-recognizes the filament loaded in your [PolyDryer](https://polymaker.com/product/polydryer/) + [PolyBox](https://polymaker.com/product/polybox/)
> or AMS-style feeders.

**SpoolScribe** is a small, cross-platform desktop app (Windows / macOS / Linux)
that lets you look up a filament by its **SKU**, see its color, temperatures and
density, and generate the **OpenSpool JSON payload** used to program an
**RFID/NFC tag**. Pair it with the [paxx12 Snapmaker U1 firmware
fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) that exposes the machine's RFID reader, and the
U1 can identify each spool automatically.

Made by [@ArN-LaB](https://github.com/ArN-LaB) — a **for-fun, free-time** hobby
project, developed when time allows. No roadmap pressure, no commercial intent.

> [!IMPORTANT]
> SpoolScribe is an **unofficial hobby project**. It is **not affiliated with
> Polymaker or Snapmaker**. See [docs/TRADEMARKS.md](docs/TRADEMARKS.md).

## Features

- Instant search across hundreds of Polymaker SKUs.
- Real color swatches + the brand logo rendered from SVG.
- Filament details: type/subtype, nozzle & bed temps, density (with live
  override from official OrcaSlicer presets when available).
- One-click **OpenSpool / NFC JSON** export.
- JSON inspector before you write a tag.
- Optional, **consent-gated** data updates from open databases.

## Why this exists

The [Snapmaker U1](https://snapmaker.com/snapmaker-u1)'s firmware was opened up (via the [paxx12 fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)), exposing the
onboard **RFID reader**. That means spools sitting in **[PolyDryer](https://polymaker.com/product/polydryer/) + [PolyBox](https://polymaker.com/product/polybox/)**
dryers or **AMS-style** multi-material feeders can be identified automatically —
*if* each spool carries a tag describing it. SpoolScribe produces those tags in
the open [OpenSpool](https://github.com/spuder/OpenSpool) format. Just for fun.

### Writing the tags (216-byte NFC)

SpoolScribe generates the **data**; you write it onto the physical tag. For
NTAG216 (888-byte / commonly "216") NFC tags, the excellent web tool
[**SpoolFlux**](https://spoolflux.dingdongclick.de/?lang=us) works great to flash
the payload — it's my go-to for writing 216 NFC tags. (SpoolFlux is a separate
third-party project, not affiliated with SpoolScribe.)

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

The same PyInstaller spec works on all three OSes (run it on the target OS):

```sh
pyinstaller spoolscribe.spec --noconfirm
```

Output lands in `dist/`. CI in [`.github/workflows/build.yml`](.github/workflows/build.yml)
builds Windows, macOS and Linux artifacts automatically, and attaches them to a
GitHub Release when you push a `v*` tag.

## Privacy & data

- **Offline by default.** Nothing leaves your machine unless you opt in.
- Updates are **consent-gated** and **fully disclosed** — see
  [docs/PRIVACY.md](docs/PRIVACY.md).
- Data sources and their licenses are documented in
  [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

Today SpoolScribe focuses on Polymaker. Making it **brand-agnostic** (Prusament,
Bambu Lab, eSun, and more, via the Open Filament Database) is on the
[roadmap](docs/ROADMAP.md) — if and when free time allows.

## Project layout

| Path | Role |
|---|---|
| `core.py` | Pure business logic (no terminal I/O). Shared by CLI & GUI. |
| `app_gui.py` | PySide6 (Qt) desktop app. |
| `convert_profile.py` | Command-line interface. |
| `scripts/` | Data-update scrapers (standard library only). |
| `data/` | Bundled database + brand logo. |
| `orca_profiles/` | Official [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer) presets (temperature overrides). |

## Documentation

- [docs/PRIVACY.md](docs/PRIVACY.md) — network transparency & consent
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — sources & licenses
- [docs/TRADEMARKS.md](docs/TRADEMARKS.md) — trademarks & non-affiliation
- [docs/ROADMAP.md](docs/ROADMAP.md) — ideas for future versions
- [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md) — how to help
- [.github/SECURITY.md](.github/SECURITY.md) — reporting issues
- [CHANGELOG.md](CHANGELOG.md) — version history
- Wiki — starter pages in [`docs/wiki/`](docs/wiki/) (copy into the GitHub Wiki)

## Acknowledgements

- [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) (MIT)
- [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) (MIT)
- [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) (MIT)
- [TheFilamentDB](https://thefilamentdb.issou.best/) (CC-BY 4.0)
- [OpenSpool](https://github.com/spuder/OpenSpool) format
- [SpoolFlux](https://spoolflux.dingdongclick.de/?lang=us) — web tool I use to write 216 NFC tags
- The [**paxx12**](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) Snapmaker U1 firmware fork that makes the RFID reader usable

## License

Source code: **MIT** — see [LICENSE](LICENSE). Datasets and brand assets keep
their own licenses (see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) and
[docs/TRADEMARKS.md](docs/TRADEMARKS.md)).
