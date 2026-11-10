# Catalogue and NFC export data contracts

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
Stored legacy identifiers remain literal data: `Produit absent` (missing product),
`Couleur à renseigner` (colour required), `Couleurs multiples incompatibles avec OpenSpool`
(multiple colours incompatible with OpenSpool), `Caractéristiques à compléter`
(incomplete characteristics), `Marque ou matière absente` (missing brand/material),
and plausibility flags `Couleur à vérifier (…)` / `Caractéristiques à vérifier (…)`
(colour/characteristics needing review). English documentation does not rename these stored tokens.
The last two mark source values that contradict themselves (black HEX for a
light name, white HEX for a dark name, nozzle outside 120–500 °C, bed outside
0–200 °C or bed maximum 0 °C, density outside 0.5–4.0, diameter outside 1.0–3.2);
`core.build_openspool` refuses to export them until they are corrected, which
records the field as yours (`Utilisateur`). Only user-owned fields are exempt;
fields without provenance are checked like source data.

The state filter accepts `all`, `ready`, `incomplete` (not ready) and
`suspect` (a reason carrying the stored `À vérifier` / “needs review” prefix).

## Settings (`config.json`)

| Key | Meaning |
|---|---|
| `network_consent`, `network_sources_revision` | Explicit authorization and the source revision it was given for |
| `language` | `auto`, `en`, `fr`, `es`, `zh_CN`; interface only, applied after restart and included in exported preferences |
| `selected_sources` | Keys of `core.SOURCE_GROUPS` to refresh |
| `update_interval_days` | Launch refresh cadence: `0` every launch, `1` daily (default), `7` weekly, `-1` manual only |
| `last_update_attempt`, `last_update_status` | Date and status (`complete` / `partial` / `failed`) of the last attempt, successful or not |
| `last_update` | Legacy date kept for older settings |
| `nfc_tag_type`, `nfc_profile` (`auto` / `essential` / `full`), `nfc_reserved_bytes` | Saved NFC default, written only by **Set as default** or `--save-nfc-default`; invalid values fall back to NTAG216 / `auto` / 0 |
| `nfc_format`, `opentag3d_output`, `opentag3d_settings` | Selected encoding, writer container and explicit per-reference OpenTag3D settings; source catalogue unchanged |
| `printer_profile`, `printer_firmware` | Printer/reader and firmware chosen in **My hardware** (`u1_stock` from older settings maps to `u1` + `stock`) |
| `orca_overrides`, `show_extra_fields` | Export options (`show_extra_fields` is kept for imported settings; provenance expands in the card) |
| `ui` | Filters, sorting, columns, geometry, splitter, view, `group` (one row per filament, default `true`) |
| `recent_brands` | Legacy browsing history, never interpreted as favorites |
| `favorite_brands`, `favorite_filaments` | Explicit persistent favorites, included in settings export/import |
| `auto_update` | Legacy flag, accepted but unused; the cadence applies |
| `qr_label` | QR paper settings only: `preset` (`d101-25x50`, `label-50x50`, `label-62x100`, `a4`, `custom`), optional `custom` profile (`width_mm`, `height_mm`, `margins_mm`, `dpi`, `orientation`), `small_format`, `error` (`M`/`Q`); validated by `qr_layout.validate_settings`, see [QR format](QR_FORMAT.md) |

`update_interval_days` must be the exact integer `0`, `1`, `7` or `-1` (`true`,
`7.0` or `"7"` are refused). Exported settings (`{"format": "spoolscribe-settings",
"version": 1, "settings": {…}}`, version an exact integer, file ≤ 128 KiB) hold
only the allow-list `core.PORTABLE_SETTINGS_KEYS`; `ui` and `export_directory` only
on explicit option. Never exported or imported: `network_consent`,
`network_sources_revision`, `last_update`, `last_update_attempt`,
`last_update_status`. Import validates the whole result with
`core.validate_settings` (also used by backup restore) before one write; omitted
keys keep their local value, lists and objects replace their category as a whole,
and a change of `selected_sources` resets the consent revision.

## Printers and readers (`data/printers.json`)

`{"format": "spoolscribe-printers", "version": 1, "updated": "YYYY-MM-DD",
"groups": {…}, "printers": [...], "external_readers": [...], "unverified": [...]}`.
Each printer has a stable `id`, `vendor`, `label`, a `group` (`native`,
`external`, `incompatible`, `none`), the `reader` technology, `firmwares`
(`id`, `label`, boolean `openspool`, optional `url` and `notes`), a `help` text
and optional per-field guidance (`fields`). `printer_profiles.validate_catalogue`
rejects unknown formats, duplicate or missing identifiers, unknown groups and
firmwares without a boolean `openspool`. The bundled file is used unless a valid
copy in the user data folder (`data/printers.json`, installed by **Update printer list…**) carries an `updated` date at least as recent.
In v0.4.0, `configuration_schema: 1` adds connection, software, documented formats
and actual effect to each installation; historical fields remain compatible.
`printer_profiles.can_export(printer, firmware, export_format)` gates the selected
format. Unknown setups remain unconfirmed. See [reader configurations](PRINTER-CONFIGURATIONS.md).
The shared reading, update and Companion snapshot rules (strict validation, dates
compared by time value, the last reliable list kept on refusal) are in the
[printer catalogue contract](PRINTER-CATALOGUE-CONTRACT.md).

