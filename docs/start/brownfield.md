# Brownfield adoption

Most adopters already have a running system, years of history, and no appetite for a
rewrite. ACIMA is designed for that starting point: **measure first, gate second, fix one
boundary at a time**.

The goal of the first phase is not a clean architecture. It is an honest baseline that the
team can keep discussing.

**Assessment is read-only.** Nothing below that creates a file happens until the owner approves a
proposal naming the paths and scope. “Adopt ACIMA” starts the assessment and proposal; it does not
pre-approve unseen configuration, baseline, waivers or CI.

The six phases below elaborate the five-phase consent workflow in the
[adoption skill](../../skills/acima-adoption/SKILL.md): Phase 1 is assessment, Phase 2 is proposal,
Phase 3 is explicit authorization, Phases 4–6 are the approved implementation, and verification and
handoff close each one. Only the approved paths are created; plans and communication documents are
optional.

Adoption does not replace the architecture the team already chose. Clean Architecture, Hexagonal,
DDD, a modular monolith and microservices all remain valid shapes, but ACIMA defines its own
portable boundary requirements; compatibility is assessed against them, not assumed from the shape.
A family may satisfy some requirements and need limited adaptation for others; a fundamental
conflict is not a reason to restructure silently. Read
[Architecture compatibility](../guides/architecture-families.md) before proposing units, and do not
present ACIMA as a reason to restructure.

## Phase 1 — Discovery

Run only read-only commands:

```bash
export TARGET=/path/to/repository
python3 tools/acima.py inspect --root "$TARGET"
python3 skills/acima-adoption/scripts/preflight.py --project "$TARGET" --format text
```

`inspect` reports the target language, existing configuration, source counts, declared
units and enforcer availability. The preflight classifies the target as `greenfield`,
`brownfield` or `adopting` and checks that the skill is still calibrated to this catalog.

If the target has no `acima.config.json`, do not run `analyze` yet. The enforcer cannot
claim a pass without declared units; it will return a tool failure, not an architecture
finding.

## Phase 2 — Proposal

Before creating a unit map, present the proposed modules, exact paths, status of each artifact,
owners and tradeoffs. The proposal template and approval question are in
[the adoption skill](../../skills/acima-adoption/assets/adoption-proposal.md).

## Phase 3 — Explicit authorization and approved scope

Only after approval for these paths, generate a first draft when the target has no config:

```bash
python3 skills/acima-adoption/scripts/preflight.py --project "$TARGET" \
  --write-draft acima.config.json --format text
```

Review it before committing. The draft is heuristic: it proposes units from directories
or projects, not from domain ownership. Rename units to domain concepts, merge accidental
splits, and decide who owns every module. Do not measure or gate against an unreviewed map.

If baseline and waivers are in the approved scope, write them:

```bash
python3 skills/acima-adoption/scripts/preflight.py --project "$TARGET" \
  --write-waivers .acima/waivers.json --format text
```

The generated owners are `unassigned`. Replace every one with a person or team, and give
each waiver a real reason and review date. Do not bulk-renew waivers.

Do not invent a delivery estimate. Scope is expressed by evidence: modules touched, files
involved, finding counts, schema migrations and the number of consumers of a boundary.
Time estimates remain an engineering judgement made by the team.

## Phase 4 — Measure after the approved map

With a reviewed config in place, measure the current state and keep the artefact:

```bash
python3 tools/acima.py analyze --root "$TARGET" --format json > acima-baseline.json
python3 tools/acima.py report  --root "$TARGET" --format markdown > acima-report.md
```

The report separates:

- findings produced by the rules that actually ran;
- warnings;
- rules that were **not evaluated** by the portable enforcer;
- the limits of the evidence.

A missing detection is not a pass. If the report lists `ACIMA-A002` as not evaluated,
the repository still has to review configuration ownership manually.

### Discovery checklist

