# SpoolScribe Wiki

Welcome! This wiki collects user-facing guides for **SpoolScribe** — preparing
[OpenSpool](https://github.com/spuder/OpenSpool) / NFC spool-tag data for the
open-firmware **[Snapmaker U1](https://snapmaker.com/snapmaker-u1)** and other
OpenSpool readers.

> These pages live in the repo under `docs/wiki/` as a starter. Copy them into
> the GitHub Wiki (the **Wiki** tab) to publish and edit them online. Links to
> the repository documentation are absolute so they keep working there.

## Pages

- [[Getting Started|Getting-Started]] — install, first run, first tag
- [[Writing RFID Tags|Writing-RFID-Tags]] — from JSON to a programmed tag
- [[Snapmaker U1 & paxx12|Snapmaker-U1-and-paxx12]] — the open firmware context
- [[Updating the Database|Updating-the-Database]] — sources, consent, cadence, backups
- [[FAQ|FAQ]] — common questions

## The catalogue in one paragraph

The installer contains no filament data. On first launch you choose the sources
(Open Filament Database, SpoolmanDB, Polymaker, Bambu Lab, SUNLU…) and the app
downloads them into your user folder: about 24,000 references from 170+
manufacturers. Manufacturer facts outrank community values, your own corrections
outrank both, and anything uncertain is held aside instead of merged. Internal
`OFD-…` / `SMDB-…` identifiers are not manufacturer SKUs; the *Référence*
column shows the manufacturer article number when the source provides one.
Filters (manufacturer, material, data state « État des données »), search,
two-level header sorting and 250-row pages apply to the whole catalogue. Logos
are reviewed local assets; a readable name replaces an unsuitable image.

Reference documentation in the repository:
[data sources](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_SOURCES.md),
[data contract](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_FORMAT.md),
[privacy](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md),
[interface guide (French)](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/UX-v0.3.0.md),
[roadmap](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/ROADMAP.md).

## Disclaimer

SpoolScribe is an unofficial hobby project, not affiliated with any filament
manufacturer or with Snapmaker. See
[TRADEMARKS.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/TRADEMARKS.md).
