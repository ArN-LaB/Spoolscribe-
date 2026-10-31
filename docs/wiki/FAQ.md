# FAQ

## Is this an official Polymaker, Prusa Research or Snapmaker app?

No. SpoolScribe is an **unofficial hobby project**, not affiliated with, endorsed
by, or connected to Polymaker, Prusa Research, ROSA3D or Snapmaker.
See `TRADEMARKS.md`.

## Does it send my data anywhere?

No. There is **no telemetry, no tracking, no account**. The only network access
is the optional, consent-gated database update. See `PRIVACY.md`.

## Is the data free to use?

The code is MIT. Most data sources are MIT; [TheFilamentDB](https://thefilamentdb.issou.best/) is CC-BY 4.0
(attribution provided). Some factual values come from Polymaker's public pages.
Full details: `DATA_SOURCES.md`.

## Do I need the paxx12 firmware?

To have the **[Snapmaker U1](https://snapmaker.com/snapmaker-u1) read tags automatically**, yes — the [paxx12 fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) exposes the
RFID reader. SpoolScribe itself just generates the tag payloads and works on any
machine.

## A SKU is missing or has no color. Can I fix it?

The CLI can add an unknown SKU against an existing product. Both the GUI and
CLI ask for an explicit representative HEX when exporting a reference with an
unknown color. Skipping the color cancels export. Corrections are saved locally
and ordinary updates preserve them. Contributions back upstream are welcome — see
`CONTRIBUTING.md`.

## Which tag hardware do I need?

Any NFC/RFID writer compatible with the tag format your reader expects. See
[[Writing RFID Tags|Writing-RFID-Tags]].

## Can I remove the Polymaker logo?

Yes — delete `data/polymaker_logo.svg`. The app works fine without it.


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
