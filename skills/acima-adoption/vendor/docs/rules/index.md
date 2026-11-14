# Rule catalog

56 rules. Six categories. Every rule has a permanent id, a severity, a conformance level and a
detection strategy. Python, TypeScript, Go and .NET each have a reference enforcer; Java is a
documented profile only and has no reference enforcer in this revision. The four third-party tier
rules (`L005`–`L007`, `D010`) are implemented by Python, TypeScript and .NET; Go reports them
`executed: false`. `G006` is implemented by all four reference enforcers; Go checks direct `go.mod`
requirements against `approvedDependencies`. The explicit-input rules (`D011`, `D012`) are implemented by Python, TypeScript
and .NET, and reported `executed: false` by Go. The named-call rule (`D017`) is implemented by Python
and .NET, and reported `executed: false` by TypeScript and Go. `A005` and `D015` execute in all four
reference enforcers. The value rule (`A006`), the composition rules (`D013`, `D014`), the
functional-capture rule (`D016`), the lifecycle rules (`A007`–`A009`) and the naming rules
(`N001`–`N002`) execute in Python, TypeScript and .NET; Go executes `N002` over type declarations and
reports `N001` `executed: false`.
`C008`, `A010`–`A015` and `N003` are manual in every profile: no portable analyzer can decide them
reliably.

The machine-readable source of truth is [`tools/acima-spec/rules.json`](../../tools/acima-spec/rules.json).
This catalog is its human-readable form; if they disagree, the JSON is authoritative.

## Categories

