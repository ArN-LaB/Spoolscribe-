# Repository audit and Desktop v0.8.0 stable promotion

Historical record, 5 November 2026. Checked base:
`89c08a657bcd752c9f6b95e15192c8390d54d156`.
[Software tag](https://github.com/ArN-LaB/Spoolscribe-/tree/v0.8.0) ·
[Binary validation](v0.8.0.md) · [Release policy](../RELEASE_POLICY.md).

## Scope and result

This pass covered documentation, actual screenshots, GitHub channel coherence,
project metadata and repository organisation. It changed no application module,
protocol, runtime resource, catalogue, Orca profile or dependency relative to
v0.8.0. Stable promotion retained the tag and six published files, without
certifying every hardware setup.

## Structure and justified maintenance

The baseline had **437 tracked files** and six visible root files:
`CHANGELOG.md`, `LICENSE`, `NOTICE`, `README.md`, `install-local.command`,
`pyproject.toml`. The review covered **41 scripts** (26 under `scripts/`,
15 CI/maintenance tools). Application modules stayed under `src/spoolscribe/`,
packaging under `packaging/`, declared resources under `data/` and historical
fixtures under `tests/fixtures/`.

Old scrapers still served CLI/compatibility or regression fixtures; absence from
the GUI alone did not justify deletion. Capture/logo/Wiki/archive/frozen-probe
tools had explicit maintenance roles. No production script was deleted merely
for an old name. Checks retained 198 declared resources, 54 protected fixtures
including 48 Orca profiles, and the 1,008-export contract.

`docs/REPOSITORY.md` was focused on current structure while the dated predecessor
remained available in Git. Active help corrected current-version errors, old
counts and writer guidance. Centralised screenshots recorded version, dimensions,
SHA-256 and scenario; demonstration images were not application resources.

**1,999 local files** under `docs/agent-runs/` and `docs/agents-prompts/` were
preserved with verified hashes. Two explicit Git exclusions prevented publication
of drafts, local paths and intermediate evidence. Public release evidence stayed
under `docs/validation/`. `dist/`, caches, preferences and `.DS_Store` remained
ignored. Final comparison covered all non-ignored paths/bytes, without claiming
to synchronise excluded local folders.

## Retained tools

| Family | Purpose |
| --- | --- |
| Acquisition workers/seeds | Chosen sources, historical enrichment, CLI and offline tests |
| `db_io`, merge/adapters | Protected writes, matching and validation |
| Icons/resources | Regeneration/provenance and compatible aliases |
| `probe_frozen_*` / `check_frozen_*` | Actual executable checks on native runners |
| `verify_archive`, `check_repository` | Native layout, links, version, fixtures/resources |
| `render_readme_*`, `sync_wiki` | Reproducible actual visuals and help publication |
| `build_catalogue_snapshot`, `import_brand_logos` | Explicit maintenance preparation, outside user installation |

## QR and mobile availability

SSQR1 remained byte-identical. Another application can read a visible QR;
M/Q error correction and SHA-256 alteration detection provide neither exclusive
app access nor encryption. The intended mobile workflow was Companion scanning;
camera opening through verified links was separate work requiring a controlled
domain/mobile configuration. No store link was invented.
[Explanation and sources](../wiki/Companion-and-QR.md).

## Verification and limits

| Check | Recorded result |
| --- | --- |
| Local Python 3.10 / macOS offscreen Qt | 618/618 passed, 104.677 s, isolated fixtures/offline |
| Local Python 3.12 / macOS offscreen Qt | 618/618 passed, 94.221 s, isolated fixtures/offline |
| Structure | 52 active Markdown, 304 local links, zero errors; help anchors checked separately; diff-check passed |
| 30 screenshots | Manifest dimensions/SHA-256 verified; contact sheet and detailed screens visually reviewed |
| Four screenshot QRs | Independent ZXing decode recovered expected manifest NDEF |
| 1,999 local work files | Hashes unchanged; no personal data/private key added |
| Publication condition | Stable v0.8.0, historical pre-releases and suffixed tags distinguished without disabling checks |
| Hardware-result form | Exact setup, versions and read-back requested without generalising one result to a family |

Repository, captions, capture digests, orphan files, versions and publication
conditions were checked before the PR. All four required GitHub checks stayed
enforced. [PR #21](https://github.com/ArN-LaB/Spoolscribe-/pull/21) merged as
`afeef1d71532106bbb01928804332e52d64d3440` after
[successful CI](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41959317795),
618 tests/configuration. Builds in that documentation-only pass skipped and
were not counted as successes; actual native builds remained those from
[initial publication](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41954082388).

At promotion, v0.8.0 became `prerelease=false`, `draft=false`, and `releases/latest`
pointed to it. Six public URLs returned HTTP 200, with unchanged asset IDs,
sizes/digests. Annotated tag `552576556b2d0f1cc9cd4c7328173e314e6996c8` still pointed
to `89c08a657bcd752c9f6b95e15192c8390d54d156`. Wiki publication used the same sources
with adapted Wiki routes.

GitHub-rendered HTML for README and two representative pages retained centring,
headings and captions. No automatable browser was available: a full visual
browser walkthrough was not performed. Qt captures were visually reviewed,
using public data or labelled synthetic demonstrations (measurements, device
settings, update report), not real instrument readings/downloads.
This audit certified neither App Store/Companion/phones nor printing or all
printers/readers. Mobile privacy documentation must describe the actual submitted
mobile application. Later English wording changes do not change these dated results.
