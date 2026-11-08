# The core of ACIMA

This is the architecture stated without reference to any analyzer, language or file layout. It is the model every rule in the catalog serves; if a rule cannot be traced to it, the rule is optional or unjustified.

## 1. The one proposition

**A module owns its implementation, exposes exactly one explicit contract, and nothing outside the module can depend on its internals.**

Everything else in ACIMA is a consequence of making that sentence true in a build rather than in a wiki.

## 2. Five fundamental requirements

| # | Requirement | Meaning | Enforced by |
|---|---|---|---|
| R1 | **Module ownership** | A module owns its domain model, implementation, dependencies and abstractions. No other module may own, share or reach into them. | `D001` `D009` `L003` |
| R2 | **Explicit contracts** | A module's complete public surface is its contracts unit: messages, the value types they need, provided ports, typed results. Implementation types are never public. | `D002` `D009` `L002` `L003` `G003` |
| R3 | **Dependency isolation** | Contracts are zero-dependency (nothing but the language core); implementations depend only on other modules' contracts; the graph is acyclic; no transitive implementation leak. | `D002`–`D008` `L001` |
| R4 | **Data and configuration ownership** | A module owns its persistence, its configuration namespace, and its mutable state. | `A001` `A002` `A003` `A004` |
| R5 | **Controlled composition** | Only the host/composition root knows every module. Modules receive peers explicitly; nothing resolves peers at runtime, and nothing references the host. | `D006` `L004` |

Optional-extension requirements are **not** part of this core:

- service topology (`P10`–`P13`, `ST-1`–`ST-12`) — a profile for multi-service products;
- library/framework public-surface classification — a profile for published artifacts.

Both are explicitly selected (`mode`, `profile`) and both fail closed when unsupported.

## 3. Where immutability belongs

Immutability is **a property of the contract requirement (R2), not a sixth requirement** — but it is a distinct, separately checkable obligation, so it remains its own principle (P6) and its own rule group (`C001`–`C007`).

The reasoning matters, because it is the part most often argued about:

- A mutable contract makes R2 false in practice: the receiver can change the sender's state, so the contract is not a boundary but a shared object.
- Immutability is cheap to check (`C001`, `C002`, `C004`—`C006` are automated) and expensive to add later.
- The constraint applies **only across the boundary**. Implementations may use mutable aggregates and ORM entities. Collapsing P6 into R2 would invite teams to "simplify" by making contracts mutable.

Consolidating P6 into R2 was rejected: it would reduce the count of principles by one and weaken an enforceable obligation. The mission does not reward smaller numbers.

## 4. Principles versus rules

- A **principle** (P1–P9) states an obligation and why it exists. It is prose, and it is normative.
- A **rule** (`ACIMA-<category><NNN>`) is the smallest independently checkable statement of that obligation, with a severity, a conformance level and an automation status.

Mapping (base standard):

| Principle | Requirements | Rules |
|---|---|---|
| P1 Service Ownership | R1 | `D001` `D009` `L003` `A001` `A002` `A003` |
| P2 Contract Isolation | R2 | `D002` `D006` `D009` `L003` `G003` |
| P3 Zero-Dependency Contracts | R2, R3 | `D003` `D004` `D008` `L002` `C005` |
| P4 Dependency Inversion | R5 | `D002` `L003` `L004` `G003` |
| P5 Strict Dependency Boundaries | R3, R5 | `D001` `D005` `D008` `L001` |
| P6 Immutable by Default | contract property of R2 | `C001`–`C007` |
| P7 Independent Evolution | R4 | `A001`–`A004` `G004` |
| P8 Executable Governance | all requirements are verifiable | `G001`–`G005` + the harness contract |
| P9 Explicit Exceptions | honesty about departures | `G001` `G002` |

Principles and rules are not merged because they answer different questions: a principle explains *why* a boundary exists, a rule says *what fails the build*. Merging them would either delete the rationale or turn prose into a tool specification.

## 5. Human judgement is part of the standard

Six normative rules cannot be decided by portable source analysis. They stay normative; a tool reports `executed: false` and a claim stays `PARTIAL ASSESSMENT` until a repository-scoped review record exists:

| Rule | Human decision |
|---|---|
| `C003` | is a contract helper validation, or business behaviour? |
| `C007` | does construction make required state obvious? |
| `L004` | is a peer resolved from a container/locator? |
| `A002` | is a configuration key shared infrastructure or another module's? |
| `A004` | do consumers pin a contracts version? |
| `G004` | is a contract change additive or breaking? |

This is the honest boundary of the architecture: enforcement covers what source text can prove, and the claim model refuses to call the rest conformant.

## 6. The three layers, and the direction of authority

```
requirement (R1–R5)
  → principle (P1–P9)                docs/standard/01-principles.md
    → normative rule (ACIMA-*)       tools/acima-spec/rules.json   ← single machine source
      → enforcement mapping          conformance/coverage.json
        → implementation             examples/<lang>/tools/*
          → regression evidence      examples/<lang>/violations/expected.json + conformance/test_*.py
            → skill guidance         skills/acima-adoption/
```

Rules flow **down** this chain. An enforcer that disagrees with `rules.json` is wrong; a skill that disagrees is out of date; a report that claims more than the execution map supports is invalid. Nothing below the catalog may add, remove or reinterpret a rule.

## 7. What a reviewer should be able to conclude

1. Modules own their code; only contracts cross boundaries.
2. The boundary is structural, not conventional: `D001`/`D009`/`L003` fail the build.
3. Contracts are dependency-free and immutable, so cycles and shared-state coupling are prevented by construction.
4. Data, configuration and statics are owned, so a module can be extracted without redesign.
5. The host is the only unit that knows the whole graph.
6. Every departure is owned, dated and fingerprinted; every claim names what was not checked.
