# SpoolScribe Wiki

Welcome! This wiki collects user-facing guides for **SpoolScribe** — writing
[OpenSpool](https://github.com/spuder/OpenSpool) / NFC spool tags for the open-firmware **[Snapmaker U1](https://snapmaker.com/snapmaker-u1)**.

> These pages live in the repo under `docs/wiki/` as a starter. Copy them into
> the GitHub Wiki (the **Wiki** tab) to publish and edit them online.

## Pages

- [[Getting Started|Getting-Started]] — install and first run
- [[Writing RFID Tags|Writing-RFID-Tags]] — from JSON to a programmed tag
- [[Snapmaker U1 & paxx12|Snapmaker-U1-and-paxx12]] — the open firmware context
- [[Updating the Database|Updating-the-Database]] — consent & data sources
- [[FAQ|FAQ]] — common questions

## Disclaimer

SpoolScribe is an unofficial hobby project, not affiliated with Polymaker,
Prusa Research, ROSA3D or Snapmaker. See `TRADEMARKS.md` in the repository.


## Universal catalogue (v0.3.0 development)

The repository regression fixture contains 24,521 references across 174 brand
labels; it is not bundled. The live catalogue depends on selected sources. Use the manufacturer/material/completeness filters together with the
search box. Click a column header for ascending/descending order; right-click
for primary/secondary sorting and visible columns. Both views
show 250 results per page, while filters/search operate on the entire catalogue.

Internal OFD/SMDB references are distinct from a manufacturer SKU. Unknown
physical data can be filled using **Compléter / corriger les caractéristiques…**;
these edits affect the product's variants and are preserved during updates.
Logos are local reviewed assets; a readable manufacturer name replaces an
unsuitable or unavailable image.

Choose **NTAG215** or **NTAG216** before export. Complete exports retain metadata;
the automatic choice uses the essential profile when required, omitting descriptives/logos while preserving printing
values and colors. The inspector shows the exact exported JSON. See the
[NFC guide](Writing-RFID-Tags.md), [data contract](../DATA_FORMAT.md) and
[roadmap](../ROADMAP.md). These development changes are not a published v0.3.0 release.

The latest interaction and printer guidance is in [UX v0.3.0](../UX-v0.3.0.md).
Settings persist; logos have no added rectangular plate; the automatic NFC profile
chooses what fits. Technical overrides are under **Réglages avancés**.
