# Universal templates for new traces

**Version: 4.0 — 2026-11-07.** Adapt these examples; do not create every file on
every run. **Never manufacture a QA, decision or PREUVES folder.** Canonical
filenames, schema keys, status codes and placeholder identifiers remain unchanged.

## 1. `docs/agent-runs/INDEX.md`

```markdown
# Development history — [actual project name]

| Phase | Attested start | Objective | State | Latest QA | Latest human decision | Next authorised action |
| --- | --- | --- | --- | --- | --- | --- |
| [AAAA-MM-JJ-SUJET](AAAA-MM-JJ-SUJET/00-PHASE.md) | YYYY-MM-DD | ... | EN_COURS | NON_REALISEE | AUCUNE | Await framing |

## Dependencies and overlaps
- ... (only when attested)
```

## 2. `00-PHASE.md`

```markdown
# Phase — [explicit objective]

- **Attested start:** YYYY-MM-DD / date not established
- **Objective:** ...
- **Scope and exclusions:** ...
- **State:** EN_COURS / EN_ATTENTE_HUMAIN / BLOQUEE / CLOTUREE / ABANDONNEE
- **Opening decision source:** reference / NON_ETABLIE
- **Latest QA:** link / NON_REALISEE
- **Latest human decision:** link / AUCUNE_ETABLIE
- **Next authorised action:** ...

## Actual loops
- [B01-OBJECTIF](B01-OBJECTIF/00-BOUCLE.md) — ...

## Synthesis and assessment
- [Synthesis](80-SYNTHESE.md) if actually created
- [Assessment](90-BILAN.md) if actually created
```

## 3. `00-BOUCLE.md`

```markdown
# Loop B01 — [objective]

- **Phase:** ...
- **Specific goal:** ...
- **State:** EN_COURS / EN_ATTENTE_HUMAIN / QA_FAIL / QA_PASS / INCOMPLETE_ENV / TERMINEE
- **Human mandate:** link / NON_ETABLI

## Events in actual order
| Attested date/order | Author | Document | Transmission/result |
| --- | --- | --- | --- |
| YYYY-MM-DD | Codex | [Mission](02-CODEX-MISSION-CLAUDE.md) | PREPARED, NOT TRANSMITTED |

## Latest QA, conclusion and next step
- **Verdict and evidence:** ... / NON_REALISEE
- **Human decision:** ... / EN_ATTENTE
- **Permitted next step:** ...
```

## 4. Report metadata (`NN-AUTHOR-TYPE.md`)

```yaml
---
trace_id: "PROJECT:PHASE:B01:02"
phase: "AAAA-MM-JJ-SUJET"
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

Follow with objective, observed facts/hypotheses, scope/exclusions, requested or
performed work, evidence/tests, limits, state and next action.

### Optional Codex → Claude handoff after framing

`02-CODEX-MISSION-CLAUDE.md` gives one objective, verified facts, source/baseline
and pre-existing work, allowed/excluded files, acceptance criteria, tests and
deliverables. **STOP; personal human transmission only.** Never claim transmission
before the human acts.

### Claude report and preparation for QA

`03-CLAUDE-IMPLEMENTATION.md` records actual changes, results/limits, commands,
tests, real environments and evidence. `04-CLAUDE-PASSATION-CODEX.md` identifies
the delta and points needing **independent** re-QA. **STOP; do not launch Codex.**

### Codex QA

`05-CODEX-QA.md` records the checked version, actual diff, reproduced/unexecuted
tests, evidence, risks, verdict (`PASS`, `PASS_AVEC_RESERVES`, `FAIL`,
`INCOMPLET_ENV`, `BLOQUE_HUMAIN`), proposed action and **STOP for a human decision**.
A later correction never changes an earlier report's verdict.

### Human decision

Create `06-HUMAIN-DECISION.md` **only for an actual human decision**, with source
and scope. Its presence does not implicitly authorise Git or publication.

## 5. `70-REGISTRE-ESSAIS.md` — only for actual resources

```markdown
# Test-resource register — [phase]

| ID | Loop | Environment/copy | Actual path | Creator/date | Source version | Result/evidence | Lifecycle state | Cleanup decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T001 | B01 | isolated test build | absolute path | ... | ... | ... | CONSERVER | Decide after QA |
```

An existing technical register may hold the entries if the phase register links
to it reliably. Do not duplicate resource volumes.

## 6. `PREUVES/MANIFESTE.csv` — only for actual evidence

```csv
preuve_id,chemin_relatif,type,horodatage,essai_id,environnement,commande_ou_methode,resultat,sha256_ou_NON_MESURE,retention
E001,E001-TEST-SUBJECT.txt,TEST,2026-11-07T10:00:00+08:00,T001,LOCAL,executed-command,PASS,NON_MESURE,CONSERVER
```

This illustrates the schema, **not an executed test**. Never copy the fictional
row into a real manifest.

## 7. `80-SYNTHESE.md` and `90-BILAN.md`

**Synthesis:** objective, actual loops, results/failures, adopted/rejected choices,
lessons, limits and next action. **Assessment:** provisional state or closure
supported by a human act, QA/decision links, deliveries, active/completed tests,
cleanup performed or absent, **measured** occupation/reclaimed space, permitted
next steps. Never write `CLOTUREE` without the required human closure decision.
