# Universal standard — phases, loops, reports and evidence

**Version: 4.0 — 2026-11-07**
**Authority:** organisation and production of agent development traces.
**Scope:** individual projects, without requiring Git or a particular technology.

## 1. Purpose and principles

Development history must explain **when, why, by whom, with what result and under
which decision** work progressed. Navigation shows dated objectives, actual agent
cycles, results and the next genuinely authorised human action.

A **phase** is one coherent functional objective, opened on an attested date.
It may be active, blocked, closed, abandoned or parallel to another phase; do not
invent a sequential timeline. A **loop** is one work cycle within that phase,
from framing and optional handoffs through QA and decision. A Codex → Claude
transition alone does not create a new loop. A correction after failed QA may
open B02/B03/etc. on a human decision.

A **report** is a distinct dated piece: never silently replace one QA report
with the next. **Evidence** supports an actual assertion/test, rather than an
unexplained accumulation of logs/screenshots. Historical paths may be renamed,
but facts, human decisions, results and verdicts retain their meaning. Any
migration requires an old → new mapping and link verification.

Keep one principal organisation. No competing phase tree, thousands of redirects
or empty directories created for hypothetical future work.

## 2. Canonical structure

```text
docs/
├── UNIVERSAL.md
├── UNIVERSAL/
└── agent-runs/
    ├── INDEX.md
    ├── 2026-11-07-[ID-]EXPLICIT-OBJECTIVE/
    │   ├── 00-PHASE.md
    │   ├── B01-LOOP-OBJECTIVE/
    │   │   ├── 00-BOUCLE.md
    │   │   ├── 01-CODEX-CADRAGE.md
    │   │   ├── 02-CODEX-MISSION-CLAUDE.md
    │   │   ├── 03-CLAUDE-IMPLEMENTATION.md
    │   │   ├── 04-CLAUDE-PASSATION-CODEX.md
    │   │   ├── 05-CODEX-QA.md
    │   │   ├── 06-HUMAIN-DECISION.md
    │   │   └── PREUVES/
    │   │       ├── MANIFESTE.csv
    │   │       └── E001-TEST-SUBJECT.txt
    │   ├── B02-TARGETED-CORRECTION/
    │   ├── 70-REGISTRE-ESSAIS.md
    │   ├── 80-SYNTHESE.md
    │   └── 90-BILAN.md
    └── 2026-11-08-OTHER-OBJECTIVE/
```

Dates/names are illustrative. Create only necessary files and directories. A
phase/loop index may exist at opening; QA or decision files must not exist before
the corresponding event. `PREUVES/` exists only for actual separate evidence;
the test register exists once a real test resource has been created.

## 3. Stable naming

| Element | Canonical name | Meaning |
| --- | --- | --- |
| Phase | `YYYY-MM-DD-[BUSINESS-ID-]EXPLICIT-SUBJECT/` | Attested start date and meaningful objective, not an abstract rank |
| Loop | `B01-SUBJECT/`, `B02-CORRECTION-.../` | Bxx increases within its phase; descriptive subtitle |
| Entry points | `INDEX.md`, `00-PHASE.md`, `00-BOUCLE.md` | Short current navigation views |
| Report | `NN-AUTHOR-TYPE[-SUBJECT].md` | Two-digit number, actual author/role and purpose |
| Synthesis | `80-SYNTHESE.md` | Results, limits and lessons |
| Assessment | `90-BILAN.md` | Operational state, decision, next action and cleanup |
| Test register | `70-REGISTRE-ESSAIS.md` | Created with the first test/copy/VM/simulator |
| Evidence | `PREUVES/E001-TYPE-SUBJECT.ext` | E001 increases within the loop, with one manifest |

The standard Codex/Claude filenames above are **conditional locations**, not
mandatory empty files. Other agents use their actual roles in `NN-AGENT-ROLE.md`;
the standard does not require Codex or Claude.

No `(1)`, `(2)`, `final-final`, `02b`, `03b`, invented temporal suffix or reused
number. A new piece by the same author within the same correction uses the next
free NN and a precise title. Project/phase/loop prefixes may be added **on export
only** to avoid download collisions. Record an uncertain historical start date
as not established instead of inventing one; record new opening dates immediately.
Existing canonical filenames, schema keys, example identifiers and machine status
codes are retained across language translations.

## 4. Roles, handoffs and permissions

The usual human-controlled workflow is:

```text
HUMAN mandate → CODEX framing/mission → STOP
HUMAN reads, authorises and personally transmits
→ CLAUDE CODE implementation/report/handoff → STOP
HUMAN reads, authorises and personally transmits
→ CODEX independent QA/verdict → STOP
HUMAN decides closure, correction, deferral, Git or publication
```

**No automatic call, launch or inter-agent transfer**, including sub-agents,
APIs, scripts, CI and automation. A prepared document is not necessarily
transmitted: `transmis: true` requires an actual human action, not a file's presence.

Technical QA neither closes a phase nor authorises Git/deployment. Git permission
must be explicit and match the requested operation. Codex does not implement an
application correction merely because QA passed/failed; a human decides the next
step. Keep targeted tasks proportionate and avoid repeated broad audits/campaigns.
If an explicitly approved project workflow differs, retain the real responsibility
and human gate rather than inventing Codex/Claude interventions.