| Check | How to answer it |
|---|---|
| Projects and modules | `acima inspect`; review the proposed unit map. |
| Existing dependencies | The enforcer's `D` findings and the project graph. |
| Circular dependencies | `ACIMA-D005` findings, including the cycle path. |
| Cross-module implementation references | `ACIMA-D001`, `D008`, `D009`. |
| Shared contracts | `ACIMA-D003`; decide which value types are local. |
| Mutable contracts | `ACIMA-C001`, `C002`. |
| Shared persistence | `ACIMA-A001`; inspect SQL and schema ownership. |
| Configuration and values | `ACIMA-A002` is manual; `A005`/`A006` are automated candidates in Python/TypeScript and manual elsewhere. |
| Composition and injection | `ACIMA-D013`/`D014` are automated candidates in Python/TypeScript; inspect scans, conventions and property injection manually elsewhere. |
| Functional capture | `ACIMA-D015`/`D016` are automated candidates in Python/TypeScript; inspect closures, callbacks and `bind`/`partial` manually elsewhere. |
| Effects and consistency | `ACIMA-C008` and `A010`–`A013` are manual everywhere: name the effect owners, transactions, retries, duplicate handling, truthful outcomes and recovery evidence where they apply. |
| Existing architecture tests | `inspect` plus a source review. |
| Existing exceptions | The waiver file; `G001`, `G002`. |

## Phase 5 — Incremental enforcement

CI and source changes are separate approvals. Start at L1 unless the repository already has a stronger baseline. The order matters:

| Order | First slice | Why |
|---|---|---|
| 1 | Extract contracts for the two most-coupled modules | unlocks the rest of the work |
| 2 | Break cycles (`D005`) | cycles make every later change harder |
| 3 | Freeze contracts (`C001`, `C002`) | mechanical and immediately valuable |
| 4 | Establish persistence ownership (`A001`) | expensive; needs schema work |
| 5 | Configuration, values and statics (`A002`, `A005`, `A006`, `A003`) | usually a small number of hot spots |
| 6 | Explicit composition and injection (`D013`, `D014`) | needs the host; reduces hidden startup behaviour |
| 7 | Functional capture (`D015`, `D016`) | usually follows once the host exposes the dependency graph |
| 8 | Effect review (`C008`, `A010`–`A013`) | name critical effects, duplicate and recovery semantics before adding retries or consumers |

Gate CI on **no new findings** at the declared level. Existing findings are allowed only
through the owned, scoped, expiring waiver file. The first merged slice should change one
boundary and leave the gate green.

For the target repository, wire the reference enforcer for its language into the target's
CI. Do not use `acima verify` as the target gate: that command verifies this ACIMA
repository and its examples.

## Phase 6 — Continuous governance

Every pull request should produce:

```text
configuration + enforcer run + findings artefact + waiver report
```

The gate blocks new `error` findings. Warnings are reported, not silently promoted to
passes. A clean run is still not a conformance certificate if a rule was not evaluated.

Review the waiver file monthly. Watch the age of exceptions, not just their count. An
expired waiver is a finding (`G002`); renewal is an individual decision.

## What not to do

- Do not rewrite the application to satisfy the standard.
- Do not declare L3 on day one because the target is small; declare what the evidence supports.
- Do not edit `acima.config.json`, expected findings or waiver dates just to make a run pass.
- Do not rename every project in one PR. Rename the project you are already changing.
- Do not treat a skipped or unevaluated rule as compliant.
- Do not add a retry, transaction, idempotency key or cancellation token merely to satisfy an effect
  checklist; decide applicability and ownership first.

## Exit criteria for an approved first adoption slice

A partial adoption uses only its approved subset and is not described as full adoption.

- [ ] the target has a reviewed `acima.config.json` and an owned waiver file;
- [ ] the enforcer runs in the target's CI on every pull request;
- [ ] one boundary change is merged;
- [ ] the baseline artefact and report are retained;
- [ ] every finding not fixed has an owner, a reason and an expiry;
- [ ] the team can run the gate without the architecture owner present.

Next: [Service topology](../standard/11-service-topology.md) if the target is moving
toward multiple services, and [Capability status](../status.md) before making a
conformance claim.
