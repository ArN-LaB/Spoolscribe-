# Snapmaker U1 & paxx12

[Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ](FAQ.md)

**Prepare OpenSpool labels for a U1 running compatible community firmware.**

<table>
<tr>
<td width="30%" align="center"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/data/printers/photos/u1.webp" alt="Snapmaker U1 product image" width="170"></td>
<td><strong>Snapmaker U1</strong><br>Four independent toolheads · 270 × 270 × 270 mm build volume.<br><br>The installed firmware determines which tag formats its reader accepts.<br><a href="https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware">paxx12 firmware project →</a></td>
</tr>
</table>

## Same printer, different tag support

| U1 configuration | What SpoolScribe can do |
| --- | --- |
| **Compatible paxx12 OpenSpool firmware** | Prepare an OpenSpool JSON file for NTAG215/216; confirm the installed version and its reader support. |
| **Stock firmware** | Provide a filament reference sheet; an OpenSpool label is not a native Snapmaker tag. |

The bundled catalogue documents OpenSpool support from paxx12 0.9.4. Follow the
firmware project’s current instructions for the exact installed release.

## From a spool to a recognised filament

| 1. Select | 2. Export | 3. Write & read back | 4. Check on the U1 |
| --- | --- | --- | --- |
| Find the product, colour and actual packaging. | Select U1, compatible firmware and your tag in **My hardware**. Save the JSON. | Use a separate NFC writer with an NDEF MIME <code>application/json</code> record. | Confirm the detected material and colour against the spool. |

[Writing guide](Writing-RFID-Tags.md) · [All printer configurations](Printers-and-Readers.md)

## What the label does — and what still needs checking

- Material and colour identify the filament for the documented OpenSpool reader.
- Exported fields are not all applied by every firmware. For example, the audited
  Paxx12-24 parser ignores density and exported bed temperatures.
- Keep an appropriate slicer profile. A readable tag does not validate printing settings.
- Physical tag, writer and U1 acceptance remains a separate check; screenshots and
  automated tests do not establish it.

This is a community setup, not official Snapmaker functionality. Firmware changes
belong to the paxx12 project; this guide covers the SpoolScribe side.

<details>
<summary><strong>Image and technical references</strong></summary>

[Printer image provenance](https://github.com/ArN-LaB/Spoolscribe-/blob/main/data/printers/photos/manifest.json) ·
[Bundled hardware catalogue](https://github.com/ArN-LaB/Spoolscribe-/blob/main/data/printers.json) ·
[NFC formats and parser references](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/FORMATS-NFC.md).

</details>
