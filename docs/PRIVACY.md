# Privacy & network transparency

SpoolScribe has no telemetry, no account and no analytics. The installer contains
no filament catalogue: the first launch asks which sources to use and downloads
them into your user folder. Browsing, editing and exporting then work offline.

## When the network is used

| Access | When | Host(s) |
|---|---|---|
| Catalogue refresh | At launch, according to the cadence set in **⚙ → Paramètres** (every launch / once a day, the default / once a week / manually only), and whenever you click **Refresh catalogue** (French: **Actualiser le catalogue**). An empty database always triggers the first download. | The selected sources below |
| Printer list refresh | Only when you click **Mon matériel → Mettre à jour la liste des imprimantes…**, and only if the network authorization has been granted. The downloaded `printers.json` is validated and installed in your user folder only when it is newer than the bundled one. | `raw.githubusercontent.com` (ArN-LaB/Spoolscribe-, `data/printers.json`, 512 KiB limit) |
| Application update check | Only when you click **⚙ → Vérifier une mise à jour de l'application**. Refused if the network authorization has been withdrawn. | `api.github.com` (read-only `releases/latest`); the release page opens in your browser only after a second click |

Nothing else contacts the network. No printer, NAS or personal Spoolman server is
ever contacted.

## Sources and hosts

The source list and its hosts are defined once, in `core.SOURCE_GROUPS`, and
shown in the **Sources du catalogue** dialog before any request. Saving the
dialog records your authorization; deselecting a source stops future requests to
it without deleting the records already downloaded. A changed source revision
asks for renewed consent. The CLI shares the same choices (`--sources`).

| Source (default) | Host | What is downloaded |
|---|---|---|
| Polymaker — manufacturer | `us-wholesale.polymaker.com` | Public wholesale catalogue (JSON), at most 40 pages |
| Open Filament Database — community | `codeload.github.com` | Official repository archive (`.tar.gz`), read in memory |
| SpoolmanDB — community | `donkie.github.io` | Compiled `filaments.json` |
| Bambu Lab — manufacturer | `raw.githubusercontent.com` (bambulab/BambuStudio) | Filament profile index, then the `@base` profiles |
| SUNLU — manufacturer | `www.sunlu.com` | PLA product page (technical and colour tables) |
| Polymaker Orca profiles (optional) | `raw.githubusercontent.com` (polymaker3d/Polymaker-Preset) | Snapmaker U1 OrcaSlicer profiles |
| TheFilamentDB (optional, legacy) | none | Local developer snapshot, not bundled in installers |

Every downloader is bounded: HTTPS only, redirects accepted only within the
declared host, response size limit (8 MiB for manufacturer pages, 32 MiB for
SpoolmanDB, 64 MiB for the OFD archive), explicit User-Agent
`SpoolScribe/0.3 (+https://github.com/ArN-LaB/Spoolscribe-; …)`, timeouts.
OFD, SpoolmanDB and the Bambu index send `If-None-Match`; when the server answers
`304 Not Modified`, nothing is downloaded again. When a server throttles
(`429` or `503`), the worker waits the announced `Retry-After` (1–30 s, 5 s by
default) and retries twice at most, then reports the source as saturated and
keeps the local data. Each worker has a fixed time budget (OFD 900 s, Bambu
600 s, SpoolmanDB and Polymaker 300 s, SUNLU 180 s): a slow link ends the step
as unreachable, never with partial data. Certificate and hostname
verification stay enabled; packaged builds carry certifi roots as a fallback and
never modify the system trust store.

Servers see the connection IP, the User-Agent and, for conditional requests, the
ETag of the last download. No catalogue content, identifier, usage data or
printer credential is transmitted.

## During a refresh

The progress bar has a **Annuler** button; the running worker is stopped and the
local database stays as it was. Closing the window during a refresh asks for
confirmation and then does the same. When sources are unreachable, the status
bar says so and the cached database is kept; nothing is rewritten.

Only one SpoolScribe instance runs per data folder (`spoolscribe.instance.lock`),
so two refreshes cannot compete for the same database.

## Local files and portable settings

Database, configuration and exports use the user data directory:

- Windows: `%APPDATA%\SpoolScribe`
- macOS: `~/Library/Application Support/SpoolScribe`
- Linux: `~/.config/SpoolScribe` (or `XDG_CONFIG_HOME`)

`SPOOLSCRIBE_DATA_HOME` and `SPOOLSCRIBE_CONFIG_PATH` isolate development or
testing. `config.json` records the consent, the selected sources, the refresh
cadence and the date/status of the last attempt; the database records only the
results of a refresh that changed something.

**⚙ → Paramètres → Retirer l'autorisation réseau** stops every automatic request;
the Sources dialog can grant it again. Settings exported from the **⚙** menu
contain interface, source, printer and tag preferences but never the network
consent; importing a file never grants it, and widening the source choice
invalidates the previous authorization. Restoring a database backup suspends
automatic refreshes for the rest of that session.

## Interface language

The four interface languages (English, French, Spanish, Simplified Chinese) are bundled locally. System-language detection and restarting after a language change do not contact a server or change consent.
