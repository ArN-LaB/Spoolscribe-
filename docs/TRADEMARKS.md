# Trademarks & non-affiliation

**SpoolScribe is an unofficial, community, hobby project. It is not affiliated
with, endorsed by, sponsored by or connected to any filament manufacturer, to
Snapmaker, or to any other company mentioned.**

## Trademarks

Product names, brand names and logos are the property of their respective
owners. They are used only for **identification and interoperability**
(nominative use), so that you can tag the spools you already own.

Non-exhaustive list of third-party trademarks referenced:

- **Polymaker®**, **Panchroma™**, **PolyTerra™**, **PolyLite™**, **PolyDryer™**,
  **PolyBox™**, **Fiberon™** — Polymaker.
- **Snapmaker®** — Snapmaker.
- **Bambu Lab®**, **AMS™**, **Bambu Studio** — Bambu Lab.
- **Prusament®**, **PrusaSlicer** — Prusa Research.
- **SUNLU**, **eSUN**, **ROSA3D**, **Anycubic**, **Creality**, **ELEGOO** and the
  other manufacturers listed in the catalogue — their respective owners.
- **OrcaSlicer**, **OpenSpool**, **Spoolman**, **OpenPrintTag** — names of
  their respective open-source projects.

Use of these names does not imply any endorsement by the trademark holders.

## Brand assets (logos)

The application bundles reviewed manufacturer logos (`data/brands/logos/`,
136 files listed in `manifest.json`) and three historical ones
(`data/brands/logos/polymaker-lines.svg`, `data/brands/logos/prusament.svg`, `data/brands/logos/rosa3d.png`).
Most come from the Open Filament Database repository, whose MIT licence covers
its data files but **does not waive the trademark rights** of the brands
depicted; logos imported from a manufacturer's own site or press kit record
their origin in the manifest (`logo_source`). Either way the mark stays its
owner's.

- A logo is shown only next to the records of its own brand, to identify it.
- The build scripts (`.github/scripts/build_catalogue_snapshot.py`,
  `.github/scripts/import_brand_logos.py`) crop empty margins, normalize format
  and size and make a uniform background transparent; they do not recolour or
  redraw artwork. A transparent background is required and checked by a test.
  The application keeps proportions and transparency and adds a thin outline
  for legibility.
- Logos judged unsuitable (blurred, product photos, incomplete artwork) are
  excluded in `.github/catalogue-logo-exclusions.json`; those brands show their
  name instead.
- No logo is ever downloaded at runtime.

## Requests

Trademark holders who want a mark or a logo removed can open an issue; the
asset will be removed from the repository and the next build, and its brand
will fall back to a text label. Remove the brand's entry from
`data/brands/manifest.json`; delete its image only when no remaining entry uses
that shared file. The repository check reports unreferenced files. For legacy
fallback artwork, also remove the corresponding alias in `scripts/resource_paths.py`
and the explicit fallback in the packaging list.


## Printer product images

Reviewed product images from manufacturers, their software repositories and
identified resellers identify the illustrated machine. They are bundled with
their original bytes and source hashes; transparent margins are fitted only at
display time. Example captions name the actual model when a choice covers a family.
They retain their owners'
rights and are not relicensed under the MIT licence of SpoolScribe. See
[PRINTER_VISUALS.md](PRINTER_VISUALS.md) and the photo manifest for provenance.
