<p align="center"><img src="docs/images/spoolscribe-animated.gif" alt="SpoolScribe animated logo" width="128" height="128"></p>

<h1 align="center">SpoolScribe <sub>v0.8.1</sub></h1>
<p align="center"><strong>Find your filament. Prepare its NFC label.</strong></p>
<p align="center">Windows · macOS · Linux<br>English · Français · Español · 简体中文</p>
<p align="center">
  <a href="https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.1"><img src="https://img.shields.io/badge/v0.8.1-stable-008899" alt="v0.8.1 stable"></a>
  <a href="https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml"><img src="https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml/badge.svg?branch=main" alt="Build and tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT licence"></a>
</p>
<p align="center"><a href="#download">Download</a> · <a href="https://github.com/ArN-LaB/Spoolscribe-/wiki/Getting-Started">Get started</a> · <a href="https://github.com/ArN-LaB/Spoolscribe-/wiki">Help centre</a> · <a href="docs/COMPANION.md">Companion</a></p>

A free desktop filament catalogue with visual colour matching, personal references,
**OpenSpool 1.0 / OpenTag3D 2.004 exports** and **offline SSQR1 QR transfer**.
No account. Your catalogue stays local after its first download.

<p align="center">
  <a href="docs/images/catalogue.png"><img src="docs/images/catalogue.png" alt="Find and select a filament" width="980"></a>
</p>
<p align="center"><strong>Find and select a filament</strong><br><sub>Actual v0.8.1 interface · public demonstration data.</sub></p>

## Download

**v0.8.1 is the current stable Desktop release.** Software stability and hardware
compatibility are separate: printer/reader setups are documented individually and
are not all physically tested. [Validation](docs/validation/v0.8.1.md) · [Release policy](docs/RELEASE_POLICY.md).

| System | Application | Integrity check |
| --- | --- | --- |
| Windows 10 / 11 · x64 | [Download ZIP](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-windows.zip) | [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-windows.zip.sha256) |
| macOS · Apple Silicon | [Download ZIP](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-macos.zip) | [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-macos.zip.sha256) |
| Linux · x64 | [Download ZIP](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-linux.zip) | [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.8.1/SpoolScribe-linux.zip.sha256) |

