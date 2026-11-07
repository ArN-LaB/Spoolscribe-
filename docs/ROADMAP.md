# SpoolScribe roadmap

Current Desktop stable: **[v0.8.1](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.1)**,
published 8 November 2026. [Release policy](RELEASE_POLICY.md). This free-time
project has no delivery deadlines.

The sections below record the capabilities and limits at each historical stage.

## Delivered in v0.3.5

- [x] English, French, Spanish and Simplified Chinese UI; system detection and English fallback.
- [x] Saved language choice and Restart now / Later after a change.
- [x] Linked manufacturer/material filters and compatible choice counts.
- [x] Clear-search control and explicit Refresh catalogue action.
- [x] Animated README logo generated from the existing vector artwork.
- [x] 267 tests per configuration: Linux/Python 3.10 and 3.12, Windows/Python 3.12, macOS/Python 3.12.
- [x] Three native builds, four-language frozen probes, 194 resources checked against Git, three ZIPs and three SHA-256 files published.

See [release validation](validation/v0.3.5.md) and [changelog](../CHANGELOG.md).

## Delivered catalogue foundation

- [x] OFD/SpoolmanDB adapters and manufacturer enrichment with provenance.
- [x] Unknown values preserved, uncertain matches held aside, protected personal copies and favourites.
- [x] Grouped spool references, preferred packaging, columns and two-level sorting.
- [x] Selectable sources, consent, offline cache, atomic writes, backups and restoration protection.
- [x] Data-driven printer compatibility, reviewed logos and printer photographs.
- [x] OpenSpool 1.0, NTAG215/216 capacity checks, essential/full profiles and preview/export parity.
- [x] Empty first installation; catalogue downloaded after consent.

## Verification still needed

- [ ] Human desktop acceptance on all three platforms.
- [ ] Physical NTAG215/216 writing and read-back with a compatible printer.
- [ ] Native-speaker review of translations.
- [ ] More reviewed manufacturer logos and printer images with traceable origins.
- [ ] Resolve ambiguous matches using documented product evidence.

## Possible future work

- Additional reviewed manufacturer adapters; no generic scraping or invented values.
- An explicit editor for unresolved matches and wider catalogue editing.
- Export presets and batch workflows if a concrete need is confirmed.
- Other tag encoders, such as OpenPrintTag, as separate protocol/hardware work.
- Direct writing/read-back only with an explicit supported-hardware scope.

Keep the application offline-first, consent-gated and free of telemetry/accounts.
Do not duplicate Spoolman, migrate RFID associations or change printer firmware.

The [previous detailed roadmap](https://github.com/ArN-LaB/Spoolscribe-/blob/5d652232e5b989028f13704ad6ca13b65724332b/docs/archive/v0.3.0/ROADMAP-before-v0.3.5.md) preserves
the v0.2.x/v0.3.0 history and screen-feedback campaigns.

## v0.4.0 — OpenTag3D pre-release

The [v0.4.0 pre-release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.4.0)
added the 2.004 encoder, NFC Tools/NDEF output and reader-specific choices.
[Validation](validation/v0.4.0.md) covered offline checks and preservation of
OpenSpool exports/preferences. Physical NFC Tools import/read-back was not
performed; OpenPrintTag was outside scope.

It also clarified [reader setups](PRINTER-CONFIGURATIONS.md): connections,
software requirements and actual effects, distinguishing external inventory from
firmware recognition. Hardware acceptance remained unmeasured.

## v0.5.0 — UX and colour search, pre-release

- [New pre-release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.5.0): colour proximity with explicit inclusive limits, protected in-card editing, compact provenance and guided export.
- Unified filters, visual printer choices, documented photos and content-aware dialogs.
- [Validation](validation/v0.5.0.md) separates software checks from real printer/RFID acceptance.
- At that publication, v0.3.5 stayed stable. The later v0.8.0 promotion separates software stability from hardware evidence.
- Autonomous QR and any Spoolman bridge remain separate work; neither is included in this release.

## v0.6.0 — SSQR1 digital transfer, pre-release

- Complete NFC message in one offline QR, PNG/SVG output and a validated SSQR1
  digital contract for OpenSpool 1.0 and OpenTag3D 2.004.
- [Validation](validation/v0.6.0.md) distinguishes independent software scans from
  physical phone, tag and printer acceptance. No NFC protocol or compatibility extension.
- Companion remains a separate future project. Printing, D101 and Bluetooth are deferred.
- At that publication, v0.3.5 remained stable. Earlier tags and binaries stay unchanged.

## v0.7.0 — colour measurements, pre-release

- HEX/RGB/CIELAB entry, labelled paste and user-confirmed CSV/TSV mapping.
- Separate local measurement registry, original values/conditions/provenance,
  exact reference links and protected backups/restoration.
- Indicative CIEDE2000 targets against declared catalogue HEX; Lab ranking only
  with documented D65/2° conditions. Existing HEX/NFC/SSQR1 contracts retained.
- [Guide](COLOUR_MEASUREMENTS.md) · [Validation and remaining limits](validation/v0.7.0.md).
- No instrument SDK, USB/Bluetooth driver or Companion development in this step.
  Authentic manufacturer exports and physical colour/RFID acceptance remain untested.
- At that publication, v0.3.5 was the latest stable release; later stable releases superseded it.

## v0.8.0 — colour and QR journey refinements, Desktop stable

- Guided Lab/RGB/file entry and explicit, user-declared device presets.
- Temporary ΔE list column, simpler cards and dialogs that grow and shrink.
- OpenTag3D temperature proposals reviewed once, valid saved values reused.
- Screen-only QR by default, optional printing references and one Companion page.
- OpenSpool, OpenTag3D and SSQR1 wire contracts unchanged. Physical printer/tag
  acceptance and published mobile apps remain separate validation work.
- [Validation](validation/v0.8.0.md) · [Companion availability](COMPANION.md).

## v0.8.1 — preferences, recovery safety and notarised macOS

Six settings tabs, portable preference previews, local unencrypted ZIP backups,
restoration/undo and persistent recovery conflicts are delivered. Provenance,
About information, opt-in diagnostics and shared printer setups are coherent.
Windows file-handle compatibility is tested on CI; new Windows/Linux builds and
a new Developer ID signed, Apple-notarised arm64 macOS archive are published.

[Validation](validation/v0.8.1.md) retains the exact test/platform limits. P0 is
not claimed fixed. Physical NFC/printing and AES-256-GCM remain separate future
work; no earlier release's binaries are replaced.
