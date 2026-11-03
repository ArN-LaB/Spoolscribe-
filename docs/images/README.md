# SpoolScribe v0.6.0 — real interface captures

Generated on 3 November 2026 from the actual v0.6.0 source at
`074f76e65739f9cd49837e6db92c1fe32b4fd81e` (the published tag target),
using Python 3.12 / PySide6 6.11.3 and Qt offscreen. English, light theme.
The renderer script is a documentation-only follow-up; application modules are unchanged.

| File | What it shows |
| --- | --- |
| `catalogue.png` | List view, crossed manufacturer/material filters, selected Polymaker Aqua Blue and NFC state |
| `collection.png` | Grid view, Bambu Lab PLA Basic Blue, actual 1 kg refill choice |
| `colour-search.png` | Real PLA ranking for `#C8E6A0`, inclusive maximum `ΔE ≤ 10`, scores on cards |
| `printers.png` | Searchable visual printer browser with real product photos and categories |
| `hardware.png` | Snapmaker U1, built-in reader, modified paxx12 software, OpenSpool and NTAG216 |
| `qr-transfer.png` | Complete SSQR1 QR with PNG/SVG digital saving; captured top of the real QR window, printing band omitted |

[captures.json](captures.json) records source commit, version, image dimensions,
selected references and SHA-256 values. These are widget captures, without AI
mockups, composite controls or personal catalogue data. The QR image contains
only a public demonstration reference and can be decoded independently.

The public repository snapshots are merged in memory through the normal merger,
then loaded from a temporary database with isolated preferences. Python’s audit
hook blocks network connections. No refresh, personal correction or physical
NFC test is claimed. Counts are a fixture demonstration, not live source coverage.

Source and artwork credits: [data sources](../DATA_SOURCES.md),
[trademarks](../TRADEMARKS.md), [printer visuals](../PRINTER_VISUALS.md).
Documentation images and their manifest are excluded from application bundles.

## Regenerate

`python .github/scripts/render_readme_screenshots.py` generates the six captures
and manifest using the build/development environment. Review the images at full
size; capture generation alone is not visual acceptance on each operating system.

## Animated logo

`spoolscribe-animated.gif` is preserved. It is a deterministic export of
`data/app/spoolscribe_logo_animated.svg`. Regenerate with
`python .github/scripts/render_readme_logo.py`: 75 frames, 3-second loop,
no remote image dependency. The source animation is unchanged.
