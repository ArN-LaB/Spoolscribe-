# SpoolScribe v0.8.1 repository structure

[Documentation](README.md) · [Historical audit](validation/repository-v0.8.0.md) · [Resources](../data/README.md) · [Fixtures](../tests/fixtures/README.md)

| Directory | Purpose |
| --- | --- |
| `src/spoolscribe/` | Logic, Qt interface, CLI and NFC/QR contracts |
| `scripts/` | Storage, sources, standalone workers and CLI compatibility |
| `packaging/` | Multiplatform PyInstaller entry/spec |
| `requirements/` | Dependencies and pinned build snapshot |
| `data/` | Declared runtime resources: application/UI icons, brands, printers, translations, licences |
| `tests/fixtures/` | Public catalogues, 48 Orca profiles and historical vectors; never bundled |
| `docs/wiki/` | Reviewed GitHub Wiki source |
| `docs/images/` | Actual screenshots and manifest, outside the application |
| `docs/validation/` | Dated public release/audit evidence |
| `.github/` | Workflows, policies and maintenance/QA tools |

Local development history lives in `docs/agent-runs/`, organised by attested
start date and objective. Its entry point is `docs/agent-runs/INDEX.md`, outside
the public repository selection; those traces remain Git-ignored. Public version
validation stays in `docs/validation/`. Publishing evidence needs an explicit
selection. Builds, caches, user preferences and OS metadata stay outside the
development-history tree.

No personal catalogue is bundled. Initial downloads build a catalogue after
consent. `data/printers.json` retains its stable public path for existing
installations. `packaging_rules.py` explicitly declares resources rather than
blindly collecting directories.

Historical scripts are not orphans when CLI, compatibility or regressions still
use them. The [audit](validation/repository-v0.8.0.md) explains retained families
and exclusions. The [earlier structure assessment](https://github.com/ArN-LaB/Spoolscribe-/blob/v0.8.0/docs/REPOSITORY.md)
and [historical archive](archive/README.md) remain accessible without changing
dated results. [Development](DEVELOPMENT.md) · [Release policy](RELEASE_POLICY.md).
