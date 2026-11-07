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

Use the same reading order for every release:

| Section | Reader's question | Content |
| --- | --- | --- |
| Opening summary | What is this version for? | A short version-specific explanation and original publication/channel |
| What's new | Why would I use it? | Three concise, version-specific workflow explanations |
| Download | Which file do I need? | Three platform cards with ZIP size, checksum and attested system requirements |
| Validation & limits | What is proven? | Visible outcomes and limits; long evidence in one collapsed record |
| Help & next steps | Where do I learn more? | Installation, help and support links with a short explanation |

Keep the main explanation in paragraphs rather than dumping commit lists. Use
tables for genuine comparisons. Long original technical records may be retained
in a clearly labelled collapsed details section; explain that old “latest stable”
statements describe the original publication stage. Do not hide failures or
promote unmeasured coverage to PASS. Keep the same section titles across versions,
and never give an old binary today's notarisation claim.

## Release presentation rules

Use a short native release title such as **v0.8.1 · Backups & recovery**. Do not
repeat it as an H1 in the body. The repository header already identifies the
product; avoid repeating “SpoolScribe Desktop” in every title, section or link.
Keep original asset names and historical quotations intact.

Write each prose paragraph on one source line in release bodies. GitHub's release
renderer turns embedded line endings into visible breaks; wrapping source at
80 characters produces narrow blocks even in a wide viewport. Let the browser
wrap paragraphs naturally. Intentional line breaks belong only in small labels,
code and data that actually require them.

Use GitHub-supported HTML tables with `width="100%"`, equal-percentage cells and
`valign="top"` for short feature, platform and help cards. Keep the cards concise,
use semantic headings and links, and check the sanitised GitHub rendering rather
than assuming arbitrary CSS or fixed-width spacers will work. Do not use scripts,
inline styles, decorative blank images or manually padded spaces to force width.

Keep known failures, unsupported coverage and important safety limits visible.
Place the original detailed test tables, full hashes and historical notes in one
clearly labelled collapsed section. Do not delete evidence to shorten the page.
Verify the wide desktop rendering and a narrow view; GitHub controls the outer
page width, padding and sidebar, which release Markdown cannot override.

Display language-choice labels in their own language: **English · Français · Español · 简体中文**. Surrounding explanations remain English; native language labels are intentional, not untranslated explanatory prose.
