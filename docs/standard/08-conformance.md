# 8. Conformance

Conformance is a claim a repository makes about itself, and it is only credible if it is machine-checked.

## 8.1 The levels

| Level | Name | Requires | Typical adoption moment |
|---|---|---|---|
| **L1** | Structural | `D001`–`D009`, `L001`–`L004`, `G001`, `G002`, `G005` | you have modules and want the graph to stay acyclic |
| **L2** | Immutable | L1 + `C001`–`C007`, `G003`, `G004` | contracts are consumed by another team |
| **L3** | Autonomous | L2 + `A001`–`A004` | modules have their own data and could be extracted |

`L004` and `C007` are `warning`-severity: at their level they must be *reported*, and a repository at
that level must show zero unwaived `error` findings. Warnings are expected to trend down; they are not
a pass/fail gate. Every other rule above is an `error`.

## 8.2 Declaring conformance

```json
{ "standard": "1.0.0", "mode": "base", "language": "go", "level": "L2" }
```

in `acima.config.json`. The declared level selects the rule subset that is executed and enforced.
`mode` selects `base` or `service-topology`; a `service-topology` claim also requires
`acima.topology.json` and the profile run in §8.8. Mode/base-profile precedence is defined in
[chapter 11](11-service-topology.md#1112-relationship-to-base-acima).

A repository MAY declare a level and run additional rules above it; it MUST NOT declare a level and
waive rules required by that level as a matter of routine. Waivers are for exceptions, and their count
is reported.

## 8.3 The checklist

### L1 — Structural

- [ ] Every module declared in `acima.config.json`; no unclassified production source (`G005`).
- [ ] Every module has a contracts unit; no module publishes implementation types (`D009`, `L003`).
- [ ] No contracts unit references a third-party package, another contracts unit, or any
      implementation (`D002`, `D003`, `D004`).
- [ ] No contracts unit references the host (`D006`).
- [ ] No implementation references another implementation (`D001`).
- [ ] The module graph is acyclic (`D005`).
- [ ] No reference leaks an implementation transitively (`D008`).
- [ ] If a legacy shared kernel is present, it references nothing (`D007`); new contracts do not reference it.
- [ ] Domain and application code do not reference infrastructure (`L001`).
- [ ] Contracts expose no framework or transport types (`L002`).
- [ ] Modules receive peers through construction, not through a locator (`L004`).
- [ ] Every waiver has owner, reason, expiry and review date (`G001`); none are expired (`G002`).

### L2 — Immutable

Everything in L1, plus:

- [ ] No contract type has setters or mutable public fields (`C001`).
- [ ] No contract exposes a mutable collection (`C002`).
- [ ] Contracts contain no business behaviour, IO or orchestration (`C003`).
- [ ] Contracts read no clock, random source, id generator or static mutable state (`C004`).
- [ ] Contracts expose no persistence types (`C005`).
- [ ] Contracts are explicitly typed — no `object`/`dynamic`/`any`/bare maps (`C006`).
- [ ] Contract types are constructible in one step, with required state obvious (`C007`, warning).
- [ ] Every public contract type is documented (`G003`, warning).
- [ ] The contracts API baseline matches the reviewed baseline (`G004`).

### L3 — Autonomous

Everything in L2, plus:

- [ ] No module reads or writes another module's schema, tables or store (`A001`).
- [ ] No module reads another module's configuration keys or secrets (`A002`).
- [ ] No cross-module communication through shared mutable statics or globals (`A003`).
- [ ] Consumers pin contracts versions, never implementation versions (`A004`).
- [ ] Dependency budgets in `acima.config.json` are respected.

## 8.4 What counts as evidence

A conformance claim is credible when all five exist:

1. **the configuration** — `acima.config.json` declaring units and level;
2. **the run** — an enforcer execution on the current commit, at the declared level, zero unwaived
   errors; for a **full conformance claim**, every rule required by that level must also be executed,
   with a recorded manual/native evidence artifact where no automated enforcer exists;
3. **the artefact** — the JSON findings file from that run, retained with the build;
4. **the waiver report** — count, owners, soonest expiry, expired count;
5. **the pipeline** — the gate runs on every pull request and blocks merges on `error`.

Anything less is documentation, not conformance. In particular: *architecture tests that pass because
they discovered nothing* are the most common false claim, which is why `G005` exists and why the
enforcers in this repository fail when a suite finds zero files.

## 8.5 Self-certification template

```markdown
## ACIMA conformance

- Repository: <name>
- Standard: 1.0.0
- Declared level: L2
- Profile: <none | service-topology, automated, n/12>
- Language profile: dotnet
- Enforcer: tests/Acima.ArchTests
- CI gate: <link to the required check>

| Check | Result |
|---|---|
| Rules executed | <executed> of <required> automated; manual/native evidence: <rules> |
| Claim | <FULL CONFORMANCE | PARTIAL ASSESSMENT> |
| Unwaived errors | 0 |
| Warnings | 3 (`C007` ×1, `G003` ×2) |
| Waivers | 1 active, 0 expired, 1 expiring within 90 days |
| Findings artefact | build #1234 / `acima.json` |
| Last verified commit | `abc1234` |
```

The count is derived from `rules.json`; never copy a fixed number. At L2 the catalog requires 25
rules. The reference portable enforcers execute 21 of those and report `L004`, `C003`, `C007` and
`G004` as not executed; without manual/native evidence for those four, the correct claim is
`PARTIAL ASSESSMENT`, not `FULL CONFORMANCE`.

## 8.6 Partial conformance is not conformance

If a rule category cannot be executed because of a language limitation (for example, Python has no
package boundaries), the language profile must say so and the enforcer must implement the rule
dynamically. "The language does not support it" is a reason to run the test, not a reason to skip it —
it is exactly the case where nothing else will catch the violation.

If an enforcer genuinely cannot evaluate a rule, it MUST report the rule as `info` with
`"executed": false` in the findings artefact rather than omitting it. A **partial assessment** lists
the unenforced rules explicitly and records the missing manual/native evidence; it MUST NOT be
called conformance. A full conformance claim requires execution or recorded manual/native evidence
for every required rule. A standard that hides what it does not check is worse than no standard.

## 8.7 Conformance and reality

A repository that fails a rule is not a bad repository. It is a repository that has chosen which
problem to fix next. The levels exist so that:

- the *first* day of adoption can be L1 with an honest waiver file;
- every subsequent change is measured against the declared level;
- the ratchet only turns one way — see [Adoption](09-adoption.md).

## 8.8 Service topology profile

The service topology profile in chapter 11 is the default for new systems. Its twelve requirements,
`ST-1`–`ST-12`, are implemented as `ACIMA-S001`–`ACIMA-S012` by
[`conformance/topology.py`](../../conformance/topology.py). The runner reads `acima.topology.json`,
scans the declared projects and sources, and is exercised by `conformance/test_topology.py` against a
clean fixture and one that violates every item. A new repository reports it as:

```markdown
- Mode: service-topology
- Base: L3 (automated subset + recorded manual evidence)
- Profile: service-topology, automated, 12/12 on <date>
- Evidence: acima.topology.json and the `conformance/topology.py` JSON artifact
```

A claim that says `service-topology` without the JSON run is overstating what the build enforces. The
S rules are profile rules outside the base catalog; they do not change the L1–L3 rule set. The runner
checks declared evidence — the one-sentence responsibility, business-rule traceability, 100% coverage
reports and the shared UI/API workflow tokens — so the manifest cannot silently drift from the tree.
It does not prove semantic completeness: a team can still declare an incomplete rule list or a
workflow that is not the product's real one. The same rule as §8.6 applies: list what is not checked
rather than hiding it.

The evidence is the same as §8.4: the topology configuration, the run, the JSON artefact and the CI
gate. The profile runner is invoked by `conformance/run.py`; a repository that adopts the profile adds
that command to the same pull-request job as its language enforcer.
