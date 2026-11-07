# Universal mission — adopt the standard in the open project

**Version: 4.0 — 2026-11-07**
**Recipient:** Codex or the agent explicitly mandated by the user.
**Authority:** execute this mission **only when the user expressly asks to apply it**.

## 1. Non-negotiable scope

Work **only on the explicitly designated open project**. Identify its root
(Git root if applicable, otherwise the project directory), without searching
parents for other projects. If multiple workspaces are open and the target is
unclear, STOP and state that fact; do not choose a neighbouring repository.

Do not inspect neighbours, personal libraries, NAS/cloud storage, remote
repositories, VMs or outside folders. External test resources already referenced
in the project may be **listed by reference** without opening them. Outside
inventory and cleanup require a separate targeted human mandate.

## 2. Read efficiently

Read `docs/UNIVERSAL.md`, `01-NORME.md`, `03-MODELES.md` and
`04-ESSAIS-ET-NETTOYAGE.md`. Read relevant active local instructions, if present:
`AGENTS.md`, `CLAUDE.md`, `docs/AGENT_WORKFLOW.md`, `README.md` and their pertinent
references. Do not replace a business contract with generic guidance.

Read the existing `docs/agent-runs/INDEX.md`, latest normalisation reports and
current phase state. Reuse inventories instead of rereading hundreds of
historical pieces or repeating an accepted migration. Run the read-only checker once:

```sh
python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
```

## 3. Apply the requested adoption

Determine whether the project is new, already organised or inherited. Do not
automatically initialise Git or assume a branch/SHA outside Git. Establish
`docs/agent-runs/INDEX.md` where phases exist and add a short UNIVERSAL link to
active instruction files **only if editing them is authorised**.

Never overwrite `AGENTS.md`, `CLAUDE.md` or `AGENT_WORKFLOW.md`: change only
contradictory documentary clauses, preserving security, tooling, testing,
business, architecture, deployment and publication rules.

New phases/loops immediately follow standard names, metadata and evidence rules.
Create no fictional piece or empty folder. In an already restructured project,
retain the compliant tree and fix only actual naming/navigation/link/status
anomalies; do not repeat a cosmetic mass migration.

Physical migration of old documents requires explicit authorisation. Use attested
dates/objectives, rename/move necessary originals, repair active references,
retain one old → new table and verified preimages, then perform one consolidated
check. Keep neither unnecessary aliases nor a competing history tree.

Check empty documentary folders. Remove only authorised unnecessary folders,
after checking hidden content and contractual dependencies. Integrate test
inventories/assessments into real phases. **No outside purge or complete project
copy deletion** without a later instruction naming qualified targets.

## 4. Safeguards

No business-code, user-data, sensitive-data, `.git`, neighbour-repository or tool
configuration change without a suitable mandate. Stage, commit, push, merge,
publication, TestFlight, CI, deployment and launching another agent are never
implicit. Never use broad `git reset --hard`, `git clean -fd`, `rm -rf` over
project sets, or `pkill`/`killall` as cleanup.

A PASS is not human permission. A past quarantine is not measured reclaimed
space. This mission concerns governance/documentation, not application QA.

## 5. Final check and minimum deliverable

After authorised changes, run **one** final verification:

```sh
python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
```

Also inspect changed active references and Git state where applicable. Warnings
do not grant implicit approval. Produce **one report** in the existing documentary
phase, or a genuinely opened governance phase if needed, without extra report layers.

Record initial/final state, changed paths, old → new destinations, repaired links,
removed empty folders, exceptions, test-resource/cleanup outcome (or `AUCUNE_PURGE`),
preserved material and next human action. Mark `PARTIEL` if relevant criteria remain unmet.

**STOP.** Prepare no Claude Code handoff unless explicitly requested. No automatic transmission.
