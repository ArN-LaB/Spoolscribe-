# Catalogue and OpenSpool data contract

## Catalogue files

The user database `polymaker_db.json` and the repository snapshots
`catalogue_ofd.json` / `catalogue_spoolman.json` share three maps:

- `_brands`: source brand labels with optional local logo/website metadata.
- `_products`: material (`type`, optional `subtype`), `brand` (the
  manufacturer), optional `line` (a product line a source listed as a brand,
  e.g. `PolyLite`), `display_name` and the physical fields. Internal keys
  identify products unambiguously.
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
| `_field_sources` | product, reference | `{field: {source, rank, value}}`. Your edits are recorded with source `Utilisateur` and rank 1000 and are never replaced. A field absent from this map has unknown provenance (historical catalogue, older installations): a manufacturer source (rank ≥ 100) may replace it, any source may complete it, and it is checked like source data. |
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
when known, else the internal identifier), `manufacturer_sku`, `source_id`, the
display fields, `family` and `variant` (from `core.material_family`), `line`,
`ready`, `quality` (the data state), a private `_hex_rank` (provenance rank of
the HEX, −1 when absent) and a private `_search` key normalized once per reload.

`core.group_filaments(rows)` is a non-destructive presentation grouping by normalized
manufacturer, product, colour, material, diameter, alpha, multiple colours and traits.
Trademarks/punctuation and a leading manufacturer name in a colour are normalized;
product grades remain distinct. Each group retains complete `variants`, a stable
`filament_id` independent of its primary reference, `variant_count` and `hex_variants`.
Conflicting known HEX values mark the group incomplete and require a reference choice
in the GUI. The selected reference, not a synthesized combination, supplies the export.
Group IDs and member reference IDs keep favorites stable across representative changes.
Historical brand-line metadata is retained with `_alias_of`; normalization does not
bypass the storage layer's protection against deletion. If an article's physical
values change while its product record is shared with other articles, reconciliation
creates a reference-specific product record (`@reference/…`) and keeps the original.
This prevents a 2.85 mm article from changing the diameter of every 1.75 mm bobbin.

## Data state

`quality` is `Export possible` or a `;`-separated list of reasons:
`Produit absent`, `Couleur à renseigner`, `Couleurs multiples incompatibles avec
OpenSpool`, `Caractéristiques à compléter`, `Marque ou matière absente`, and the
plausibility flags `Couleur à vérifier (…)` and `Caractéristiques à vérifier (…)`.
The last two mark source values that contradict themselves (black HEX for a
light name, white HEX for a dark name, nozzle outside 120–500 °C, bed outside
0–200 °C or bed maximum 0 °C, density outside 0.5–4.0, diameter outside 1.0–3.2);
`core.build_openspool` refuses to export them until they are corrected, which
records the field as yours (`Utilisateur`). Only user-owned fields are exempt;
fields without provenance are checked like source data.

The state filter accepts `all`, `ready`, `incomplete` (not ready) and
`suspect` (any *À vérifier* reason).

## Settings (`config.json`)

| Key | Meaning |
|---|---|
| `network_consent`, `network_sources_revision` | Explicit authorization and the source revision it was given for |
| `language` | `auto`, `en`, `fr`, `es`, `zh_CN` ; interface uniquement, choix appliqué au redémarrage, inclus dans les réglages exportés |
| `selected_sources` | Keys of `core.SOURCE_GROUPS` to refresh |
| `update_interval_days` | Launch refresh cadence: `0` every launch, `1` daily (default), `7` weekly, `-1` manual only |
| `last_update_attempt`, `last_update_status` | Date and status (`complete` / `partial` / `failed`) of the last attempt, successful or not |
| `last_update` | Legacy date kept for older settings |
| `nfc_tag_type`, `nfc_profile` (`auto` / `essential` / `full`), `nfc_reserved_bytes` | Saved NFC default, written only by **Définir par défaut** or `--save-nfc-default`; invalid values fall back to NTAG216 / `auto` / 0 |
| `printer_profile`, `printer_firmware` | Printer/reader and firmware chosen in **Mon matériel** (`u1_stock` from older settings maps to `u1` + `stock`) |
| `orca_overrides`, `show_extra_fields` | Export options (`show_extra_fields` is kept for imported settings; provenance expands in the card) |
| `ui` | Filters, sorting, columns, geometry, splitter, view, `group` (one row per filament, default `true`) |
| `recent_brands` | Legacy browsing history, never interpreted as favorites |
| `favorite_brands`, `favorite_filaments` | Explicit persistent favorites, included in settings export/import |
| `auto_update` | Legacy flag, accepted but unused; the cadence applies |

