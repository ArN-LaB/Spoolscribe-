# 🖨 Printers & readers

[⌂ Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ](FAQ.md)

**Check the reader and installed software, not just the printer name.**
SpoolScribe exports OpenSpool 1.0 JSON. A printer having RFID/NFC does not
mean it accepts that format.

<table>
<tr>
<td width="50%" align="center"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers/photos/u1.webp" alt="Snapmaker U1" width="140"><br><strong>Snapmaker U1</strong><br>OpenSpool with compatible paxx12 firmware.</td>
<td width="50%" align="center"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers/photos/bambu-x1c-transparent.png" alt="Bambu Lab X1 Carbon, illustrated AMS family model" width="140"><br><strong>Bambu Lab X1 Carbon</strong><br>Native tags use a different format; an external OpenSpool reader is a separate setup.</td>
</tr>
</table>

## OpenSpool configurations

NFC export is available for these documented configurations. Confirm the exact
firmware and external-reader documentation before writing a tag.

| Printer / setup | Required software | Reader & limits |
| --- | --- | --- |
| Snapmaker U1 | **paxx12 open firmware** — reads OpenSpool since 0.9.4 | NFC ISO 14443-A, integrated (NTAG21x); Material and colour identify the filament; brand is optional. [Firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware) |
| Flashforge AD5X / Creator 5 | Zmod / Kiln OS + FF_NFC | FF_NFC community reader; Community firmware; check the reader's documentation. [Zmod](https://github.com/ghzserg/zmod) |
| Klipper + Spoolman (Voron, Sovol SV08, RatRig…) | Klipper + Spoolman | External NFC reader (SpoolSense, nfc2klipper, Happy Hare…); The format each module understands depends on its version; check its documentation |
| Bambu Lab + external OpenSpool reader | Stock firmware + developer mode | OpenSpool ESP32 + PN532 → printer via MQTT (developer mode); The AMS does not read the tag; the external reader sends the filament over MQTT. [OpenSpool](https://github.com/spuder/OpenSpool) |
| Other OpenSpool reader | per reader | any; All printing parameters are required by SpoolScribe; their use depends on the reader |

## Other RFID formats & reference sheets

For these configurations, SpoolScribe provides filament information for your
slicer. It does **not** generate their native tag format; NFC export controls are hidden.

| Printer / setup | Software | Why an OpenSpool tag is not sufficient |
| --- | --- | --- |
| Snapmaker U1 | Stock firmware | Reads only Snapmaker tags (MIFARE Classic 1K); an OpenSpool tag is ignored |
| Flashforge AD5X / Creator 5 | Stock firmware | No spool reader |
| Bambu Lab X1 / P1 / A1 / H2 (AMS) | Stock, or X1Plus (X1 only) | The AMS ignores OpenSpool, OpenTag3D and OpenPrintTag; X1Plus changes nothing. Reference sheet for Bambu Studio |
| Prusa CORE One / MK4S / XL | Stock 8.0+ | OpenPrintTag uses ISO 15693 tags and a CBOR payload: an NTAG215/216 OpenSpool tag is not read; no OpenPrintTag encoder in SpoolScribe |
| Creality K2 / K2 Plus / Hi (CFS) | Stock | NTAG tags are not read by the CFS |
| Anycubic Kobra S1 / Kobra 3 (ACE Pro) | Stock | Unencrypted but different from OpenSpool |
| Elegoo Centauri Carbon 2 (CANVAS) | Stock | Binary Elegoo format, different from OpenSpool |
| QIDI Plus4 / Q2 / Max4 (QIDI Box) | Stock | Official QIDI specification, different from OpenSpool |
| UltiMaker 3 / S-series (Material Station) | Stock | UltiMaker format, different from OpenSpool |
| Raise3D Pro3 HS | Stock | Reference sheet only |
| MakerBot METHOD | Stock | Reference sheet only |
| XYZprinting da Vinci | Stock | Reference sheet only |
| No reader (Snapmaker Artisan/J1, Flashforge AD5M, Phrozen Arco, Zortrax, Kingroon…) | Stock | An external reader remains possible (see Klipper + Spoolman) |

<details>
<summary><strong>Technical reader specifications for the other configurations</strong></summary>

| Configuration | Reader / native format |
| --- | --- |
| Snapmaker U1 · Stock firmware | same |
| Flashforge AD5X / Creator 5 · Stock firmware | — |
| Bambu Lab X1 / P1 / A1 / H2 (AMS) · Stock, or X1Plus (X1 only) | RFID MIFARE Classic, encrypted and signed (Bambu spools) |
| Prusa CORE One / MK4S / XL · Stock 8.0+ | Optional NFC-V ISO 15693 reader (CORE One); firmware 8.0 reads OpenPrintTag |
| Creality K2 / K2 Plus / Hi (CFS) · Stock | RFID MIFARE Classic, proprietary (Creality spools) |
| Anycubic Kobra S1 / Kobra 3 (ACE Pro) · Stock | NFC NTAG213 in Anycubic's format |
| Elegoo Centauri Carbon 2 (CANVAS) · Stock | NFC NTAG213, published Elegoo specification |
| QIDI Plus4 / Q2 / Max4 (QIDI Box) · Stock | RFID MIFARE Classic (QIDI spools) |
| UltiMaker 3 / S-series (Material Station) · Stock | NFC NTAG216 in UltiMaker's format (Cura GUID) |
| Raise3D Pro3 HS · Stock | Proprietary RFID |
| MakerBot METHOD · Stock | Proprietary RFID ISO 15693 |
| XYZprinting da Vinci · Stock | Proprietary NFC (DRM) |
| No reader (Snapmaker Artisan/J1, Flashforge AD5M, Phrozen Arco, Zortrax, Kingroon…) · Stock | none |

</details>

<details>
<summary><strong>External readers and their formats</strong></summary>


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


</details>

## Check an uncertain or missing configuration


- Behaviour of the Bambu Lab X2D / P2S / H2C and of the ACE 2 Pro.
- Availability of the Prusa OpenPrintTag reader outside the CORE One family.
- Formats decoded by Happy Hare, nfc2klipper and SpoolSense in their current versions.

If your printer or firmware is missing or wrong, open an issue with the reader
technology, the firmware and a link to its documentation; the list is data, not
code, and can be refreshed without a new release.



## Find your setup in the app

Open **⚙ → My hardware**, search for the printer or reader, and confirm the
installed software. The picker shows a short product summary and an explicit
OpenSpool status. **Refresh list** retrieves the reviewed hardware catalogue
after network consent; failed updates keep the current list.

Images illustrate named models, not every printer in a family. Accessories and
reader support may differ. [Image provenance](https://github.com/ArN-LaB/Spoolscribe-/blob/main/data/printers/photos/manifest.json).

<details>
<summary><strong>Catalogue, other formats and source references</strong></summary>

This guide follows the bundled hardware catalogue dated 2026-11-01:
[data/printers.json](https://github.com/ArN-LaB/Spoolscribe-/blob/main/data/printers.json).
Its public path remains stable for existing app installations. A newer validated
list can be installed without a new application release. An unpublished list or
network error leaves the current catalogue available.

OpenSpool, OpenTag3D and OpenPrintTag have different encodings. This guide describes
the export implemented by SpoolScribe, not every format a reader might support.
See [NFC formats and source verification](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/FORMATS-NFC.md).
No new encoder or physical acceptance is implied.

</details>

[Ready to write a tag? →](Writing-RFID-Tags.md) · [U1 walkthrough →](Snapmaker-U1-and-paxx12.md)