## 5. Minimum metadata and content

New traces include front matter or equivalent:

```yaml
---
trace_id: "PROJECT:PHASE:B01:02"
phase: "YYYY-MM-DD-ID-SUBJECT"
boucle: "B01-OBJECTIVE"
sequence: 2
auteur: "CODEX"
fonction: "MISSION-CLAUDE"
date: "YYYY-MM-DD"
statut: "PREPARE"
transmis: false
source_ref: "NON_ETABLI"
---
```

Use attested names/dates; unknown means `NON_ETABLI`, never a fictional
reconstruction. Describe the objective, observed facts versus hypotheses, scope
and exclusions, Git **or non-Git** source context, requested/actual actions,
commands/results, evidence, limits, status and next **authorised** action.

QA has a separate verdict (`PASS`, `PASS_AVEC_RESERVES`, `FAIL`, `INCOMPLET_ENV`,
`BLOQUE_HUMAIN`). Untested is never a success. A report retains its original
verdict after a later correction. A human-decision piece exists only for an
attested decision, with its source/date/scope/restrictions; a proposal is not permission.

Handoffs must be self-contained and identify the exact file, verified facts,
delta, acceptance criteria and tests. Chat gives the path and short summary;
an agent never transmits the mission to the next agent automatically.
Never record secrets, keys, tokens, passwords, personal information or user data
in reports/evidence.

## 6. Evidence

Create `PREUVES/` only when separate evidence is actually produced/referenced.
One `MANIFESTE.csv` uses the stable schema:

```csv
preuve_id,chemin_relatif,type,horodatage,essai_id,environnement,commande_ou_methode,resultat,sha256_ou_NON_MESURE,retention
```

Attach evidence to the right **loop**, with a date, real environment
(simulation/local/browser/device/VM/production), useful command/method, observable
result and limits. For large evidence outside the repository, give a stable
location and relevant digest rather than importing giant caches/archives to
manufacture a trace. Absent evidence is not PASS. Retain what is needed for QA
and reproduction, not every regenerable build byte.

## 7. Navigation, history and closure

`INDEX.md` lists phases by attested start, overlaps/dependencies, status, latest
valid QA/decision and next human action. `00-PHASE.md` gives objective, start,
state and loop links. `00-BOUCLE.md` records actual event order, human transmission
and QA.

`80-SYNTHESE.md` summarises results, failures, adopted/rejected solutions,
lessons and remaining risks; it can be provisional. `90-BILAN.md` records
operational state, established human decisions, next action, active/cleaned/
protected resources and **measured** space reclaimed. Never label a phase
`CLOTUREE` without the required human decision. End a loop with a short synthesis
and index update, not a new directory merely because the agent stops.

No “empty for later” directory. Report empty or `.DS_Store`-only trace directories;
remove them only when authorised and free of contractual dependencies. Do not
clean neighbouring business docs or Git/build folders to improve a metric.

## 8. Historical migration: only once and only when needed

Do not repeat a complete restructuring without an explicit need. If adoption
is requested, read this project's index, decisions and previous reports only.
Map actual path changes and objectives without inventing chronology. Back up
relevant preimages, including untracked files, verify them and respect Git safeguards.

Rename/move necessary originals, repair active references, anchors, scripts and
agent rules, retain dated raw evidence and translate old paths through one mapping.
Remove only wholly redundant aliases with proof of no unique content and a
restoration route. Never delete an original decision, QA, report or proof.
Run one consolidated check of local links, Unicode/case collisions, empty folders,
Git state, verdict preservation and registers. Put the short result and mapping
in the existing documentary phase; do not create competing navigation.

Moving/renaming/reference repair is authorised only within the explicitly
approved documentary scope. Installing this kit alone permits no deletion,
quarantine purge, commit or push.

## 9. Project-specific instructions remain authoritative

This is the common organisation/traceability standard, not a replacement for
project security, architecture, privacy, teaching, browser tests, signing,
hardware QA or CI/CD rules. Keep recognised `AGENTS.md`, `CLAUDE.md`,
`AGENT_WORKFLOW.md` and `README.md` entry points. When authorised, add a short
UNIVERSAL link and replace only contradictory documentary naming clauses.

Technical/security rules retain their authority in their domains. Common rules
apply to **new documentary traces** unless the human explicitly decides otherwise.
Identify and resolve real local contradictions without mass-merging or rewriting
frozen historical instructions.

## 10. Efficient verification

Reuse stable references and check the delta, then perform one final consolidated
verification; avoid hundreds of repeated checks and migration reports.
`docs/UNIVERSAL/OUTILS/verifier.py` is **read-only** and checks naming, structural
files, detectable local links and empty folders. It is not application QA or an
absolute guarantee of every URL, rendered anchor or dynamically generated link.

## 11. Test environments and cleanup

Read [`04-ESSAIS-ET-NETTOYAGE.md`](04-ESSAIS-ET-NETTOYAGE.md) for immediate resource
registration, post-QA assessment, protection of unique work and cleanup only
under targeted authorisation.
