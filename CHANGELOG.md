# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on history.** The `0.1.x` line was a rapid same-day development series
> (`0.1.0` → `0.1.6`) used to iterate on packaging and UI in public. Those
> point releases have been consolidated into **`0.2.0`**, the first curated
> public release. Their highlights are preserved below under *Development
> history* for reference.

## [0.3.0] — Unreleased

### UX revision after user feedback

- Header-only two-level sorting, contextual column selection, searchable manufacturers
  with Polymaker default/recent shortcuts, bottom pagination and database status.
- Row deselection, transparent logo presentation, explicit data-completeness wording.
- Empty installer catalogue, initial download and selected-source refresh at launch;
  cached records survive failures and restores inhibit same-session automatic work.
- Manufacturer-first field provenance and exact identity reconciliation, with uncertain
  cross-source matches held out of the table. Official Polymaker/Bambu/SUNLU adapters.
- Printer-specific field guidance, automatic NFC profile choice and advanced options.
  No Bambu proprietary tag or OpenPrintTag encoder is claimed.
- Persistent workspace/settings import/export and explicit newer-release discovery.


### Added
- Universal catalogue sources: 22,838 OFD references / 157 new brands plus 599
  SpoolmanDB references / 14 complementary manufacturers, kept in the repository
  as audited regression snapshots. Installers contain no catalogue: the first
  launch downloads the selected sources. Upstream MIT notices are bundled.
- Manufacturer, material and completeness filters; accent-insensitive multi-word
  search; primary/secondary column sorting with numeric values and 250-row pages.
- Explicit editing of local product temperatures, diameter and density.
- NTAG215 (496-byte NDEF area) and NTAG216 (872-byte area), explicit essential
  export profile, writer reserve, remaining space and distinct export filenames.
- Generic conservative source workers and renewed consent for the new hosts.
- Offline native packaged catalogue/NFC smoke check in CI.

### Fixed
- Manufacturer-specific CLI metadata instead of a hard-coded Polymaker lookup.
- Logos retain aspect ratio and transparent surroundings with a subtle outline;
  no background plate is added. 137 new logos reviewed; unsuitable images use a
  name fallback.
- Material names containing slashes (e.g. PA6/66) no longer trigger an invalid
  legacy Orca profile lookup. Existing Orca presets remain unchanged.

### Audit fixes (31 October 2026)

Data integrity:
- Reconciliation identities keep product grades (`PLA+` ≠ `PLA`) and include the
  colour when a manufacturer article number is reused: an OFD refresh no longer
  absorbs ~650 references nor rewrites temperatures/colours of another product.
  Every absorbed source record is now listed in `_source_aliases`.
- A source that stops publishing a value never empties the local one; the case
  is reported as a conserved conflict. A refresh returning less than half of a
  source's previous references is refused before merging.
- Source values that contradict themselves are flagged **À vérifier** and cannot
  reach a tag until explicitly corrected: black HEX for a light colour name,
  white HEX for a dark one, nozzle/bed/density/diameter outside printable ranges,
  bed maximum of 0 °C. User corrections and historical entries are trusted.
- Orca profiles without plate temperature give an unknown bed, not 0 °C.
- Workers run directly default to the user data folder, never the repository
  fixture. Development snapshot records merged in memory carry provenance, so a
  later refresh can still update them.
- SpoolmanDB complements only manufacturers not already covered, as documented.
- `tests/test_ux.py` skips its Qt interaction tests without PySide6 instead of
  failing at import; 12 new integrity tests.

Synchronisation:
- Launch refresh follows a cadence (**Paramètres**: every launch / daily (default)
  / weekly / manual); the **Mettre à jour** button always forces a refresh. An
  empty database still triggers the first download.
- OFD, SpoolmanDB and the Bambu index send `If-None-Match`; an unchanged source
  answers 304 and the step ends immediately without re-downloading.
- A running synchronisation can be cancelled (button next to the progress bar)
  and the window can be closed after confirmation; the current worker is killed
  and the local database is left as it was.
