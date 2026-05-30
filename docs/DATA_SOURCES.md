# Data sources & licensing

SpoolScribe does not own the filament data it displays. It aggregates publicly
available data from the sources listed below. This file documents each source,
its license, and the obligations that come with it.

The application **never accesses any of these sources without your explicit,
per-session consent** (see [PRIVACY.md](PRIVACY.md)).

## Summary

| Source | Maintainer | License | Obligation |
|---|---|---|---|
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) | Donkie & contributors | **MIT** | None (attribution appreciated) |
| [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) | Open Filament Collective / SimplyPrint | **MIT** | None — "free to use, redistribute, and embed in commercial products" |
| [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) | Polymaker (official) | **MIT** | None |
| [TheFilamentDB](https://thefilamentdb.issou.best/) | issou.best | **CC-BY 4.0** | **Attribution required** (see below) |
| Polymaker Wiki | Polymaker | Factual data only | See "Factual data" below |
| Polymaker US Wholesale catalogue | Polymaker | Factual data only | See "Factual data" below |

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
  (treated as **authoritative**, as these match Prusa's published swatches),
  with [TheFilamentDB](https://thefilamentdb.issou.best/) filling any remaining
  gaps (CC-BY 4.0, attribution above).
- **ROSA3D** — colors are taken from
  [SpoolmanDB `rosa3d.json`](https://raw.githubusercontent.com/Donkie/SpoolmanDB/master/filaments/rosa3d.json)
  in **fill-missing** mode only (the project's curated values for the Silk /
  Pastel PLA families are more representative than SpoolmanDB's CSS-approximated
  entries, so they are preserved).

Transparent / translucent variants (e.g. "Red Transparent", "Clear") are left
without a solid HEX on purpose — no authoritative solid color exists — and the
OpenSpool export falls back to `000000` for those.

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

The Polymaker logo and brand names are **trademarks of Polymaker** and are NOT
covered by this project's MIT license. See [TRADEMARKS.md](TRADEMARKS.md).

## Your own generated output

The OpenSpool / NFC JSON files you generate describe **your own physical
spools**. They are yours to use freely.
