# Privacy & network transparency

SpoolScribe has no telemetry, no account and no analytics. The installer contains
no filament catalogue: the first launch asks which sources to use and downloads
them into your user folder. Browsing, editing and exporting then work offline.

## When the network is used

| Access | When | Host(s) |
|---|---|---|
| Catalogue refresh | At launch, according to the cadence set in **Settings** (every launch / once a day, the default / once a week / manually only), and whenever you click **Refresh catalogue**. An empty database always triggers the first download. | The selected sources below |
| Printer list refresh | Only when you click **My hardware → Update printer list…**, and only if the network authorization has been granted. The downloaded `printers.json` is validated and installed in your user folder only when it is newer than the bundled one. | `raw.githubusercontent.com` (ArN-LaB/Spoolscribe-, `data/printers.json`, 512 KiB limit) |
| Application update check | Only when you click **Check for an application update**. Refused if the network authorization has been withdrawn. | `api.github.com` (read-only `releases/latest`); the release page opens in your browser only after a second click |

Nothing else contacts the network. No printer, NAS or personal Spoolman server is
ever contacted.

## Sources and hosts

The source list and its hosts are defined once, in `core.SOURCE_GROUPS`, and
shown in the **Catalogue sources** dialog before any request. Saving the
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

The progress bar has a **Cancel** button; the running worker is stopped and the
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

**Settings → Withdraw network permission** stops every automatic request;
the Sources dialog can grant it again. **Export preferences…** writes a
plain-text JSON file (not encrypted) with interface, source, printer and tag
preferences; it never contains the network consent, refresh dates or statuses,
and includes the layout or the absolute export-folder path only when you tick
them. Importing a file never grants consent, and widening the source choice
invalidates the previous authorization. Restoring a database backup suspends
automatic refreshes for the rest of that session.

## Interface language

The four interface languages (English, Français, Español, 简体中文) are bundled locally. System-language detection and restarting after a language change do not contact a server or change consent.

## OpenTag3D (v0.6.0 pre-release)

Payload, NFC Tools profile and NDEF generation are entirely local. Explicit
settings are saved per reference in user preferences, not sent to catalogue
sources. The application downloads no OpenTag3D schema or service.

## Digital SSQR1 QR (v0.6.0)

The QR and PNG/SVG files are generated locally from the complete NDEF message
already prepared for export. No server, download link or Companion account is
used. Anyone receiving the image can decode it: do not share a QR containing
information you want to keep private. SHA-256 detects alteration, not authenticity.
The decoder validates lengths and launches no URL or command. Companion was
separate future work at this stage; printing and physical tests were deferred.

## Local colour measurements (v0.7.0)

Manual entries, pasted text and selected CSV/TSV files are processed locally.
The separate `colour_measurements.json` registry keeps the chosen values,
conditions, sample notes and provenance; these can contain information you enter.
Measurements and their backups are not sent to catalogue sources and are not
embedded in NFC/SSQR1 exports. Importing a file never uploads or rewrites it.
No instrument connection, USB/Bluetooth driver, SDK or new network service is added.
See [measurement storage and controls](COLOUR_MEASUREMENTS.md).

## Local device entry presets (v0.8.0)

On explicit save, `colour_device_profiles.json` stores user-declared device names
and reusable entry conditions next to the colour registry. It is not uploaded,
not bundled and not included in settings exports. Coordinates, calibration,
sample information and measurement dates are never reused by a device preset.
The new Companion and paper-guide buttons open public information pages in your
browser only when clicked; no new background request or store detection is added.

## Local data backups (v0.8.1)

**Back up my data…** writes a ZIP archive only where you choose. It is **not
encrypted**: it contains your catalogue with personal copies and corrections,
colour references (which may hold notes you entered), device presets, local Orca
profiles and, if you choose, your preferences (the layout and the absolute
export-folder path only when ticked separately). Its manifest lists file names,
sizes and SHA-256 digests; it holds no user name, absolute source path, machine
identifier or network consent. Nothing is uploaded. Keep the archive in a
protected location. A restore shows a preview first and keeps a private copy of
the replaced files in your data folder. See [Backing up your data](wiki/Backup-and-Restore.md).

## Opt-in diagnostics (v0.8.1)

Starting SpoolScribe with `--diagnostics` (or `SPOOLSCRIBE_DIAGNOSTICS=1`) records
window, dialog and screen events, Python exceptions and Qt warnings in a private
folder `diagnostics/` of the data folder (owner-only permissions), plus a crash
stack file. It is off by default. Paths are shortened, screen names and serial
numbers are not written, and preferences, filament names and searches are not
logged. Nothing is sent: share a file only if you decide to, after reading it.
