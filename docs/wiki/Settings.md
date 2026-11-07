# Application settings

[Help home](Home.md) · [Catalogue updates](Updating-the-Database.md) · [Colour values](Measuring-Colours.md)

Open the main settings menu, then **Settings…**. Six tabs: **Catalogue**,
**Filaments**, **Tags and export**, **Colours**, **Interface** and **Data and
backups**. Make the change and **Save**; **Cancel** discards the fields of this
window. Two catalogue buttons act immediately and are labelled as such:
**Catalogue sources…** and **Withdraw network permission**. Cancelling the
window does not undo them. This six-tab layout is available in Desktop v0.8.1. The screenshots below
are generated from that version using public demonstration data.

## Catalogue: refresh at your pace

Choose the launch refresh cadence: every launch, daily, weekly or manually only.
The cadence is what counts; the older `auto_update` setting is kept for
compatibility and has no effect of its own (`auto_update: false` with a weekly
cadence is valid). A value this window cannot represent is shown as such and kept
until you choose another one. A manual refresh remains available. Network
permission can be withdrawn; the last downloaded catalogue stays local.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-catalogue.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-catalogue.png" alt="Choose the refresh cadence" width="820"></a>
</p>
<p align="center"><strong>Choose the refresh cadence</strong><br><sub>Source selection and network permission are separate.</sub></p>

## Filaments: preselect a real option

Choose your usual mass and spool/refill preference. The app uses them only when
that actual option exists in the selected record; you can choose another size.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-spools.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-spools.png" alt="Set the usual spool size" width="820"></a>
</p>
<p align="center"><strong>Set the usual spool size</strong><br><sub>This preference does not invent missing pack sizes.</sub></p>

## Tags and export: keep the destination predictable

Choose the output directory. The export action still asks for its destination.
Downloading the Orca source only makes profiles available. **Prefer Orca values
at export** decides whether an applicable profile replaces catalogue values; when
off, the profile only fills in missing values. **My hardware…** opens the printer,
reader and NFC tag choice; the QR paper format is set in the QR window. Inspect
the effective values (**Origin and reliability** in the filament details) before
writing a tag.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-export.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-export.png" alt="Choose export preferences" width="820"></a>
</p>
<p align="center"><strong>Choose export preferences</strong><br><sub>The export preview shows the effective values.</sub></p>

## Interface: use your language

**English · French · Spanish · Simplified Chinese**. Automatic follows the system language,
with English as fallback. Save, then choose **Restart now** or **Later**. This
restarts the interface without deleting your data or favourites.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-interface.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-interface.png" alt="Choose the interface language" width="820"></a>
</p>
<p align="center"><strong>Choose the interface language</strong><br><sub>A restart applies the saved language.</sub></p>

## Colours: set the maximum distance

Choose a preset or a manual ΔE limit. A small value narrows the results; **All
colours** removes the distance limit. It does not guarantee a matching printed colour.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-colours.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-colours.png" alt="Set an inclusive ΔE limit" width="820"></a>
</p>
<p align="center"><strong>Set an inclusive ΔE limit</strong><br><sub>ΔE is a distance, not a percentage.</sub></p>

## Data and backups: two different operations

- **Export/Import preferences…** writes a plain-text JSON file (not encrypted)
  with your preferences and tag settings. It never contains network permission,
  refresh dates or status. Layout/filters and the absolute export-folder path are
  included only when you tick them. Before importing, a preview shows which
  categories are replaced (lists as a whole), which local values are kept and what
  is ignored; changing sources asks for network permission again.
- **Back up/Restore my data…** creates an unencrypted ZIP archive of your data
  (full catalogue with personal copies and corrections, colour references, device
  presets, local Orca profiles, and preferences if chosen). See
  [Backing up your data](Backup-and-Restore.md).

**Export the filament’s OpenSpool JSON…** in the main menu writes one readable
OpenSpool file for the selected filament; it is not a backup.

<p align="center"><a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-backups.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/settings-backups.png" alt="Preferences and data backups in v0.8.1" width="820"></a></p>
<p align="center"><strong>Keep preferences and backups distinct</strong><br><sub>Both exports are local and unencrypted. AES-256-GCM is not implemented.</sub></p>
