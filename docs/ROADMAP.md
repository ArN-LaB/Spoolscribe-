# Roadmap

SpoolScribe is a **for-fun, free-time** project. There is no deadline, no
commercial goal, and no guarantee any of this ships. This roadmap simply records
ideas in roughly the order they might happen — contributions welcome.

## Guiding principles

- Stay **honest** about data licensing and trademarks.
- Stay **offline-first** and **consent-gated** for any network access.
- Keep the **core** logic UI-agnostic (shared by CLI and GUI).
- Prefer **small, reversible** changes.

## v0.3.0 — universal catalogue (development, not released)

- [x] Generic OFD source adapter covering all usable manufacturers in the official archive.
- [x] Complementary SpoolmanDB adapter for manufacturers absent from the curated/OFD catalogue.
- [x] Separate, traceable offline snapshots; original catalogue and local corrections preserved.
- [x] Manufacturer/material/completeness filters, multi-word search, numeric two-level sorting and pagination.
- [x] Reviewed HiDPI logos with transparent backgrounds and a readable name fallback.
- [x] Explicit local editing of temperatures, density and diameter.
- [x] NTAG215/NTAG216 capacity selection, optional essential payload, writer reserve and exact preview/export parity.
- [x] Offline data, GUI, CLI, migration and export regression coverage.
- [x] Native packaged catalogue/TLS smoke checks added to the three-platform workflow.
- [x] Header sorting/context menus, selectable columns, searchable brands/recent shortcuts and deselection.
- [x] No catalogue/Orca data in installers; first download and refresh at each authorized launch.
- [x] Manufacturer-first provenance, complementary values and pending ambiguous identity matches.
- [x] Selectable sources; official Polymaker, Bambu and SUNLU adapters.
- [x] Printer/reader guidance, automatic NFC sizing, advanced options hidden by default.
- [x] Persistent settings, settings file import/export and explicit application-update discovery.
- [ ] Additional reviewed manufacturer parsers: eSUN, versioned Prusa settings; no generic scraping promises.
- [ ] OpenPrintTag encoder (separate protocol/hardware), if requested.
- [ ] Run the new revision through the remote four-configuration CI and three builds.
- [ ] Human macOS/Windows/Linux acceptance and physical NTAG215/216 read-back.
- [ ] Release decision for v0.3.0.

The historical repository regression snapshot (excluded from installers) adds 22,838 OFD references from 157 brands and 599
SpoolmanDB references from 14 complementary manufacturers. Twenty OFD brand
folders have no usable variants. Missing data remain explicit; these figures
are source coverage, not a guarantee of complete manufacturer catalogues.

## v0.2.2 — released

- [x] Compact NFC export with retained metadata, validation and capacity check.
- [x] Explicit missing-color entry in GUI and CLI.
- [x] Atomic database storage, backups, conservative bundled-data merge.
- [x] Honest update status, preserved local corrections and offline tests.
- [x] PySide6 6.11.3 compatibility correction, archive-layout checks and bundled TLS roots.
- [ ] Physical NFC read-back and full cross-platform interactive acceptance.

## v0.2.0 / v0.2.1 — released

- [x] Cross-platform GUI (PySide6) + CLI sharing a pure `core`.
- [x] Polymaker SKU lookup → OpenSpool / NFC JSON export.
- [x] Consent-gated, fully disclosed data updates.
- [x] Multiplatform single-file builds via GitHub Actions + tagged releases.
- [x] **Prusament** curated coverage — HEX from SpoolmanDB (authoritative) + TheFilamentDB.
- [x] **ROSA3D** curated coverage — HEX from SpoolmanDB (fill-missing) with curated Silk/Pastel values.
- [x] Brand logos in the detail panel; OS light/dark theming; friendly empty state.
- [x] Single source of truth for the version (`core.APP_VERSION`).

## Next quality-of-life work

- [x] Search ergonomics and local physical-field editing.
- [ ] Broader catalogue creation/editing beyond those fields.
- [ ] Export presets / batch export of multiple SKUs.
- [x] Settings panel (sources, consent revocation, saved workspace) in the GUI.
- [ ] Study optional Spoolman filament lookup only after a distinct user need is validated;
      no duplication of Filament Manager/SpoolLink or UID migration in SpoolScribe.
- [ ] Localisation (the UI currently mixes FR/EN).

## Universal database: delivered foundation and remaining work

SpoolScribe now uses generic adapters. Remaining source/API work is separate
from the implemented v0.3.0 development scope:

- [x] **Prusament** (Prusa) — via SpoolmanDB + TheFilamentDB. ✓
- [x] **ROSA3D** — via SpoolmanDB. ✓
- [x] **Bambu Lab**, **eSUN**, **SUNLU**, and all other compatible source manufacturers.
- [x] Generic import of the path-addressed OFD source tree from its official HTTPS archive.
- [ ] Direct static REST API ingestion once HTTPS endpoints/redirects are reliably usable.
      The archive adapter already provides broad coverage without per-brand scrapers.
- [x] A brand selector in the UI, with reviewed logos and metadata.
- [x] Pure source-adapter registry; new manufacturers require no per-brand parser.

> Any new data source MUST be documented in [DATA_SOURCES.md](DATA_SOURCES.md)
> and added to `core.NETWORK_SOURCES` so it appears in the consent disclosure.

## Maybe / nice-to-have

- [ ] Direct NFC writing from within the app (hardware-dependent).
- [ ] Read-back / verify a written tag.

## Non-goals

- No telemetry, accounts, or cloud sync.
- No commercial offering.
- No bundling of trademarked assets beyond what's needed for identification.
