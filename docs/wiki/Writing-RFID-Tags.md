# 🏷 Writing RFID tags

[⌂ Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ](FAQ.md)

**One file, one compatible tag, then a read-back check.**

| SpoolScribe | NFC writing app | Compatible reader |
| --- | --- | --- |
| Select a filament → export JSON | Write an NDEF MIME record → read it back | Check the detected material and colour |

Choose the printer or reader first (**⚙ → My hardware**), with its firmware when that matters. For the Snapmaker U1 under the
paxx12 firmware, for Flashforge machines under Zmod + FF_NFC, for Klipper +
Spoolman readers, for a Bambu printer fed by an external OpenSpool reader and
for other OpenSpool readers, SpoolScribe produces an OpenSpool 1.0 JSON payload.
Bambu AMS, Prusa OpenPrintTag, Creality CFS, Anycubic ACE, Elegoo, QIDI or
UltiMaker tags are not generated; for those printers the card is a reference
sheet and the tag controls are hidden. See
[Printers and Readers](Printers-and-Readers.md).

SpoolScribe prepares the **JSON data** only. A separate writer, such as
SpoolFlux on iPhone, programs the physical NFC tag. SpoolScribe does not write
memory pages, change a Capability Container (CC) or associate a hardware UID.

## Choose the right export

| Choice | Use it for |
| --- | --- |
| **Essential · recommended** | A compact NFC payload with the supported filament fields. |
| **Full · advanced** | Extra names and brand metadata, when capacity allows. |
| **Readable archive** | An indented reference copy; not intended for writing verbatim to a tag. |

<details>
<summary><strong>Profile fields and command-line options</strong></summary>

- **Essential** — the recommended profile and the default (`auto`): protocol and
  version, material type and subtype, brand, representative HEX, explicit alpha
  and additional colours, nozzle and bed ranges, diameter and density. This is
  the compact set supplied to compatible readers. SpoolScribe checks the actual payload against the selected tag and writing reserve before export.
- **Full** — an explicit choice under **My hardware → Advanced settings** (or
  `--nfc-profile full`): the essential fields plus the reference, product and colour names and
  brand metadata (website, logo URL). Larger; extra names/branding do not replace the slicer profile.
  Unknown metadata is omitted, never written as `null`.
- **Readable archive** (**⚙ → Export JSON archive…**): all
  full-profile fields, indented, under an `_archive.json` filename. It may
  exceed a tag's capacity and is not meant to be written verbatim.

No colour or printing value is ever dropped to make an export fit: an oversized
export is refused before anything is written.

CLI: `python -m spoolscribe.convert_profile` (interactive; `--export-format nfc` by default,
`--export-format archive` for the archive), with `--tag-type NTAG215|NTAG216`,
`--nfc-profile auto|essential|full` and `--reserve-bytes N`. `--compact` only
changes the terminal display. `--brand`, `--material` and typed references are
case-insensitive.

The NFC inspector (**Show JSON**) uses the same serializer as the NFC
file: what you see is what is written.

</details>

## Choose your tag

| Chip | User memory | Standard declared NDEF area |
| --- | --- | --- |
| **NTAG215** | 504 bytes | **496 bytes** |
| **NTAG216** | 888 bytes | **872 bytes** |

The app checks the complete payload against the selected tag and writing reserve.
An export that does not fit is refused; colours and printing values are not silently dropped.

<details>
<summary><strong>Technical details: NDEF, byte budget and writer reserve</strong></summary>

NTAG215/216 are chip models, not byte counts. NTAG215 has 504 bytes of user
memory and its standard CC `E1103E00` declares 496 bytes for NDEF. NTAG216 has
888 bytes of user memory and CC `E1106D00` declares 872 bytes. See the
[NXP data sheet, sections 8.5.4–8.5.6](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf).

Use one **NDEF MIME `application/json` record** containing UTF-8 JSON, as in
[OpenSpool](https://github.com/spuder/OpenSpool). A plain NDEF Text record is not
accepted by the OpenRFID revision bundled in Paxx12-24.

SpoolScribe counts the UTF-8 JSON bytes, the complete MIME record and its Type 2
TLV plus terminator, assuming no record ID and no additional record. For a JSON
payload of 256 bytes or more the budget is JSON bytes plus 22 bytes of NDEF
header plus 5 bytes of TLV/terminator; shorter records use their shorter headers. The
4-byte CC is outside the declared area and is not counted.

The card shows the remaining margin for the chosen tag. The optional writer
reserve (**Advanced settings**) subtracts the bytes your writer may add; a zero
reserve does not mean that SpoolFlux or another writer adds nothing. The writer
must check the tag's actual writable capacity and read the tag back.

</details>

## Colours: what to confirm

| Colour state | What to do |
| --- | --- |
| **Unknown** | Enter an explicit representative HEX or cancel. |
| **Conflicting sources** | Compare the shades in the card and confirm yours. |
| **Transparent / multicolour** | Check the explicit source colours; reader support varies. |

<details>
<summary><strong>Alpha, additional colours and reader limitations</strong></summary>

An unknown HEX never becomes black automatically. At export, enter an explicit
six-character representative HEX or cancel; the value is saved locally. A
source HEX that contradicts the colour name (black for "White") is flagged
*Needs review* and must be confirmed in the card first.

For transparency, an optional explicit `alpha` is available: `00` transparent,
`FF` opaque. No alpha or colour is inferred from a product name. Explicit
`additional_color_hexes` are retained, but not all readers use them: Paxx12-24
OpenRFID uses alpha and ignores additional colours; it also ignores the exported
density and bed temperatures and derives the bed temperature from its own table.
Their presence in the JSON does not guarantee that a printer applies them.

For imported multicolour records the source colours are shown in the colour
dialog; choosing a representative HEX keeps the others. More than four
additional colours, or an incompatible per-colour alpha, block export rather
than being truncated.

The OpenSpool version stays `1.0`. Temperatures are exported as integers,
diameter/density as positive numbers, HEX as six uppercase characters.

</details>

## Write, read back, check

1. In **My hardware**, choose the printer/reader and its firmware, the tag
   (NTAG215 or NTAG216), optionally the profile and the writer reserve under
   **Advanced settings**. These choices apply to the current session; **Set as default** next to the tag selector keeps them for later launches (CLI:
   `--save-nfc-default`).
2. Export the NFC file and check its size estimate in the card.
3. Import it into your writer and select MIME `application/json`.
4. Program the tag and read it back.
5. Check the printer's detected brand, material and colour.

<details>
<summary><strong>Diagnosis: empty TLV, Capability Container and parser reference</strong></summary>

`0300FE` denotes an empty NDEF TLV; it is not filament data. A reader error
about CC `E1107F00` concerns tag formatting/compatibility. Neither is proof of a
SpoolScribe defect; a JSON export cannot repair a tag's CC.

The audit simulated the parser pinned by
[Paxx12-24](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/v2.0.0-paxx12-24/overlays/firmware-extended/64-app-openrfid/pre-scripts/01-install-openrfid.sh),
[OpenRFID a13bc9e](https://github.com/suchmememanyskill/OpenRFID/blob/a13bc9e181374e182f61db4e69abf9fa1786cc29/src/tag/openspool/processor.py).
Physical iPhone/tag/printer acceptance remains a separate check.

</details>

[← Check compatibility](Printers-and-Readers.md) · [Get help →](FAQ.md)
