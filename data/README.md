# Application resources

This directory contains resources used by SpoolScribe, not user filament data,
old exports or regression profiles. [Documentation](../docs/README.md) ·
[Test data](../tests/fixtures/README.md)

| Location | Contents and use |
| --- | --- |
| `app/` | Windows/macOS/Linux icons and static/animated logo SVG sources |
| `ui/` | SVG icons used by Qt controls |
| `brands/manifest.json` | 147 reviewed brand entries with provenance, hashes and logo paths |
| `brands/logos/` | 141 manifest-referenced images plus the historical ROSA3D fallback logo |
| `printers/photos/` | 15 product photographs and provenance manifest |
| `translations/` | Local four-language catalogue and translation guidance |
| `licenses/` | Source licences, TheFilamentDB attribution and Segno BSD licence |
| `printers.json` | Public/bundled hardware catalogue at a stable path used by released versions |

Several brand entries may share one **byte-identical** image without duplicating
bytes or losing names/provenance. Legacy logo paths remain readable through
`scripts/resource_paths.py`; personal files are neither moved nor overwritten.
Catalogues, audits, Orca profiles and the historical TheFilamentDB snapshot live
in `tests/fixtures/` with their prior hashes unchanged. User data stays in the
normal system-specific data folder, outside the repository.

Packaging uses explicitly declared resources. An image added without a manifest
reference is not bundled. Repository checks reject orphan resources and duplicate
binary images.
