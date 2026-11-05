# Colour measurements — Desktop P1, v0.8.0 Pre-release

Available in [v0.8.0 Pre-release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0).
The software checks do not certify an instrument, its proprietary export format
or a physical printed colour. [Validation and limits](validation/v0.8.0.md).

## What it does

From *Teintes* → **Lab, RGB ou fichier…** the user can:

1. **Enter** a HEX sRGB code, 8-bit RGB channels or CIELAB coordinates
   (decimal point or comma, never a thousands separator).
2. **Paste** text copied from a device application. Only labelled, *whole*
   values are recognised (`HEX`, `RGB`, `L*`/`a*`/`b*` or `Lab x y z`,
   `D50`/`D65`, `2°`/`10°`). RGB channels are three whole integers 0–255
   separated by one kind of separator — spaces (`RGB 116 202 191`), commas
   (`RGB 116, 202, 191`, `RGB(116,202,191)`) or semicolons; blanks around a
   comma or semicolon do not change its kind (`RGB 116,202, 191`); a decimal
   (`191.5`, `191,5`), four digits (`1910`), a fourth number (`191, 5`) or
   mixed separators (`116,5 202 191`) refuse the whole set with a message
   quoting the values as typed, never a truncated or re-split value; a
   colour space named as not sRGB (`Adobe RGB`, `Display P3`, …) is reported
   and never converted, an unbalanced set (`L*=50 a*=1 b*=2 L*=80`) is
   reported. Several sets or conditions are shown and the main one is chosen
   explicitly; the conditions found in the text are kept as declared context
   on every set, including an sRGB principal; editing the text withdraws the
   proposal until it is interpreted again; unlabelled numbers are never
   coordinates.
3. **Import** a CSV/TSV: UTF-8 (BOM accepted) by default, CP1252/Latin-1 only
   on explicit choice; the file size is checked before it is read;
   comma/semicolon/tab separator and decimal mark confirmed; columns mapped by
   position with the header shown (colour, name, illuminant, observer,
   geometry, SCI/SCE, aperture, device, manufacturer, material, finish,
   thickness, backing, note, date); duplicate headers are listed, never picked
   silently; when Lab, HEX and/or RGB columns are all mapped the **principal
   set is an explicit choice** and the others are kept as alternatives, with
   inconsistencies listed as warnings; the observer accepts only `2`, `2°`,
   `10`, `10°` (and `deg`/`degrés`), so `-2°` is a record error; a
   “N valid / M to fix / K potential duplicates” report precedes any write; a
   partial import is a confirmed choice.
4. **Save** measurements in `colour_measurements.json` (user data folder),
   rename, link to an exact catalogue reference or personal copy, detach,
   delete (with backup) and restore the registry from its backup — also when
   the current file is unreadable or oversized: the window shows the problem,
   the explicit restoration replaces exactly the file that was seen (revision
   checked under lock and again just before replacing) and keeps it next to
   the registry, whatever its state.
5. **Document** the optional metadata the model carries, unknown by default:
   geometry, SCI/SCE, aperture, calibration, profile (conditions) and
   material, finish, thickness, backing, surface state (sample), through the
   progressive “more details” of the manual entry, the pasted-text conditions
   or the CSV columns. A small swatch previews a confirmed HEX/RGB code; a
   Lab value never gets a preview.
6. **Use a measurement as target** of *Teintes proches*. The target is the
   acquisition itself (identifier and name), never its colour alone: two
   saved measurements with equal values are two targets; distances already
   computed for the same values are reused, the identity is not.

## Colour entry and navigation in v0.8.0

**Lab, RGB ou fichier…** opens **Valeurs couleur : Lab, RGB, fichier**: the
application uses entered values or imported readings; it does not measure through
a connected device. Colour ranking has a dedicated **ΔE distance** column in
list view, automatically shown only while comparison is active. Card headings keep
the manufacturer once; the product range/material below the colour omits its repeated prefix.

Dialogs resize when details open **and close**, within the available screen.
QR information follows its visible content; scrollbars appear when space runs out.
Manual resizing remains available.