- An offline attempt no longer rewrites the 12 MB database and its backups at
  every launch: unchanged outcomes stay out of the file, the attempt date lives
  in the settings, and an offline start shows a status line instead of a modal box.
- A single application instance per data folder (`spoolscribe.instance.lock`);
  a database lock left by a dead or interrupted worker is recovered instead of
  blocking every later save.
- The Polymaker and Orca downloaders go through the bounded same-host fetcher
  (8 MiB limit, declared User-Agent, no foreign redirect, 40-page cap) as
  PRIVACY.md already stated. A stray symbolic link in the OFD archive is skipped
  instead of failing the whole refresh; the Bambu index cap is 600 profiles.
- `--run-script` only executes bundled workers (CI probes opt in through
  `SPOOLSCRIBE_RUN_SCRIPT_ALLOW`). The release check refuses redirects before
  following them and tolerates a `-dev` suffix on the local version.
- Consent dialog and `NETWORK_SOURCES` describe exactly the hosts contacted
  (wiki.polymaker.com removed; the obsolete first list is gone).

NFC:
- The recommended profile is now **essential** (material, colours, temperatures,
  diameter, density: everything a reader uses); it fits every reference on
  NTAG215. The full profile (descriptions, brand metadata, logo URL) is an
  explicit choice in the advanced settings and the CLI (`--nfc-profile full`).
- Full-profile payloads no longer write `null` brand metadata or logo keys.
  45 of the 1,008 historical exports differ only by those omitted keys (the
  fixture keeps the v0.2.2 digest and the verification note).
- CLI: `--nfc-profile auto` (default), case-insensitive `--brand`/`--material`
  and reference lookup, strict argument parsing, empty-database hint for
  `--list` on first launch instead of a misleading restore message.

Interface:
- Unchecked boxes are visible again (styled indicator with a check mark),
  disabled fields look disabled, quick-access manufacturers are chips, the
  column chooser is a labelled button, and Ctrl+F / Ctrl+E / Ctrl+U / Escape
  shortcuts are available.
- The **Référence** column shows the manufacturer article when known
  (internal `OFD-…`/`SMDB-…` identifiers stay in the tooltip and in a separate
  *Réf. interne* sort key); **Produit** stretches so the table fits 1440 px.
- Typing in the search field and dragging columns/splitter no longer write the
  settings file at every event: search is debounced (180 ms) and preferences
  are written once, 700 ms after the last change. Search keys are normalised
  once per reload instead of at every keystroke; colour swatches are cached.
- The card is rendered once per selection (no duplicate table/grid refresh);
  logos are cached per theme and keep their full Retina size with the outline.
  Bitmaps under 24 px fall back to the brand name; others may be enlarged ≤ 2×.
- No more "Polymaker" fallback for a record without brand or after an OS theme
  change; the selected row and its page survive sorting, filtering and refreshes.
- Tag controls are hidden (not greyed) when the chosen printer has no OpenSpool
  export; the grid view supports Escape/re-click deselection; the manufacturer
  field is never rewritten while typing; importing settings restores tag,
  reserve, printer help, extra fields and shortcuts consistently.
- Thousands use the French separator; export shows a status line instead of a
  modal box; a corrupt `ui` setting no longer crashes startup; About text updated.
- Dead code removed (`logo_with_contrast_plate`, `add_soft_halo`, unused imports).

Build, CI, licences and documentation:
- macOS is built as a native onedir `.app` (resources under `Contents/Frameworks`):
  no 40 MB extraction at every launch, and no dependency on the onefile+BUNDLE
  combination that PyInstaller 7 refuses. Windows and Linux stay single-file.
  `upx` disabled for reproducible builds.
- GitHub Actions are pinned by commit SHA; jobs have timeouts and a per-branch
  concurrency group; internal pull requests are no longer tested twice.
- Dependabot ignores PyInstaller ≥ 7, PySide6/Shiboken ≥ 6.12 and other majors;
  `pyinstaller>=6.0,<7` in the requirements; unused PyYAML dropped and the
  pinned build requirements regenerated.
- CI resource verification handles the macOS bundle layout; frozen probes run
  through `SPOOLSCRIBE_RUN_SCRIPT_ALLOW`.
