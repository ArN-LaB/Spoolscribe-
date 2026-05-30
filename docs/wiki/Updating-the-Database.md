# Updating the Database

SpoolScribe ships with a bundled database so it works **fully offline**. You can
optionally refresh it from open data sources — but only with your explicit
consent.

## How updates work

- **Offline by default.** A fresh install never contacts the network on its own.
- **Consent-gated.** The first time you trigger an update, the app shows the
  exact list of sources and asks Yes/No. Your choice is saved locally.
- **Disclosed.** The full source list is in `DATA_SOURCES.md` and hard-coded in
  `core.NETWORK_SOURCES`.

## Triggering an update

- **GUI:** click **"Update database"**. Approve the consent dialog the first time.
- **CLI:** type `U`. You'll be asked to grant (and optionally auto-update).

## Sources

| Source | License | Used for |
|---|---|---|
| [SpoolmanDB](https://github.com/Donkie/SpoolmanDB) | MIT | Prusament HEX (authoritative) · ROSA3D HEX (fill-missing) |
| [Open Filament Database](https://github.com/OpenFilamentCollective/open-filament-database) | MIT | Generic brand enrichment |
| [Polymaker-Preset](https://github.com/Polymaker3D/Polymaker-Preset) (official) | MIT | Polymaker temps / density |
| [TheFilamentDB](https://thefilamentdb.issou.best/) | CC-BY 4.0 | Prusament HEX (gap-fill) |
| [Polymaker Wiki / Wholesale](https://polymaker.com) | Factual data (© Polymaker) | Polymaker HEX / SKU |

## Resetting your choice

Delete the config file to be asked again:

- **Windows:** `%APPDATA%\SpoolScribe\config.json`
- **macOS:** `~/Library/Application Support/SpoolScribe/config.json`
- **Linux:** `~/.config/SpoolScribe/config.json`

See `PRIVACY.md` for the full transparency statement.
