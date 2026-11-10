# 8. Conformance

Conformance is a claim a repository makes about itself, and it is only credible if it is machine-checked.

## 8.1 The levels

| Level | Name | Requires | Typical adoption moment |
|---|---|---|---|
| **L1** | Structural | `D001`–`D016`, `L001`–`L007`, `G001`, `G002`, `G005`, `G006` | you have modules and want the graph to stay acyclic |
| **L2** | Immutable | L1 + `C001`–`C008`, `G003`, `G004` | contracts are consumed by another team |
| **L3** | Autonomous | L2 + `A001`–`A015` | modules have their own data and effects, and could be extracted |

`warning`-severity rules must be *reported* at their level, and a repository at that level must show
zero unwaived `error` findings. Warnings are expected to trend down; they are not a pass/fail gate.
The catalog is authoritative for each rule's severity.

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
- [ ] Application-owned components are registered and constructed explicitly at the composition
      boundary; no scan, convention or dynamic discovery hides the graph (`D013`, warning).
- [ ] Dependencies arrive through constructors or composition functions, not property/field
      injection or post-construction assignment (`D014`, warning).
- [ ] Closures, callbacks and returned functions do not capture application dependencies from a
      module or enclosing local; pure closures remain allowed (`D015`, warning).
- [ ] Partial application or method binding of an application dependency occurs at the composition
      boundary, not inside a component (`D016`, warning).
- [ ] Every required construction and invocation input is supplied explicitly; no dependency arrives
      through an optional parameter or a default (`D011`, `D012`, warning).
- [ ] Every integration library is declared in `externals` with one adapter and one port, and only
      that adapter imports it (`L005`, `L006`).
- [ ] No vendor type appears outside its adapter and no port carries a vendor shape (`L007`, `D010`).
- [ ] Every manifest package has a reviewed `externals` entry, and none is past its review date
      (`G006`).
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
- [ ] Boundary operations make their business behaviour, material preconditions, failure semantics and
      observable effects visible (`C008`).
- [ ] Every public contract type is documented (`G003`, warning).
- [ ] The contracts API baseline matches the reviewed baseline (`G004`).

### L3 — Autonomous

Everything in L2, plus:

- [ ] No module reads or writes another module's schema, tables or store (`A001`).
- [ ] No module reads another module's configuration keys or secrets (`A002`).
- [ ] Components receive configuration from the composition boundary; no implementation or adapter
      reads ambient environment or global configuration (`A005`, warning).
- [ ] Operational timeouts, retries, limits, rates, batch sizes and retention values have a named
      owner or an explicit configuration source (`A006`, warning).
- [ ] No cross-module communication through shared mutable statics or globals (`A003`).
- [ ] Consumers pin contracts versions, never implementation versions (`A004`).
- [ ] Every externally visible effect has one owner and an execution boundary; callers do not perform
      a provider's effect (`A010`).
- [ ] Retry, duplicate, consistency, partial-completion and cancellation semantics are explicit where
      the operation's design makes them applicable (`A011`).
- [ ] Effect outcomes distinguish success, failure, unknown and partial completion truthfully
      (`A012`).
- [ ] Logging, metrics and telemetry observe behaviour without concealing or altering it, and the
      diagnostic, business-event and audit-record purposes are distinguishable (`A014`).
- [ ] Every multi-step state change and transaction names one owner and a declared consistency
      guarantee, with recovery, compensation or reconciliation where they apply (`A015`).
- [ ] Critical effects have evidence proportionate to their failure impact (`A013`, warning).
- [ ] Dependency budgets in `acima.config.json` are respected.

## 8.4 What counts as evidence

A conformance claim is credible when all six exist:

1. **the configuration** — `acima.config.json` declaring units, level and mode;
2. **the run** — an enforcer execution on the current commit, at the declared level, zero unwaived
   errors;
3. **the manual evidence** — for a **full conformance claim**, every rule required by that level
   that the run reports as `executed: false` must have a repository-scoped entry in
   `.acima/manual-evidence.json`;
4. **the artefact** — the JSON findings file from that run, retained with the build;
5. **the waiver report** — count, owners, soonest expiry, expired count;
6. **the pipeline** — the gate runs on every pull request and blocks merges on `error`.

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
- Manual evidence: `.acima/manual-evidence.json` (<n> accepted entries)

