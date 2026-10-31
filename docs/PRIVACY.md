# Privacy & network transparency

The initial catalogue is downloaded after source selection. There is no filament
catalogue in the installer. Subsequent launches refresh the selected sources;
failed requests preserve the previous local database. Searching, filtering,
editing and exporting cached records work offline.

## Source selection and authorization

The **Mettre à jour / Sources du catalogue** dialog lists selectable sources and
hosts. Saving authorizes those sources; **Télécharger et enregistrer** also starts
the refresh. A source can be deselected without deleting its existing records.
Settings can revoke network authorization. Restoration inhibits startup updates
for the remainder of that process. A changed source revision requires renewed
consent. The CLI shares source preferences (`--sources`) and the `U` command.

Default sources:

- `us-wholesale.polymaker.com`: official manufacturer catalogue.
- `codeload.github.com`: canonical OFD source archive.
- `donkie.github.io`: compiled public SpoolmanDB catalogue.
- `raw.githubusercontent.com/bambulab/BambuStudio`: official Bambu filament facts.
- `www.sunlu.com`: official SUNLU PLA technical/color tables.

Optional Polymaker Orca profiles use `raw.githubusercontent.com`. The legacy
TheFilamentDB option reads a local developer snapshot, not bundled in installers.
Each new downloader bounds size and rejects redirects outside its declared HTTPS
host. Certificate and hostname verification stay enabled. Frozen apps retain the
certifi trust-root fallback; no system trust store is changed.

**⋯ → Vérifier une mise à jour de l’application** separately makes a read-only
request to `api.github.com/repos/ArN-LaB/Spoolscribe-/releases/latest`. It opens the
verified repository release page only after a click. It neither installs nor
executes downloaded code and does not downgrade a development version.

These are ordinary HTTPS requests. Servers see the connection IP and User-Agent;
no local catalogue, personal identifier, usage telemetry, printer credential or
personal Spoolman/NAS endpoint is transmitted. There is no analytics/account service.

## Local files and portable settings

Database, configuration and exports use the user data directory:

- Windows: `%APPDATA%\SpoolScribe`
- macOS: `~/Library/Application Support/SpoolScribe`
- Linux: `~/.config/SpoolScribe` (or `XDG_CONFIG_HOME`)

`SPOOLSCRIBE_DATA_HOME` / `SPOOLSCRIBE_CONFIG_PATH` can isolate development/testing.
Settings exports include interface/source/printer preferences, but exclude network
consent. Import never grants consent, and widening the source choice invalidates
its old authorization. Catalogue backups and atomic/concurrent-write protections
remain local. No existing user database or preference file is reset by this change.