## Logo manifest (`data/brands/manifest.json`)

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

## Colour measurement registry (v0.7.0)

`colour_measurements.json`, next to `polymaker_db.json` in the user data folder.
It is **not** a catalogue file: `load_db`/`save_db` never read it, syncs never
touch it, and restoring one file never restores the other. It is written through
the generic validated-JSON storage (`save_validated_json`: lock, revision check
before and immediately before `os.replace`, `.bak` of the previous bytes,
concurrent copy on conflict). Opening the window does not create the file.

```json
{"schema": "spoolscribe-colour-measurements", "version": 1,
 "measurements": {"MEAS-<uuid4>": {
   "name": "…", "role": "target | filament_sample", "created_at": "<UTC>", "measured_at": null,
   "original": {"space": "sRGB_HEX | sRGB_RGB8 | CIELAB", "components": {…}, "lexemes": {…}, "raw_text": null, "alternatives": []},
   "conditions": {"illuminant": "D65 | D50 | other | null", "illuminant_note": null, "observer": "2 | 10 | null", "geometry": null, "specular": null, "aperture": null, "calibration": null, "profile_note": null},
   "provenance": {"method": "manual | paste | csv", "device_manufacturer": null, "device_model": null, "source_app": null, "operator_note": null, "file_name": null, "file_sha256": null, "record_number": null},
   "sample": {"type": "unknown | raw_filament | printed_sample | painted_surface | object | other", "material": null, "finish": null, "thickness": null, "backing": null, "surface_note": null},
   "association": null, "content_digest": "<sha256 of normalised values and conditions>"}}}
```

Rules: `null` means unknown, nothing is inferred (no default illuminant or
observer, no instrument); `created_at` is the registry creation instant, distinct
from an optional reported `measured_at`; `L*` is bounded to [0, 100], `a*`/`b*`
only have to be finite; RGB8 channels are integers 0–255; lexemes keep the typed
text (`"73,2"`). An `association` is an exact SKU or `USER-…` identifier chosen
by the user; a missing SKU is reported, never re-attributed. Changing numbers
creates a new measurement. The digest only flags similar acquisitions.
Comparison policy: sRGB → indicative (derived D65/2° basis); CIELAB D65/2° →
indicative, compared directly to the catalogue Lab; anything else → blocked.
For an sRGB value, `conditions` only record the context declared with it
(for example the illuminant mentioned in a pasted text); the comparison
reference of sRGB stays the derived basis. `original.alternatives` keep the
other sets recognised with the principal one (paste: with the declared
conditions; CSV: the other mapped colour columns). The registry is read only
when its size is within 20 MiB (checked before any read or parse), is never
reset when unusable, and an explicit restoration keeps the replaced file next
to it (`colour_measurements.json.before-restore-*`).

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

Review the audit reports and every logo contact sheet before copying the generated
`data/` resources and `tests/fixtures/catalogues/` snapshots from the empty review
directory. Keep their roles separate; do not replace the historical catalogue or
the Orca profiles. Identical artwork is shared, retaining every manifest entry. The
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
The OpenTag3D label form may propose `preferred_weight_g` as the filament mass
when a label has none (1000 if the key is absent or invalid, labelled as a
default; nothing for 0). It is saved only in that label's settings, on Save.

`welcome` records on this computer that the quick welcome was finished (`done`)
or skipped (`skipped`). It is machine state: never exported or imported, never
written over an unreadable configuration. The welcome is offered automatically
only to a brand-new profile (no configuration file and an empty data folder).

The UI persists both favorite filters and the manufacturer-search text. Spool
artwork is computed from the selected HEX and is display-only. For ambiguous
colours it stays neutral; package preference is not colour confirmation.

`data/printers/photos/manifest.json` records file names, source URLs, hashes and
illustrated models for reviewed UI artwork. It is separate from the filament
catalogue and from `data/printers.json` compatibility flags. These additional
images are bundled, never downloaded automatically by the running app.

## Personal filament copies (v0.3.5)

A personal copy adds its own `USER-<uuid>` SKU and private product key, leaving the original reference intact. The product display name ends in an editable ` @suffix`. `_personal`, `_personal_origin`, `_personal_suffix` and `_personal_base_name` are local metadata, preserved in the database/backups and omitted from NFC payload metadata. Same origin/suffix saves update the existing personal copy.

Source reconciliation excludes personal SKUs from identity/article/family matching. Copied fields carry high-priority `Copie personnelle` provenance; explicit physical edits use `Utilisateur`. An explicit HEX edit of a copy is stored on the copy's own SKU with `Utilisateur` provenance; only edited fields become `Utilisateur`, never the whole copied record. Copying a colour does not silently confirm an implausible source HEX. Existing explicit corrections and null values remain protected. Standard reference exports are unchanged. The display name is used in personal export filenames and full payloads; the suffix is an application label, not a new printer material type or NFC standard.

