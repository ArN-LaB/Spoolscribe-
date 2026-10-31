# Updating the Database

SpoolScribe ships with a bundled database so it works **fully offline**. You can
optionally refresh it from open data sources — but only with your explicit
consent.

## How updates work

- **Offline by default.** A fresh install never contacts the network on its own.
- **Consent-gated.** The first time you trigger an update, the app shows the
  exact list of sources and asks Yes/No. Your choice persists locally across sessions. Automatic startup updates also require a separate opt-in.
- **Disclosed.** The full source list is in `DATA_SOURCES.md` and hard-coded in
  `core.NETWORK_SOURCES`.

## Triggering an update

- **GUI:** click **"Update database"**. Approve the consent dialog the first time.
- **CLI:** type `U`. You'll be asked to grant (and optionally auto-update).

## Sources

| Source | License | Used for |
|---|---|---|
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) | MIT | Fill missing HEX; preserve existing local values |
| [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) | MIT | Generic brand enrichment |
| [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) (official) | MIT | Polymaker temps / density |
| [TheFilamentDB](https://thefilamentdb.issou.best/) | CC-BY 4.0 | Prusament HEX (gap-fill) |
| [Polymaker Wiki / Wholesale](https://polymaker.com) | Factual data (© Polymaker) | Polymaker HEX / SKU |

## Status and local data

Frozen applications include Mozilla CA roots through certifi. They are used when
Python finds no default trust roots. Existing system roots and explicit
`SSL_CERT_FILE` / `SSL_CERT_DIR` settings are preserved; TLS certificate and
hostname verification remain enabled. No system certificate store is modified.

The bundled TheFilamentDB snapshot contains Prusament entries but no ROSA3D
entries. Its multibrand step therefore reports a partial result for ROSA3D;
this is independent of HTTPS connectivity and does not invent missing colors.

Each worker reports changed, unchanged, unavailable, partial or failed. A pipeline
with a failed/unavailable source is never a complete update. Only a fully checked,
validated pipeline advances the complete-refresh date. Available partial data can
be retained, with the previous complete-refresh date and an explicit partial status.
An empty source or an index with no usable target colors is unavailable, even if
the download succeeded. A valid source with no new matching data is unchanged.
Missing data for one target brand makes a multibrand check partial; missing data
for every target brand makes it unavailable.

Writes are validated and atomic. `polymaker_db.json.bak` retains the previous valid
revision; `polymaker_db.json.pre-update.bak` retains the state before the whole
pipeline. A corrupt database is reported, not treated as an empty catalogue.

Ordinary updates preserve existing HEX and physical corrections. Direct scraper
`--force` options, where available, explicitly allow replacing existing values;
the GUI pipeline does not pass them. New bundled catalogues add missing entries
and fields, preserve existing values (including intentional null colors), and
record conflicts in `_bundle_conflicts`, shown in the GUI stats tooltip.
Export preserves local physical values by default. To explicitly prefer the Orca
profile at export time, enable the GUI Settings option or CLI `--orca-overrides`.
Profiles still fill missing physical fields; malformed profiles produce an error.

Downloaded existing Orca files are preserved unless their downloader is explicitly
run with `--force`. An invalid newly downloaded profile is rejected before replacing
an existing file. No unverified PPS-CF10 characteristics or color mappings are added.

## Restoring a backup

Close other writers first. The GUI offers restoration of `.bak` when its database
is unreadable. From source, `python convert_profile.py --restore-db` asks before
restoring `.bak`; give a path to choose another backup, for example:

```sh
python convert_profile.py --restore-db "/path/to/polymaker_db.json.pre-update.bak"
```

The replaced file is retained as `polymaker_db.json.before-restore-*`; a backup is
validated before restoration. An interrupted write may leave a `.lock` file. Verify
that no writer is running before removing that lock and retrying.

After a successful restoration, automatic startup updates and bundled catalogue
merges are suspended for that database for the rest of the current application
process. The restored file remains the exact selected backup until an explicit
edit or manual update. Consent and automatic-update preferences are preserved;
the next launch uses them normally.

## Concurrent edits

Application writers use a shared lock and stale-revision checks. A further check
runs after the temporary file is flushed, immediately before publication. If a
concurrent change is detected, the save stops and the detected bytes are retained
in `polymaker_db.json.concurrent-*`, including unfinished JSON. The error reports
the recovery path; compare versions before retrying. If the file was deleted,
there are no concurrent bytes to copy and the save still stops.

This is not absolute exclusion of external editors or synchronizers that ignore
the lock: they can still write between the final check and replacement. Close
other writers before updates or restoration, and avoid editing the JSON in an
external editor while SpoolScribe is saving. The recovery files are local copies,
not an unlimited version history or a multi-file transaction.

## Changing consent

GUI Settings > **Retirer l'autorisation réseau** revokes consent and automatic
updates. The CLI `U` command lets you grant or revoke consent again. Neither an
export nor browsing requires network access.

## Resetting your choice

Delete the config file to be asked again:

- **Windows:** `%APPDATA%\SpoolScribe\config.json`
- **macOS:** `~/Library/Application Support/SpoolScribe/config.json`
- **Linux:** `~/.config/SpoolScribe/config.json`

See `PRIVACY.md` for the full transparency statement.
