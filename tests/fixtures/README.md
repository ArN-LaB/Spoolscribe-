# Reference fixtures — SpoolScribe v0.6.0

[Application resources](../../data/README.md) · [Development](../../docs/DEVELOPMENT.md)

| Directory | Purpose |
| --- | --- |
| `catalogues/` | Historical Polymaker/Prusament/ROSA3D catalogue and OFD/SpoolmanDB snapshots |
| `catalogues/audits/` | Provenance and coverage reports for those snapshots |
| `orca/` | 48 official profiles used for regression testing |
| `legacy/` | TheFilamentDB snapshot for development and optional historical enrichment |
| `qr/ssqr1_vectors.json` | Normative SSQR1 vectors with exact NDEF for both formats and no personal data |
| `manifest.json` | Original locations and SHA-256 of 54 files moved without changing content |

Synthetic JSON fixtures, exceptions and the 1,008-export contract remain here.
Tests use temporary copies and deny network connections. No fixture is bundled
in an executable or copied into a new user's installation.

The historical manifest still covers the 54 files moved in v0.3.5. New QR vectors
change neither it nor the 48 Orca profiles. Old logo paths in snapshots are
intentionally retained: resource aliases keep them readable, preserving catalogue
hashes and demonstrating compatibility with existing installations.
