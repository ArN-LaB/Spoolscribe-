# Roadmap

SpoolScribe is a **for-fun, free-time** project. There is no deadline, no
commercial goal, and no guarantee any of this ships. This roadmap records what
is done and what remains — contributions welcome.

## Guiding principles

- Stay **honest** about data licensing and trademarks.
- Stay **offline-first** and **consent-gated** for any network access.
- Keep the **core** logic UI-agnostic (shared by CLI and GUI).
- Prefer **small, reversible** changes.

## v0.3.0 — universal catalogue (stable, 1 November 2026)

- [x] Generic OFD source adapter covering all usable manufacturers in the official archive.
- [x] Complementary SpoolmanDB adapter for manufacturers absent from the other sources.
- [x] Separate, traceable offline snapshots; original catalogue and local corrections preserved.
- [x] Manufacturer/material/data-state filters, multi-word search, two-level header sorting, column chooser, pagination.
- [x] Reviewed HiDPI logos with transparent backgrounds and a readable name fallback.
- [x] Explicit local editing of temperatures, density, diameter and colour.
- [x] NTAG215/NTAG216 capacity check, essential/full profiles, writer reserve and exact preview/export parity.
- [x] No catalogue/Orca data in installers; first download, then refresh at a configurable cadence.
- [x] Manufacturer-first provenance, complementary values and pending ambiguous identity matches.
- [x] Selectable sources; explicit Polymaker, Bambu Studio and SUNLU manufacturer enrichment.
- [x] Printer/reader guidance, advanced options hidden by default.
- [x] Persistent settings, settings file import/export and explicit application-update discovery.
- [x] Native packaged catalogue/TLS smoke checks in the three-platform workflow.

### Screen feedback, 1 November 2026 — local corrective pass

- [x] Explicit manufacturer/filament favorites, persistent identities and favorites filter.
- [x] Bounded sidebar, migration of old splitter sizes, scrolling dialogs and fixed export actions.
- [x] Printer/software questions without assuming a modified U1; progressive technical details.
- [x] Diameter-specific groups, selectable packaging and explicit choice for conflicting hues.
- [x] Preserve historical brand-line metadata; reject incoherent partial temperature pairs; fix OFD line websites.
- [x] Native macOS bundle logo paths, complete filter reset preserving favorites, colour swatches then packaging, and schematic printer cards.
- [x] Explicit partial source coverage, analysis counters, inline printer-list fallback and readable sync progress.
- [x] HEX-driven spool hero/grid, product-first cards, four parameter tiles and a compact export footer.
- [x] Homogeneous favorite stars/filters, preferred packaging settings and direct saved-source synchronisation.
- [x] Reviewed official printer images for U1, X1 Carbon and QIDI Plus4; documented summaries and searchable selection.
- [x] Shared app/test startup style and font, native geometry assertions, restored export tools, quieter favorite stars and perspective reel.
- [ ] Review further model-specific images before bundling; keep unsupported entries textual.
- [ ] Resolve remaining ambiguous source matches with documented product evidence.
- [x] Remote four-configuration CI: 237 tests per configuration, three native builds.
- [ ] Human screen acceptance and physical NFC readback.

### Audit 31 October 2026 — applied

Four read-only audits (data/core, sources/network/security, Qt interface,
build/CI/tests/docs) were run on the development branch; every finding was
addressed in separate commits, see [CHANGELOG.md](../CHANGELOG.md):

- [x] **Data integrity** — merge identities keep product grades and colours
      (no more absorption of ~650 OFD references), a source cannot empty its own
      values, a shrunken source is refused, implausible colours/physics are
      flagged *À vérifier* and blocked at export, workers never write to the
      repository fixture.
- [x] **Synchronisation** — refresh cadence, conditional downloads (ETag),
      cancellation, closable window, no database rewrite when offline, single
      instance, stale-lock recovery, bounded Polymaker/Orca downloaders,
      `--run-script` restricted to bundled workers.