| Check | Result |
|---|---|
| Rules executed | <executed> of <required> automated; manual evidence: <rules> |
| Claim | <FULL CONFORMANCE | PARTIAL ASSESSMENT> |
| Claim gate | `acima claim --require full` exits 0 at the current commit |
| Claim provenance | repository, commit, standard, catalog/config hashes, enforcer version, source inventory |
| Unwaived errors | 0 |
| Warnings | 3 (`C007` ×1, `G003` ×2) |
| Waivers | 1 active, 0 expired, 1 expiring within 90 days |
| Findings artefact | build #1234 / `acima.json` |
| Last verified commit | `abc1234` |
```

A claim is evidence about one repository state. `FULL CONFORMANCE` at an older commit is historical,
not current; a changed catalog, configuration, baseline or source inventory requires fresh
measurement. Missing provenance — repository, commit, catalog hash, configuration hash, enforcer
version or source inventory — means currentness cannot be established and must not be assumed.
Uncommitted source or configuration changes cannot be represented by a committed run. Historical
reports stay readable and must not be deleted, but only a claim whose provenance matches the current
checkout may be called current conformance.

The count is derived from `rules.json`; never copy a fixed number. At L2 the catalog requires 37
rules. The reference portable enforcers execute 32 of those and report `L004`, `C003`, `C007`,
`C008` and `G004` as not executed; without manual evidence for those five, the correct claim is
`PARTIAL ASSESSMENT`, not `FULL CONFORMANCE`. At L3 the catalog requires 55 rules; 41 execute and
the fourteen manual rules are `L004`, `C003`, `C007`, `C008`, `A002`, `A004`, `A010`–`A015`, `N003`
and `G004`. The five
third-party tier rules, the two explicit-input rules, the two value rules, the two composition
rules, the two functional-capture rules, the three lifecycle rules and the two naming rules
(`N001`–`N002`) execute in the Python and TypeScript enforcers; a Go or .NET run reports those
eighteen `executed: false`, so that repository needs manual evidence for them or the scoped statement
in §8.10. `N003` is one of the fourteen manual rules, not an automated gap.

The claim class is computed, not chosen by the author:

```bash
python3 tools/acima.py claim --report acima.json \
  --evidence .acima/manual-evidence.json --level L2 --require full
