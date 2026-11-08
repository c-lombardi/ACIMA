# Rule catalog

29 rules. Five categories. Every rule has a permanent id, a severity, a conformance level and a
detection strategy. Each of the four implemented language profiles has a reference enforcer; Java
is a documented profile only and has no reference enforcer in this revision.

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

### Layering

| Id | Rule | Sev | Level |
|---|---|---|---|
| `L001` | Domain references infrastructure | error | L1 |
| `L002` | Contracts reference a framework type | error | L1 |
| `L003` | Implementation type published outside the module | error | L1 |
| `L004` | Module resolved through a service locator | warning | L1 |

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

Only `L004`, `C007`, `A002`, `A004` and `G003` are warnings. Every other rule is an error. This ratio
is deliberate: a catalogue of warnings is a catalogue of things nobody fixes.

## Rules that need judgement

Four rules cannot be fully decided by a parser. They are still in the catalogue because the enforcer
can do most of the work and force the conversation:

| Rule | What the tool does | What a human does |
|---|---|---|
| `C003` | flags methods with branching, IO calls or non-trivial bodies in contract types | decides whether a helper is validation or a business rule |
| `C007` | flags contract types with parameterless constructors and settable state | decides whether a builder is justified |
| `A002` | flags reads of configuration keys outside the unit's namespace | decides whether the key is genuinely shared infrastructure |
| `G003` | flags public contract types without documentation | writes the documentation |

A rule that mixes machine and human judgement must say which part is which — otherwise the tool gets
blamed for the human's decision, and the rule gets disabled.

## Profile requirements outside the catalog

Chapter 11 defines the service topology default as `ST-1`–`ST-12`. They are conformance requirements,
not base-catalog rules, and use the profile namespace `ACIMA-S001`–`S012`. The runner is
[`conformance/topology.py`](../../conformance/topology.py), which reads `acima.topology.json`,
scans the tree and emits findings in the same shape as the language enforcers. A claim that includes
the profile cites the JSON run, not a hand-completed checklist — see
[Conformance](../standard/08-conformance.md#88-service-topology-profile).
