# Lab, RGB or a file: use a reference colour

[Home](Home.md) · [Visual tour](Visual-Tour.md) · [Download v0.8.0 Pre-release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0)

**Keep a reference colour without changing the filament catalogue.**
Open **Colours → Lab, RGB or file…**.

| 1. Choose an entry | 2. Check the interpretation | 3. Save or search |
| --- | --- | --- |
| **Enter:** HEX, RGB or CIELAB from your source. **Paste:** labelled text. **Import:** a CSV/TSV file you select. | Confirm the values, conditions and principal colour set. For files, confirm encoding, separator, decimal mark and columns. | Save to the local registry, or use an eligible value as an indicative target. A smaller ΔE means closer declared catalogue colours. |

## Can this value be compared?

| What you have | What the app does |
| --- | --- |
| A confirmed HEX or RGB sRGB code | Shows an indicative match against declared screen colours. |
| CIELAB with D65 and 2° documented by the source | Uses the original Lab coordinates for an indicative search. |
| Unknown conditions, D50, 10° or other conditions | Keeps the value; explains why ranking is unavailable. Do not guess missing conditions. |

The catalogue contains declared HEX codes, not physical measurements. Gloss,
translucency, printing and preparation can change the result. No match is a
certificate of the printed colour.

## Your saved references

**Saved** lets you rename, link to an exact filament reference, detach, delete
and restore a backup. Original values and provenance remain available. The
registry is a separate local file; linking never replaces a catalogue HEX or
changes an NFC/SSQR1 export. Editing numbers creates a new measurement.

An invalid RGB channel such as `RGB 116 202 191,5` is refused; it is never
rounded or silently cut down to 191. A rejected import requires correction or
an explicit partial-import decision before any write.

P1 adds no USB/Bluetooth connection, instrument SDK or certified manufacturer
export format. Generic CSV/TSV support does not imply validation with a device.
[Full guide and scientific limits](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/COLOUR_MEASUREMENTS.md) · [Validation](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/validation/v0.8.0.md).

Device entry presets can be saved and explicitly reapplied. Their name never implies calibration or D65/2° conditions. Comparison adds a dedicated ΔE column in list view; it disappears when comparison stops.
