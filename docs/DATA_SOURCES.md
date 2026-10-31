# Data sources & licensing

SpoolScribe does not own the filament data it displays. It downloads publicly
available data from the sources below, after your explicit, saved consent (see
[PRIVACY.md](PRIVACY.md)). This file documents each source, its licence, how
the adapter uses it and what it refuses to guess.

## Summary

| Source | Maintainer | Licence / basis | Used for | Obligation |
|---|---|---|---|---|
| [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) (OFD) | Open Filament Collective | **MIT** (data) | Broad manufacturer / material / colour / size catalogue, read from the official repository archive | Keep the upstream notice (`data/brand_logos/OFD-LICENSE.txt`). Logos in that repository remain their owners' trademarks (see below) |
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) | Donkie & contributors | **MIT** | Complementary references for manufacturers not covered by the other sources | Keep the upstream notice (`data/SpoolmanDB-LICENSE.txt`) |
| Polymaker US wholesale catalogue | Polymaker | Public Shopify product JSON; factual values | Product variants, article numbers, explicit colour HEX, packaging | Facts only; see "Factual data" |
| [Bambu Studio profiles](https://github.com/bambulab/BambuStudio/tree/master/resources/profiles/BBL/filament) | Bambu Lab | Repository under **AGPL-3.0**; only facts are kept | Density, diameter and nozzle range of `Bambu … @base` profiles, plus the profile URL | No profile, G-code or printer setting is redistributed |
| [SUNLU PLA product page](https://www.sunlu.com/products/pla-3d-printing-filament) | SUNLU | Public product page; factual values | Density, bed range, official colour codes of SUNLU PLA | Facts only |
| [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) (optional source) | Polymaker (official) | **MIT** | OrcaSlicer profiles for the Snapmaker U1 (temperature overrides at export) | Keep the upstream notice |
| [TheFilamentDB](https://thefilamentdb.issou.best/) (legacy, developer snapshot) | issou.best | **CC-BY 4.0** | Historical colour HEX of the curated brands | **Attribution required**: see `data/TheFilamentDB-ATTRIBUTION.txt` and below |
| Manufacturer logos | Respective brands | **Trademarks**, not covered by any of the licences above | Identification of the selected brand in the interface | Identification only; removal on request ([TRADEMARKS.md](TRADEMARKS.md)) |

A new source is added as a group in `core.SOURCE_GROUPS` (name, hosts, worker
scripts), documented here and in PRIVACY.md. The consent dialog and
`core.NETWORK_SOURCES` are derived from that table; there is no second list to
maintain.

## Priority and merge rules

Every imported field carries its provenance (`_field_sources`: source, rank,
value). When sources disagree:

| Rank | Owner | Can replace |
|---:|---|---|
| — | **Your corrections** (a field without provenance, including a deliberate `null`) | Nothing replaces them, ever |
| 100 | Manufacturer workers: Polymaker, Bambu Lab, SUNLU | Community values that have not been edited |
| 20 | Open Filament Database | SpoolmanDB values, and its own earlier values |
| 10 | SpoolmanDB | Its own earlier values; fills unknowns left by higher ranks |

Historical records without a `source` field are treated as user-owned by
precaution. A lower-ranked source can fill a value the higher rank left unknown.

Identity between sources is never guessed from material and colour alone. Two
records are the same filament when they share the brand, a manufacturer article
number **and** a compatible colour (same name, or same HEX under another name)
with compatible packaging, or when brand, product name and colour match
exactly with compatible packaging. Product grades stay distinct (`PLA+` is not
`PLA`). Reviewed historical Polymaker renames are explicit aliases. Anything
ambiguous is listed in `_pending_source_matches` and kept out of the table.
Every absorbed source record is listed in `_source_aliases` of the record that
kept it.

SpoolmanDB only adds manufacturers that no other source already covers.

## Guard rails

- **A source cannot empty its own value.** A field the source stops publishing
  keeps its local value; the case is reported as a conserved conflict
  (`… (valeur retirée par la source, conservée)`).
- **A shrunken source is refused.** A refresh returning less than half of the
  references the same source delivered before is rejected before merging
  (`check_source_shrink`); the local data stay untouched.
- **Implausible values are flagged, not exported.** A black HEX (`000000`) for a
  light colour name, a white HEX for a dark name, a nozzle temperature outside
  120–500 °C, a bed temperature outside 0–200 °C or a bed maximum of 0 °C, a
  density outside 0.5–4.0 g/cm³ or a diameter outside 1.0–3.2 mm mark the record
  **À vérifier** in the data-state column. Export is refused until the value is
  corrected explicitly, which also makes it yours. Your corrections and
  historical records are never second-guessed.
- **Unknown stays unknown.** Missing physical values are `null`; an Orca profile
  without plate temperature gives an unknown bed, not 0 °C; no colour, alpha or
  temperature is inferred from a product name.
- **Conditional downloads.** OFD, SpoolmanDB and the Bambu index are fetched
  with `If-None-Match`; an unchanged source ends the step without download.

## Adapter limits

| Source | Implemented use | Not done |
|---|---|---|
| Polymaker wholesale | Variants, article numbers, packaging, explicit HEX from option labels, reviewed rename aliases | No guessed temperatures or density; at most 40 catalogue pages |
| OFD | `brand → material → filament → variant → sizes` from the archive, namespaced `OFD-` identifiers, logos reviewed offline | Archive links are skipped; the static REST API is not used |
| SpoolmanDB | `SMDB-` references with exact normalized brand names and the explicit eSUN/ROSA aliases | No fuzzy product merge; covered manufacturers are skipped |
| Bambu Studio | Density, diameter, nozzle range of `@base` profiles matched to existing Bambu families by exact name (at most 600 profiles) | Plate-specific temperatures and G-code are never generalized or executed |
| SUNLU | Density, bed range and colour table of the PLA page, matched to existing SUNLU PLA families | Speed-dependent nozzle ranges are not flattened; an unrecognized page fails the step |

Manufacturer enrichment runs after the catalogues that establish identity and
needs an existing family to attach to; it never creates references.

### Other sources researched, not imported

- [eSUN PLA+ page](https://www.esun3d.com/pla-pro-product) and
  [printer-specific parameters](https://www.esun3d.com/uploads/eSUN-Fast-filaments-print-parameters2.pdf):
  revision- and printer-dependent tables need a dedicated parser and fixtures.
- [PrusaSlicer settings](https://github.com/prusa3d/PrusaSlicer-settings): official,
  versioned and printer-dependent; no adapter yet.
- [SimplyPrint](https://simplyprint.io/alternatives/filameter) republishes OFD;
  [SpoolSense](https://spoolsense.org/intro/how-it-works/) is a reader project;
  [OpenPrintTag](https://openprinttag.org/) is a tag format, not a catalogue.

## Repository regression snapshot (not installed)

`data/polymaker_db.json` keeps the original curated records. The additive
offline files are test fixtures and are excluded from installers:

| Source | File | Source brands | References |
|---|---|---:|---:|
| OFD source tree | `data/catalogue_ofd.json` | 157 | 22,838 |
| SpoolmanDB compiled catalogue | `data/catalogue_spoolman.json` | 14 | 599 |

With the three curated brands the fixture exposes 174 source brand labels and
24,521 references. A reference is a source colour/size/packaging record, not
necessarily a unique formulation or SKU; a source can list sub-brands as brands.

OFD snapshot: commit
[`1dda27a4afcc4f9200b5b3867e85e75f8e1ea147`](https://github.com/OpenFilamentCollective/open-filament-database/tree/1dda27a4afcc4f9200b5b3867e85e75f8e1ea147),
archive SHA-256 `6830802bd85f00c8979ea086414c2e1f3a76ec5d931c295bd779b72d3087bd6e`.
SpoolmanDB snapshot: [`filaments.json`](https://donkie.github.io/SpoolmanDB/filaments.json),
SHA-256 `06f1788582d110008bec27a81ecd98b2abc963d22adf7149802967cc7a721c0c`.
Both collected on 2026-10-31; `data/catalogue_*_audit.json` record counts, hashes,
rejected and incomplete records. Twenty OFD brand folders have no usable variant.

### Logos

137 OFD logos passed a format, size and contact-sheet review; twenty were
excluded (`.github/catalogue-logo-exclusions.json`) and 14 complementary
manufacturers have none, so 34 brands show their name instead. The build script
(`.github/scripts/build_catalogue_snapshot.py`) crops transparent SVG margins and
normalizes raster images; the application keeps colours, proportions and
transparency, adds a thin outline and shows the name for bitmaps under 24 px.
Hashes are recorded in `data/brand_logos/manifest.json`. Runtime updates never
download or approve a logo. The MIT licence of the OFD repository covers its
data, not the trademarks it depicts: see [TRADEMARKS.md](TRADEMARKS.md).

## Attribution required: TheFilamentDB (CC-BY 4.0)

Colour HEX values derived from TheFilamentDB are licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

> Colour data: © TheFilamentDB (https://thefilamentdb.issou.best/), CC-BY 4.0.
> Values were normalized to six-digit HEX and matched to products by material
> and colour name; no other change.

The attribution is kept in `data/TheFilamentDB-ATTRIBUTION.txt`, here and in the
application's About dialog. The developer snapshot `data/thefilamentdb.jsonl.gz`
is not bundled in installers.

## Curated colour enrichment (Prusament & ROSA3D)

- **Prusament** — colours from [SpoolmanDB `prusament.json`](https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/prusament.json)
  (fill-missing; local corrections preserved), then TheFilamentDB for remaining gaps.
- **ROSA3D** — colours from [SpoolmanDB `rosa3d.json`](https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/rosa3d.json)
  in fill-missing mode; the curated Silk / Pastel values are kept.

Transparent, translucent and multicolour variants keep no solid HEX on purpose.
Export requires an explicitly chosen representative HEX; `000000` is never
substituted. An explicit `alpha` can express transparency; additional colours are
retained when the source provides them (reader support varies).

## Factual data (manufacturer pages)

Individual facts — a HEX code, a temperature, a density, an article number — are
data, not creative expression, and are used for interoperability only, under
nominative use of the product names. SpoolScribe stores the minimal factual
fields and the source URL, never the pages, layouts or profile files. If a
manufacturer or any source asks for removal of specific data, open an issue and
it will be removed.

## Your own generated output

The OpenSpool / NFC JSON files you generate describe your own spools. They are
yours to use freely.