Unzip and open the application. No Python installation is needed.
The v0.8.1 macOS Apple Silicon archive is signed with Developer ID and notarised
by Apple. Keep Gatekeeper enabled. Windows is not commercially signed. Linux
needs a recent glibc and Qt system libraries. Intel/universal2 is not provided.
[First-launch instructions](https://github.com/ArN-LaB/Spoolscribe-/wiki/Getting-Started) · [Build from source](docs/DEVELOPMENT.md).

## New in v0.8.1

- Clearer settings, refresh cadence and portable preference import/export.
- Previewed ZIP backups, restoration and explicit undo, with recoverable conflicts.
- Origin and reliability of effective values, multilingual About information.
- Shared printer configurations: unknown setups require explicit confirmation;
  uncertain NFC exports remain blocked.
- Optional local diagnostics, off by default. AES-256-GCM is a future feature:
  preference JSON and data-backup ZIP files are **not encrypted**.

[Back up and restore your data](docs/wiki/Backup-and-Restore.md) · [Settings](docs/wiki/Settings.md).

## Find the right reference

1. Select your catalogue sources and refresh after giving network permission.
2. Choose a manufacturer and material: each filter narrows the other.
3. Select the colour and the actual spool size. Pin useful favourites.
4. Keep your adjustments in a personal copy; source refreshes preserve it.

<p align="center">
  <a href="docs/images/collection.png"><img src="docs/images/collection.png" alt="See the colour and spool size" width="980"></a>
</p>
<p align="center"><strong>See the colour and spool size</strong><br><sub>Switch between list and grid without losing your selection.</sub></p>

[Filaments, filters, columns and favourites](docs/wiki/Filaments-and-Favourites.md).

## Compare colours

Enter a HEX code or choose a swatch, then **Compare**. A smaller **ΔE** means
closer declared screen colours. The limit **ΔE ≤ 10** is a maximum distance,
not a percentage. Effects, transparency and printing can change the real result.

<p align="center">
  <a href="docs/images/colour-search.png"><img src="docs/images/colour-search.png" alt="Find nearby colours" width="980"></a>
</p>
<p align="center"><strong>Find nearby colours</strong><br><sub>The same ΔE values are available in list view.</sub></p>

Have Lab/RGB values or a file instead? Open **Lab, RGB or file…** to enter values,
interpret labelled text or review CSV/TSV columns. Save references and explicitly
reuse device entry settings without altering catalogue colours.

<p align="center">
  <a href="docs/images/colour-lab.png"><img src="docs/images/colour-lab.png" alt="Use documented colour values" width="800"></a>
</p>
<p align="center"><strong>Use documented colour values</strong><br><sub>CIELAB needs documented D65 and 2° conditions for catalogue comparison.</sub></p>

[Colour entry, files and saved references](docs/wiki/Measuring-Colours.md).

## Choose the real printer setup

Select the model, then the reader and software actually installed. The result
explains what the configuration can read. A USB reader alone is not proof that
the printer firmware accepts a format.

<p align="center">
  <a href="docs/images/hardware.png"><img src="docs/images/hardware.png" alt="Check the reader and software" width="780"></a>
</p>
<p align="center"><strong>Check the reader and software</strong><br><sub>Compatibility depends on the complete setup.</sub></p>

[Printer setup help](docs/wiki/Printers-and-Readers.md).

## Take the label to Companion

**Show QR Code — SpoolScribe Companion** displays the complete NFC message in an
offline QR. Save PNG or SVG, or keep it on screen. The QR contains data, not a
website or an App Store link.

<p align="center">
  <a href="docs/images/qr-companion.png"><img src="docs/images/qr-companion.png" alt="Transfer the complete NFC message" width="620"></a>
</p>
<p align="center"><strong>Transfer the complete NFC message</strong><br><sub>Companion mobile downloads are not yet available.</sub></p>

**SpoolScribe Companion is being developed for mobile use.** Official iOS and
Android links will appear on the [shared availability page](docs/COMPANION.md).
Until then, use a writer compatible with the chosen OpenSpool JSON or OpenTag3D
NDEF file. Desktop does not write the physical NFC tag.

A generic scanner can read SSQR1 text. QR error correction repairs damaged data;
it does not restrict scanning to Companion. [QR help](docs/wiki/Companion-and-QR.md)
explains the distinction and the future app-link path.

## Help, privacy and feedback

| Need | Start here |
| --- | --- |
| Learn each screen | [Illustrated help centre](docs/wiki/Home.md) |
| Select labels or paper | [Product codes and manufacturer templates](docs/PRINTING_GUIDE.md) |
| Understand stored data | [Privacy](docs/PRIVACY.md) · [Data sources](docs/DATA_SOURCES.md) |
| Check software validation | [v0.8.1 evidence](docs/validation/v0.8.1.md) |
| Report a problem or a working setup | [Issues](https://github.com/ArN-LaB/Spoolscribe-/issues/new/choose) |
| Contribute or support development | [Contributing](.github/CONTRIBUTING.md) · [Buy Me a Coffee](https://buymeacoffee.com/arn_lab) |

Report the model, reader, firmware/plugin, tag type and format when sharing a
hardware result. Software CI is not a certification of every listed printer.
**822 offline tests** run in each of four CI configurations; three native builds
also exercise catalogue/NFC, colour entry and independent digital QR decoding.

SpoolScribe is independent of printer and filament manufacturers. Code: MIT.
Data licences and artwork credits: [NOTICE](NOTICE) · [Trademarks](docs/TRADEMARKS.md).

## Development agents

For development, review, handoffs and documentation maintenance, start with
[UNIVERSAL](docs/UNIVERSAL.md), then retain the project-specific technical and safety rules in
[Contributing](.github/CONTRIBUTING.md) and [Development](docs/DEVELOPMENT.md).