| Prefix | Concern | Chapter |
|---|---|---|
| `D` | Dependency and structure | [Dependency rules](dependency.md) |
| `L` | Layering inside a module | [Dependency rules](dependency.md#layering-l) |
| `C` | Contract shape and immutability | [Contract rules](contracts.md) |
| `A` | Autonomy at runtime | [Autonomy rules](autonomy.md) |
| `N` | Intent-revealing naming and semantic clarity | [Naming rules](naming.md) |
| `G` | Governance and exception hygiene | [Governance rules](autonomy.md#governance-g) |

## All rules

### Dependency and structure

| Id | Rule | Sev | Level |
|---|---|---|---|
| `D001` | Implementation references another implementation | error | L1 |
| `D002` | Contracts reference an implementation | error | L1 |
| `D003` | Contracts reference another contracts unit | error | L1 |
| `D004` | Contracts carry a third-party dependency | error | L1 |
| `D005` | Circular module dependency | error | L1 |
| `D006` | Contracts reference a composition boundary | error | L1 |
| `D007` | Shared kernel violation | error | L1 |
| `D008` | Transitive implementation leak | error | L1 |
| `D009` | Access to another module's internals | error | L1 |
| `D010` | Port exposes a vendor shape | error | L1 |
| `D011` | Optional construction dependency | error | L1 |
| `D012` | Optional argument hides an operational decision | error | L1 |
| `D013` | Implicit component registration | warning | L1 |
| `D014` | Property or field injection | warning | L1 |
| `D015` | Closed-over module-owned dependency | warning | L1 |
| `D016` | Partial application of a module-owned dependency | warning | L1 |
| `D017` | Unlabeled function or method argument | warning | L1 |

### Layering

| Id | Rule | Sev | Level |
|---|---|---|---|
| `L001` | Domain references infrastructure | error | L1 |
| `L002` | Contracts reference a framework type | error | L1 |
| `L003` | Implementation type published outside the module | error | L1 |
| `L004` | Module resolved through a service locator | warning | L1 |
| `L005` | Integration library used outside its declared adapter | warning | L1 |
| `L006` | Adapter without a port | error | L1 |
| `L007` | Vendor type outside the adapter | warning | L1 |

### Contract shape

| Id | Rule | Sev | Level |
|---|---|---|---|
| `C001` | Mutable contract state | error | L2 |
| `C002` | Mutable collection exposure | error | L2 |
| `C003` | Behaviour in contracts | error | L2 |
| `C004` | Ambient or non-deterministic state | error | L2 |
| `C005` | Persistence type leak | error | L2 |
| `C006` | Untyped payload | error | L2 |
| `C007` | Cannot be constructed in one step | warning | L2 |
| `C008` | Business behaviour is opaque at the boundary | error | L2 |

### Autonomy

| Id | Rule | Sev | Level |
|---|---|---|---|
| `A001` | Shared database ownership | error | L3 |
| `A002` | Cross-module configuration key | warning | L3 |
| `A003` | Cross-module mutable static state | error | L3 |
| `A004` | Version-lock coupling | warning | L3 |
| `A005` | Configuration read outside the composition boundary | warning | L3 |
| `A006` | Meaningful value without one immutable owner | warning | L3 |
| `A007` | Unnecessary transient lifetime | warning | L3 |
| `A008` | Captive scoped dependency | warning | L3 |
| `A009` | Shared mutable state without ownership | warning | L3 |
| `A010` | Effect boundary is unowned | error | L3 |
| `A011` | Effect semantics are hidden | error | L3 |
| `A012` | Effect outcome is untruthful | error | L3 |
| `A013` | Critical effect has no evidence | warning | L3 |
| `A014` | Telemetry conceals or alters business behaviour | error | L3 |
| `A015` | Unowned consistency boundary | error | L3 |

### Naming

| Id | Rule | Sev | Level |
|---|---|---|---|
| `N001` | Non-idiomatic type identifier | warning | L3 |
| `N002` | Generic responsibility name | warning | L3 |
| `N003` | Semantic naming clarity review | warning | L3 |

### Governance

| Id | Rule | Sev | Level |
|---|---|---|---|
| `G001` | Undocumented exception | error | L1 |
| `G002` | Expired waiver | error | L1 |
| `G003` | Undocumented contract surface | warning | L2 |
| `G004` | Unreviewed contract change | error | L2 |
| `G005` | Unclassified source | error | L1 |
| `G006` | Undeclared external dependency | warning | L1 |

## How to read a rule

Every rule entry has the same six parts:

1. **Statement** — what it requires, in one sentence.
2. **Violation** — code that breaks it.
3. **Finding** — what the enforcer prints. This is the contract: your tooling should print something
   this useful.
4. **Why** — the failure mode it prevents.
5. **Fix** — the change, not the theory.
6. **Detection** — how it is actually checked, and what cannot be checked.

## Severity

| Severity | Meaning | Gate |
|---|---|---|
| `error` | A defect. Fails the build at the rule's level. | blocks merge |
| `warning` | A strong default that was departed from. Reported, tracked, not blocking. | reported only |
| `info` | Something the reviewer should know (an additive API change, an unparsed file). | reported only |

Only `L004`, `C007`, `A002`, `A004`, `A013`, `G003`, `N001`–`N003` and the ratcheting rules recorded in `rules.json` are
warnings; every other rule is an error. Every ratcheting rule becomes `error` at the next major
release — the ratchet is recorded in `rules.json` as
`severityRatchet: { "to": "error", "at": "2.0.0" }` and explained in
[§8.10](../standard/08-conformance.md#810-third-party-governance-and-the-swap-drill) and the
[changelog](../../CHANGELOG.md). This ratio is deliberate: a catalogue of warnings is a catalogue of
things nobody fixes.

## Rules that need judgement

Fourteen normative rules cannot be decided by the portable reference enforcers. The machine-readable
catalog marks them `automation: "manual"`; the other 42 are `automation: "automated"`. They remain
in the catalogue because a native analyzer, package metadata or a human review can decide them, but
a clean portable run is not evidence that they pass. A full conformance claim records one
repository-scoped entry per manual rule in `acima/evidence/manual-evidence.json`; without that file the
claim is `PARTIAL ASSESSMENT`. See [Conformance §8.9](../standard/08-conformance.md#89-manual-evidence-for-full-claims).

| Rule | Severity | What the portable tool does | What a human or native analyzer does |
|---|---|---|---|
| `C003` | error | reports `executed: false` | decides whether a contract helper is validation or business logic, IO or orchestration |
| `C007` | warning | reports `executed: false` | decides whether a builder or multi-step construction is justified and whether required state is obvious |
| `C008` | error | reports `executed: false` | decides whether a boundary operation hides a business decision, nondeterministic input or meaningful effect |
| `L004` | warning | reports `executed: false` | inspects framework-specific service-locator/container resolution |
| `A002` | warning | reports `executed: false` | decides whether a configuration key is genuinely shared infrastructure or another module's key/secret |
| `A004` | warning | reports `executed: false` | inspects published package/artifact versions across the product graph |
| `A010` | error | reports `executed: false` | identifies the effect owner and execution boundary; confirms no caller performs a provider's effect |
| `A011` | error | reports `executed: false` | decides whether retry, duplicate, consistency, partial-completion and cancellation semantics are explicit where applicable |
| `A012` | error | reports `executed: false` | checks that success, failure, unknown and partial outcomes are reported truthfully |
| `A013` | warning | reports `executed: false` | decides whether a critical effect has evidence proportional to its failure impact |
| `A014` | error | reports `executed: false` | decides whether telemetry observes behaviour or replaces a business decision, and whether diagnostics, business events and audit records are distinguishable |
| `A015` | error | reports `executed: false` | names the owner and the guarantee of each consistency boundary, and checks recovery, compensation or reconciliation |
| `N003` | warning | reports `executed: false` | decides responsibility, side-effect, unit, abbreviation, boolean and domain-consistency clarity |
| `G004` | error | reports `executed: false` | compares a reviewed per-language API baseline and classifies the change as additive or breaking |

`G003` is executed, but a human still writes and reviews the documentation it looks for. The other
42 rules execute in at least one reference enforcer and have gallery fixtures; the third-party tier,
explicit-input, value, composition, functional-capture, lifecycle and naming rules execute in Python,
TypeScript and .NET. A Go run reports eighteen automated rules plus the fourteen manual rules
`executed: false`; a .NET run reports only the fourteen manual rules, so a full claim needs manual
evidence for those unexecuted rules.

A rule that mixes machine and human judgement must say which part is which — otherwise the tool gets
blamed for the human's decision, and the rule gets disabled.

## Profile requirements outside the catalog

Chapter 11 defines the service topology default as `ST-1`–`ST-12`. They are conformance requirements,
not base-catalog rules, and use the profile namespace `ACIMA-S001`–`S012`. The runner is
[`conformance/topology.py`](../../conformance/topology.py), which reads `acima.topology.json`,
scans the tree and emits findings in the same shape as the language enforcers. A claim that includes
the profile cites the JSON run, not a hand-completed checklist — see
[Conformance](../standard/08-conformance.md#88-service-topology-profile).
