> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Repository presentation and maintenance

Applied on 1 November 2026, after publication of v0.3.0.

## Public presentation

- README rebuilt around an actual application preview, platform downloads, four
  first-use steps and concise compatibility/source explanations.
- Two screenshots use public snapshots and isolated demo preferences;
  [capture provenance](../../images/README.md). Technical details moved to
  [DEVELOPMENT](../../DEVELOPMENT.md).
- About describes a multi-manufacturer catalogue and preparation of OpenSpool
  files, rather than direct NFC writing or a three-brand-only catalogue.
- Topics reflect desktop use, OpenSpool and NTAG215/216. The homepage points to
  the latest release. The unused Packages block is hidden; Releases, sponsorship
  and contributor attribution remain visible.
- The standard MIT licence, NOTICE and contributor covenant are retained.
  Security reporting remains private; the policy now describes the catalogue,
  preferences, backups and exports actually stored locally.

## Main branch

The active GitHub branch protection requires a PR, a branch up to date with main
and these four checks from the GitHub Actions app (ID 15368):

- `Tests ubuntu-latest / Python 3.10`
- `Tests ubuntu-latest / Python 3.12`
- `Tests windows-latest / Python 3.12`
- `Tests macos-latest / Python 3.12`

Force pushes and deletion are disabled, including for administrators. Review
threads must be resolved. Zero external approvals are required so a solo
maintainer can merge a passing PR without approving their own work.
These rules do not change tag or release contents.

## Dependabot PR #3

[PR #3](https://github.com/ArN-LaB/Spoolscribe-/pull/3) updates SHA-pinned
`actions/checkout` to 7.0.1 and `actions/setup-python` to 7.1.0. Its branch was
updated with main and then [explicitly tested and built](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41280766854):
four successful test configurations and three successful native builds on
`b260303db9e367f934b399f27244ae20459f8c5c`. The earlier skipped builds were not
counted as validation. It was merged as `74f0a919312b954a556a18b708e2f43fd650b7d3`.

No new application version, tag or release is created for this presentation
change. v0.3.0 binaries and their checksums remain intact. Catalogue fixtures,
Orca profiles, application behaviour and personal user data are unchanged.
