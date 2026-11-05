# Releases: software stability and hardware evidence

[Download v0.8.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0) · [Validation](validation/v0.8.0.md) · [Compatibility help](wiki/Printers-and-Readers.md)

## Current decision

**v0.8.0 is the current Desktop stable release**, following the authorised
promotion audit on 5 November 2026. Its first publication was a pre-release.
Promotion changes the GitHub release channel and latest pointer only: the annotated
tag, commit, three archives and three SHA-256 files are not replaced or rebuilt.
The old v0.3.5 stable release remains available as history, not the default download.

Stable means the supported **software workflow** passed its release gates:
four Python/OS configurations, three native builds, frozen application probes,
contract regressions, and public archive/hash checks. It does not mean access to
or physical certification of every printer listed in the catalogue.

## Keep compatibility evidence separate

| Evidence | What it supports |
| --- | --- |
| Documented setup | Primary documentation identifies the model, reader, firmware/plugin and accepted format. |
| Software-validated export | Tests cover the exported bytes, bounds and transfer contract. |
| Physically tested setup | A dated, reproducible result identifies the exact printer, reader, firmware/plugin, tag and read-back. |
| Unsupported or unknown | The integration is not established; no successful printer use is promised. |

These are descriptions of evidence, not new runtime certification badges.
A missing hardware report does not make the entire Desktop app a permanent beta.
Unknown setups still require cautious, explicit wording and a real read-back test.
[Send a hardware result](https://github.com/ArN-LaB/Spoolscribe-/issues/new/choose).

## Future releases

- Stable releases use `vX.Y.Z`. Fixes increment Z; additive features increment Y
  while the project is below 1.0. Wire-format changes need explicit contract review.
- Candidate releases use an explicit suffix such as `vX.Y.Z-rc.N` and the GitHub
  Pre-release flag. Version metadata must pass platform/build checks before tagging.
- `main` is the maintained source; only a tagged, validated release is a download.
- Do not rerun an old tag to replace public files. Fixes receive a new tag/version.
- Promotion requires explicit authorisation, existing green software evidence,
  an unchanged asset audit and updated current help/metadata. Keep the initial
  publication evidence; annotate the later channel change instead of rewriting it.
- Companion has its own mobile build/version/review cycle. Desktop stable does
  not announce a released or certified iOS/Android application.

## Repository information and the future App Store entry

The public repository supplies Desktop downloads, accurate descriptions, current
illustrations, support links and a Desktop privacy policy. It is not an App Store
approval or a substitute for reviewing the actual Companion binary.

Before mobile submission, the mobile support URL, screenshots, availability and
privacy policy must describe the shipped Companion experience, including its actual
data and NFC permissions. The Desktop policy is not automatically a mobile policy.
See Apple's [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/),
sections 1.5, 2.3 and 5.1.1, consulted 5 November 2026.
