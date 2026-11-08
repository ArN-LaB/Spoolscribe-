# Repository layout

[Documentation](README.md) · [Develop and build](DEVELOPMENT.md) · [Contributing](../.github/CONTRIBUTING.md)

| Directory | Purpose |
| --- | --- |
| `src/spoolscribe/` | Application logic, Qt interface, CLI and NFC/QR contracts |
| `scripts/` | Source adapters, acquisition workers and CLI compatibility |
| `packaging/` | Native PyInstaller build and macOS signing tools |
| `requirements/` | Runtime dependencies and pinned build snapshot |
| `data/` | Application resources, printer catalogue, translations and licences |
| `tests/fixtures/` | Public regression data and historical reference vectors; excluded from installers |
| `tests/` | Offline software and interface checks for source contributors |
| `docs/wiki/` | Reviewed source of the illustrated help centre |
| `docs/images/` | Real demonstration captures and their provenance |
| `docs/validation/` | Dated software release validation |
| `docs/archive/releases/` | Original release notes and validation references |
| `docs/support/`, `docs/privacy/`, `docs/assets/` | Public support/privacy site and its shared presentation files |
| `.github/` | CI, security/contribution policies and repository maintenance tools |

The remaining Markdown pages explain installation, use, formats, compatibility,
privacy, data sources and compilation. `LICENSE`, `NOTICE` and the data licences
record redistribution and attribution requirements. Images and their manifests
provide the illustrated help and its provenance. They are part of the public
project documentation even when they are not bundled with the app.

No personal catalogue is bundled. Initial downloads populate a per-user catalogue after consent. Build output, caches and user settings are excluded from version control. Resource inclusion is explicitly declared in `src/spoolscribe/packaging_rules.py` rather than collecting arbitrary directories.

The printer catalogue stays at `data/printers.json` for compatibility with existing installations. Historical fixtures remain reproducible inputs; updating current data is not a reason to overwrite their bytes.
