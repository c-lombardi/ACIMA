# Outcomes and metrics

An adoption without defined outcomes becomes an architecture club. Define what "working" means
before the first commit, in terms the organisation already uses, and report it on a cadence that
survives a busy quarter.

## Outcomes by phase

| Phase | Outcome | Evidence | Typical duration |
|---|---|---|---|
| Calibrated | the skill matches the standard at this commit | preflight `SKL-*` all pass | minutes |
| Classified | the target's mode and language are known | preflight report attached to the plan | an hour |
| Planned | unit map, owners, dates, metrics agreed | ADR-0001 + adoption plan, reviewed | a week |
| Baselined | existing findings are measured and owned | baseline JSON + waivers with named owners | a week |
| Gated | CI blocks new `error` findings | a required check, seen failing then passing | a week |
| First slice | one boundary change merged | merged PR, count unchanged or lower | 1–2 weeks |
| Ratcheting | count falls every month | monthly one-pager, same query each time | a quarter |
| Autonomous | modules could be extracted without a rewrite | L3 clean, persistence and config isolated | quarters |

## Metrics that mean something

Two families. Report both; either alone is gameable.

**Architecture metrics (leading):**

| Metric | Definition | Target |
|---|---|---|
| Unwaived errors | findings at the declared level, minus waivers | zero |
| Finding count | total findings at the declared level | monotone non-increasing per month |
| Waiver age | median days since `reviewedOn` | < 45 |
| Unowned waivers | `owner == unassigned` | zero |
| Coverage | source files inside a declared unit | 100% |
| Gate liveness | a deliberately broken branch fails CI | verified quarterly |

**Delivery metrics (lagging, the ones managers already track):**

| Metric | Why it matters here |
|---|---|
| Lead time for changes | the boundary should reduce cross-team surprises, not add ceremony |
| Change failure rate | `D001`/`A001` violations are a common cause of coupled failures |
| Time to first PR for a new joiner | contracts make the safe surface discoverable |
| Incidents caused by cross-module data access | the thing `A001` exists to prevent |

Do not claim a delivery improvement without a before/after measurement. "It feels faster" is not
a metric, and an architecture programme that overclaims loses the next budget cycle.

## Anti-metrics

| Anti-metric | Why it is harmful |
|---|---|
| Rules executed | 55 rules recorded as executed over zero discovered files is a false pass |
| Lines of architecture documentation | documentation is not enforcement |
| Percentage of "compliant" modules before a baseline exists | there is no denominator; the number is invented |
| Waivers closed | closing a waiver by deleting the code that needed it is good; by bulk-renewal is not |
| Level reached | a level with unowned waivers is a label, not a state |

## Definition of done per level

Use the checklists in `docs/standard/08-conformance.md` §8.3 as the source of truth. The
programme-level summary:

**L1 — Structural.** The unit map covers all production source, the graph is acyclic, contracts
are dependency-free, and every exception has an owner and an expiry. *Evidence:* clean L1 run +
waiver report.

**L2 — Immutable.** Contracts are frozen data with no behaviour, no framework types, no mutable
collections, and the reviewed API baseline matches. *Evidence:* L2 automated run plus manual
artifacts for `C003`, `C007`, `C008` and `G004`; the API baseline diff is an artifact, not a green
run.

**L3 — Autonomous.** Each module owns its persistence, configuration and externally visible effects;
modules do not share mutable statics; consumers pin contracts versions; retry, duplicate, consistency
and recovery semantics have owners where they apply. *Evidence:* L3 automated run plus manual
artifacts for `A002`, `A004` and `A010`–`A013`, a schema ownership map, a configuration namespace map,
an effect/recovery review, and runtime grant evidence where the claim is operational autonomy.

A level is claimed per repository, per commit. It expires when the commit changes; the CI artefact
is what keeps it current.

## The monthly one-pager

Same five lines every month, so month-over-month comparison is honest:

```markdown
## ACIMA status — <month>
Level: L1 (declared) · Units: 7 · Gate: required
Findings: 214 → 198 (D001 41→33, C001 22→12, D005 3→3)
Waivers: 31 active · 4 expiring in 30 days · 0 unowned
Merged: <slice> (#PR) · Next: <slice> · Risk: <blocker with owner>
```

If the count rose, explain the cause in the same line. A metric that only ever improves is a
metric nobody believes.

## Review cadence

| Cadence | Question | Decision |
|---|---|---|
| Weekly | did the gate fire correctly? | fix false positives within the week |
| Monthly | is the count falling and are owners real? | reassign, renew, or escalate |
| Quarterly | should the level rise, or should a rule change? | raise, hold, or amend the standard |
| Annually | is the enforcer still cheaper than the defects it prevents? | keep, simplify, or withdraw rules |

## When to stop

Stop adding discipline when (`09-adoption.md` §9.7):

- the remaining findings are in code scheduled for deletion;
- a rule repeatedly produces waivers for legitimate designs — amend the rule;
- the enforcer has become a product with its own roadmap.

Stopping deliberately is a success condition. An architecture programme with no exit criteria
becomes a tax with a standup.

## Self-certification

Use the template in `docs/standard/08-conformance.md` §8.5. It asks for the run, the artefact, the
waiver report, the pipeline and the last verified commit. The executed count must be derived from
the catalog; the reference portable enforcers do not execute `L004`, `C003`, `C007`, `C008`, `G004`,
`A002`, `A004`, `A010`–`A013` or `N003`. If any required line is empty, or a required rule is
`executed:false`, the
repository is a **partial assessment**, not fully conformant. That is a perfectly good thing to be,
as long as it is labelled accurately.
