# Updating the Database

The installer contains artwork and code, but **no filament catalogue and no
Orca profiles**. The first launch opens the source selection; the download
builds the local database in your user folder. If a source is unavailable, the
cached data remain usable offline.

## Sources and consent

**Mettre à jour** (Ctrl+U) opens the **Sources du catalogue** dialog. Each source
shows the host it contacts. **Télécharger et enregistrer** saves the choice and
starts a refresh; **Enregistrer seulement** saves it for the next launch.
Deselecting a source prevents future requests to it; existing records are kept.
The first selection records your network consent; **⋯ → Paramètres → Retirer
l'autorisation réseau** withdraws it. The CLI shares the choices (`--sources`)
and its `U` command can reconsider consent.

Sources, hosts and licences:
[DATA_SOURCES.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_SOURCES.md),
[PRIVACY.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md).

## Cadence

**⋯ → Paramètres → Actualisation au lancement** sets when the app refreshes by
itself: at every launch, once a day (default), once a week, or manually only.
An empty database always triggers the first download. **Mettre à jour** forces a
refresh regardless of the cadence.

Open Filament Database, SpoolmanDB and the Bambu profile index are fetched
conditionally: when the server answers that nothing changed since the last
download, the step ends immediately. Polymaker runs first, then the community
catalogues, then the Bambu and SUNLU enrichment.

## During a refresh

A progress bar shows the current source; **Annuler** stops the running worker
and keeps the database as it was. Closing the window during a refresh asks for
confirmation and does the same. Only one instance of SpoolScribe runs per data
folder.

When the sources cannot be reached, the status bar says so and nothing is
rewritten. When a refresh changes something, the bottom **Base de données**
button opens the details: date of the last attempt, last complete refresh of
the selected sources, result of each source, conserved local values and pending
identity matches.

## What a refresh may and may not change

- Manufacturer values replace community values that you have not edited.
- Your corrections, including a deliberately unknown value, are never replaced.
- A source that stops publishing a value does not empty the local one; the
  case is listed as a conserved value.
- A source that returns less than half of its previous references is refused.
- Values that contradict themselves are flagged *À vérifier* and blocked at
  export until you confirm them.
- Uncertain identities between sources are held aside, never merged.

## Backups and restoration

Every save keeps the previous revision in `polymaker_db.json.bak`; a refresh
also keeps `polymaker_db.json.pre-update.bak`. The GUI offers restoration of
`.bak` when the database is unreadable. From source:

```sh
python convert_profile.py --restore-db
python convert_profile.py --restore-db "/path/to/polymaker_db.json.pre-update.bak"
```

The replaced file is kept as `polymaker_db.json.before-restore-*`. After a
restoration, automatic refreshes are suspended for the rest of that session.

## Concurrent edits and locks

Writes use validation, atomic replacement, a writer lock and revision checks.
If an external editor changed the file meanwhile, the save stops and the
detected bytes are kept in `polymaker_db.json.concurrent-*`. A lock left by a
crashed or killed worker is recovered automatically (dead process, or lock
older than 15 minutes); a lock of a live process still blocks. Close other
writers before updates or restoration.

## Settings file

**⋯ → Enregistrer les réglages… / Charger des réglages…** export and import the
interface, source, printer and tag preferences. Imported files never grant
network consent, and a different source selection invalidates the previous
authorization until you confirm it in the Sources dialog.
