# UNIVERSAL — agent entry point

**Standard version: 4.0 — 7 November 2026**
**Applies to any project, regardless of language, repository or tooling.**

> Any agent working on development, review, handoff or trace maintenance starts
> here. `UNIVERSAL/` contains the common standard, not an application-specific contract.

## Required reading order

1. [`UNIVERSAL/01-NORME.md`](UNIVERSAL/01-NORME.md): authoritative rules for phases, loops, Markdown, decisions and evidence.
2. [`UNIVERSAL/03-MODELES.md`](UNIVERSAL/03-MODELES.md): templates and required fields for new traces only.
3. [`UNIVERSAL/04-ESSAIS-ET-NETTOYAGE.md`](UNIVERSAL/04-ESSAIS-ET-NETTOYAGE.md): lifecycle of copies, tests, VMs, simulators and caches.
4. [`UNIVERSAL/02-MISSION-ADOPTION.md`](UNIVERSAL/02-MISSION-ADOPTION.md) **only when the user requests installation/adoption** in the current project.
5. Read relevant existing technical instructions (`AGENTS.md`, `CLAUDE.md`, `docs/AGENT_WORKFLOW.md`, `README.md`, etc.).

## Common rules and project-specific contracts

Development trace names and organisation follow `UNIVERSAL/01-NORME.md`.
Project security, business, teaching, Git, publication, testing and tooling rules
remain applicable. Do not replace them with generic guidance.

For documentary-format conflicts, apply the common standard to new pieces and
identify active references requiring reconciliation. For technical or permission
conflicts, do not make the human's decision. **Recent explicit human decisions
prevail over agent proposals. A QA PASS does not authorise Git or deployment.**

## Scope and verification

**Current project only.** Use the explicitly designated open project's root,
not a parent directory. Do not inspect other projects, accounts, repositories
or storage to “harmonise everything”. External test resources may be identified
only under an explicit human mandate with verifiable ownership; never clean
them implicitly.

Read-only documentation checker:

```sh
python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
```

If adoption is requested, read `UNIVERSAL/02-MISSION-ADOPTION.md`, work only on
this project, then STOP with a short report. **No automatic Codex ↔ Claude Code
handoff.** Existing filenames, metadata keys and status codes remain stable even
when the explanatory documentation is written in English.
