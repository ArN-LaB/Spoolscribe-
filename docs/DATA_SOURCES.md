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
| [TheFilamentDB](https://thefilamentdb.issou.best/) (legacy, developer snapshot) | issou.best | **CC-BY 4.0** | Historical colour HEX of the curated brands (ROSA3D is absent from the snapshot: a warning, not a failure) | **Attribution required**: see `data/TheFilamentDB-ATTRIBUTION.txt` and below |
| [Printer list](https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers.json) (optional, on click) | This project | **MIT** (repository file) | Printers/readers, firmwares and tag protocols shown in **Mon matériel** | Downloaded only on request; validated; installed only when newer than the bundled copy |
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
| 1000 | **Your corrections**, recorded as source `Utilisateur` (including a deliberate `null`) | Nothing replaces them, ever; a differing source value is listed as `… (correction locale conservée)` |
| 100 | Manufacturer workers: Polymaker, Bambu Lab, SUNLU | Community values and fields of unknown provenance |
| 20 | Open Filament Database | SpoolmanDB values, and its own earlier values |
| 10 | SpoolmanDB | Its own earlier values; fills unknowns left by higher ranks |
| 0 | Fields without provenance (historical catalogue, databases created by an older build) | Replaced by a manufacturer, completed by any source, re-asserted by their own source; checked like any source value |

A lower-ranked source can fill a value the higher rank left unknown. A field of
unknown provenance that already equals the incoming value simply gains that
provenance. Databases created by an earlier preview build (all fields without
provenance) are therefore no longer frozen: the next manufacturer refresh
corrects them.

### Product lines and manufacturers

Some sources list product lines as brands. `scripts/catalogue_sources.BRAND_LINES`
folds them into their manufacturer and keeps the line on the product (`line`):
PolyLite, PolyTerra, PolyMax, PolyFlex, PolyMide, PolySonic, PolyCast, PolySmooth,
PolyWood, PolyDissolve, PolySupport, PolyBox, Panchroma and Fiberon → Polymaker;
PrimaCreator, PrimaSelect, PrimaValue, 3D Prima Basic and PrimaFil → 3D Prima;
Hyper → Creality; Extrafill → Fillamentum. Adapters apply the table at import;
an existing database is migrated in memory when it is loaded (174 → 165 brands
on the first real database reviewed) and the brand metadata of the manufacturer
wins over the line's.

### Material families and filament grouping

`core.material_family` derives a family (`core.MATERIAL_FAMILIES`: PLA, PETG,
PCTG, PET, ABS, ASA, TPU, TPE, TPC, TPI, PA, PC, PP, PVA, HIPS, PEEK, PEKK, PEI,
PPSU, PSU, PES, PPS, PBT, POM, PMMA, PVB, PVDF, PHA, PCL, EVA, PVC, CPE, BVOH,
PPE, PEBA) and a variant from each source label: `ABS+MATTE` → ABS "+Matte",
`EASYASA` → ASA "Easy", `HTPLA+` → PLA "HT +", `PA6-CF` → PA "PA6 CF". The
family only drives the sidebar filter; the source label and the exported
OpenSpool `type` are unchanged.

`core.group_filaments` shows one row per filament (manufacturer + product +
colour name): spool sizes, refills and diameters become `variants`
(`variant_count`), and the HEX shown is the best-documented one (user, then
manufacturer, then OFD, then SpoolmanDB, then unknown provenance; ties go to the
most frequent value). `hex_variants` counts the distinct hues the sources gave
to that filament; the card warns when it exceeds one.

A matched source record whose local product record is missing (a historical
orphan) is healed with the source product instead of aborting the refresh.

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
  corrected explicitly, which also makes it yours. Only your own corrections
  (source `Utilisateur`) are exempt; fields of unknown provenance are checked
  like any source value.
- **Unknown stays unknown.** Missing physical values are `null`; an Orca profile
  without plate temperature gives an unknown bed, not 0 °C; no colour, alpha or
  temperature is inferred from a product name.
- **Conditional downloads.** OFD, SpoolmanDB and the Bambu index are fetched
  with `If-None-Match`; an unchanged source ends the step without download.
- **Throttling and slow links.** `429`/`503` answers are retried after the
  server's `Retry-After` (1–30 s, 5 s by default), twice at most, then the source
  is reported as saturated. Workers have fixed budgets (OFD 900 s, Bambu 600 s,
  SpoolmanDB and Polymaker 300 s, SUNLU 180 s); a timeout ends the step as
  unreachable and keeps the local data.

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
24,521 references (165 manufacturers once product lines are folded, about
15,500 filaments once packagings are grouped). A reference is a source
colour/size/packaging record, not necessarily a unique formulation or SKU.

OFD snapshot: commit
[`1dda27a4afcc4f9200b5b3867e85e75f8e1ea147`](https://github.com/OpenFilamentCollective/open-filament-database/tree/1dda27a4afcc4f9200b5b3867e85e75f8e1ea147),
archive SHA-256 `6830802bd85f00c8979ea086414c2e1f3a76ec5d931c295bd779b72d3087bd6e`.
SpoolmanDB snapshot: [`filaments.json`](https://donkie.github.io/SpoolmanDB/filaments.json),
SHA-256 `06f1788582d110008bec27a81ecd98b2abc963d22adf7149802967cc7a721c0c`.
Both collected on 2026-10-31; `data/catalogue_*_audit.json` record counts, hashes,
rejected and incomplete records. Twenty OFD brand folders have no usable variant.

### Logos

147 logos (118 PNG, 29 SVG) are listed in `data/brand_logos/manifest.json`
with their hash, size and provenance; twenty-one OFD images were excluded
(`.github/catalogue-logo-exclusions.json`) and 14 complementary manufacturers
have none, so those brands show their name instead. **A transparent background
is mandatory**: `tests/test_logos.py` checks that every raster logo has
transparent corners (three filled square/round logos are marked
`filled_shape` and exempt) and that no SVG carries a full-size background
rectangle. `.github/scripts/import_brand_logos.py` imports reviewed logos from a
`sources.json` review file (official site, press kit, GitHub, Wikimedia), makes
a uniform background transparent, trims and bounds the image and records
`logo_source` (`url`, `source_kind`, `licence_note`); its `--retouch-existing`
mode reprocesses the logos already listed. The bundled manifest takes precedence
over the `logo_path` a database remembers, so a replaced logo shows without a
refresh. Official logos are being re-sourced brand by brand through that
process; until a brand is imported, its reviewed OFD image stays. The
application keeps colours, proportions and transparency, adds a one-device-pixel contrast edge only when the artwork would be unreadable
on the current background, and shows the name for bitmaps under 24 px. Runtime updates never download or
approve a logo. The MIT licence of the OFD repository covers its data, not the
trademarks it depicts: see [TRADEMARKS.md](TRADEMARKS.md).

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

### Screen-feedback corrections, 1 November 2026

OFD product-line metadata with a website no longer raises an error after its variants
were imported. Historical brand-line keys are retained as aliases when canonicalizing
manufacturers, so the no-deletion storage guard remains active. Partial enrichment
that would invert a temperature range keeps the previous pair and records a conflict.
Presentation grouping keeps diameter/grade/transparency distinctions; a normalized
colour label is not permission to overwrite differing source HEX values. See
[the corrective validation](archive/v0.3.0/VALIDATION-RETOURS-v0.3.0.md) for measurements and remaining gaps.


### Coverage shown in the application

The catalogue is not exhaustive. Polymaker has a direct manufacturer catalogue;
Bambu Studio enriches existing Bambu records with profile characteristics, and
SUNLU currently enriches existing PLA records. Neither enrichment is a complete
catalogue of that manufacturer's colours or products. OFD and SpoolmanDB broaden
coverage but may omit products, packaging or fields; SpoolmanDB currently adds
manufacturers absent from the principal catalogue rather than merging every
same-brand community record.

The source chooser shows the last recorded analysis counts, when available,
including incomplete records. Counts describe that snapshot, not the total
manufacturer range and not the number of unique selectable filaments after
reconciliation. A successful refresh means the selected sources were processed;
colour differences and uncertain identities can remain. The report labels this
**Sources actualisées** and shows unresolved counts separately.

The native macOS package now resolves the `Frameworks/data` → `Resources/data`
link before applying the path containment check. Historical Polymaker, Prusament
and ROSA3D artwork also has a bundled fallback independent of downloaded metadata.
Path escapes outside the resolved data directory remain rejected. Frozen probes
check all manifest paths and render the three historical manufacturers' logos.


### Printer presentation assets

The visual workspace adds original manufacturer images for U1, X1 Carbon and
QIDI Plus4 and a separate presentation module. These files do not change the
filament catalogue or printer compatibility flags. They are bundled rather
than downloaded at runtime; see [PRINTER_VISUALS.md](PRINTER_VISUALS.md).
