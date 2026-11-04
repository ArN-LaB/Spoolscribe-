# Synthetic measurement fixtures

Every file here is **synthetic**, written by hand for the tests of the colour
measurement importer. None is an export of a real instrument or application
(Nix, Datacolor, ColorReader, TD1s, CHNSpec or any other brand); the device
names inside are placeholders. Values are arbitrary CIELAB/sRGB coordinates.

| File | Purpose |
|---|---|
| `synthetic_lab_semicolon_fr.csv` | semicolon separator, decimal comma, CRLF, a D50 row, an exact repetition and an invalid row |
| `synthetic_rgb_comma.csv` | comma separator, R/G/B columns, one out-of-range channel |
| `synthetic_lab_bom_crlf.tsv` | UTF-8 BOM, tabulation, `LAB_*` aliases, quoted multi-line cell, a 10° row |
| `synthetic_paste_conflicts.txt` | pasted text with contradictory HEX/RGB, a Lab set and D50/10° conditions |
| `synthetic_latin1.csv` | not UTF-8: the importer must refuse until an encoding is chosen explicitly |
| `hex_baseline_digests.json` | the six HEX ranking digests measured on the unmodified engine (audit of 4 November 2026) |