The measurement window groups **values**, **comparison conditions** and optional
**sample / device information**. Labels sit above their fields; advanced geometry,
specular and calibration details stay collapsed until needed. L*, a* and b* are
explained without converting or guessing values.

The footer follows the active entry: save / search for manual and pasted values,
check rows / save batch for CSV, one search action for saved measurements. CSV
preview and column mapping appear only after choosing a readable file. Optional
columns detected in the file are expanded for review. Editing mappings or defaults
still withdraws the checked import report.

**Device entry presets** can be saved from the optional device section and offered
at the next launch. Selecting a preset does not apply its conditions: the user
checks the device and clicks **Use these settings**. A preset stores only the
user-declared manufacturer/model, illuminant/observer, geometry, specular mode,
aperture and profile note. It never stores colour coordinates, sample preparation,
measurement date or calibration. Calibration is recorded separately for each session.
Unknown conditions stay unknown; names never imply D65/2° or certification.

Presets live in `colour_device_profiles.json` next to the measurement registry,
with strict schema/size/count bounds, revision checks and a `.bak` backup. Opening
the dialog creates no file. Save, default choice and deletion are explicit actions;
a corrupt or concurrently changed preset file is not overwritten. Settings export
continues to exclude these device presets and measurements.

## What it never does

- No instrument, SDK, driver, network, OCR, spectral data, ICC profile, LCh/XYZ.
- No modification of the catalogue, personal copies, settings, OpenSpool /
  OpenTag3D / SSQR1 outputs. Linking a measurement does not change the colour
  the catalogue declares nor what is exported.
- No automatic deduplication, merge or link by colour name / SKU-like text.
- No formula, URL or command interpretation of pasted or imported text.

## Comparison policy

| Measurement | Ranking against the catalogue | Level shown |
|---|---|---|
| HEX / RGB8 (sRGB) | unchanged HEX engine (`colour_distance.rank`) | Proximité indicative |
| CIELAB, D65, 2° | original Lab vs Lab of each declared HEX, same CIEDE2000 | Proximité indicative |
| CIELAB, D50 | none (no chromatic adaptation in P1) | Conditions insuffisantes |
| CIELAB, 10°, other or unknown illuminant/observer | none | Conditions insuffisantes |
| Huge finite values | none (arithmetic overflow guarded) | Conditions insuffisantes |

Catalogue candidates are declared screen colours, so a measurement is never
called “comparable” to them. The business rule `pair_policy` qualifies two
*physical* CIELAB measurements as comparable only with documented, identical
illuminant, observer, geometry, specular mode, instrument and sample
preparation; an illuminant declared “other” is compared by its documented
description (D55 and D75 are different), with no equivalence inferred
between device names, illuminants or geometries. P1 ships the rule and its
tests, not a comparison screen.

All validation and import errors carry a French template and named values
(`MeasurementError.template` / `.values`), translated piece by piece in the
four interface languages; condition texts are composed from translated pieces.

## Scientific limits

sRGB → CIELAB uses the engine’s D65/2° conversion (IEC 61966-2-1 primaries),
which is a derived basis, not a measured condition. D50 ↔ D65 adaptation
(Bradford or other) and 10° ↔ 2° conversions are deliberately absent: no
universal triplet conversion exists without spectral data. ΔE00 between a
measurement and a declared colour helps choose a filament; it is not a
certificate of the printed result (gloss, translucency, thickness, backing).

## Files

- `src/spoolscribe/colour_measurements.py` — model, validation, parsing, policies.
- `src/spoolscribe/colour_import.py` — paste interpretation, CSV preview/mapping/validation, bounds.
- `src/spoolscribe/measurement_store.py` — registry over `scripts.db_io.save_validated_json`.
- `src/spoolscribe/colour_targets.py` — target adapter for the existing ranking.
- `src/spoolscribe/ui_colour_measurements.py` — the window.
- `src/spoolscribe/device_profiles.py` — explicit local device entry presets (preview).
- `tests/fixtures/measurements/` — synthetic fixtures only (see its README).
