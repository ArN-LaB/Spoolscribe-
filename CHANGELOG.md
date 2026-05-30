# Changelog

All notable changes to SpoolScribe are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ArN-LaB/Spoolscribe-/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.1.0