- [x] **NFC** — essential profile recommended (fits NTAG215), full profile
      explicit and free of `null` metadata, CLI `--nfc-profile auto`.
- [x] **Interface** — visible checkboxes, readable references, debounced
      search and settings writes, cached swatches/logos at Retina size, no
      Polymaker fallback, selection kept across refreshes, hidden tag controls
      without OpenSpool export, keyboard shortcuts, dead code removed.
- [x] **CI, packaging, docs** — actions pinned by commit, Dependabot bounds,
      PyInstaller < 7, macOS one-directory `.app`, licences and trademarks
      clarified, README quick start, archived reports.

### Second review on real data, 1 November 2026 — applied

The first test build was run on a real installation (24,649 references created
by an earlier preview build, without provenance). Six remarks, all addressed:

- [x] **Interface** — sidebar of facets (manufacturers with explicit favorites,
      material families, data state) instead of three dropdowns and quick-access
      chips; ⚙ menu; **Mon matériel** dialog; card with references, provenance
      and a hardware summary; one row per filament.
- [x] **Inconsistent lists and colours** — product lines folded into their
      manufacturer (PolyLite, Panchroma, Fiberon…); packagings of one filament
      grouped with the best-documented HEX; manufacturer sources now correct
      fields of unknown provenance, so old installations are no longer frozen.
- [x] **Duplicates and merging** — grouping, orphan records healed, a report
      after each refresh (references, ready filaments, conserved values, pending
      matches, result per source), last result shown per source.
- [x] **Printers** — data-driven list (`data/printers.json`) with reader
      technology, firmware and "reads OpenSpool" flag, refreshable from the
      repository.
- [x] **Logos** — transparent background enforced by a test, import tool with
      provenance, manifest-first resolution.
- [x] **Search and filters** — the sidebar replaces the redundant controls.

### Post-release validation and follow-up

Stable publication was authorized after automated validation. The unchecked
items below remain open; publication does not imply hardware or human acceptance.

- [ ] Finish re-sourcing official manufacturer logos through
      `.github/scripts/import_brand_logos.py` (the review file is being built).

- [x] Run the revision through the remote four-configuration CI and the three builds
      (237 tests per configuration; see [CI validation](VALIDATION-CI-v0.3.0.md)).
- [ ] Human acceptance on macOS, Windows and Linux (first launch, download, export).
- [ ] Physical NTAG215/NTAG216 write and read-back with a real printer.
- [ ] Optionally move the legacy scrapers (`scripts/scrape_*`, `seed_*`,
      `sync_*_assets.py`) to `scripts/legacy/` and shrink the bundled scripts.
- [ ] Optionally store `data/catalogue_ofd.json` gzip-compressed (11.9 MB in Git).
- [ ] Additional reviewed manufacturer parsers (eSUN, versioned Prusa settings), no generic scraping.
- [ ] OpenPrintTag encoder (separate protocol/hardware), if requested.

## v0.2.2 — released

- [x] Compact NFC export with retained metadata, validation and capacity check.
- [x] Explicit missing-colour entry in GUI and CLI.
- [x] Atomic database storage, backups, conservative bundled-data merge.
- [x] Honest update status, preserved local corrections and offline tests.
- [x] PySide6 6.11.3 compatibility correction, archive-layout checks and bundled TLS roots.
- [ ] Physical NFC read-back and full cross-platform interactive acceptance.

## v0.2.0 / v0.2.1 — released

- [x] Cross-platform GUI (PySide6) + CLI sharing a pure `core`.
- [x] Polymaker SKU lookup → OpenSpool / NFC JSON export.
- [x] Consent-gated, fully disclosed data updates.
- [x] Multiplatform builds via GitHub Actions + tagged releases.
- [x] **Prusament** curated coverage — HEX from SpoolmanDB (authoritative) + TheFilamentDB.
- [x] **ROSA3D** curated coverage — HEX from SpoolmanDB (fill-missing) with curated Silk/Pastel values.
- [x] Brand logos in the detail panel; OS light/dark theming; friendly empty state.
- [x] Single source of truth for the version (`core.APP_VERSION`).

