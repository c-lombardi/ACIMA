---
name: acima-adoption
description: Adopt, audit, and enforce the ACIMA architecture standard in a greenfield or brownfield repository. Use when the user asks to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, run an architecture audit against the ACIMA rule catalog, migrate a shared "Common" project, or onboard a team with no prior exposure to contract-based modular architecture. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.0.0-draft.1"
  skill-version: "1.2.3"
  catalog-sha256: "ec2a77d7a2ed4d8c68fd71c32ad47ac486022b2eb541b959a23f1d2b7ea9221b"
---

# ACIMA adoption

You are applying the ACIMA architecture standard — Autonomous, Contract-Isolated, Immutable
Modular Architecture — to a real repository. The standard lives in this repository:

- `tools/acima-spec/rules.json` — the 29-rule catalog. **Normative.**
- `docs/standard/` — the specification. Chapters 4 (dependency model), 5 (contract design),
  8 (conformance) and 9 (adoption) are the ones you will use most.
- `examples/<language>/` — a working ordering system (four modules in Python, three in
  TypeScript, Go and .NET), an enforcer, and a violation gallery.

Your job is not to explain ACIMA. It is to leave the target repository with **units declared, a
baseline measured, an enforcer wired, a first slice merged, and a named human owner for every
exception** — and to say plainly what is still missing.

## Outcomes (definition of done)

| Phase | Done when |
|---|---|
| Preflight | `preflight.py` exits 0, or every blocker has a named owner and a next action |
| Classified | The target is labelled `greenfield`, `brownfield` or `adopting`, with evidence |
| Planned | `adoption-plan.md` and `communication-plan.md` exist, filled, with dates and names |
| Baselined | A run artefact exists; every pre-existing finding is waived with owner + expiry |
| First slice | One boundary change is merged, not proposed |
| Gated | CI fails on new `error` findings at the declared level |
| Handed off | The team can run the gate without you; outcomes are reported in their terms |

A repository is **fully conformant** at a level only when the run artefact shows **zero unwaived
errors** at that level on the current commit **and every rule required by that level was executed**,
with a recorded manual/native evidence artifact where no automated rule exists. If any required rule
is `executed: false`, the result is a **PARTIAL ASSESSMENT**, not conformance. Anything less is a
plan, and you must call it a plan.

## Hard rules

1. **Never invent a rule ID.** Every finding cites an ID from `rules.json`.
2. **Never edit `rules.json`, an `expected.json`, or a manifest hash to make a check pass.**
   If the catalog has moved, stop and re-read it; the mismatch is the point.
3. **Never waive without owner, reason, scope, finding fingerprint, expiry and review date.**
   `ACIMA-G001` exists because unowned exceptions become permanent, and a fingerprint is what
   stops a baseline from hiding a new finding in the same unit.
4. **Never bulk-renew waivers.** Renewal is an individual decision by the named owner.
5. **Never declare conformance without a run.** "The architecture tests pass" is not evidence
   unless the run discovered files — zero findings from zero files is the most common false claim.
   Zero findings require all of the following: `sourceFiles > 0`, a complete execution map, exit
   code 0 or 1, valid JSON, the expected catalog and level, and controlled violations detected in
   disposable fixtures. Use `scripts/inject_violation.py` for that last check: it proves `L001` by
   injecting one violation into a copy of the target and proves `D001` with a disposable two-unit
   fixture, so a green result cannot come from an enforcer that saw nothing. If any condition is
   missing, report `not proven`, never `conformant`.
6. **Never treat invalid, truncated or missing output as zero findings.** Check the exit code,
   parse the JSON, and confirm the run is complete. A tool failure is `invalid assessment`, not a
   clean baseline. Keep the raw output where it can be inspected.
7. **Never start brownfield adoption at L3.** Start at L1, ratchet upward.
8. **Never rewrite the target to satisfy the standard.** Change the smallest boundary, then measure.
9. **Never apply ACIMA to a codebase whose owner has not asked for it.** This is a governance
   change, not a refactor.
10. **Never declare a library profile to silence a finding.** A profile needs publishable evidence,
    a named owner, a justification, and path-scoped declarations. Classified findings stay in the
    report; a new edge outside the declared paths must still fail. See
    [the library profile](../../docs/standard/12-library-profile.md).
11. **A required `executed: false` rule makes the result partial.** Name every such rule and the
    manual/native evidence it needs. Never report `FULL CONFORMANCE` from an incomplete execution
    map, even when the error count is zero.

## Workflow

### Step 0 — Preflight (always, before anything else)

```bash
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
```

Exit codes: `0` ready, `1` blocked, `2` the tool could not run. **Do not continue past a blocker.**
Report the blocker to the user in its own words, with the remedy the preflight printed.

