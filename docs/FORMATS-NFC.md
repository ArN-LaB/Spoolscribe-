# Is OpenSpool 1.0 the only RFID/NFC format for 3D printers?

**No.** OpenSpool is one of several data formats. A compatible NFC chip, encoding
and reader software are three separate requirements. The current
[stable Desktop release](https://github.com/ArN-LaB/Spoolscribe-/releases/latest)
prepares **OpenSpool 1.0** and **OpenTag3D 2.004** without physically writing a tag.
The descriptions below are documentary checks, not certification of every printer.

| Format | Documented encoding and medium | SpoolScribe export |
| --- | --- | --- |
| OpenSpool 1.0 | JSON, one `application/json` NDEF record, NTAG215/216; project examples set `version` to `1.0` | Compact NFC output and a full archive, using the existing rules |
| OpenTag3D | Separate standard, published version 2.004 at the time of review; binary structure, `application/opentag3d` NDEF, NTAG215/216 according to its specification | Absent in v0.3.5; [available in subsequent releases](OPENTAG3D.md) |
| OpenPrintTag | `application/vnd.openprinttag` NDEF with CBOR sections; the specification describes ISO/IEC 15693-3/NFC-V | Not implemented |
| Manufacturer formats | Device-specific encoding and reading requirements; some require keys. An RFID/NFC reader does not necessarily accept OpenSpool | No proprietary encoder; OpenSpool reading only for an explicitly documented setup |

Primary sources: [OpenSpool protocol and 1.0 example](https://github.com/spuder/OpenSpool#-openspool-protocol),
[OpenTag3D specification](https://opentag3d.info/spec.html),
[OpenPrintTag data format](https://github.com/OpenPrintTag/openprinttag-specification/blob/main/docs_src/nfc_data_format.md).
OpenSpool 1.0 and OpenTag3D 2.004 are versions of **different formats**. Changing a
JSON `version` value does not convert a tag.

## Snapmaker U1

The [extended firmware OpenSpool documentation](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/openspool.md)
describes OpenSpool 1.0 JSON, its fields and U1 extensions. Its
[RFID reader matrix](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md)
also documents OpenRFID and other formats/readers. OpenSpool is therefore not the
only format described for that ecosystem. These sources are on **develop**;
they do not verify the firmware installed on your machine.

Acceptance testing must check the actual firmware, detection system and tag.
Adding the OpenTag3D encoder neither changes Paxx12 nor replaces a physical NFC
test. See [Printers and readers](wiki/Printers-and-Readers.md) for setup requirements.

## What compatibility means in the interface

Compatibility with SpoolScribe means the ability to read its **OpenSpool or
OpenTag3D export** for the selected setup. A printer may read its own RFID or
OpenPrintTag without accepting a SpoolScribe OpenSpool export. You can still
browse filament information for other printer categories.

[OpenTag3D 2.004 export](OPENTAG3D.md) uses a separate encoding: raw NDEF in the GUI,
with legacy writer containers retained in the CLI/API. It does not convert
existing OpenSpool tags or provide an OpenPrintTag encoder. Physical acceptance
remains separate from software tests.

## SSQR1 transports the selected format

SSQR1 is not a third NFC format. It carries the **complete OpenSpool or OpenTag3D
NDEF message** without converting it. The digital QR can be displayed or saved
as PNG/SVG. A Companion implementation must decode it before writing a chip;
a generic QR reader does not perform that write.
[Digital contract](QR_FORMAT.md) · [Illustrated workflow](wiki/Companion-and-QR.md).
