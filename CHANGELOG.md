# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
