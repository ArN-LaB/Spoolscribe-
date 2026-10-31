# Catalogue and OpenSpool data contract

## Catalogue files

The user database `polymaker_db.json` and the repository snapshots
`catalogue_ofd.json` / `catalogue_spoolman.json` share three maps:

- `_brands`: source brand labels with optional local logo/website metadata.
- `_products`: material (`type`, optional `subtype`), `brand`, `display_name`
  and the physical fields. Internal keys identify products unambiguously.
- `_skus`: internal reference → product key, `color_name`, `hex`, source
  identity (`source`, `source_id`, `source_path`), packaging (`weight`,
  `spool_refill`), optional `manufacturer_sku`, `source_colors`, `alpha`.

All files are UTF-8 JSON. Duplicate keys, NaN/Infinity, invalid HEX, boolean or
negative physical numbers, reversed temperature ranges and missing product links
are rejected at load and save time. Unknown physical values are `null`, never
fabricated defaults. The historical two orphan references remain visible
exceptions; no new orphan can be added.

`min_temp`, `max_temp`, `bed_min_temp`, `bed_max_temp` are integer °C;
`diameter` is positive mm, `density` positive g/cm³, `weight` grams of filament.
A single temperature published by SpoolmanDB becomes an equal minimum/maximum.

### Provenance and bookkeeping keys

| Key | Where | Meaning |
|---|---|---|
| `_field_sources` | product, reference | `{field: {source, rank, value}}` for every imported field. A field absent from this map is yours (or historical) and is never replaced. |
| `_source_aliases` | reference | `{source: [source ids…]}` — every source record absorbed into this reference, in order. Older files may hold a single string; it is upgraded to a list on the next merge. |
| `_product_aliases` | reference | Reviewed historical product names (Polymaker renames). |
| `_pending_source_matches` | database | `{source: [{source_id, reason, candidates?}]}` — ambiguous records kept out of the table. |
| `_source_conflicts`, `_source_conflicts_by_source` | database | Fields where a local value won over a source, including `… (valeur retirée par la source, conservée)`. |
| `_source_snapshots` | database | `{ofd: {references, sha256, etag?, …}, spoolman: {…}, polymaker: {references}, bambu: {etag, profiles}}`; `etag` enables conditional downloads and `references` the shrink check. |
| `_update_status`, `_source_results`, `_selected_sources`, `_last_updated` | database | Outcome of the last refresh that changed something and date of the last complete refresh of the selected sources. `_last_attempt` is no longer written to the database (see settings). |
| `_bundled_digest`, `_bundle_conflicts` | database | Historical packaged-catalogue merge bookkeeping; current installers bundle no catalogue. |

## Identity

OFD references are `OFD-<size UUID>` (or the variant UUID when size is absent);
SpoolmanDB references are `SMDB-<24 hex characters of SHA-256(source id)>`.
Neither is a manufacturer SKU: `manufacturer_sku` holds only an upstream article
number, and several sizes/refills can legitimately share one.

Two records are one filament when brand, normalized article number, colour
(same normalized name, or one name unknown, or same HEX) and packaging are
compatible, or when brand, normalized product name, colour name and packaging
match exactly. Normalization drops accents, case, punctuation and trademark
symbols but keeps `+`, so `PLA+` and `PLA` stay distinct. Anything else is
pending, never a duplicate.

`core.list_skus` rows expose `sku` (internal), `reference` (manufacturer article
when known, else the internal identifier; shown in the *Référence* column),
`manufacturer_sku`, `source_id`, the display fields, `ready`, `quality` (the data
state) and a private `_search` key normalized once per reload.

## Data state

