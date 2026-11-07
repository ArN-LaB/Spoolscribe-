# OpenTag3D export

[Documentation](README.md) · [Reader setups](PRINTER-CONFIGURATIONS.md) · [NFC formats](FORMATS-NFC.md) · [Historical validation](validation/v0.8.0.md)

The [current stable Desktop release](https://github.com/ArN-LaB/Spoolscribe-/releases/latest)
prepares **OpenTag3D 2.004**. This is a separate format alongside OpenSpool;
it does not add OpenPrintTag or physically write a chip.

## Choose the hardware before the format

In **My hardware**, select the reader and software actually installed. Available
formats are limited to those declared for that setup.

| Selected setup | Available formats |
| --- | --- |
| U1, paxx12 default detection | OpenSpool 1.0 |
| U1, paxx12 OpenRFID detection | OpenSpool 1.0 or OpenTag3D 2.004 |
| Explicitly compatible OpenTag3D reader | OpenTag3D 2.004 |
| Bambu AMS, Prusa OpenPrintTag and other unsupported native formats | Browse filament information; no additional export enabled |

OpenRFID is a reading system; OpenSpool and OpenTag3D are data formats. The
paxx12 OpenRFID and OpenRFID Generic modes read both formats. U1 OpenTag3D support
is documented for **OpenRFID**, not the default detection system. Check the
installed version and reader documentation. SpoolScribe changes no printer
firmware or settings.

## Prepare a label

Select the filament, colour and actual spool packaging. Choose OpenTag3D 2.004
and your NTAG215/216 in **My hardware**, then open **Prepare label…**. Review
filament mass and target temperatures, and explicitly shorten labels if needed.
Check the preview and export to the chosen folder; the confirmation identifies
the saved file. Import it into a suitable writer, write and read back the tag,
then check what the reader recognises. Those physical steps require your own test.

Confirmed settings are stored **per spool reference** in user preferences.
Source catalogue data stays intact and refreshes do not replace those settings.
Preference export/import preserves the reader software, format and file type.
The current GUI defaults to raw NDEF; legacy NFC Tools containers remain available
through the CLI/API and imported preferences, rather than a mobile/desktop writer
selector in the hardware workflow.

## Values to review

| Value | Rule |
| --- | --- |
| Nozzle and bed targets | Explicit values within known bounds; any labelled proposal must be reviewed and confirmed, never silently selected |
| Chamber temperature | Never invented; `0` means no heating and needs confirmation |
| Mass | Filament mass excluding the empty spool, not a measured remaining mass |
| Encoded temperatures | Multiples of 5 °C; an unrepresentable value is refused, never silently rounded |
| Names | UTF-8 lengths checked without truncation: manufacturer 16 bytes, material and variant 5 bytes each |
| Colours | Four RGBA values in total; unknown colour requires confirmation, and no extra colour is silently dropped to fit |
| Manufacturer article | Used only when supplied; an OFD/Spoolman identifier is not turned into a manufacturer article |

Temperature bounds are optional in OpenTag3D: unknown bounds remain absent.
Diameter and density must be known. Optional fields unsupported by this initial
integration remain unset.

## Which file to use

| Output | Contents | Intended destination |
| --- | --- | --- |
| Raw NDEF message (`.ndef`, current GUI default) | Complete binary NDEF message | A writer that can import it; compatibility must be checked |
| NFC Tools mobile (`.json`, legacy CLI/API option) | Import profile with the binary message in a base64 envelope | Mobile profile import; physical acceptance untested |
| NFC Tools Desktop (`.json`, legacy CLI/API option) | Import profile with MIME type and payload bytes | NFC Tools Desktop import; physical acceptance untested |

An NFC Tools profile is **not OpenSpool JSON**. Import it as a profile rather
than writing it as a text record. Other writers' proprietary file containers
are not qualified by this integration. **View export** shows the exact generated
profile JSON; `.ndef` previews show decoded fields and hexadecimal bytes. Raw
NDEF contains no UID, manufacturer memory or Capability Container.

The payload is 224 bytes, the NDEF message 248 bytes, and Type 2 TLV/terminator
occupancy 251 bytes before writer-specific additions:

| Tag | Standard NDEF capacity | Headroom before the user's reservation |
| --- | --- | --- |
| NTAG215 | 496 bytes | 245 bytes |
| NTAG216 | 872 bytes | 621 bytes |

A reservation exceeding capacity is refused. JSON/base64 file size on disk is
not the tag's memory occupancy.

<details>
<summary><strong>CLI and explicit settings</strong></summary>

Create a local `label.json` file:

```json
{"print_temp": 210, "bed_temp": 60, "chamber_temp": 0, "weight": 1000}
```

These are example inputs, not universal temperature recommendations. From a
source installation:

```sh
python -m spoolscribe.convert_profile --nfc-format opentag3d \
  --printer opentag3d --firmware any --tag-type NTAG215 \
  --opentag-output nfctools-mobile --opentag-settings label.json
```

Enter the catalogue reference and confirm export. Missing targets and mass are
requested if not supplied. U1/OpenRFID uses
`--printer u1 --firmware paxx12_openrfid`. Select `nfctools-desktop` or `ndef`
for the other outputs. The historical archive mode remains OpenSpool;
OpenTag3D/archive is refused.

</details>

## Specification and evidence

The implementation follows the [OpenTag3D specification](https://opentag3d.info/spec.html)
and [machine schema](https://opentag3d.info/spec.json), version 2.004, revision
`5e5069cf5696e03bdd328e7bc3d15ee2fde97909`. Updates require review; schemas are
never downloaded at runtime. Other primary references are the
[official creation tool and writer files](https://opentag3d.info/make),
[U1 RFID detection](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md)
and the [pinned OpenRFID decoder](https://github.com/suchmememanyskill/OpenRFID/tree/a13bc9e181374e182f61db4e69abf9fa1786cc29/src/tag/opentag3d).
A development-branch capability description does not prove installed firmware.

SpoolScribe's encoder independently implements the standard's fields and units;
no OpenTag3D website or OpenRFID code is bundled. The
[historical software validation](validation/v0.8.0.md) records its tests and
limits. Physical imports, tags and printers require separate acceptance evidence.

## Temperature proposals and confirmation

Since v0.8.0, missing targets can be proposed from a single explicit matching
Orca U1 value, only when U1 is selected. Otherwise a known range may provide a
labelled midpoint estimate, rounded to the existing 5 °C grid within bounds.
The origin is shown; it is not a new manufacturer recommendation. Several
conflicting bed-profile values do not provide one documented target.

Without a usable range the field stays empty. Chamber heating is not inferred
from material: choose **No heating** explicitly when appropriate or enter a value.
Already confirmed values are not replaced. Editing withdraws confirmation;
**Save** remains blocked until the adjacent **Validate temperatures** control is
used. Cancelling saves no proposal and changes neither catalogue nor encoder.

Once saved values produce a valid complete label, NFC export and preview reuse
them without reopening the form. The complete message is validated at each action.
Missing or incompatible values return you to preparation. **Edit label values…**
always opens the form and requires renewed confirmation before saving. SSQR1
always carries the exact same complete NDEF message.
