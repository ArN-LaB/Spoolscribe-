# Printer catalogue contract (v1)

[Data format](DATA_FORMAT.md) · [Reader configurations](PRINTER-CONFIGURATIONS.md)

`data/printers.json` is the **single editorial source** of printers, readers and
reading configurations. SpoolScribe Desktop reads it and can refresh it on
explicit request; SpoolScribe Companion embeds a generated, byte-identical
snapshot and never downloads it. This document is the contract both readers
implement. It adds **no schema**: `format: "spoolscribe-printers"`, `version: 1`
and `configuration_schema: 1` are unchanged, and so is the data.

## 1. Two levels

| Level | Question | Desktop | Companion |
| --- | --- | --- | --- |
| Structural reading | Is this a readable v1 document? | `printer_profiles.parse_catalogue_bytes`, `validate_catalogue` | `parseCatalogueBytes`, `validateCatalogue` |
| Update admissibility | Can it replace the active list? | `update_refusal`, `compare_update`, `install_catalogue` | simulated in memory only (tests) |

A structurally valid document can be inadmissible as an update. Historical v1
documents without configuration metadata stay readable; missing fields are
**unknown**, never filled with conclusions. A missing date never becomes "today".

## 2. Bytes

At most **512 KiB** (`size`). UTF-8 without byte order mark (`utf8`). JSON per
RFC 8259 with no duplicate keys and no `NaN`/`Infinity` (`json`).

## 3. Structural rules, in order (first failure wins)

The error code is part of the contract; both readers report the same first code.

1. `format` is `"spoolscribe-printers"` (`format`); `version` is the integer 1, not
   `true` or `1.0` (`version`); `configuration_schema`, if present, is the integer 1
   (`schema`).
2. `updated`, if present, is a calendar-valid `YYYY-MM-DD` (00:00 UTC) or
   `YYYY-MM-DDTHH:MM[:SS[.ffffff]]` with `Z` or `±HH:MM` (`updated`). A time
   without an offset is refused. `source`, if present, is an `https://` URL (`source`).
3. `groups`, if present: keys among `native`, `external`, `incompatible`, `none` (`groups`).
4. `printers`: a non-empty list of at most 500 objects (`printers`, `printer`).
5. Each printer: `id` matches `[a-z0-9][a-z0-9_.-]{0,63}` (`id`) and is unique
   (`duplicate`); `hidden`, if present, is a real boolean (`hidden`); `group` is
   known (`group`); `label` (1–200), `vendor` (≤100), `reader`, `help` (≤2000) are
   texts (`text`); `fields` maps texts to texts (`fields`); `firmwares` is a
   non-empty list of at most 64 configurations (`firmwares`).
6. Each configuration: object (`firmwares`); `id` as above (`id`), unique within the
   printer (`duplicate`); `openspool` is a real boolean (`firmwares`); `label`,
   `choice_label` (≤120), `reader`, `notes` are texts (`text`); `url`, if present,
   is `https://` (`url`); `formats` (default `["openspool"]` when `openspool`,
   else `[]`) lists distinct exporters among `openspool`, `opentag3d`, with
   `"openspool" ∈ formats ⇔ openspool` (`formats`); `reader_formats`, if present,
   lists at most 32 distinct tokens `[a-z0-9][a-z0-9_.-]{0,47}` containing every
   exported format (`reader_formats`); `connection`, `firmware_kind`, `effect`,
   `evidence`, if present, are known values (`metadata`); `checked`, if present,
   is a valid date (`date`).
7. With `configuration_schema: 1` (outside hidden historical aliases), or when
   `connection` is present, all of `connection`, `firmware_kind`, `effect`,
   `evidence`, `reader_formats`, `reader`, `notes`, `url`, `checked` are required
   (`metadata`).
8. A configuration that exports a format must be `documented` or `experimental`
   with an effect other than `none` (`export`).
9. `external_readers` (`id`, `label`, optional `https://` `url`, `works_with`,
   `tags`) and `unverified` (texts) are bounded lists (`external_readers`, `unverified`).

Texts are counted in code points; NUL, C0 controls other than tab and newline,
and lone surrogates are refused. **Extra optional fields are tolerated and never
interpreted** (they do not create capabilities). Unknown `reader_formats` tokens
are kept verbatim as unknown; tokens are compared exactly, never by substring
(`opentag3d_0.12` is not `opentag3d`).

## 4. Updates (Desktop)

A candidate is admissible only with a valid `updated` (`updated_missing`) and an
`https://` `source` (`source_missing`). It is compared with the **active reliable
list** (bundled, or the user copy when valid and at least as recent) **by time
value**:

| Candidate vs active | Decision |
| --- | --- |
| later | `install` |
| earlier | `regression`, active list kept |
| same instant, same data | `unchanged`, nothing written |
| same instant, different data | `conflict`, active list kept |

Formatting, the notation of `updated` and the runtime markers `_origin`/`_update`
are not data. The new profiles are prepared in memory first; the user copy is
then published with `scripts/db_io.save_validated_json` (lock, revision checked
again just before replacing, atomic replacement, `.bak` of the previous bytes).
A refusal, a storage failure, a concurrent change or an HTTP error keeps the
active list and the in-memory profiles. A removed printer is not replaced by
another one in the interface; it stays to be specified.

## 5. Meaning of the fields (both applications)

`formats` is what **Desktop exports**; `reader_formats` is what the **reader of this
configuration** is documented to read; `effect` says what happens (printer,
external inventory, standalone reader, none). `formats: []` does not mean "no RFID"
(Prusa CORE One reads OpenPrintTag over CAN), and `group: incompatible` is a
historical category, not a verdict on every reader of a brand. `evidence` is a
documentary level; nothing in v1 records a physical test, so no reader may claim
"observed". An absent format is "not listed", not "unsupported". Version or
capacity limits live in `notes`: quote them, never parse them.

## 6. Companion snapshot and shared corpus

`scripts/export_printer_catalogue.py --companion-root <Companion>` (offline,
deterministic, `--check` writes nothing) writes:

- `assets/compatibility/printers.snapshot.json`: exact bytes of the local canonical file;
- `assets/compatibility/printers.snapshot.manifest.json`: repository, path, HEAD,
  whether the catalogue file differs from HEAD, size, SHA-256, dates, counts.
  Provenance is `local-canonical`; publication at that revision is not claimed;
- `test/fixtures/compatibility/catalogue_conformance.generated.json`: the shared
  corpus. Bases (canonical catalogue, historical v1 `84d4866`), patch operations,
  byte cases and update cases, each with the expected first error code, update
  refusal and the SHA-256 of the canonical projection (sorted keys, compact
  separators, UTF-8). Python checks every expectation when generating; the Dart
  tests apply the same cases to the Companion reader.

The snapshot changes only by regenerating from Desktop and rebuilding Companion.
