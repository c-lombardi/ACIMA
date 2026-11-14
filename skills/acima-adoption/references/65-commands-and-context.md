# 65 Commands And Context


## Commands

Every command below is read-only unless marked.

| Command | Purpose | Writes |
|---|---|---|
| `acima.py status --root .` | scope-aware objectives, evidenced steps, blockers, one next action | no |
| `acima.py inspect --root .` | language, units, level, enforcer readiness | no |
| `acima.py assess --root .` | fit assessment and verdict | no |
| `acima.py analyze --root .` | run the reference enforcer, print findings | no |
| `acima.py fix --report <run> [selector]` | finding → catalog remedy and correction shape | no |
| `acima.py report --root .` | evidence report naming rules that did not run | no |
| `acima.py claim --report <run> --level <L> --require full` | `FULL`/`PARTIAL`, bound to current provenance, and gate it | no |
| `summarize.py --root <target> --report <run>` | run → reader-facing summary | `--out` only |
| `preflight.py --project <target>` | calibration, classification and automatic module-map proposal | `--write-*` only |
| `acima.py adoption start --root <target> --mode guided` | start the one adoption flow; legacy `full` state resumes but a new `full` start is refused | writes `acima/state.json` and generated artifacts |
| `acima.py adoption status --root <target>` | current stage, artifacts, blockers and one next action | no |
| `acima.py adoption approve --root <target> --map-decisions <json> --scope <json>` | record the scoped map and adoption approvals, then implement | the approved artifacts only |
| `acima.py adoption remediate --root <target> --choice none` | decline immediate source remediation and retain the proposal | decision and handoff artifacts only |
| `acima.py adoption remediate --root <target> --choice selected --selected <id> --confirm` | apply named ready fixes after review | selected source files and focused tests |
| `acima.py adoption remediate --root <target> --choice all --confirm` | apply all applicable ready fixes | all ready recommendations, never manual ones |
| `acima.py adoption remediate ... --confirm-scope` then `--confirm-implementation` | large brownfield two-step authorization | source changes only after the second confirmation |
| `acima.py adoption guidance --root <target>` | apply generated agent guidance when the scope already authorized it, otherwise show the proposal | instruction files and support documents |
| `acima.py adoption guidance --root <target> --approve` | approve and apply generated agent guidance without repeating discovery | generated instructions, validation record and final handoff |
| `module_map.py discover --project <target>` | read-only candidate boundaries, evidence, recommendations and decisions | `--write-proposal` only |
| `module_map.py review --project <target> --proposal <json> --decisions <json>` | validate explicit per-boundary and per-recommendation decisions | `--write-approval`, `--write-config` only |
| `inject_violation.py --project <target> --out acima/evidence/proof.json` | prove the enforcer detects controlled input | `--out` only |
| `<language enforcer> --root <target> --format json` | the gate for one language | no |

When a user must run a command, give purpose, working directory, prerequisites, whether it writes,
one copyable form, expected success output, and what to do on failure. Support PowerShell and POSIX
where the user runs it.



## Context files

Read these before proposing or resuming; never reconstruct state from the conversation:
`acima.config.json` (approved units, level, mode), `acima/evidence/module-map.approval.json` (proposal
identity, reviewer, date, scoped decisions and approval state), `acima/evidence/adoption-scope.json` (approved objectives and
approval metadata), `acima/evidence/assessment.json` (the read-only assessment evidence),
`acima/evidence/baseline.json` (frozen fingerprints), `acima/evidence/waivers.json` (owned exceptions),
`acima/evidence/manual-evidence.json` (manual-rule evidence), `acima/handoff/STATUS.md` (next step),
`acima/evidence/gate-*.json` (the runs a claim rests on), `acima/evidence/triage.json` (recorded defect /
artefact / review decisions). Missing means missing: name the artefact and the phase that produces
it; do not invent contents. Optional docs: `acima/optional/adoption-plan.md`,
`acima/optional/communication-plan.md`, `acima/handoff/adoption-summary.md`, `acima/handoff/handoff.md`.
