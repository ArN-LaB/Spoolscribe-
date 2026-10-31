# Updating the Database

The v0.3.0 development installer contains artwork and code, but **no filament
catalogue or Orca profiles**. First launch opens source selection. Download once
to constitute the local database; subsequent authorized launches refresh those
sources. If a service is unavailable, the cached data remain usable offline.

**Mettre à jour** opens selectable sources. Choose **Télécharger et enregistrer**
or **Enregistrer seulement**. Deselecting a source prevents future requests to it;
it does not erase existing records. The first selection records network consent.
Settings can revoke it. The CLI shares the choices (`--sources`), and `U` can
reconsider consent. `--list` is a read-only offline command.

Sources and endpoints: [DATA_SOURCES.md](../DATA_SOURCES.md).
Manufacturer values take priority over source-owned community values, while
explicit local edits/nulls remain protected. Exact identities merge complementary
facts; ambiguous records are held separately instead of creating possible duplicates.

The bottom **Base de données** panel shows the last attempt, last complete refresh
of the **selected** source set, each worker result, conflicts and pending identities.
A skipped/deselected source is not reported as a successful check. Failed or partial
steps prevent the complete-refresh date from advancing. A valid source with no
novel facts can report unchanged. Missing factual fields remain explicit.

Frozen builds retain certifi trust roots without disabling TLS verification. This
does not guarantee availability of any source. The optional developer-only
TheFilamentDB snapshot lacks ROSA3D colors; it is not included in the installer.

Writes use validation, atomic replacement, revision checks and backups.
`polymaker_db.json.pre-update.bak` preserves the pre-pipeline state. Ordinary
updates do not overwrite existing Orca files. No printer or NAS is contacted.

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

## Changing consent and preferences

Settings → **Retirer l'autorisation réseau** stops automatic network use. The
Sources dialog can grant it again. Menu ⋯ exports/imports interface preferences;
imported files never grant network consent. Application-update discovery is a
separate explicit GitHub request; see [PRIVACY.md](../PRIVACY.md).
