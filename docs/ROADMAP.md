# SpoolScribe roadmap

Current stable: **[v0.3.5](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.3.5)**,
published 1 November 2026. This free-time project has no delivery deadlines.

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

## v0.4.0 — OpenTag3D en préversion

- Encodeur 2.004, sorties NFC Tools et NDEF, choix par lecteur : disponibles dans la [préversion v0.4.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.4.0).
- Contrôles hors réseau, conservation des exports OpenSpool et réglages : [validation](validation/v0.4.0.md).
- Recette des imports NFC Tools et lecture sur matériel réel : non exécutée.
- OpenPrintTag : hors de cette étape.

La passe v0.4.0 précise également les [installations de lecture](PRINTER-CONFIGURATIONS.md) :
connexion, logiciel nécessaire et effet réel, sans assimiler inventaire externe et
reconnaissance par le firmware. La validation matérielle reste à effectuer.
