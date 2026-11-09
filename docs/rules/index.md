# Rule catalog

34 rules. Five categories. Every rule has a permanent id, a severity, a conformance level and a
detection strategy. Python, TypeScript, Go and .NET each have a reference enforcer; Java is a
documented profile only and has no reference enforcer in this revision. The five third-party tier
rules (`L005`–`L007`, `D010`, `G006`) are implemented by the Python and TypeScript enforcers in this
revision and reported `executed: false` by Go and .NET.

The machine-readable source of truth is [`tools/acima-spec/rules.json`](../../tools/acima-spec/rules.json).
This catalog is its human-readable form; if they disagree, the JSON is authoritative.

## Categories

| Prefix | Concern | Chapter |
|---|---|---|
| `D` | Dependency and structure | [Dependency rules](dependency.md) |
| `L` | Layering inside a module | [Dependency rules](dependency.md#layering-l) |
| `C` | Contract shape and immutability | [Contract rules](contracts.md) |
| `A` | Autonomy at runtime | [Autonomy rules](autonomy.md) |
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
| `D006` | Contracts reference the host | error | L1 |
| `D007` | Shared kernel violation | error | L1 |
| `D008` | Transitive implementation leak | error | L1 |
| `D009` | Access to another module's internals | error | L1 |
| `D010` | Port exposes a vendor shape | error | L1 |

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

### Autonomy

| Id | Rule | Sev | Level |
|---|---|---|---|
| `A001` | Shared database ownership | error | L3 |
| `A002` | Cross-module configuration key | warning | L3 |
| `A003` | Cross-module mutable static state | error | L3 |
| `A004` | Version-lock coupling | warning | L3 |

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

Only `L004`, `C007`, `A002`, `A004`, `G003` and the three ratcheting third-party rules (`L005`,
`L007`, `G006`) are warnings; every other rule is an error. The three ratcheting rules become `error`
at the next major release — the ratchet is recorded in `rules.json` as
`severityRatchet: { "to": "error", "at": "2.0.0" }` and explained in
[§8.10](../standard/08-conformance.md#810-third-party-governance-and-the-swap-drill) and the
[changelog](../../CHANGELOG.md). This ratio is deliberate: a catalogue of warnings is a catalogue of
things nobody fixes.

## Rules that need judgement

Six normative rules cannot be decided by the portable reference enforcers. The machine-readable
catalog marks them `automation: "manual"`; the other 28 are `automation: "automated"`. They remain
in the catalogue because a native analyzer, package metadata or a human review can decide them, but
a clean portable run is not evidence that they pass. A full conformance claim records one
repository-scoped entry per manual rule in `.acima/manual-evidence.json`; without that file the
claim is `PARTIAL ASSESSMENT`. See [Conformance §8.9](../standard/08-conformance.md#89-manual-evidence-for-full-claims).

| Rule | Severity | What the portable tool does | What a human or native analyzer does |
|---|---|---|---|
| `C003` | error | reports `executed: false` | decides whether a contract helper is validation or business logic, IO or orchestration |
| `C007` | warning | reports `executed: false` | decides whether a builder or multi-step construction is justified and whether required state is obvious |
| `L004` | warning | reports `executed: false` | inspects framework-specific service-locator/container resolution |
| `A002` | warning | reports `executed: false` | decides whether a configuration key is genuinely shared infrastructure or another module's key/secret |
| `A004` | warning | reports `executed: false` | inspects published package/artifact versions across the product graph |
| `G004` | error | reports `executed: false` | compares a reviewed per-language API baseline and classifies the change as additive or breaking |

`G003` is executed, but a human still writes and reviews the documentation it looks for. The other
28 rules execute in at least one reference enforcer and have gallery fixtures; the third-party tier
rules are scoped to Python and TypeScript in this revision, so a Go or .NET run reports them
`executed: false` and a full claim needs manual evidence for them.

A rule that mixes machine and human judgement must say which part is which — otherwise the tool gets
blamed for the human's decision, and the rule gets disabled.

## Profile requirements outside the catalog

Chapter 11 defines the service topology default as `ST-1`–`ST-12`. They are conformance requirements,
not base-catalog rules, and use the profile namespace `ACIMA-S001`–`S012`. The runner is
[`conformance/topology.py`](../../conformance/topology.py), which reads `acima.topology.json`,
scans the tree and emits findings in the same shape as the language enforcers. A claim that includes
the profile cites the JSON run, not a hand-completed checklist — see
[Conformance](../standard/08-conformance.md#88-service-topology-profile).