```

`claim` exits `0` only when the requested class is satisfied **and** the claim is current. It exits
`1` when a full claim is requested but the run is only a partial assessment or its provenance does
not match the current repository state, and `2` when the run or evidence document is invalid. The
same model is available in `acima report --format json` under the `claim` key.

## 8.6 Partial conformance is not conformance

If a rule category cannot be executed because of a language limitation (for example, Python has no
package boundaries), the language profile must say so and the enforcer must implement the rule
dynamically. "The language does not support it" is a reason to run the test, not a reason to skip it —
it is exactly the case where nothing else will catch the violation.

If an enforcer genuinely cannot evaluate a rule, it MUST report the rule as `info` with
`"executed": false` in the findings artefact rather than omitting it. A **partial assessment** lists
the unenforced rules explicitly and records the missing manual evidence; it MUST NOT be called
conformance. A full conformance claim requires execution or accepted repository-scoped manual
evidence for every required rule. A standard that hides what it does not check is worse than no
standard.

The claim classes are exclusive:

| Class | Conditions | May be called conformance? |
|---|---|---|
| `FULL CONFORMANCE` | every required rule executed or covered by accepted manual evidence; zero unwaived error findings; provenance matches the current repository, commit, catalog, configuration and source inventory | yes, for that state |
| `PARTIAL ASSESSMENT` | a complete, valid run, but at least one required rule has no execution or accepted manual evidence | no |

`FULL CONFORMANCE` describes the measured state, not the repository forever: a later commit, a
changed catalog or configuration, a changed baseline, a modified working tree, or missing provenance
makes it historical, stale or incomplete evidence. Historical claims remain available; they are
never reported as current.

A catalog-manual rule reported as `executed: true` does not count as executed. The catalog is
authoritative about how a rule is decided, so a run that claims to execute a manual rule has
misstated its execution map; the rule still needs repository-scoped manual evidence. This is what
prevents an unsupported check from passing silently, and it is why a clean automated run cannot
establish full conformance on its own when required evidence is missing. An execution map that omits
a required rule is not partial — it is `INVALID ASSESSMENT` and exits `2`, because the run did not
account for every obligation the declared level requires.
| `INVALID ASSESSMENT` | missing execution map, missing level, malformed output or unreadable evidence | no; exit `2` |

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

## 8.9 Manual evidence for full claims

`.acima/manual-evidence.json` is version-controlled with the config and waivers. It records the
review that replaces an automated rule, not a promise to review later:

```json
{
  "standard": "1.0.0-draft.1",
  "evidence": [
    {
      "rule": "ACIMA-C003",
      "scope": "repository",
      "owner": "team-contracts",
      "reviewer": "architecture-review",
      "method": "review",
      "artifact": "docs/reviews/C003-contract-behaviour.md",
      "reviewedOn": "2026-11-08",
      "expires": "2027-05-08",
      "result": "pass"
    }
  ]
}
```

A full claim requires one accepted entry for every required rule that did not execute. An entry is
accepted only when:

- `rule` is a catalog id required by the declared level and marked `automation: manual` in the
  catalog (or reported `executed: false` by the run);
- `scope` is `repository` — unit- or path-scoped evidence cannot certify the whole repository;
- `owner`, `reviewer`, `method` and `artifact` are non-empty;
- `reviewedOn` is an ISO date not in the future and `expires` is an ISO date not in the past;
- `artifact` exists at that path and contains the recorded review;
- `result` is `pass`.

Expired, missing or malformed evidence makes the claim `PARTIAL ASSESSMENT`; accepted evidence still
only supports a claim whose repository, commit, standard, catalog and configuration match the current
checkout. Evidence problems do not make the run
invalid. A missing execution map, an unknown level or malformed JSON is `INVALID ASSESSMENT` and exits
`2`. The reference enforcers continue to report the fourteen manual rules as `executed: false`; the evidence file
is how a repository records the review the portable tool cannot perform.

## 8.10 Third-party governance and the swap drill

The third-party gate is two artefacts and one experiment:

1. **The declaration** — an `externals` entry for every manifest package, each with a tier, an owner,
   a reason, a review date and an expiry. Chapters 4 §4.10 and 7 §7.4 define the shape; `G006` fails
   the run when a package is missing or an entry has expired.
2. **The seam** — for `tier: integration`, exactly one adapter unit and one port unit (`L006`). Only
   the adapter imports the vendor (`L005`); no vendor type appears outside it (`L007`); the port names
   nothing but its own types (`D010`).
3. **The swap drill** — the only evidence that the seam is real rather than declared.

### The swap drill

The drill answers one question: *if the vendor disappeared, what would have to change?* The answer
must be "the adapter and the composition root", never "the application".

```bash
python3 conformance/swap_drill.py --project conformance/fixtures/third-party/python
```

It copies the fixture to a disposable directory and then:

1. deletes every directory owned by a declared adapter unit;
2. writes a stub adapter that implements the port with no vendor;
3. resolves every import of every **application** unit (`implementation`, `contracts`, `port`)
   against the remaining tree and the language core;
4. fails when an application file imports a declared vendor, a removed adapter, or an unresolvable
   third-party package, and fails when it never references the port at all.

The last check is the one people skip: an application that compiles without the adapter because it
never used the port has no seam, it has an unused declaration.

### What a passing drill proves, and what it does not

It proves the application units compile against the port with the vendor removed. It does **not**
prove the adapter is correct, that the port's vocabulary is good, or that the vendor is replaceable in
practice (data migration, wire formats and behaviour differences are not architectural). Record the
drill in the conformance claim next to the run artefact:

```markdown
- Third-party tiers: <n> declared, <m> integration, `G006` clean
- Swap drill: `conformance/swap_drill.py --project <fixture>` passed on <date>
```

The drill is implemented for Python fixtures in this revision. TypeScript fixtures are covered by
the same enforcer rules but not yet by an executable drill; say so rather than claiming both.
