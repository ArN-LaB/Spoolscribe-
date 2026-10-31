# Writing RFID Tags

SpoolScribe prepares OpenSpool 1.0 **JSON data**. A separate writer, such as
SpoolFlux on iPhone, programs the physical NFC tag. SpoolScribe does not write
memory pages, change a Capability Container (CC), or associate a hardware UID.

## Export choices

- **Exporter pour NFC** produces compact JSON. The existing brand, product,
  SKU, color-name and logo metadata are retained.
- The GUI **⋯ > Exporter la sélection en archive JSON…** action produces the
  same fields with indentation, under an `_archive.json` filename.
- CLI: `python convert_profile.py --export-format nfc` (default), or
  `--export-format archive`. `--compact` still only controls terminal display.

The NFC inspector uses the same serialization as the NFC file. Validation
happens before the output is opened. An archive may exceed tag capacity and is
not intended to be written verbatim to a tag.

## Tag and record format

NTAG216 means the chip model, **not 216 bytes**. It has 888 bytes of user memory;
the standard CC `E1106D00` declares a 872-byte NDEF area. See the
[NXP data sheet, sections 8.5.4–8.5.6](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf).

Use one **NDEF MIME `application/json` record** containing UTF-8 JSON, as in
[OpenSpool](https://github.com/spuder/OpenSpool). A plain NDEF Text record is not
accepted by the OpenRFID revision bundled in Paxx12-24.

SpoolScribe measures characters, UTF-8 bytes, the complete MIME record, and its
Type 2 TLV plus terminator. It assumes no record ID and no additional records.
For a JSON payload of 256 bytes or more, the budget is JSON bytes + 22 bytes for
NDEF + 5 bytes for TLV/terminator. Short records use their actual shorter headers.
The 4-byte CC is outside the declared data area and is not counted twice.

Any records added by the writer require additional space. The writer must also
check the actual tag's available/writable capacity and perform read-back.

## Unknown, transparent and multicolor filaments

An unknown HEX never becomes black automatically. At export, enter an explicit
six-character representative HEX or cancel. The value is saved locally.

For transparency, an optional explicit `alpha` is available: `00` is transparent,
`FF` opaque. No alpha or representative color is inferred from a product name.
Explicit `additional_color_hexes` are retained, but not all readers use them.
Paxx12-24 OpenRFID uses alpha but ignores additional colors. It also ignores the
exported density/bed-temperature fields and derives bed temperature from its own
table; their presence in JSON does not guarantee their application by a printer.

The OpenSpool version remains `1.0`. Temperatures are exported as numbers,
diameter/density as positive finite numbers, and HEX as six uppercase characters.

## Writing and diagnosis

1. Export the NFC file and review its data and capacity estimate.
2. Import it into your writer and select MIME `application/json`.
3. Program the tag and verify it by reading it back.
4. Check the printer's detected brand, material and color.

`0300FE` denotes an empty NDEF TLV; it is not useful filament data. A reader error
about CC `E1107F00` concerns tag formatting/compatibility. Neither is proof of a
SpoolScribe JSON-generation defect. A JSON export cannot repair a tag's CC.

The audit simulated the parser pinned by
[Paxx12-24](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/v2.0.0-paxx12-24/overlays/firmware-extended/64-app-openrfid/pre-scripts/01-install-openrfid.sh),
[OpenRFID a13bc9e](https://github.com/suchmememanyskill/OpenRFID/blob/a13bc9e181374e182f61db4e69abf9fa1786cc29/src/tag/openspool/processor.py).
Physical iPhone/tag/printer acceptance remains a separate check.