Settings exported from the application contain everything except the consent
keys; importing never grants consent.

## Printers and readers (`data/printers.json`)

`{"format": "spoolscribe-printers", "version": 1, "updated": "YYYY-MM-DD",
"groups": {…}, "printers": [...], "external_readers": [...], "unverified": [...]}`.
Each printer has a stable `id`, `vendor`, `label`, a `group` (`native`,
`external`, `incompatible`, `none`), the `reader` technology, `firmwares`
(`id`, `label`, boolean `openspool`, optional `url` and `notes`), a `help` text
and optional per-field guidance (`fields`). `printer_profiles.validate_catalogue`
rejects unknown formats, duplicate or missing identifiers, unknown groups and
firmwares without a boolean `openspool`. The bundled file is used unless a valid
copy in the user data folder (`data/printers.json`, installed by **Mettre à jour
la liste des imprimantes…**) carries an `updated` date at least as recent.
`printer_profiles.can_export(printer, firmware)` is the only test used to show
the tag controls and allow an OpenSpool export.

## Logo manifest (`data/brand_logos/manifest.json`)

One entry per reviewed logo, keyed by the OFD brand UUID (or a slug for a logo
imported from another source): `name`, `path`, `sha256`, `width`, `height`;
for OFD images `source_path`, `source_commit`, `source_sha256`; for imported or
retouched images `transparent_background: true` and `logo_source` (`url`,
`source_kind`, `licence_note`, `retrieved`); `filled_shape: true` marks a
square/round logo that legitimately fills its corners. The application resolves
a brand's logo through this manifest first (by normalized brand name), then
through the `logo_path` stored in the database.

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
| **Essential** (recommended; `auto` resolves to it) | `protocol`, `version`, `type`, `color_hex`, `brand`, `min_temp`, `max_temp`, `bed_min_temp`, `bed_max_temp`, `diameter`, `density`, `subtype`, `alpha`, `additional_color_hexes` — compact OpenSpool fields; actual use depends on the reader, and size is checked for each export |
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


## Packaging preferences and visual presentation

`preferred_weight_g` is an integer from 0 to 20000; default 1000, with 0 meaning
use the catalogue proposal. `preferred_packaging` is `any`, `spool`, or `refill`.
These config values are exported/imported with settings and validated before
saving an imported file. They never modify catalogue records. An unavailable
weight keeps the actual reference and is indicated in the GUI; unknown refill
metadata is not synthesized. Explicit choices are remembered per group during
the session, and are invalidated if the group's source HEX set changes.

The UI persists both favorite filters and the manufacturer-search text. Spool
artwork is computed from the selected HEX and is display-only. For ambiguous
colours it stays neutral; package preference is not colour confirmation.

`data/printer_photos/manifest.json` records file names, source URLs, hashes and
illustrated models for reviewed UI artwork. It is separate from the filament
catalogue and from `data/printers.json` compatibility flags. These additional
images are bundled, never downloaded automatically by the running app.

## Personal filament copies (v0.3.5)

A personal copy adds its own `USER-<uuid>` SKU and private product key, leaving the original reference intact. The product display name ends in an editable ` @suffix`. `_personal`, `_personal_origin`, `_personal_suffix` and `_personal_base_name` are local metadata, preserved in the database/backups and omitted from NFC payload metadata. Same origin/suffix saves update the existing personal copy.

Source reconciliation excludes personal SKUs from identity/article/family matching. Copied fields carry high-priority `Copie personnelle` provenance; explicit physical edits use `Utilisateur`. Copying a colour does not silently confirm an implausible source HEX. Existing explicit corrections and null values remain protected. Standard reference exports are unchanged. The display name is used in personal export filenames and full payloads; the suffix is an application label, not a new printer material type or NFC standard.
