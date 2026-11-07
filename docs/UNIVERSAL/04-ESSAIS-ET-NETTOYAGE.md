# Test-resource lifecycle and careful cleanup

**Version: 4.0 — 2026-11-07.** These rules cover project copies, laboratories,
clones/worktrees, caches/builds, virtual environments, VMs, containers, browsers,
Xcode, simulators and other test setups without imposing a particular tool.

## 1. Register resources at creation

When a test creates a distinct resource, record its T001 identifier
**immediately**: current project, phase/loop, objective, author, real absolute
path, source/revision, any process, current state and end-of-life conditions.
Do not multiply complete project copies for a repeatable test that only needs
an isolated build or fixture.

Use the phase's `70-REGISTRE-ESSAIS.md`, or an existing technical register linked
from it. Completing a test does not erase its history: keep the result,
conclusion and evidence location accessible.

## 2. Assess after a test, QA or phase

Before cleanup, retain useful results, errors, conclusions, unique diffs and
reproduction evidence **outside the resource to be cleaned**. Identify unintegrated
code, unique branches/commits, data, secrets/profiles/identities and dependencies
on still-open tests.

| Stable state code | Meaning |
| --- | --- |
| `ACTIF` | Used by an active process/campaign; do not touch |
| `CONSERVER` | Essential for reproduction, pending QA or unique work |
| `PARTAGE` | Shared across stages/projects; not an exclusive temporary resource |
| `INCERTAIN` | Origin, diff or usefulness unproven; preserve |
| `NETTOYABLE_APRES_ACCORD` | Redundancy/no unique content demonstrated; targeted permission pending |
| `QUARANTAINE` | Reversible move requiring a restoration manifest; no default space-reclaimed claim |
| `NETTOYE` | Attested deletion with exact path and measured outcome |

## 3. Who may clean what?

At execution end, close only **your own** processes, sessions, sockets, servers
and temporary profiles with proven ownership/lifecycle. The mandate must
authorise removing the created resource. Never stop a pre-existing user instance
or use broad patterns, `pkill` or `killall`.

After QA, permanently deleting a complete copy, VM, simulator, worktree,
snapshot, historical shared cache or quarantine requires **separate targeted
human permission naming the paths**, with proof of no unique work and no ongoing
use. QA PASS or documentary closure does not imply deletion permission.

Strictly regenerable caches may be purged only under explicit mandate and after
an inactivity check. Unknown environments remain protected.

## 4. Copies elsewhere

Never automatically search outside the current project. A human must authorise
the locations and inventory purpose. A similar name is not ownership evidence:
corroborate a Git reference, creation manifest, declared origin or relevant
content match **without inspecting neighbouring projects**. Do not follow
out-of-root symlinks, traverse unauthorised volumes/synchronisation areas or ask
for `sudo`.

Distinguish parent/child projects, product copies versus a separately authorised
Wiki repository, signed distributions versus caches, and simulator profiles
versus simple temporary fixtures.

## 5. Operational closure and disk space

`90-BILAN.md` summarises test outcomes once, cleaned/quarantined/protected/uncertain
resources, restoration manifests, **bytes permanently deleted**, **observed free
space before/after** and limits. APFS hard links, clones and snapshots mean logical
size alone does not prove reclaimed space. Moving to Trash on the same volume
does not reclaim it at that stage.

No global Trash emptying, opportunistic archive/download deletion or broad
DerivedData/simulator/VM/snapshot purge. Prefer one consolidated qualified batch
to dozens of small cleanups. Keep cleanup simple, measured and reversible wherever possible.