## Next quality-of-life work

- [x] Search ergonomics and local physical-field editing.
- [ ] Broader catalogue creation/editing beyond those fields; manual editor for pending matches.
- [ ] Export presets / batch export of multiple references.
- [x] Settings panel (sources, cadence, consent revocation, saved workspace) in the GUI.
- [ ] Study optional Spoolman filament lookup only after a distinct user need is validated;
      no duplication of Filament Manager/SpoolLink or UID migration in SpoolScribe.
- [ ] Localisation (the UI is French, the docs mostly English).

## Universal database: delivered foundation and remaining work

The catalogue comes from two generic community adapters (OFD archive,
SpoolmanDB compiled JSON) that need no per-brand code, plus explicit
manufacturer enrichment adapters (Polymaker wholesale, Bambu Studio profiles,
SUNLU page) that only add facts to families the catalogues already contain.

- [x] **Prusament** (Prusa) — via SpoolmanDB + TheFilamentDB.
- [x] **ROSA3D** — via SpoolmanDB.
- [x] **Bambu Lab**, **eSUN**, **SUNLU**, and every other manufacturer present in OFD/SpoolmanDB.
- [x] Generic import of the path-addressed OFD source tree from its official HTTPS archive.
- [ ] Direct static REST API ingestion once HTTPS endpoints/redirects are reliably usable.
- [x] A manufacturer sidebar in the UI, with reviewed logos and metadata.
- [x] Source registry in `core.SOURCE_GROUPS`; the consent list is derived from it.

> Any new data source MUST be documented in [DATA_SOURCES.md](DATA_SOURCES.md)
> and [PRIVACY.md](PRIVACY.md), and added as a group in `core.SOURCE_GROUPS`
> so it appears in the consent disclosure.

## Maybe / nice-to-have

- [ ] Direct NFC writing from within the app (hardware-dependent).
- [ ] Read-back / verify a written tag.

## Non-goals

- No telemetry, accounts, or cloud sync.
- No commercial offering.
- No bundling of trademarked assets beyond what's needed for identification.

### Local UX follow-up — 1 November, 11:07–11:12 feedback

- [x] Visual printer browser, explicit arrow and search.
- [x] Alphabetical material search, equal characteristic actions and overflow-only scrolling.
- [x] Bobines preferences separated from export configuration.
- [x] Shared catalogue/synchronisation summaries and control-size rules.
- [x] Cross-platform CI for the integrated code (237 tests per configuration).
- [ ] Human acceptance of the integrated application and physical NFC readback.

- [x] Expanded-state UX correction: bounded storage details, stable printer-card resize, aligned local correction form and provenance (local sixth pass, human acceptance pending).

- [x] Printer compatibility filters, native transparent photos, aligned secondary controls and About support link (local seventh pass; human acceptance pending).

- [x] Export destination/confirmation, fixed-size JSON inspection, isolated @suffix personal copies and sourced NFC format explanation (local eighth pass; human acceptance pending).


## v0.3.5 — interface languages and linked filters (prepared locally)

- [x] English, French, Spanish and Simplified Chinese UI, with OS detection and English fallback.
- [x] Persistent language override, applied on restart; included in settings files.
- [x] Manufacturer/material facet intersection and compatible choice counts.
- [x] Clear-search affordance and explicit catalogue-refresh label.
- [x] Restore the animated README logo without an external image host.
- [ ] Native-speaker acceptance of translations.
- [ ] Four-configuration CI matrix and three release builds on the final commit.
- [ ] Human desktop acceptance and physical NFC read-back (not inferred from automation).

See [v0.3.5 validation](VALIDATION-v0.3.5.md). Existing roadmap and historical
validation entries above retain their original scope.

- [x] v0.3.5 follow-up: native macOS UI-language detection, declared bundle languages and Restart now / Later after saving/importing a language. Real source-process relaunch tested with isolated settings.
