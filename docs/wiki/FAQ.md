# Frequently asked questions

[Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ]()

**Jump to:** [Your catalogue](#your-catalogue) · [Hardware & tags](#hardware--tags) · [Privacy & files](#privacy--files)

## Your catalogue

<details>
<summary><strong>Does clearing filters delete my favourites?</strong></summary>

No. Clearing filters resets the current search and filter choices, including
favourites-only views. Saved manufacturer and filament favourites remain available.

</details>

<details>
<summary><strong>Why is the app empty after installation?</strong></summary>

The installer contains no catalogue. Choose your sources in the first dialog
and click **Refresh now**. Offline, nothing can be shown until a
first download has succeeded; afterwards the cached catalogue works offline.

</details>

<details>
<summary><strong>Why do PolyLite, Panchroma or Fiberon not appear as manufacturers?</strong></summary>

They are Polymaker product lines that some sources list as brands. SpoolScribe
files them under Polymaker (likewise PrimaSelect/PrimaValue under 3D Prima,
Hyper under Creality, Extrafill under Fillamentum); the card shows
« Marque · ligne ».

</details>

<details>
<summary><strong>Why is there one row for several spool sizes?</strong></summary>

A row is a filament: manufacturer, product and colour. Its 1 kg, 3 kg, refill
or 2.85 mm references are grouped and listed in the card (**References**),
each with its state. Choose your actual packaging before export; the OpenSpool fields depend on the selected export profile. When
the sources disagree on the hue, the best-documented HEX (yours, then the
manufacturer's, then the community's) is shown and the card says so.

</details>

<details>
<summary><strong>A reference is missing, has no colour, or is marked “Needs review”</strong></summary>

- **Missing colour**: the GUI and the CLI ask for an explicit representative HEX
  at export time; cancelling the colour cancels the export.
- **Missing temperatures / density / diameter**: the export button becomes
  **Correct the properties…** and opens the in-card draft; save a personal copy with an
  editable `@suffix`; the source stays intact.
- **“Needs review”**: the source published a value that contradicts itself
  (for example a black HEX for a "White" filament, or a density of 7 g/cm³).
  Open the card, correct the value explicitly, and the record becomes exportable.
- **Missing reference**: the CLI can add an unknown reference against an existing
  product. Contributions upstream (to Open Filament Database or SpoolmanDB)
  benefit everyone.

Your corrections are saved locally with the provenance « Utilisateur » and
survive every refresh. Values of unknown origin (older installations) are
corrected by manufacturer sources and completed by community sources.

</details>

<details>
<summary><strong>What does « Export possible » mean?</strong></summary>

Only that the required catalogue fields are filled in. It says nothing about the
filament's quality, nor that every printer recognizes the tag. OpenTag3D additionally
requires explicit label settings; see [the writing guide](Writing-RFID-Tags.md).

</details>

<details>
<summary><strong>How do I change the interface language?</strong></summary>

Open **Settings → Interface**. Choose the system language or English, French, Spanish or Simplified Chinese. Save, then restart now or later. Your data and favourites remain intact.

</details>

## Hardware & tags

<details>
<summary><strong>My printer is not in the list, or my firmware is missing</strong></summary>

**My hardware → Refresh list** downloads the
current `data/printers.json` from the repository (network authorization
required). If your machine is still missing, open an issue with the reader
technology and firmware; see [Printers and Readers](Printers-and-Readers.md).

</details>

<details>
<summary><strong>Do I need the paxx12 firmware?</strong></summary>

To have the **[Snapmaker U1](https://snapmaker.com/snapmaker-u1) read tags
automatically**, yes — the
[paxx12 fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)
exposes the RFID reader. SpoolScribe itself only generates the tag payloads and
works on any machine. Other OpenSpool-capable readers can use the same files.

</details>

<details>
<summary><strong>Which tag and which profile?</strong></summary>

NTAG215 or NTAG216. The app checks the usable capacity (respectively 504 or 872 bytes for this NDEF workflow), not just the chip’s advertised memory. The recommended *essential* profile
(material, colours, temperatures, diameter, density) is the compact choice. The app checks the actual payload against your tag and reserve before export. The *full* profile adds names and brand metadata and is an explicit choice.
These profiles apply to OpenSpool; OpenTag3D uses its own binary layout and explicit
label settings. See [Writing RFID Tags](Writing-RFID-Tags.md).

</details>

<details>
<summary><strong>Which tag hardware do I need?</strong></summary>

SpoolScribe Companion is in development. Until an official download is available,
use a writer compatible with the exported file: OpenSpool JSON or OpenTag3D raw
NDEF. Desktop does not select or certify a third-party writing application.
See [label export](Writing-RFID-Tags.md) and [Companion availability](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/COMPANION.md).

</details>

## Privacy & files

<details>
<summary><strong>Is this an official app of a filament manufacturer or of Snapmaker?</strong></summary>

No. SpoolScribe is an **unofficial hobby project**, not affiliated with, endorsed
by, or connected to any filament manufacturer (Polymaker, Bambu Lab, Prusa
Research, SUNLU, eSUN…) or to Snapmaker. See
[TRADEMARKS.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/TRADEMARKS.md).

</details>

<details>
<summary><strong>Does it send my data anywhere?</strong></summary>

No. There is **no telemetry, no tracking, no account**. The network is used for
four things only, all listed before you agree: the first download of the
catalogue, the refresh of the sources you selected (at the cadence you choose,
daily by default, or when you click **Refresh catalogue**), the printer list refresh
when you click **My hardware → Refresh list**, and
the release check when you click **Check for an application update**. Servers see
your IP and the User-Agent, nothing about your catalogue or printer. See
[PRIVACY.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md).

</details>

<details>
<summary><strong>Is the data free to use?</strong></summary>

The code is MIT. Open Filament Database and SpoolmanDB are MIT;
[TheFilamentDB](https://thefilamentdb.issou.best/) is CC-BY 4.0 (attribution
provided); manufacturer pages provide factual values only. Logos remain the
trademarks of their owners. Full details:
[DATA_SOURCES.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_SOURCES.md).

</details>

<details>
<summary><strong>Can I remove a manufacturer logo?</strong></summary>

Logos are bundled in the application with a transparent background (checked by
a test); the packaged app shows the brand name when a logo is absent. Official
logos are being re-sourced brand by brand with their origin recorded in the
manifest. To build a copy without a logo, remove its entry from
`data/brands/manifest.json`; delete the image only when no other entry uses it.
See the [removal and legacy fallback rules](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/TRADEMARKS.md).
Trademark holders can also request removal by opening an issue.

</details>

<details>
<summary><strong>Where are my files?</strong></summary>

Database, settings and exports are in your user folder, never next to the
application: `%APPDATA%\SpoolScribe` (Windows), `~/Library/Application
Support/SpoolScribe` (macOS), `~/.config/SpoolScribe` (Linux). Backups
(`polymaker_db.json.bak`, `.pre-update.bak`) sit next to the database. To move
your data to another computer, see [Backing up your data](Backup-and-Restore.md).

</details>

Still stuck? [Report an issue](https://github.com/ArN-LaB/Spoolscribe-/issues/new/choose) with your app version, operating system and the steps that reproduce it.
