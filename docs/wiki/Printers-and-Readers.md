# Printers and Readers

SpoolScribe writes nothing to a printer: it prepares an OpenSpool JSON payload
for an NTAG215/NTAG216 tag. Whether that tag is ever read depends on the
machine's spool reader and its firmware. The list below is the bundled
`data/printers.json` (version 2026-11-01), shown in **⚙ → Mon matériel**; the
dialog's **Mettre à jour la liste des imprimantes…** button downloads the
current file from the repository (network authorization required, strict
validation, installed only when newer).

Four groups:

| Group | Meaning |
|---|---|
| **Native** | The printer's own reader reads an OpenSpool NTAG |
| **External reader** | A separate NFC reader reads the tag and tells the printer or Spoolman |
| **Proprietary** | The printer has a reader, but it only accepts its own (often encrypted) tag format |
| **No reader** | Nothing reads a spool tag; an external reader remains possible |

## Printers

| Printer | Reader | Firmware | SpoolScribe export | Note |
|---|---|---|---|---|
| Snapmaker U1 | NFC ISO 14443-A, integrated (NTAG21x) | **paxx12 open firmware** — reads OpenSpool since 0.9.4 | **OpenSpool** | Material and colour identify the filament; brand is optional. [Firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) |
| Snapmaker U1 | same | Stock firmware | none | Reads only Snapmaker tags (MIFARE Classic 1K); an OpenSpool tag is ignored |
| Flashforge AD5X / Creator 5 | FF_NFC community reader | Zmod / Kiln OS + FF_NFC | **OpenSpool** | Community firmware; check the reader's documentation. [Zmod](https://github.com/ghzserg/zmod) |
| Flashforge AD5X / Creator 5 | — | Stock firmware | none | No spool reader |
| Klipper + Spoolman (Voron, Sovol SV08, RatRig…) | External NFC reader (SpoolSense, nfc2klipper, Happy Hare…) | Klipper + Spoolman | **OpenSpool** (conservative) | The format each module understands depends on its version; check its documentation |
| Bambu Lab + external OpenSpool reader | OpenSpool ESP32 + PN532 → printer via MQTT (developer mode) | Stock firmware + developer mode | **OpenSpool** | The AMS does not read the tag; the external reader sends the filament over MQTT. [OpenSpool](https://github.com/spuder/OpenSpool) |
| Other OpenSpool reader | any | per reader | **OpenSpool** (conservative) | All printing parameters are required by SpoolScribe; their use depends on the reader |
| Bambu Lab X1 / P1 / A1 / H2 (AMS) | RFID MIFARE Classic, encrypted and signed (Bambu spools) | Stock, or X1Plus (X1 only) | none | The AMS ignores OpenSpool, OpenTag3D and OpenPrintTag; X1Plus changes nothing. Reference sheet for Bambu Studio |
| Prusa CORE One / MK4S / XL | Optional NFC-V ISO 15693 reader (CORE One); firmware 8.0 reads OpenPrintTag | Stock 8.0+ | none | OpenPrintTag uses ISO 15693 tags and a CBOR payload: an NTAG215/216 OpenSpool tag is not read; no OpenPrintTag encoder in SpoolScribe |
| Creality K2 / K2 Plus / Hi (CFS) | RFID MIFARE Classic, proprietary (Creality spools) | Stock | none | NTAG tags are not read by the CFS |
| Anycubic Kobra S1 / Kobra 3 (ACE Pro) | NFC NTAG213 in Anycubic's format | Stock | none | Unencrypted but different from OpenSpool |
| Elegoo Centauri Carbon 2 (CANVAS) | NFC NTAG213, published Elegoo specification | Stock | none | Binary Elegoo format, different from OpenSpool |
| QIDI Plus4 / Q2 / Max4 (QIDI Box) | RFID MIFARE Classic (QIDI spools) | Stock | none | Official QIDI specification, different from OpenSpool |
| UltiMaker 3 / S-series (Material Station) | NFC NTAG216 in UltiMaker's format (Cura GUID) | Stock | none | UltiMaker format, different from OpenSpool |
| Raise3D Pro3 HS | Proprietary RFID | Stock | none | Reference sheet only |
| MakerBot METHOD | Proprietary RFID ISO 15693 | Stock | none | Reference sheet only |
| XYZprinting da Vinci | Proprietary NFC (DRM) | Stock | none | Reference sheet only |
| No reader (Snapmaker Artisan/J1, Flashforge AD5M, Phrozen Arco, Zortrax, Kingroon…) | none | Stock | none | An external reader remains possible (see Klipper + Spoolman) |

"SpoolScribe export: none" means the tag controls are hidden in the card and
the record is a reference sheet for your slicer profile. No proprietary tag
format is generated.

## External readers listed

| Reader | Works with | Tags |
|---|---|---|
| [OpenSpool](https://github.com/spuder/OpenSpool) (ESP32 + PN532) | Bambu Lab via MQTT | OpenSpool |
| SpoolEase | Bambu Lab | SpoolEase format (NDEF URL) |
| FF_NFC | Flashforge under Zmod / Kiln OS | OpenSpool |
| nfc2klipper | Klipper + Spoolman | depends on configuration |
| Happy Hare (NFC) | Klipper MMU | depends on configuration |
| SpoolSense | Klipper + Spoolman | depends on configuration |
| SpoolLink | Snapmaker U1 + Spoolman (spool linked by tag UID) | UID only |
| Prusa OpenPrintTag reader | Prusa CORE One | OpenPrintTag (ISO 15693) |

## Not confirmed by a primary source

- Behaviour of the Bambu Lab X2D / P2S / H2C and of the ACE 2 Pro.
- Availability of the Prusa OpenPrintTag reader outside the CORE One family.
- Formats decoded by Happy Hare, nfc2klipper and SpoolSense in their current versions.

If your printer or firmware is missing or wrong, open an issue with the reader
technology, the firmware and a link to its documentation; the list is data, not
code, and can be refreshed without a new release.
