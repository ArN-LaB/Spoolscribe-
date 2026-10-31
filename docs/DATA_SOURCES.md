# Data sources & licensing

SpoolScribe does not own the filament data it displays. It aggregates publicly
available data from the sources listed below. This file documents each source,
its license, and the obligations that come with it.

The application **never accesses any of these sources without your explicit,
saved consent** (see [PRIVACY.md](PRIVACY.md)).

## Summary

| Source | Maintainer | License | Obligation |
|---|---|---|---|
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) | Donkie & contributors | **MIT** | Retain copyright and permission notice when redistributing substantial portions |
| [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) | Open Filament Collective / SimplyPrint | **MIT** | Retain the upstream copyright and permission notice |
| [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) | Polymaker (official) | **MIT** | Retain the upstream copyright and permission notice |
| [TheFilamentDB](https://thefilamentdb.issou.best/) | issou.best | **CC-BY 4.0** | **Attribution required** (see below) |
| Polymaker Wiki | Polymaker | Factual data only | See "Factual data" below |
| Polymaker US Wholesale catalogue | Polymaker | Factual data only | See "Factual data" below |

## Runtime policy after the UX revision

The installer no longer contains catalogue snapshots. The source picker selects
which network workers run; the resulting database is cached in the user directory.
Manufacturer-owned fields outrank community fields when provenance proves that
no personal edit has occurred. Unknown source-owned fields may be complemented
by a lower-priority source. Explicit user edits/nulls remain protected.

| Source | Implemented use | Identity / limits |
|---|---|---|
| Polymaker wholesale, official | Product variants, article numbers and explicit HEX | Manufacturer SKU, size/packaging, exact names and reviewed historical rename mappings; no guessed physics |
| OFD, MIT | Broad manufacturer/material/color/size catalogue | Namespaced source IDs; exact reconciliation with existing records |
| SpoolmanDB, MIT | Complementary catalogue and facts | Exact identity matches merge; ambiguous same-brand records stay in the pending-match audit |
| [Bambu Studio manufacturer profiles](https://github.com/bambulab/BambuStudio/tree/master/resources/profiles/BBL/filament) | Directly stated density, diameter and nozzle range from Bambu `@base` profiles | Exact family-name matching; printer/plate-specific temperatures and G-code are not generalized or executed |
| [SUNLU official PLA](https://www.sunlu.com/products/pla-3d-printing-filament) | Density, bed range, explicit color codes | Exact SUNLU PLA family/color; nozzle ranges tied to print speed are not flattened |

Polymaker initializes first; community catalogues can complement missing factual
values. Bambu/SUNLU enrichment follows identity acquisition and uses the same
manufacturer-first field priority. Existing legacy values without provenance are
protected conservatively rather than retroactively classified as automatic data.
A full-refresh date applies to **the selected source set**, recorded with the result
of every step. Deselecting a source does not erase data. No exact-identity duplicate
is inserted; uncertain identities are not claimed to be resolved.

### Other sources researched

- [eSUN PLA+ manufacturer page](https://www.esun3d.com/pla-pro-product) and
  [official printer-specific parameters](https://www.esun3d.com/uploads/eSUN-Fast-filaments-print-parameters2.pdf):
  identified, not imported automatically. Product revision and printer-specific
  table context need a dedicated parser and fixtures before normalizing values.
- [PrusaSlicer settings](https://github.com/prusa3d/PrusaSlicer-settings): official,
  versioned and printer-dependent. A guessed unversioned `PrusaResearch.ini` URL
  returned 404; no fallback data were invented. No automatic adapter in this pass.
- [SimplyPrint](https://simplyprint.io/alternatives/filameter) also uses OFD; treating
  it as an independent catalogue would duplicate the same upstream dataset.
- [SpoolSense](https://spoolsense.org/intro/how-it-works/) is a reader/integration
  project, not an additional independent filament catalogue ingested here.
- [OpenPrintTag](https://openprinttag.org/) publishes a data-format specification;
  that is not a second manufacturer catalogue. Its encoder is outside this pass.

The manufacturer parsers store factual fields and source URLs, not whole product
pages or executable printer profiles. Upstream licenses and trademark rights apply.

## Repository regression snapshot — initial v0.3.0 development pass (not installed)

The original `data/polymaker_db.json` is unchanged. Additive offline files contain:

| Source | File | Additional source brands | References |
|---|---|---:|---:|
| OFD source tree | `data/catalogue_ofd.json` | 157 | 22,838 |
| SpoolmanDB compiled catalogue | `data/catalogue_spoolman.json` | 14 | 599 |

The historical repository fixture, together with the three curated brands, exposes **174 source brand labels
and 24,521 references**. A reference identifies a source color/size/packaging
record, not necessarily a unique physical formulation or manufacturer SKU.
The source can represent sub-brands as independent manufacturers.

OFD snapshot: commit
[`1dda27a4afcc4f9200b5b3867e85e75f8e1ea147`](https://github.com/OpenFilamentCollective/open-filament-database/tree/1dda27a4afcc4f9200b5b3867e85e75f8e1ea147),
archive SHA-256 `6830802bd85f00c8979ea086414c2e1f3a76ec5d931c295bd779b72d3087bd6e`.
The adapter reads `brand.json → material.json → filament.json → variant.json →
sizes.json` from the official HTTPS archive without extracting archive paths.
The static REST API was evaluated; some endpoints redirected or failed, so the
archive is the implemented transport. It uses the same canonical path-based data.

SpoolmanDB snapshot: [`filaments.json`](https://donkie.github.io/SpoolmanDB/filaments.json),
SHA-256 `06f1788582d110008bec27a81ecd98b2abc963d22adf7149802967cc7a721c0c`.
Only manufacturers not covered by the curated/OFD catalogues are added, including
Fusion, R3D, CR3D, Filament Unger and REDLINE FILAMENT. Exact normalized brand names
and the explicit eSUN/ROSA aliases are used; there is no fuzzy product merge.

Both snapshots were collected on 2026-10-31. The `data/catalogue_*_audit.json`
files record counts, hashes, rejected records, incomplete records and exclusions.
Twenty OFD brand folders contain no usable variant. The curated Polymaker,
Prusament and ROSA3D sets retain priority to avoid ambiguous cross-source joins.
Unknown values stay unknown; public community data are not a manufacturer warranty.

The upstream MIT notices are retained in `data/brand_logos/OFD-LICENSE.txt` and
`data/SpoolmanDB-LICENSE.txt`. Original licenses and trademark rights still apply.

### Logo quality

137 additional OFD logos passed format, dimensions and visual contact-sheet review.
SVG artwork stays vector-based; unnecessary transparent margins are cropped.
Raster images are decoded and normalized without upscaling. Twenty unsuitable
images were excluded (tiny/blurred graphics, product photos, incomplete artwork);
14 complementary manufacturers have no reviewed logo in this snapshot. These
34 brands use a readable name fallback. See `data/brand_logos/manifest.json`,
`data/catalogue_ofd_audit.json` and `.github/catalogue-logo-exclusions.json`.

Selection never downloads a remote image. Logos keep their colors, proportions and
transparent surroundings; the UX revision removes added rectangular plates and uses a subtle outline.
A future upstream logo change needs a new asset review before bundling.

### Update and import contract

`sync_universal_catalogue.py` and `sync_spoolman_catalogue.py` use the pure adapters
in `scripts/catalogue_sources.py`. They add missing fields/references through the
existing revision-aware storage. Local values, nulls and corrections win. An
unavailable source reports failure; rejected records make an update partial and
prevent advancement of the complete-refresh date. Incomplete but structurally
valid data are explicitly distinguishable from a failed source request.

Runtime hosts are disclosed in `core.NETWORK_SOURCES` and the source picker.
Existing consent is renewed for this source revision.
See [DATA_FORMAT.md](DATA_FORMAT.md) for identifiers, units and export validation.

## Attribution required: TheFilamentDB (CC-BY 4.0)

Hex color data derived from TheFilamentDB is licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

> Color data: © TheFilamentDB (https://thefilamentdb.issou.best/), CC-BY 4.0.

This attribution is retained here and in the application's "Sources" disclosure.

## Multi-brand color enrichment (Prusament & ROSA3D)

Beyond Polymaker, SpoolScribe enriches the **color HEX** of other brands from
the same public databases, cross-referenced by material + color name:

- **Prusament** — colors are taken from
  [SpoolmanDB `prusament.json`](https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/prusament.json)
  (used to fill missing values; existing local corrections are preserved),
  with [TheFilamentDB](https://thefilamentdb.issou.best/) filling any remaining
  gaps (CC-BY 4.0, attribution above).
- **ROSA3D** — colors are taken from
  [SpoolmanDB `rosa3d.json`](https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/rosa3d.json)
  in **fill-missing** mode only (the project's curated values for the Silk /
  Pastel PLA families are more representative than SpoolmanDB's CSS-approximated
  entries, so they are preserved).

Transparent / translucent variants (e.g. "Red Transparent", "Clear") are left
without a solid HEX on purpose — no authoritative solid color exists. Export
requires an explicitly chosen representative HEX; it never substitutes `000000`.
A user-provided `alpha` can express transparency. Additional colors are retained
when explicitly provided, but reader support varies (Paxx12-24 OpenRFID does not
use additional colors). No color or transparency is inferred from a product name.

## Factual data (Polymaker Wiki & Wholesale catalogue)

SpoolScribe also reads **factual values** — HEX color codes, nozzle/bed
temperatures, density, SKU identifiers — published by Polymaker on its public
wiki and wholesale catalogue.

- Individual facts (a hex code, a temperature) are **not protected by
  copyright**; they are data, not creative expression.
- These values are used solely for **interoperability** (to let you tag your
  own spools), under nominative fair use of the product names.
- SpoolScribe does **not** redistribute Polymaker's pages, layout, or any
  creative compilation; it stores only the minimal factual fields needed.

If Polymaker (or any source) requests removal of specific data, open an issue
and it will be removed promptly.

## Brand assets

Manufacturer names and logos remain **trademarks of their respective owners** and are NOT
covered by this project's MIT license. See [TRADEMARKS.md](TRADEMARKS.md).

## Your own generated output

The OpenSpool / NFC JSON files you generate describe **your own physical
spools**. They are yours to use freely.
