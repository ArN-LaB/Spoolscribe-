# Backing up your data

[Help home](Home.md) · [Application settings](Settings.md) · [Catalogue updates](Updating-the-Database.md)

> Available in Desktop v0.8.2. Earlier v0.8.0 downloads keep the automatic
> `.bak` copies described in the [FAQ](FAQ.md), but do not contain these commands.

**Settings › Data and backups** (or the main menu) offers two operations that do
not overlap:

| Command | What the file contains |
| --- | --- |
| **Export preferences…** | Plain JSON with your preferences and tag settings only |
| **Back up my data…** | ZIP archive of your data, described below |

## What a backup contains

The archive is a **ZIP file that is not encrypted**. Anyone who has the file can
read it, so keep it somewhere protected. An encrypted backup is not available in
this version.

Always included:

- the **full catalogue**, with its identifiers, personal copies, corrections and
  provenance.

Included when present:

- the colour measurement registry;
- device entry presets;
- local Orca profiles;
- your updated printer list.

The following items are options:

| Option | Default |
| --- | --- |
| Preferences, including OpenTag3D settings per reference, favourites and QR paper | On |
| Layout and filters | Off |
| Absolute path of the export folder (it may reveal a personal folder name) | Off |
| Generated exports in the data folder's `output` folder | Off |

A backup never contains:

- network permission, refresh dates or refresh status;
- caches and raw sources, which can be downloaded again;
- audit reports, bundled logos and the application's internal `.bak` copies;
- diagnostics logs, technical files, or an export folder chosen outside the data
  folder.

The preview lists each category as *included*, *missing* or *not included*, with
the reason. An unrecognised file is reported in the preview: it is neither
included nor deleted.

A backup or restore is refused while a refresh is running, and any open edit is
handled first.
Replacing an existing archive needs your explicit confirmation in the save dialog.

## Restoring

1. **Restore my data…** and choose the ZIP. The archive is fully checked before
   anything is written. Its list of contents, digests and sizes must match, and its
   content must pass the same validation as the application's own files. A
   damaged, altered, oversized or unknown-version archive is refused.
2. A preview shows what will be **replaced**, **created** or left **unchanged**,
   and what stays as it is on this computer. A category missing from the backup
   never deletes your current file. Preferences omitted from the backup keep their
   local value. Network permission is never granted by a restore. If the catalogue
   sources change, permission is asked again before the next refresh.
3. **Restore** writes the files. If a file changed after the preview, the restore
   stops and asks you to preview again.
4. Restart SpoolScribe when offered, so every view reloads.

Before replacing anything, SpoolScribe keeps an **exact copy** of the files it is
about to change. **Undo the last restore…** in **Data and backups** puts them
back. A file changed since the restore is left untouched.

## If a restore is interrupted

Each restore keeps a journal. If the application stops in the middle (crash,
power loss), the next start **undoes** the interrupted restore before reading any
data: you are back to your previous files, and a message says so. A restore is
never half-finished in the background.

If a file was changed or created by another program in the meantime, SpoolScribe
does not overwrite or delete it, even when its content happens to be identical to
what the restore would have written: SpoolScribe only touches the exact files it
created itself. The journal and copies are kept, and a warning shows where. You
can retry the rollback, or keep the current state.

**Limits.** This is a transaction for SpoolScribe itself. Several file
replacements are not one atomic operation of the file system: another program
that ignores SpoolScribe's locks could see an intermediate state. Restored files
are written with private permissions. Backups made on one operating system restore
on another; native Windows and Linux runs have not been measured yet.

Technical format: [data formats](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_FORMAT.md#data-backup-archive-spoolscribe-backup-v1).
Privacy: [Desktop privacy](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md).