## OpenTag3D 2.004 (current stable version: v0.8.3)

This independent binary format does not change the historical OpenSpool JSON
contract. It uses MIME `application/opentag3d`, not `application/json`, with NFC
Tools mobile/Desktop profile envelopes or a raw NDEF message. Required targets
and filament mass are explicit; no range midpoint or silently rounded value is
substituted. [Fields, sizes and writer formats](OPENTAG3D.md).

## Device entry presets (v0.8.0)

`colour_device_profiles.json` is separate from measurements and the catalogue.
Schema `spoolscribe-device-presets`, version 1, up to 32 profiles and 64 KiB;
each profile has a UUID key, name, manufacturer, model and whitelisted conditions.
The optional default points to an existing profile. Applying it is explicit.
Only declared illuminant/observer, geometry, specular mode, aperture and profile
note are reusable; no colour coordinates, calibration, date or sample data.
Revision-checked writes preserve a backup and refuse corrupt or concurrent data.

## Data backup archive (`spoolscribe-backup` v1)

Written by **Back up my data…** (`backup.create_backup`). It is a ZIP archive,
**not encrypted**, using deflate. Members:

| Member | Type | Content |
| --- | --- | --- |
| `data/polymaker_db.json` | `catalogue` | Exact bytes of the catalogue, required |
| `data/colour_measurements.json` | `registry` | Measurement registry, if present |
| `data/colour_device_profiles.json` | `presets` | Device entry presets, if present |
| `data/printers.json` | `printers` | Validated user printer list, if present |
| `config/preferences.json` | `config` | Same envelope as exported settings, filtered as above (option) |
| `orca_profiles/<name>.json` | `orca` | Local Orca profiles |
| `output/<relative path>` | `export` | Generated exports of the data folder (option, off by default) |

### Manifest

`manifest.json` has exactly these keys:

- `format: "spoolscribe-backup"` and `version: 1`, an exact integer;
- `app: {name, version}`;
- `created_utc` (`YYYY-MM-DDTHH:MM:SSZ`);
- `options`: four exact booleans, `include_config`, `include_layout`,
  `include_export_path` and `include_exports`;
- `entries`: a list of `{path, type, bytes, sha256}`;
- `absent`: types absent at creation;
- `excluded`: categories announced as not included.

The manifest contains no user name, absolute source path, machine identifier or
consent.

### Analysis before restore

Nothing is written during analysis. The archive is refused in any of these cases:

- an unknown version;
- a manifest that is missing, duplicated or has extra keys;
- a member that is missing, unexpected or a duplicate;
- a case or Unicode normalisation collision;
- an absolute path, `..`, a drive letter or a backslash;
- a link, a non-regular member or an encrypted member;
- a size or digest mismatch;
- content that fails its own validator;
- options inconsistent with the content.

Limits are 4096 members and 512 MiB uncompressed in total. Per member: catalogue
128 MiB, registry and presets at their existing limits, printers 512 KiB,
preferences 128 KiB, Orca profile 8 MiB, export file 64 MiB. Sizes are checked in
the central directory and again while reading.

### Restore transaction

The restore lives in `<DATA_HOME>/.spoolscribe-restore/` (0700):

- `restore.lock`, a kernel lock;
- one `tx-<id>/` per restore, holding `journal.json`
  (`spoolscribe-restore-journal` **v2**: phase, targets, `before`/`after`
  digests and the identity `before_identity` — device, inode, size, mtime — of
  each object to be replaced), `new/`, `snapshot/` (exact previous bytes, or a
  recorded absence) and `done/<n>` **proofs**.

A configuration outside `DATA_HOME` gets a `<config>.restore-pending` pointer.
Revisions seen in the preview are re-checked under lock. The journal is made
durable before the first publication. For each item, a proof file
(`spoolscribe-restore-proof`: index, `after` digest and the identity of the exact
private object about to be published) is written durably **before** the
publication. An absent target is created with a hard link of that object
(`os.link`), which the OS refuses if anything exists there; a present target is
replaced with `os.replace` only if its identity and digest are still the ones
recorded. A folder that does not support hard links refuses the restore before
anything is written.

On error, or at the next start (`recovery.bootstrap()`, which runs before `core`
is imported in the GUI, `python -m spoolscribe` and the CLI), items are
**rolled back** only when the object present is provably ours: identity equal to
the proof and digest equal to `after`. An interrupted restore is never completed.
Byte equality alone never proves ownership: an object with the published bytes
but another identity is **ambiguous**, kept and reported as a conflict; a file
whose content matches neither the snapshot nor the published bytes belongs to
someone else and is left untouched. In both cases the journal is kept in a
recoverable state, which **Keep the current state** can dismiss. A v1 journal
(without proofs) is kept and reported, never replayed. Up to three committed
snapshots are kept for **Undo the last restore**.

This is a logical transaction for cooperating SpoolScribe processes, not an
atomic file-system transaction.
