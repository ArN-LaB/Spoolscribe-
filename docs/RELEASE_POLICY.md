# Releases: software stability and hardware evidence

[Download v0.8.1](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.1) · [Validation](validation/v0.8.1.md) · [Compatibility help](wiki/Printers-and-Readers.md)

## Current decision

**v0.8.1 is the Desktop stable release**, built from the integrated Desktop 002
sources. Its macOS arm64 archive is Developer ID signed, Apple-notarised and
stapled. Windows and Linux archives are new CI builds from the same source commit.
The original v0.8.0 tag and six assets remain unchanged. Its release wording
is maintained in English under the common documentation policy below.

The historical macOS SIGSEGV was not reproduced in the bounded diagnostics; its
cause is not established. The owner explicitly authorised release without claiming
a crash fix. Reopen the diagnosis if a new incident occurs.

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

## Public language and common release layout

All editable product descriptions, README/help pages, Wiki pages and release
titles/bodies are maintained in **English**. The application remains multilingual.
Do not rewrite Git history, move tags, replace assets or translate literal
protocol identifiers merely to change documentation language. A historical
release can have its explanatory wording translated without changing its dated
outcomes, channel or binaries.

Use a short native release title such as **v0.8.1 · Backups & recovery**. The body opens with a short purpose statement, without repeating the title or product name.

## Editorial layout

Use the same modest heading level and reading order for every version: **Highlights**, **Download**, then **Notes**. Describe one to three real changes in short paragraphs with an inline lead phrase. A focused fix does not need three invented selling points. Use whitespace and clear language instead of a grid of framed feature/help cards.

A single semantic download table aligns the operating system, attested build, ZIP size/link and checksum. Use the same table for the current README and release. Do not pad cells with repeated instructions to force width. A centred compact table is preferable to large, uneven boxes; paragraphs use the available content width naturally. Explain extraction and platform requirements once beneath the table.

Keep meaningful user-facing limits visible. Long test matrices, hashes, source commits and original technical notes belong in the linked, versioned [publication records](archive/README.md) and [validation documentation](validation/v0.8.1.md), with historical outcomes intact. An optional **Build & validation details** disclosure contains a brief factual summary and links, not a second copy of the release page.

Write each prose paragraph in release bodies on one source line, letting the browser wrap naturally. Never run a whitespace-flattening replacement across Markdown headings, blank lines, tables, lists or code fences. In a disclosure, use explicit HTML paragraphs and links, with blank lines around the block. Check both the closed and expanded output: raw heading markers, pipe-table separators and triple-backtick fences must not leak into ordinary rendered text. Reference: [GitHub collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections).

Review the actual published rendering, not just accepted HTML attributes. Preserve content and verify light/dark readability where accessible; do not claim mobile or visual coverage that was not observed. GitHub owns the outer page width and sidebar. Do not add scripts, inline styles, decorative spacers or screenshots from a newer version to dress up an old release.

Display language-choice labels in their native form: **English · Français · Español · 简体中文**. Explanatory prose remains English. Use the same restrained typography and task names in the README, Wiki and public support entry points.

## Companion review information

Make mobile [support](https://arn-lab.github.io/Spoolscribe-/support/), [privacy](https://arn-lab.github.io/Spoolscribe-/privacy/) and [availability](COMPANION.md) easy to find and clearly separate from Desktop downloads and policy. Keep the actual dated prototype scope visible until a reviewed shipping-build policy replaces it. Never turn Desktop tests or macOS notarisation into a Companion App Store approval claim.

Apple calls for accurate metadata and functional support/privacy links; a polished website alone does not establish acceptance. [App Review](https://developer.apple.com/app-store/review/) and [Guidelines 2.3 / 5.1.1](https://developer.apple.com/app-store/review/guidelines/), checked 8 November 2026. No mobile project or submitted build was audited by this documentary change.
