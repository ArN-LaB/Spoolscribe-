# Getting started

[Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ](FAQ.md)

[Prefer pictures? Follow the v0.6.0 visual tour](Visual-Tour.md).

**From an empty catalogue to your first exported label.** No Python installation needed.

| 1. Install | 2. Download sources | 3. Pick a filament | 4. Export |
| --- | --- | --- | --- |
| Choose your platform. | Give consent and refresh. | Confirm colour and spool size. | Configure a reader and save the file. |

## 1. Download and open

**v0.6.0 is a pre-release.** [Choose v0.3.5 for the latest stable build](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.3.5).

| Platform | v0.6.0 pre-release download | Inside the ZIP |
| --- | --- | --- |
| **Windows · x64** | [Application](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-windows.zip) · [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-windows.zip.sha256) | One <code>SpoolScribe.exe</code> |
| **macOS · Apple Silicon** | [Application](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-macos.zip) · [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-macos.zip.sha256) | One <code>SpoolScribe.app</code> |
| **Linux · x64** | [Application](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-linux.zip) · [SHA-256](https://github.com/ArN-LaB/Spoolscribe-/releases/download/v0.6.0/SpoolScribe-linux.zip.sha256) | One <code>SpoolScribe</code> executable |

Verify the download’s origin and checksum, unzip it and open the application.

<details>
<summary><strong>First-launch checks on macOS, Windows and Linux</strong></summary>

- **macOS:** the Apple Silicon bundle is ad hoc signed, without Apple notarisation.
  Use the system’s per-application **Open** option after verification. Do not disable
  Gatekeeper globally. For your own source builds, see the
  [local installation guide](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/LOCAL_MACOS_INSTALL.md).
- **Windows:** the executable has no commercial signing certificate. Verify origin
  and checksum before responding to SmartScreen.
- **Linux:** a recent glibc and Qt libraries <code>libegl1</code>,
  <code>libxkbcommon0</code> and <code>libdbus-1-3</code> are required.

Compare the supplied SHA-256 using <code>shasum -a 256</code> on macOS,
<code>sha256sum</code> on Linux, or <code>Get-FileHash -Algorithm SHA256</code> in PowerShell.

[Run or build from source](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DEVELOPMENT.md).

</details>

## 2. Choose the language and download the catalogue

**English · Français · Español · 简体中文**

The app follows supported system languages and otherwise uses English.
Change it in **Settings → Interface**. Save, then choose **Restart now** or
**Later**; your data and favourites remain intact.

The first launch starts empty. Choose your sources, give network consent and
click **Refresh now**. Later, **Refresh catalogue** lets you refresh on demand.
After the first download, your saved catalogue works offline.

[Choose sources and understand refresh results](Updating-the-Database.md)

## 3. Find your filament

[![List view: filters on the left, filaments in the centre, selected filament and export on the right](https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/catalogue.png)](https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/catalogue.png)

| Narrow the list | Keep your favourites | Confirm the actual spool |
| --- | --- | --- |
| Search products, colours or references. Manufacturer and material filters narrow each other. | Save manufacturers and filaments. Clearing filters keeps those favourites. | Open a row or grid card. Choose the shade when sources disagree, then the available spool size. |

Click a column header to sort; click again to reverse. Its context menu selects
primary/secondary sort and visible columns. Use the list/grid buttons to switch views.

**Your usual packaging:** set it in **Settings → Spools**. It is preselected when available.
**Your own adjustments:** **Edit…** opens a draft inside the card; **Save a copy** stores an
independent copy with an editable <code>@suffix</code>, **Cancel** writes nothing. The value
comparison shows reference, Orca, personal and exported values. The source stays intact;
refreshes preserve your copy.

## 4. Configure your reader and export

| In the app | Next action |
| --- | --- |
| **My hardware** | Choose the printer, then combine reader/software/installed-solution buttons. [Check compatibility](Printers-and-Readers.md). |
| **Tag type** | Choose the NTAG215 or NTAG216 you bought. Advanced profile/reserve settings are optional. |
| **Format / writing app** | Choose an eligible format. OpenTag3D offers NFC Tools mobile/Desktop profiles and an expert raw NDEF output. |
| **Show JSON / Show export** | Inspect the file; the window size stays unchanged. |
| **Export for NFC** | Choose a destination folder and wait for the saved-file confirmation. Cancelling creates no file. |

An explicitly configured OpenSpool or OpenTag3D setup enables the corresponding
export. The result distinguishes printer recognition from external inventory.
Other setups provide a reference sheet. SpoolScribe prepares the payload and does not replace the slicer profile.

The export card connects your printer and tag, with a space-left gauge.
**Details**, beside the tag, opens **Your next steps** and a separate **Technical information** tab.
The **Colours** section sits below **Materials** in the left sidebar: choose a swatch
or enter a code, then **Compare**. **Remove** clears only this comparison.
All filter categories share the same collapsible card design. The active-filter
button lists your criteria without adding a paragraph. **Remove** also clears an
unapplied colour code; it is disabled when empty. Saved favourites remain intact.
**Help** explains the results and excluded records in cards, with the method in a separate tab.
Printed results may differ from on-screen colours.

Named printer/family choices have transparent product photos, with the actual
illustrated model identified in example captions. Generic choices without a
specific model, and standalone readers, retain clearly identified icons.
The same images appear in the picker, hardware card and export card.
For OpenTag3D, **Details → Your next steps →
Edit label values…** opens the settings. The main card keeps a single primary action.

**Next:** use the matching NFC writing app, read the tag back, then check it on your reader.
Documented support is not exhaustive hardware certification;
[successful tests and problems are welcome](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=printer_compatibility.yml).

[Continue to writing and read-back](Writing-RFID-Tags.md)
