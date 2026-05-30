# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on history.** The `0.1.x` line was a rapid same-day development series
> (`0.1.0` → `0.1.6`) used to iterate on packaging and UI in public. Those
> point releases have been consolidated into **`0.2.0`**, the first curated
> public release. Their highlights are preserved below under *Development
> history* for reference.

## [Unreleased]

## [0.2.0] - 2026-05-30

First curated public release. Consolidates the `0.1.x` development series and
adds a round of UI polish, a single source of truth for the version, and a
tidied repository.

### Added
- **Three brands, authoritative colours.** Polymaker (hundreds of SKUs) plus
  curated **Prusament** (PLA, PETG, ASA, PC Blend — spools *and* refills) and
  **ROSA3D** (PLA Starter/Silk/Pastel/HS, PETG, PCTG, ASA, ABS+, recycled
  R-PLA/R-PET-G). HEX codes come from [SpoolmanDB](https://github.com/Donkie/SpoolmanDB)
  (authoritative for Prusament, fill-missing for ROSA3D) and
  [TheFilamentDB](https://thefilamentdb.issou.best/), with curated overrides for
  the Silk/Pastel families.
- **Brand logos in the detail panel** for Polymaker (SVG), Prusament and ROSA3D
  (PNG), fetched from the
  [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database)
  (MIT) and stored locally.
- **Dedicated app logo & icon** (`data/spoolscribe_logo.svg`, `data/app.ico`,
  `data/app.icns`) used for the window, taskbar and Windows executable.
- **OS light/dark theme support** that follows the system colour scheme and
  updates live when it changes.
- **Friendly empty state** with an animated spool logo when no filament is
  selected.

### Changed
- **Single source of truth for the version.** `core.APP_VERSION` is now the only
  place the version is declared; `spoolscribe.spec` reads it from `core.py` and
  `pyproject.toml` is kept aligned — no more "sync the version number" releases.
- **Reworked detail panel.** The colour preview is a labelled band showing the
  HEX directly on the swatch; characteristics live in a card; the primary
  "Générer le tag NFC" action is emphasised with secondary actions grouped below.
- **Header cleanup.** A single animated logo (no duplicate wordmark); the window
  title carries the product name.
- **JSON inspector resizes the window** instead of overflowing, so no stray
  scrollbars appear when toggling it.
- **Tidied repository.** Build artifacts removed, `tools/` folded into
  `scripts/`, dead imports pruned, `.gitignore` extended.

### Packaging
- **Single-file builds** on Windows / macOS / Linux (PyInstaller onefile) with
  embedded version metadata and a macOS `.app` bundle.
- Writable data (database, downloaded Orca profiles, output) is stored in a
  per-user directory and seeded from the bundle on first run.
- **SHA256 checksums** published with every release artifact.
- Consent-gated, fully disclosed data updates that work inside the frozen app.

---

## Development history (`0.1.x`, superseded by `0.2.0`)

These were same-day iterations, kept here for traceability:

- **0.1.6** — Header cleanup; single animated logo.
- **0.1.5** — Brand logos for Prusament & ROSA3D in the detail panel; logo widget
  supports SVG and PNG.
- **0.1.4** — Multi-source HEX enrichment for Prusament & ROSA3D (SpoolmanDB +
  TheFilamentDB); `docs/DATA_SOURCES.md` extended.
- **0.1.3** — App logo & icon; OS light/dark theme; friendly empty state;
  reworked detail panel; bundled `difflib` fix for packaged updates.
- **0.1.2** — Database updates work in the packaged app; per-user writable data;
  UTF-8 worker output; URL-encoded Orca downloads.
- **0.1.1** — Single-file executables; Windows version metadata; macOS `.app`;
  SHA256 checksums.
- **0.1.0** — Initial cross-platform GUI + CLI sharing a pure `core`;
  consent-gated updates; PyInstaller packaging; CI matrix build.

[Unreleased]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.2.0
# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on history.** The `0.1.x` line was a rapid same-day development series
> (`0.1.0` → `0.1.6`) used to iterate on packaging and UI in public. Those
> point releases have been consolidated into **`0.2.0`**, the first curated
> public release. Their highlights are preserved below under *Development
> history* for reference.

## [Unreleased]

## [0.2.0] - 2026-05-30

First curated public release. Consolidates the `0.1.x` development series and
adds a round of UI polish, a single source of truth for the version, and a
tidied repository.

### Added
- **Three brands, authoritative colours.** Polymaker (hundreds of SKUs) plus
  curated **Prusament** (PLA, PETG, ASA, PC Blend — spools *and* refills) and
  **ROSA3D** (PLA Starter/Silk/Pastel/HS, PETG, PCTG, ASA, ABS+, recycled
  R-PLA/R-PET-G). HEX codes come from [SpoolmanDB](https://github.com/Donkie/SpoolmanDB)
  (authoritative for Prusament, fill-missing for ROSA3D) and
  [TheFilamentDB](https://thefilamentdb.issou.best/), with curated overrides for
  the Silk/Pastel families.
- **Brand logos in the detail panel** for Polymaker (SVG), Prusament and ROSA3D
  (PNG), fetched from the
  [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database)
  (MIT) and stored locally.
- **Dedicated app logo & icon** (`data/spoolscribe_logo.svg`, `data/app.ico`,
  `data/app.icns`) used for the window, taskbar and Windows executable.
- **OS light/dark theme support** that follows the system colour scheme and
  updates live when it changes.
- **Friendly empty state** with an animated spool logo when no filament is
  selected.

### Changed
- **Single source of truth for the version.** `core.APP_VERSION` is now the only
  place the version is declared; `spoolscribe.spec` reads it from `core.py` and
  `pyproject.toml` is kept aligned — no more "sync the version number" releases.
- **Reworked detail panel.** The colour preview is a labelled band showing the
  HEX directly on the swatch; characteristics live in a card; the primary
  "Générer le tag NFC" action is emphasised with secondary actions grouped below.
- **Header cleanup.** A single animated logo (no duplicate wordmark); the window
  title carries the product name.
- **JSON inspector resizes the window** instead of overflowing, so no stray
  scrollbars appear when toggling it.
- **Tidied repository.** Build artifacts removed, `tools/` folded into
  `scripts/`, dead imports pruned, `.gitignore` extended.

### Packaging
- **Single-file builds** on Windows / macOS / Linux (PyInstaller onefile) with
  embedded version metadata and a macOS `.app` bundle.
- Writable data (database, downloaded Orca profiles, output) is stored in a
  per-user directory and seeded from the bundle on first run.
- **SHA256 checksums** published with every release artifact.
- Consent-gated, fully disclosed data updates that work inside the frozen app.

---

## Development history (`0.1.x`, superseded by `0.2.0`)

These were same-day iterations, kept here for traceability:

- **0.1.6** — Header cleanup; single animated logo.
- **0.1.5** — Brand logos for Prusament & ROSA3D in the detail panel; logo widget
  supports SVG and PNG.
- **0.1.4** — Multi-source HEX enrichment for Prusament & ROSA3D (SpoolmanDB +
  TheFilamentDB); `docs/DATA_SOURCES.md` extended.
- **0.1.3** — App logo & icon; OS light/dark theme; friendly empty state;
  reworked detail panel; bundled `difflib` fix for packaged updates.
- **0.1.2** — Database updates work in the packaged app; per-user writable data;
  UTF-8 worker output; URL-encoded Orca downloads.
- **0.1.1** — Single-file executables; Windows version metadata; macOS `.app`;
  SHA256 checksums.
- **0.1.0** — Initial cross-platform GUI + CLI sharing a pure `core`;
  consent-gated updates; PyInstaller packaging; CI matrix build.

[Unreleased]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.2.0
# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] - 2026-05-30

### Changed
- **Header cleanup.** The "SpoolScribe" wordmark text is removed from the
  top bar — the window title already carries it. The app logo in the header
  is now a plain static icon (36 px) instead of a second spinning widget.
- **Single animated logo.** Only the empty-state panel shows the spinning
  spool (96 px); the header no longer duplicates it. The animation is now
  clearly visible at that size.

## [0.1.5] - 2026-05-30

### Added
- **Brand logos for Prusament and ROSA3D.** The detail panel now shows the
  brand logo when a Prusament or ROSA3D filament is selected, just like
  Polymaker. Logos are fetched from
  [OpenFilamentCollective/open-filament-database](https://github.com/OpenFilamentCollective/open-filament-database)
  (MIT) and stored locally as `data/prusament_logo.png` and
  `data/rosa3d_logo.png`.
- New script `scripts/sync_multibrand_assets.py` wired into `UPDATE_PIPELINE`.

### Changed
- **Logo widget in the detail panel** now supports both SVG (Polymaker) and
  PNG (Prusament, ROSA3D) formats — no longer limited to `QSvgWidget`.

## [0.1.4] - 2026-05-30

### Added
- **Multi-source HEX enrichment for Prusament & ROSA3D.** Color codes are now
  sourced from [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) and
  [TheFilamentDB](https://thefilamentdb.issou.best/) instead of offline
  approximation tables.
  - *Prusament* — SpoolmanDB is treated as **authoritative** (official Prusa
    swatches: Jet Black `#24292A`, Prusa Orange `#EA5E1A`, Gravity Grey
    `#9FA4A8`); TheFilamentDB fills remaining gaps.
  - *ROSA3D* — SpoolmanDB fills only **missing** entries; curated values for
    the Silk / Pastel PLA families are preserved (SpoolmanDB uses CSS primaries
    for those, which are less accurate).
  - Transparent / translucent variants (`Red Transparent`, `Clear`, …) are
    intentionally left without a solid HEX; the OpenSpool export falls back to
    `000000`.
- New scripts `scripts/scrape_spoolman_multibrand_hex.py` and
  `scripts/scrape_thefilamentdb_multibrand_hex.py`, both wired into
  `core.UPDATE_PIPELINE`.
- `docs/DATA_SOURCES.md` extended with a "Multi-brand color enrichment" section
  documenting the per-brand override policy and source URLs.

## [0.1.3] - 2026-05-30

### Added
- **Dedicated SpoolScribe app logo & icon.** A new, original spool-and-thread
  mark (`data/spoolscribe_logo.svg`) is shown in the window header and used as
  the window/taskbar icon and the Windows executable icon (`data/app.ico`,
  generated by `tools/make_icons.py`).
- **Light / dark theme support.** The interface now follows the OS colour
  scheme and updates live when it changes, with readable, theme-aware accents,
  cards and text.
- **Friendly empty state.** When no filament is selected, the right panel shows
  the app logo and a short hint instead of an unlabelled blank rectangle.

### Changed
- **Reworked the detail panel for clarity.** The colour preview is now a labelled
  band that displays the HEX value directly on the swatch; characteristics sit in
  a card; the primary “Générer le tag NFC” action is emphasised with secondary
  actions grouped below.

### Fixed
- **TheFilamentDB update no longer fails in the packaged app**
  (`ModuleNotFoundError: No module named 'difflib'`): `difflib`, `unicodedata`
  and other standard-library modules used by the scrapers are now bundled.

## [0.1.2] - 2026-05-30

### Fixed
- **Database updates now work in the packaged app.** The bundled scrapers run
  as worker processes inside the frozen executable; their standard-library
  imports (`urllib.request`, `urllib.error`, `gzip`, `ssl`…) are now included in
  the build, fixing `ModuleNotFoundError` during updates.
- **No more lost data in single-file builds.** Writable data (the working
  database, downloaded Orca profiles, generated output) is stored in a per-user
  directory (`%APPDATA%/SpoolScribe`, `~/Library/Application Support/SpoolScribe`,
  `~/.config/SpoolScribe`) and seeded from the bundle on first run — instead of a
  temporary folder that disappeared. Read-only resources stay in the bundle.
- **Unicode output no longer crashes updates on Windows** (`UnicodeEncodeError`):
  worker stdout/stderr are forced to UTF-8.
- **Orca profile download** now URL-encodes paths containing spaces, fixing
  “URL can't contain control characters” errors.

## [0.1.1] - 2026-05-30

### Changed
- **Windows / macOS / Linux builds are now single-file** (PyInstaller onefile):
  one `SpoolScribe.exe` / binary / `.app` — no more `_internal` folder next to
  the executable.

### Added
- Embedded **version metadata** in the Windows executable (ProductName,
  CompanyName, FileDescription…) so the OS shows “SpoolScribe — ArN-LaB” in file
  properties and the SmartScreen/UAC prompt instead of a blank “Unknown
  publisher”.
- macOS `.app` bundle with proper `Info.plist` metadata.
- **SHA256 checksums** published alongside every release artifact so users can
  verify download integrity.

## [0.1.0] - 2026-05-30

### Added
- Cross-platform desktop GUI (`app_gui.py`) built on PySide6 (Qt): instant
  search, color swatches, SVG brand logo, JSON inspector, one-click export.
- Shared pure-logic core (`core.py`) used by both the CLI and the GUI.
- Consent-gated, fully disclosed data updates (`core.NETWORK_SOURCES`,
  `docs/PRIVACY.md`). Offline by default; no network without explicit opt-in.
- PyInstaller spec and GitHub Actions workflow producing Windows, macOS and
  Linux artifacts, with automatic GitHub Releases on `v*` tags.
- Project governance: `LICENSE` (MIT), `docs/DATA_SOURCES.md`,
  `docs/TRADEMARKS.md`, `docs/PRIVACY.md`, `docs/ROADMAP.md`,
  `.github/SECURITY.md`, `.github/CONTRIBUTING.md`, `.github/CODE_OF_CONDUCT.md`,
  issue and PR templates, and starter wiki pages under `docs/wiki/`.
- `pyproject.toml` with project metadata and version source of truth.

### Changed
- Refactored the original single-file script into `core` + thin CLI.
- Renamed the project to **SpoolScribe**; spec renamed to `spoolscribe.spec`.
- Cleaned repository: removed one-off bootstrap scripts, raw scrape caches,
  bundled PDF, and generated output; minimized root directory.

[Unreleased]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.1.2
[0.1.1]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.1.1
[0.1.0]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.1.0
