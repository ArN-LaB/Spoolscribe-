# Catalogue and OpenSpool data contract

## Offline catalogue

`data/polymaker_db.json` retains the original curated records. The separate
`catalogue_ofd.json` and `catalogue_spoolman.json` files use the same three maps:

- `_brands`: source brand labels and optional local logo/website metadata.
- `_products`: material, manufacturer and physical fields. Internal keys identify
  products unambiguously; `display_name` is the readable UI/export label.
- `_skus`: internal reference → product key, color, source identity and packaging.

All files are UTF-8 JSON. Duplicate keys, NaN/Infinity, invalid HEX, boolean or
negative physical numbers, reversed temperature ranges and missing product links
are rejected. New importers also validate source identity, required text, units
and array shapes. Unknown physical values are `null`, never fabricated defaults.
The historical two orphan references remain visible exceptions; no new orphan is added.

Temperature fields `min_temp`, `max_temp`, `bed_min_temp`, `bed_max_temp` are
integer degrees Celsius. `diameter` is positive millimetres, `density` positive
g/cm³, and optional `weight` is filament mass in grams. A single temperature
published by SpoolmanDB becomes an equal minimum/maximum, not an invented range.
Incomplete but valid records can be browsed and corrected locally; export
requires all printing fields and a representative color.

## Identity and preservation

OFD references are `OFD-<size UUID>` (or the variant UUID when size is absent).
Spoolman references are `SMDB-<24 hex characters of SHA-256(source ID)>` with
collision checks; the original ID remains in `source_id`. Neither is a claimed
manufacturer SKU. `manufacturer_sku` contains only an upstream article number.
Spool sizes/refills can legitimately share a manufacturer SKU.

`source`, `source_id`, `source_path`, source aliases and source snapshot hashes
retain provenance. `_field_sources` records the automatic value/source/priority
for each imported field. Manufacturer facts outrank community data; known values
can complement source-owned unknowns. Explicit personal edits remove automatic
ownership of those fields, including deliberate nulls. Existing fields without
provenance remain protected. Conflicts and uncertain source identities are reported.

Canonical identities use manufacturer article numbers with compatible packaging,
or exact brand/product/color matches. Reviewed historical Polymaker aliases are
explicit. Ambiguous cross-source records remain in `_pending_source_matches`
rather than being inserted as possible duplicates. No fuzzy material/color-only join.

All normal startup uses the user data directory. New installers start with an empty
catalogue and download selected sources; repository snapshots remain offline test
fixtures and are not packaged. Existing user files survive upgrades. Explicitly
loading a repository fixture can still combine its neighboring supplements in
memory without modifying their bytes. Restoration inhibits automatic updates for
that process. Physical edits apply to all references sharing the product key;
the dialog shows the affected count.

## Colors

`hex` is a representative six-digit color or `null`. An upstream eight-digit
RGBA value is split into RGB and an explicit two-digit `alpha`. A transparency
trait alone never creates a numerical alpha. Unknown source colors remain null.

Multiple source colors are preserved in `source_colors`. No first color is silently
selected as representative: the user chooses a HEX. Export then retains the other
source colors as `additional_color_hexes`, up to OpenSpool's four additional colors.
An unrepresentable set or incompatible per-color alpha blocks export rather than
silently discarding colors. Reader/firmware support for additional colors varies.

## Export profiles

The GUI automatic mode tries the complete profile then the essential profile, with
an explicit indication when descriptions are omitted. Both profiles are OpenSpool `protocol: "openspool"`, `version: "1.0"` JSON.

| Profile | Retained fields |
|---|---|
| Complete | Existing printing fields, explicit color extensions, SKU/product/color-name and supported brand/logo metadata |
| Essential (automatically recommended or manually selected) | Protocol/version, type, brand, RGB, nozzle/bed ranges, diameter, density, subtype, explicit alpha and additional colors |
| Readable archive | All supported complete-export fields, independent of selected NFC profile and without a tag-size rejection |

The archive is the complete **OpenSpool export record**, not a backup of the
database: source UUID/traits/packaging that are not OpenSpool fields remain in the
catalogue. Use the database backups to retain all source and user data.

JSON serialization rejects non-finite numbers and happens before any destination
write. Preview and file export share the same serializer. NTAG215/216 affect
capacity only. No compression, proprietary protocol or truncation is used.
See [Writing RFID Tags](wiki/Writing-RFID-Tags.md) for framing and writer reserve.

## Preparing a new reviewed snapshot

Download the official source archive and compiled SpoolmanDB JSON separately,
record the OFD commit and both SHA-256 hashes, and retain their MIT license files.
Then run the offline development tool using a fresh output directory:

```sh
python .github/scripts/build_catalogue_snapshot.py \
  --archive /path/to/ofd.tar.gz --commit FULL_40_CHARACTER_COMMIT \
  --spoolman /path/to/filaments.json --spoolman-license /path/to/SpoolmanDB-LICENSE.txt \
  --output /path/to/reviewed-data --review /path/to/contact-sheets
```

Review the audit reports and every logo contact sheet before copying the generated
files into `data/`. Do not replace the historical catalogue or Orca profiles.
The tool needs the existing build dependencies (Pillow/PySide6), while runtime
source adapters use the Python standard library only. Runtime updates do not
automatically approve new remote logos. Tests use synthetic/local data and deny
network access; source collection is a separate, explicit development operation.
