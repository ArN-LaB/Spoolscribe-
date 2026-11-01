# Catalogue updates & backups

[Home](Home.md) · [Get started](Getting-Started.md) · [Compatibility](Printers-and-Readers.md) · [FAQ](FAQ.md)

**Refresh selected sources while keeping your own work.**

| 1. Choose | 2. Refresh | 3. Review |
| --- | --- | --- |
| Select the sources you want to contact. | Follow progress; cached data stay available if a source fails. | Read the result and inspect any unresolved records. |

**Data priority:** your corrections → manufacturers → community sources.

The installer contains artwork and code, but **no filament catalogue and no
Orca profiles**. The first launch opens the source selection; the download
builds the local database in your user folder. If a source is unavailable, the
cached data remain usable offline.

## Sources and consent

**Refresh catalogue** (Ctrl+U) opens the **Catalogue sources** dialog. Each source
shows the host it contacts and the result of its last run (updated, unchanged,
unreachable, partial, error). **Refresh now** saves the choice and
starts a refresh; **Save only** saves it for the next launch; **Details of the last refresh** reopens the last report.
Deselecting a source prevents future requests to it; existing records are kept.
The first selection records your network consent; **Settings → Revoke network permission** withdraws it. The CLI shares the choices (`--sources`)
and its `U` command can reconsider consent.

Sources, hosts and licences:
[DATA_SOURCES.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_SOURCES.md),
[PRIVACY.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md).

## Cadence

**Settings → Refresh on startup** sets when the app refreshes by
itself: at every launch, once a day (default), once a week, or manually only.
An empty database always triggers the first download. **Refresh catalogue** forces a
refresh regardless of the cadence.

Open Filament Database, SpoolmanDB and the Bambu profile index are fetched
conditionally: when the server answers that nothing changed since the last
download, the step ends immediately. Polymaker runs first, then the community
catalogues, then the Bambu and SUNLU enrichment.

## Read the refresh result

| Result | Meaning | Next step |
| --- | --- | --- |
| **Complete** | All selected required steps succeeded. | Browse the refreshed catalogue. |
| **Partial** | Some steps failed; available data were preserved. | Inspect the source details and retry later. |
| **Failed** | The refresh could not complete. | Keep using cached data and inspect the report. |
| **Cancelled** | The refresh was stopped. | The previous database is kept. |


A progress bar shows the current source; **Cancel** stops the running worker
and keeps the database as it was. Closing the window during a refresh asks for
confirmation and does the same. Only one instance of SpoolScribe runs per data
folder.

When the sources cannot be reached at launch, the status bar says so and nothing
is rewritten. After a manual refresh, or whenever a source fails, a **report**
window opens: complete / partial / failed / cancelled, references, ready
filaments and manufacturers with their change, conserved local or manufacturer
values, pending identity matches (held aside, never duplicated), the priority
order, and a table with the result, reference count and message of each source.
A source that throttles (`429`) is retried after the delay it announces, then
reported as saturated; a very slow download ends the step as unreachable after
its time budget (OFD 15 min, Bambu 10 min, SpoolmanDB and Polymaker 5 min). In
both cases the local data stay as they were — run the refresh again later.

The bottom status button (“Catalogue: …”) opens
the database details: date of the last attempt, last complete refresh of the
selected sources, result of each source, conserved values and pending matches.

## What a refresh may and may not change

- Manufacturer values replace community values that you have not edited, and
  values of unknown origin (a database created by an older build).
- Your corrections, including a deliberately unknown value, are never replaced.
- Product lines listed as brands by a source are filed under their manufacturer;
  a historical reference whose product record was lost is repaired, not dropped.
- A source that stops publishing a value does not empty the local one; the
  case is listed as a conserved value.
- A source that returns less than half of its previous references is refused.
- Values that contradict themselves are flagged *Needs review* and blocked at
  export until you confirm them.
- Uncertain identities between sources are held aside, never merged.

## Backups and restoration

<details>
<summary><strong>Backup files and restoration commands</strong></summary>

Every save keeps the previous revision in `polymaker_db.json.bak`; a refresh
also keeps `polymaker_db.json.pre-update.bak`. The GUI offers restoration of
`.bak` when the database is unreadable. From source:

```sh
python -m spoolscribe.convert_profile --restore-db
python -m spoolscribe.convert_profile --restore-db "/path/to/polymaker_db.json.pre-update.bak"
```

The replaced file is kept as `polymaker_db.json.before-restore-*`. After a
restoration, automatic refreshes are suspended for the rest of that session.

</details>

<details>
<summary><strong>Concurrent edits, locks and recovery</strong></summary>

Writes use validation, atomic replacement, a writer lock and revision checks.
If an external editor changed the file meanwhile, the save stops and the
detected bytes are kept in `polymaker_db.json.concurrent-*`. A lock left by a
crashed or killed worker is recovered automatically when the operating system
confirms that its process has stopped, on Windows, macOS and Linux. A live or
inaccessible process remains protected regardless of the lock age. Close other
writers before updates or restoration. External editors that ignore the lock
still require revision checks; the lock alone cannot exclude them.

</details>

## Keep your settings too

**Save settings to file… / Load settings…** export and import the
interface, source, printer/firmware and tag preferences. Imported files never grant
network consent, and a different source selection invalidates the previous
authorization until you confirm it in the Sources dialog.

[Back to the catalogue guide](Getting-Started.md) · [Questions?](FAQ.md)