The preflight asserts the skill is calibrated to the catalog in this repository *at this commit*:
`SKL-002` compares `rules.json` against the pinned SHA-256 in `manifest.json`, and `SKL-003`
checks that all 23 portable rule IDs still exist. If either fails, the standard changed after
this skill was written. Re-read the changed rules, update the skill deliberately, and only then
continue. Never silence the check.

### Step 1 — Classify

The preflight reports one of:

| Mode | Evidence | You do |
|---|---|---|
| `greenfield` | no `acima.config.json` and no source files | [greenfield playbook](references/10-greenfield.md) — full shape from day zero, declare L3 |
| `brownfield` | no `acima.config.json` and at least one existing source file | [brownfield playbook](references/20-brownfield.md) — measure, freeze, ratchet |
| `adopting` | `acima.config.json` present | verify the baseline, then resume at the current level |

Then read the **architecture mode** from `acima.config.json.mode` before proposing units. `base`
(or an absent field) applies P1–P9 and P2.1's one-contracts-unit rule. `service-topology` applies
P1–P9 plus P10–P13 and supersedes exactly P2.1 and P3.5 with per-layer contracts and total
isolation; this revision has no service workflow, so stop and report `NOT SUPPORTED`. Do not infer
the mode from directory names, and do not let `acima.topology.json` substitute for the config field.

Also classify the **architecture kind** before proposing units: application, modular monolith,
multi-service system, library, framework, SDK, plugin system, multi-package repository, or a mix.
A repository can be several at once; do not force one label. Use manifests, published artifacts
(`private`, `files`, `exports`, `IsPackable`, `PackageId`), deployment files and entry points as
evidence, and say which evidence you used.

If `acima.topology.json` exists, or the tree is organized as `services/<Service>/` with per-layer
`.Contracts` projects, this revision has **no supported service-topology workflow**. Stop and report
`NOT SUPPORTED`; do not apply base P2.1's one-contracts-unit rule to that repository. The service
profile is specified in [chapter 11](../../docs/standard/11-service-topology.md) and implemented by
`conformance/topology.py`, but this skill does not yet generate or validate its manifest.

If the mode is ambiguous, say so and ask one question: *"Is this repository allowed to gain a
build-blocking architecture gate, and who owns the exceptions?"* Do not proceed without an owner.

### Step 2 — Plan before touching code

Copy and fill:

- [`assets/adoption-plan.md`](assets/adoption-plan.md) → the target repo's `docs/acima/adoption-plan.md`
- [`assets/communication-plan.md`](assets/communication-plan.md) → `docs/acima/communication-plan.md`

Both templates require names, dates and metrics. A plan with `TBD` in the owner column is not a plan.
Use [references/50-outcomes.md](references/50-outcomes.md) to choose metrics that the team already
cares about (lead time, deploy frequency, incident count) rather than architecture-internal counts
alone.

### Step 3a — Greenfield: scaffold, don't negotiate

Follow [references/10-greenfield.md](references/10-greenfield.md). The order is fixed: contracts →
implementation → host → `acima.config.json` → empty waiver file → CI gate. Each contract owns its
value types; there is no shared kernel. The gate goes in **before** the second module exists, so the
rules are never optional.

### Step 3b — Brownfield: measure, freeze, then move

Follow [references/20-brownfield.md](references/20-brownfield.md). The ratchet is:

```bash
# 1. draft a unit map (heuristic, review it before committing)
python3 skills/acima-adoption/scripts/preflight.py --project . --write-draft acima.config.json

# 2. measure at L1 and write the review artefact
python3 skills/acima-adoption/scripts/preflight.py --project . --format json > acima-baseline.json

# 3. turn the baseline into scoped waivers, then replace "unassigned" with real owners
python3 skills/acima-adoption/scripts/preflight.py --project . --write-waivers .acima/waivers.json

# 4. gate CI on "no new findings", then reduce the count one PR at a time
```

Do not fix the architecture first. Freeze the measurement first; the number is what makes the
programme discussable.

### Step 4 — Execute one slice

Pick the slice by the migration order in `docs/standard/09-adoption.md` §9.2: contracts extraction
for the two most-coupled modules, then cycle breaking, then immutability, then persistence
ownership. **Never start with persistence.** It needs a data migration and it is where adoption
programmes die.

One slice means one merged pull request that changes one boundary and leaves the gate green.

### Step 5 — Verify, with the run artefact

```bash
# the enforcer for the target language, from this repository
python3 examples/python/tools/acima_arch.py      --root <target> --format json
node     examples/typescript/tools/acima-arch.mjs --root <target> --format json
(cd examples/go && go run ./tools/archtest --root <absolute-target> --format json)
dotnet run --project examples/dotnet/tools/Acima.ArchTests -- --root <target> --format json
```

