---
name: acima-adoption
description: Adopt, audit, and enforce the ACIMA architecture standard in a greenfield or brownfield repository. Use when the user asks to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, run an architecture audit against the ACIMA rule catalog, migrate a shared "Common" project, or onboard a team with no prior exposure to contract-based modular architecture. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.0.0-draft.1"
  skill-version: "1.0.2"
  catalog-sha256: "125a1a3fc2096a25cf8a849aa701d571e73c6aead977c6f012cf4f60c4b1fe77"
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

A repository is conformant at a level only when the run artefact shows **zero unwaived errors**
at that level on the current commit. Anything less is a plan, and you must call it a plan.

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
6. **Never start brownfield adoption at L3.** Start at L1, ratchet upward.
7. **Never rewrite the target to satisfy the standard.** Change the smallest boundary, then measure.
8. **Never apply ACIMA to a codebase whose owner has not asked for it.** This is a governance
   change, not a refactor.

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
Check three things: exit code, unwaived `error` count, and that the enforcer discovered the
expected units (a run that classifies nothing is a false pass — `ACIMA-G005` should have fired).

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