`quality` is `Export possible` or a `;`-separated list of reasons:
`Produit absent`, `Couleur à renseigner`, `Couleurs multiples incompatibles avec
OpenSpool`, `Caractéristiques à compléter`, `Marque ou matière absente`, and the
plausibility flags `Couleur à vérifier (…)` and `Caractéristiques à vérifier (…)`.
The last two mark source values that contradict themselves (black HEX for a
light name, white HEX for a dark name, nozzle outside 120–500 °C, bed outside
0–200 °C or bed maximum 0 °C, density outside 0.5–4.0, diameter outside 1.0–3.2);
`core.build_openspool` refuses to export them until they are corrected, which
removes their provenance and makes them yours. Historical entries without
`source` are never flagged.

## Settings (`config.json`)

| Key | Meaning |
|---|---|
| `network_consent`, `network_sources_revision` | Explicit authorization and the source revision it was given for |
| `selected_sources` | Keys of `core.SOURCE_GROUPS` to refresh |
| `update_interval_days` | Launch refresh cadence: `0` every launch, `1` daily (default), `7` weekly, `-1` manual only |
| `last_update_attempt`, `last_update_status` | Date and status (`complete` / `partial` / `failed`) of the last attempt, successful or not |
| `last_update` | Legacy date kept for older settings |
| `printer_profile`, `nfc_tag_type`, `nfc_profile` (`auto` / `essential` / `full`), `nfc_reserved_bytes`, `orca_overrides`, `show_extra_fields` | Export assistant |
| `ui` | Filters, sorting, columns, geometry, splitter, view |
| `recent_brands` | Quick-access manufacturers |
| `auto_update` | Legacy flag, accepted but unused; the cadence applies |

Settings exported from the application contain everything except the consent
keys; importing never grants consent.

## Colours

`hex` is a representative six-digit colour or `null`. An upstream eight-digit
RGBA value is split into RGB and an explicit two-digit `alpha`. A transparency
trait alone never creates an alpha. Multiple source colours are preserved in
`source_colors`; the user chooses the representative HEX and the others are
exported as `additional_color_hexes` (at most four). An unrepresentable set
blocks export rather than discarding colours.

## Export profiles

Both profiles are OpenSpool `protocol: "openspool"`, `version: "1.0"` JSON.

| Profile | Fields |
|---|---|
| **Essential** (recommended; `auto` resolves to it) | `protocol`, `version`, `type`, `color_hex`, `brand`, `min_temp`, `max_temp`, `bed_min_temp`, `bed_max_temp`, `diameter`, `density`, `subtype`, `alpha`, `additional_color_hexes` — everything a reader uses; fits every reference on NTAG215 |
| **Full** (explicit choice) | Essential fields plus `sku`, `product`, `color_name`, `brand_meta` (`name`, `website`, `origin`, `logo_url`, `logo_path`), `logo_url`, `image`. Unknown metadata is omitted, never written as `null` |
| **Readable archive** | All full-profile fields, indented, without a tag-size check (`_archive.json`) |

The archive is the complete OpenSpool export record, not a database backup.
Serialization rejects non-finite numbers and happens before any file is opened;
the inspector and the export share the serializer. NTAG215/216 only change the
capacity check (496 / 872 bytes of NDEF area). See
[Writing RFID Tags](wiki/Writing-RFID-Tags.md).

## Preparing a new reviewed snapshot

Download the official OFD archive and the compiled SpoolmanDB JSON, record the
OFD commit and both SHA-256 hashes, keep their MIT licence files, then run the
offline tool into a fresh output directory:

```sh
python .github/scripts/build_catalogue_snapshot.py \
  --archive /path/to/ofd.tar.gz --commit FULL_40_CHARACTER_COMMIT \
  --spoolman /path/to/filaments.json --spoolman-license /path/to/SpoolmanDB-LICENSE.txt \
  --output /path/to/reviewed-data --review /path/to/contact-sheets
```

Review the audit reports and every logo contact sheet before copying the files
into `data/`. Do not replace the historical catalogue or the Orca profiles. The
tool needs the build dependencies (Pillow/PySide6); runtime adapters use the
standard library only. Tests use local data and deny network access.