Then, from the target repository, run its own wired command (the one CI runs) and keep the JSON.
Validate before reporting anything:

1. exit code is 0 or 1 (2 or a crash is a tool failure, not architecture debt);
2. the JSON parses, and its byte size matches the file you kept — never read a large report through
   a fixed-size pipe or a terminal capture that can truncate it;
3. `sourceFiles` is greater than zero and matches the expected scope;
4. `execution` names every catalog rule, and every `executed: false` has a reason;
5. the report's standard, level and catalog identity are the ones you intended;
6. any `classified` entries have a rule, path, owner and reason — they are reported decisions, not
   suppressed findings;
7. the expected units were discovered (a run that classifies nothing is a false pass — `ACIMA-G005`
   should have fired);
8. if any rule required by the declared level is `executed: false`, report **PARTIAL ASSESSMENT** and
   name the manual/native evidence needed; a zero error count does not make it full conformance.

A zero-finding result additionally requires controlled violations. The prover runs both by
default:

```bash
python3 skills/acima-adoption/scripts/inject_violation.py --project <target> --format json
```

`ACIMA-L001` copies the target to a disposable directory, injects one language-appropriate
forbidden dependency, and requires that rule at that exact path. `ACIMA-D001` builds a disposable
two-unit fixture where one implementation unit imports another and requires the cross-module
finding; it does not depend on the target's unit map, so single-module repositories are proven
too. Use `--rule L001` or `--rule D001` to run one. The prover never writes to the working copy,
and it withholds injection details unless `--reveal` is passed, so an assessment agent can run it
before being told what was injected. Exit `1` means `not proven`; if the check cannot run, report
`not proven`.

### Step 6 — Hand off

- Fill the conformance self-certification in `docs/standard/08-conformance.md` §8.5.
- Deliver the [communication plan](references/40-communication.md) — kickoff, first finding,
  first waiver negotiation, and the recurring update.
- Run the [newcomer onboarding](references/30-adoption-for-newcomers.md) for anyone who has never
  seen contract-based modular architecture. Assume zero background; do not assume they will read
  the spec.

## Stop conditions

Stop and ask the user when any of these is true:

| Condition | Why |
|---|---|
| `preflight.py` exits 1 | the skill is not calibrated, or the target is not what it appears to be |
| The target has no named owner for exceptions | waivers would become anonymous, which `G001` forbids in spirit |
| Two modules disagree about who owns a concept | this is org design; no rule fixes it (`09-adoption.md` §9.4) |
| A rule produces waivers for legitimate designs repeatedly | the rule may be wrong — amend the standard, do not bend the code |
| The target language is Java | the profile exists, the reference implementation does not; say so |
| `acima.config.json.mode` is `service-topology`, or `acima.topology.json` exists | this skill revision has no supported service-profile workflow; do not force the base unit model |
| A library profile is requested without publishable evidence | the declaration would be an undocumented exemption (`G001` in spirit) |
| A library profile is requested for Python or Go | there is no reference implementation for that profile; do not silently treat public API as a leak |
| A unit map hides a dependency that the manifests prove exists | remap the boundary or disclose the finding; never report clean |
| The requested change would require editing the catalog | that is a standards change, not an adoption task |

## Reference map

| File | Use it for |
|---|---|
| [00-preflight.md](references/00-preflight.md) | every check ID, what it means, how to fix it |
| [10-greenfield.md](references/10-greenfield.md) | day-zero sequence and file skeletons |
| [20-brownfield.md](references/20-brownfield.md) | ratchet, seams, extraction recipe, sequencing |
| [30-adoption-for-newcomers.md](references/30-adoption-for-newcomers.md) | teaching people with no background |
| [40-communication.md](references/40-communication.md) | what to say to teammates, managers, skeptics |
| [50-outcomes.md](references/50-outcomes.md) | metrics, reporting, definition of done per level |
| [60-troubleshooting.md](references/60-troubleshooting.md) | false positives, waiver storms, monorepos, gaps |
| [glossary.md](references/glossary.md) | plain-language definitions to reuse verbatim |

## Maintaining this skill

The manifest pins the catalog hash, the standard version, the portable rule set and the enforcer
paths. When the standard changes:

1. run `preflight.py`; `SKL-002`, `SKL-003` or `SKL-006` will fail;
2. read the changed rules and the affected references;
3. update the manifest hash and `skill-version`, and the references that describe the change;
4. re-run `preflight.py --deep` so the examples are proven, not assumed;
5. commit the skill change separately from any product change.

A skill that silently follows a moving standard is worse than no skill: it produces confident,
outdated advice.