- TheFilamentDB attribution (CC BY 4.0) shipped in `data/TheFilamentDB-ATTRIBUTION.txt`;
  logos documented as third-party marks modified by the build (TRADEMARKS.md);
  Bambu Studio (AGPL-3.0, facts only) and SUNLU added to the source table.
- README rewritten around a three-step quick start (download and Gatekeeper /
  SmartScreen, first launch, export and write); PRIVACY, DATA_SOURCES,
  DATA_FORMAT, ROADMAP, UX guide, wiki and CONTRIBUTING aligned with the code;
  v0.2.2 and earlier v0.3.0 reports moved to `docs/archive/`.

### Compatibility
- Original catalogue bytes and all 1,008 compatible default exports are unchanged.
- Unknown physical values remain null, source multicolors remain intact, and an
  essential export never silently drops alpha, additional colors or printing values.
- Existing local fields, including intentional nulls, win during upgrades/updates.
- No direct NFC writing, UID association, Spoolman server, firmware or NAS change.

## [0.2.2] - 2026-10-31

### Fixed
- Use the validated PySide6/Shiboken 6.11.3 build set and exclude 6.12 to avoid
  the native `none_dealloc` crash observed on Linux with Python 3.10 (CI-01).
- Preserve bundled catalogue, profiles and worker bytes across OS checkouts;
  verify embedded resources against Git before packaging.
- Disable generated Python bytecode during builds to keep worker resources clean.
- Validate OpenSpool data before preview/export: no invented black color or
  manufacturer, no null/non-finite physical values or reversed ranges.
- Compact NFC JSON keeps the complete existing field set. Capacity checks use
  UTF-8 bytes plus one `application/json` NDEF record and Type 2 TLV framing.
  Readable archive exports remain available under a separate filename.
- GUI and CLI can explicitly supply a representative HEX and optional alpha
  for an unknown color. No transparency or multicolor values are inferred.
- Confine exported filenames to the output directory.
- Atomically save validated databases, preserve the last good revision and
  a separate pre-update backup, and report corruption or stale saves.
- Preserve local physical values at export unless the user explicitly selects
  the Orca override setting/CLI flag.
- Preserve local HEX and physical corrections during ordinary updates; merge
  additions from newer bundled catalogues without replacing existing values.
- Report unavailable sources and partial updates honestly. Only a fully
  successful pipeline advances the complete-refresh date.
- Allow the CLI to reconsider saved network consent; GUI settings can revoke it.

### Tests and packaging
- Bundle portable CA roots for frozen HTTPS workers, preserving existing trust
  configuration and strict TLS verification. Check native frozen TLS trust offline
  on all three build platforms.
- Package only the native application for each OS: `.app` on macOS, `.exe` on
  Windows, and the Linux executable. Validate archive layout and binary format.
- Add offline catalogue, OpenSpool, NFC size, storage, updater, Orca and GUI tests.
- Run tests on pushes/PRs and require them before the existing three-OS builds.
- Record a Python 3.12 build dependency snapshot in `requirements-build.txt`.
- Include the shared storage helper in packaged worker execution.

### Compatibility
- OpenSpool protocol/version stay `openspool` / `1.0`; metadata fields are retained.
- 76 missing HEX values and two orphan catalogue references remain explicit
  data-quality exceptions; no unverified catalogue correction is fabricated.
- No Spoolman integration or UID migration, firmware/NAS change or direct NFC writing.
- Hardware read-back and Windows/Linux packaged execution require separate validation.

## [0.2.1] - 2026-05-30

### Fixed
- **Brand logo rendering for wide wordmarks (ROSA3D).** The logo widget was a
  52×52 px square — ROSA3D's 334×94 wordmark was squished to ~15 px tall.
  `load_brand_pixmap` now accepts a separate `max_w` bound; the logo widget is
  160×52 px (left-aligned), so ROSA3D renders at ~160×45 px while square logos
  (Polymaker, Prusament) are unaffected.

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

## Detailed development history (superseded)

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

[0.3.0]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.2.0
