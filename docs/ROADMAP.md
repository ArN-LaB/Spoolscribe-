# Roadmap

SpoolScribe is a **for-fun, free-time** project. There is no deadline, no
commercial goal, and no guarantee any of this ships. This roadmap simply records
ideas in roughly the order they might happen — contributions welcome.

## Guiding principles

- Stay **honest** about data licensing and trademarks.
- Stay **offline-first** and **consent-gated** for any network access.
- Keep the **core** logic UI-agnostic (shared by CLI and GUI).
- Prefer **small, reversible** changes.

## v0.2.0 — current (first curated release)

- [x] Cross-platform GUI (PySide6) + CLI sharing a pure `core`.
- [x] Polymaker SKU lookup → OpenSpool / NFC JSON export.
- [x] Consent-gated, fully disclosed data updates.
- [x] Multiplatform single-file builds via GitHub Actions + tagged releases.
- [x] **Prusament** full coverage — HEX from SpoolmanDB (authoritative) + TheFilamentDB.
- [x] **ROSA3D** full coverage — HEX from SpoolmanDB (fill-missing) with curated Silk/Pastel values.
- [x] Brand logos in the detail panel; OS light/dark theming; friendly empty state.
- [x] Single source of truth for the version (`core.APP_VERSION`).

## v0.3 — quality of life

- [ ] Editable "missing hex" workflow directly in the GUI table.
- [ ] Export presets / batch export of multiple SKUs.
- [ ] Settings panel (consent, auto-update interval) in the GUI.
- [ ] Localisation (the UI currently mixes FR/EN).

## v0.4+ — toward a more universal database

The long-term idea is to make SpoolScribe **brand-agnostic**, not Polymaker-only.
Candidate sources (all to be vetted for license compatibility first):

- [x] **Prusament** (Prusa) — via SpoolmanDB + TheFilamentDB. ✓
- [x] **ROSA3D** — via SpoolmanDB. ✓
- [ ] **Bambu Lab**, **eSun**, **Sunlu**, and other common brands.
- [ ] Generic import from the **Open Filament Database** REST API
      (path-based addressing) rather than per-brand scrapers.
- [ ] A brand selector in the UI, with per-brand logos and metadata.
- [ ] Pluggable "source adapters" so adding a brand is a small, isolated change.

> Any new data source MUST be documented in [DATA_SOURCES.md](DATA_SOURCES.md)
> and added to `core.NETWORK_SOURCES` so it appears in the consent disclosure.

## Maybe / nice-to-have

- [ ] Direct NFC writing from within the app (hardware-dependent).
- [ ] Read-back / verify a written tag.

## Non-goals

- No telemetry, accounts, or cloud sync.
- No commercial offering.
- No bundling of trademarked assets beyond what's needed for identification.
