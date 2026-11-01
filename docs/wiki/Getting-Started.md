# Getting started with SpoolScribe v0.3.5

[Wiki home](Home.md) · [FAQ](FAQ.md)

## 1. Download and open

Download the archive and companion SHA-256 from
[the v0.3.5 release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.3.5).

| Platform | Contents |
| --- | --- |
| Windows x64 | One `SpoolScribe.exe` |
| macOS Apple Silicon | One `SpoolScribe.app` |
| Linux x64 | One `SpoolScribe` executable; recent glibc and Qt runtime libraries required |

Verify origin and checksum before opening. Windows has no commercial signing
certificate. The macOS bundle is ad hoc signed, without Apple notarisation:
use the system’s per-application Open option after verification. Do not disable
Gatekeeper globally. For personal source builds, use the
[local installation guide](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/LOCAL_MACOS_INSTALL.md).

For Python source use and compilation, see
[Development](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DEVELOPMENT.md).

## 2. Choose the language and download the catalogue

The app follows supported system languages and otherwise uses English.
**Settings → Interface** lets you choose English, Français, Español or 简体中文.
After saving, choose **Restart now** or **Later**. No data or favourites are lost.

The first launch starts empty. Choose sources, give network consent and refresh.
Later launches use the saved cadence; **Refresh catalogue** forces a refresh.
Offline, the last downloaded catalogue remains usable.
[Source and backup details](Updating-the-Database.md).

## 3. Find your filament

Search across products, colours and references. Selecting a manufacturer limits
materials to those available; selecting a material also narrows manufacturers.
Filter by favourites or data state. Resetting filters keeps saved favourites.

Click a column header to sort, click again to reverse; its context menu selects
primary/secondary sort or visible columns. Choose a row or grid card to inspect
a filament. Its actual packaging references are grouped in the detail card.
Choose the correct shade if sources disagree, then the available spool size.
Set a preferred packaging in **Settings → Spools**.

**Modify** creates an independent personal copy with an editable `@suffix`.
The source record stays intact and refreshes preserve the copy.

## 4. Configure your reader and export

In **⚙ → My hardware**, choose printer/reader and installed software. Only a
compatible OpenSpool configuration enables NFC export; other setups provide
a reference sheet. [Check compatibility](Printers-and-Readers.md).

Choose the NTAG215 or NTAG216 you bought. Advanced profile/reserve options remain
optional. Then:

1. Inspect the JSON if desired; the window size stays unchanged.
2. Click **Export for NFC** and choose a destination folder.
3. Wait for the saved-file confirmation. Cancelling creates no file.
4. Use a separate NFC writing app, read the tag back and test the reader.

SpoolScribe prepares the payload; it does not write the tag or replace the
slicer profile. [Writing guide](Writing-RFID-Tags.md).
