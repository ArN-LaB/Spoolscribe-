# README screenshots

Generated on 1 November 2026 from the actual SpoolScribe v0.3.5 source interface
(Python 3.12 / PySide6 6.11.3, Qt offscreen, 1480 × 920 logical pixels).

- `catalogue.png`: list view, Polymaker PLA, selected Panchroma Basic PLA Aqua Blue.
- `collection.png`: grid view, Bambu Lab PLA Basic Blue, selected 1 kg refill.

The public repository snapshots were merged in memory through the normal merger,
then loaded from a temporary database with isolated preferences. Network access
was blocked. No personal catalogue, correction or user path is shown. The demo
uses a Snapmaker U1 / paxx12 OpenSpool configuration with NTAG216.

These are direct widget captures, without compositing or invented controls.
The screen shows an offline demonstration, not a successful live refresh or a
physical NFC test. Source and brand credits remain in
[DATA_SOURCES](../DATA_SOURCES.md) and [TRADEMARKS](../TRADEMARKS.md).
Documentation images are excluded from application bundles.

## Animated logo

`spoolscribe-animated.gif` restores the animated spool in the README. It is a deterministic export of `data/app/spoolscribe_logo_animated.svg`, not a screenshot or new logo. Regenerate with `python .github/scripts/render_readme_logo.py` (development dependencies). 75 frames, 3-second loop; no remote image dependency.

Regenerate both actual English-interface captures with `python .github/scripts/render_readme_screenshots.py` (build/development dependencies). The app version, catalogue source and selected SKU are printed for each image.
