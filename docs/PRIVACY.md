# Privacy & network transparency

SpoolScribe is built to be **transparent about every byte that leaves your
machine**. The short version: it works fully offline, and it never touches the
network unless **you explicitly say yes**.

## What runs locally (always offline)

- Searching, browsing, and viewing filament data.
- Generating OpenSpool / NFC JSON files.
- Everything in the bundled database `data/polymaker_db.json`.

No account, no telemetry, no analytics, no tracking. Ever.

## What requires the network (opt-in only)

Only the **"Update database"** action makes network requests. It is:

1. **Disabled by default.** A fresh install never calls the network on its own.
2. **Consent-gated.** The first time you trigger an update, the app shows you
   the exact list of sources and asks for a clear Yes/No. Your answer is stored
   in a local config file.
3. **Auditable.** The full list of contacted hosts is in
   [DATA_SOURCES.md](DATA_SOURCES.md) and hard-coded in `core.NETWORK_SOURCES`.

### Hosts contacted during an update

- `raw.githubusercontent.com` (SpoolmanDB, Open Filament Database, Polymaker-Preset)
- `wiki.polymaker.com`
- `us-wholesale.polymaker.com`
- TheFilamentDB data (local dump `data/thefilamentdb.jsonl.gz`)

### What is sent

Only standard HTTP GET requests (a normal `User-Agent`). **No personal data,
no identifiers, no usage data** are transmitted.

## Where settings are stored

Your consent choice and update preferences live in a local JSON file:

- **Windows:** `%APPDATA%\SpoolScribe\config.json`
- **macOS:** `~/Library/Application Support/SpoolScribe/config.json`
- **Linux:** `~/.config/SpoolScribe/config.json`

Delete that file to reset all choices (the app will ask again next time).

## Changing your mind

- **GUI:** the consent dialog reappears whenever consent is not granted.
- **CLI:** the `U` command re-asks and lets you grant or revoke access.
