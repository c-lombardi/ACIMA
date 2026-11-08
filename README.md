# ACIMA

**Autonomous, Contract-Isolated, Immutable Modular Architecture** — an engineering standard for
systems whose modules can be changed, tested and extracted independently, and whose boundaries are
enforced by the build rather than by review.

> Status: **Draft 1** (`1.0.0-draft.1`) · Normative specification plus executable reference
> implementations in TypeScript, Python, Go and C#/.NET. The Java profile is written; its
> reference implementation is not included in this revision, and the status table says so.

ACIMA is not a project template and not a diagram. It is a set of obligations about **what may
reference what**, **what a contract is allowed to contain**, and **how violations are found**.
Everything in it is written so a machine can fail a build over it.

---

## The idea in one page

Split every module into two halves that cannot be confused with each other:

```
        ┌──────────────────────┐          ┌──────────────────────┐
        │  Catalog.Contracts   │◄─────────│       Catalog        │
        │  zero dependencies   │  owns    │  domain, data, logic │
        │  immutable messages  │          │  nothing published   │
        └──────────▲───────────┘          └──────────────────────┘
                   │ referenced
        ┌──────────┴───────────┐
        │        Orders        │
        │  never references    │
        │  Catalog's internals │
        └──────────────────────┘
```

A module's **contracts** are its entire public surface: immutable messages and the capabilities it
promises. Its **implementation** is private, replaceable, and invisible to every other module. Because
contracts depend on nothing and implementations depend only on contracts, cycles become structurally
impossible and every module becomes extractable.

That core is the *Explicit Contract Projects* pattern. ACIMA's contribution is to make the rest of
the promise enforceable: contracts are **zero-dependency and immutable by rule**, module autonomy
extends to **runtime state and persistence ownership**, and every rule ships with **a finding format,
a waiver format and a conformance level** so teams can adopt it incrementally and prove it.

## The thirteen principles

| # | Principle | What it forbids |
|---|-----------|-----------------|
| P1 | **Service Ownership** — every module owns its implementation, abstractions, dependencies and domain | shared "common" projects that quietly own everyone's code |
| P2 | **Contract Isolation** — every module owns its public contracts | publishing implementation types; implicit public surface |
| P3 | **Zero-Dependency Contracts** — contracts reference nothing but the language core; the shared kernel is legacy compatibility | framework, ORM, transport and utility packages inside contracts |
| P4 | **Dependency Inversion** — consumers own their integration abstractions | provider contracts reshaped to fit one consumer; resolving peers at runtime |
| P5 | **Strict Dependency Boundaries** — no cross-module implementation references, no cycles | "just this once" implementation references |
| P6 | **Immutable by Default** — contracts, messages, commands, queries and value objects never mutate | setters, mutable collections, ambient clocks and identifiers in contracts |
| P7 | **Independent Evolution** — modules change and ship without coordinating with consumers | version-locked modules; shared schemas; shared mutable statics |
| P8 | **Executable Governance** — violations fail the build | architecture rules that live only in a wiki |
| P9 | **Explicit Exceptions** — every departure is owned, justified, scoped and dated | silent suppressions and permanent waivers |
| P10 | **Service-Aligned Topology** — one service, one directory, projects named for the owner | cross-service `Shared` projects; service names that do not match the directory |
| P11 | **Layer Contract Independence** — every layer owns its contract surface and transforms at the boundary | DTOs passed through layers; one contracts project serving two layers |
| P12 | **Absolute Contract Isolation (default)** — contracts reference nothing, not even the kernel | shared-kernel or serializer attributes inside contracts |
| P13 | **Product-Oriented Services** — UI/API workflow parity, core logic in the API domain, deployment-agnostic services | UI-only rules; vendor SDKs in the domain; infrastructure-shaped services |

P1–P9 are the base standard. P10–P13 are the service topology profile in
[chapter 11](docs/standard/11-service-topology.md); they are checked manually in this revision.

Full text: [Principles](docs/standard/01-principles.md).

## What you get in this repository

| Area | Contents |
|------|----------|
| **Standard** | The normative specification: principles, vocabulary, module anatomy, dependency matrix, contract design, runtime boundaries, governance, conformance levels, adoption path, FAQ |
| **Rule catalog** | 29 rules across five categories with detection strategy, remediation and per-language examples |
| **Language profiles** | How each obligation is expressed, enforced and tested in C#, TypeScript, Python, Go and Java |
| **Service topology (default)** | One directory per service, independent layer contracts, absolute contract isolation, vendor adapter seams and `<Source>.<Target>` messaging — chapter 11 plus a section in every language profile |
| **Reference implementations** | A three-module ordering system in TypeScript, Python, Go and C#/.NET, compiled and tested |
| **Violation gallery** | Deliberately broken fixtures for every portable rule, in each implemented language, with expected findings checked into the repository |
| **Conformance harness** | A single runner that executes every language's architecture tests and asserts the gallery produces the documented findings |
| **Agent skill** | `skills/acima-adoption` — a portable skill that classifies a target as greenfield, brownfield or adopting, pins the catalog hash, drafts a unit map and baseline waivers, and carries the adoption, communication, onboarding and outcomes playbooks |

```
docs/            the standard, the rules, the language profiles, the guides
examples/        dotnet | typescript | python | go   (compiling reference implementations)
                 java                                (profile written; implementation not included yet)
tools/           the machine-readable rule catalog + per-language analyzers
conformance/     runs every language suite and compares against the expected findings
skills/          agent skill for applying and auditing the standard (preflight, playbooks, templates)
```

## What this buys you in review

ACIMA's day-to-day value is not the diagram; it is the **decision speed of a pull request**. The
gate answers the structural questions before a human spends time on the diff, so review attention
goes to product outcomes instead of boundary archaeology.

| Review question | Answered mechanically by | A human still decides |
|---|---|---|
| May this unit depend on that one? | the unit map and `D001`–`D009` | whether the dependency is the right product boundary |
| Is the change's blast radius contained? | contracts-only edges, acyclic graph (`D005`), `G004` API baseline | whether the scope matches the intent |
| Can a caller mutate this contract? | `C001`, `C002` | whether the contract models the domain |
| Does this touch another module's data or state? | `A001`, `A003` | whether the capability split is right |
| Is this exception acceptable? | `G001`, `G002` — owner, reason, scope, expiry | whether to grant it at all |

Three consequences follow:

- **Narrow scopes are visible.** A contracts change is a published-surface change; an
  implementation change is private. They can be reviewed — and required — as separate pull
  requests, so a surface change cannot hide inside a refactor.
- **Side effects are computable.** No implementation references, no cycles, no shared mutable
  statics and no shared schema mean the affected units are derivable from the declared graph,
  not discovered in staging.
- **AI assistance becomes auditable.** Findings are JSON with a rule id, path, line, evidence and
  remedy, so an agent can run the enforcer and cite the same rubric a human uses. The
  [agent skill](skills/acima-adoption/SKILL.md) pins the catalog hash, so its advice is written
  against the rules actually in this revision. The agent proposes; the owner decides.

Full outline, reviewer checklist and AI-assisted review protocol:
[Review and decisions](docs/guides/review-and-decisions.md).

## Conformance levels

ACIMA is adopted in levels. Each level is a superset of the last, and each is machine-verifiable.

| Level | Name | Adds | Rules |
|-------|------|------|-------|
| **L1** | Structural | Contracts exist; dependency matrix and layering enforced | `D*` `L*` `G*` |
| **L2** | Immutable | Contract shape, immutability and API baseline enforcement | `C*` `G003` `G004` |
| **L3** | Autonomous | Persistence, configuration and state ownership | `A*` |

Declare the target level in `acima.config.json`; a repository is conformant at a level only when
every rule required by that level passes with zero findings outside a valid waiver.

## Quickstart

```bash
# run one language's architecture tests
cd examples/python     && python3 -m unittest discover -s tests -p 'test_*.py'
cd examples/typescript && node --test tests/*.test.mjs
cd examples/go         && go test ./tests/...
cd examples/dotnet     && dotnet run --project tools/Acima.ArchTests -- --verify

# run every implemented profile and verify each gallery matches its documented findings
python3 conformance/run.py
```

### With a coding agent

[`skills/acima-adoption`](skills/acima-adoption/SKILL.md) is a portable agent skill. Install it
where your agent reads skills (`.claude/skills/` for Claude Code) and ask it to adopt ACIMA in a
repository. It starts with a read-only preflight that verifies the skill still matches this
catalog, classifies the target, and prints the exact next step:

```bash
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
```

The preflight pins the `rules.json` hash and enforcer paths, so it fails loudly when the standard
changes instead of giving stale advice. The skill also ships the adoption plan, communication plan
and onboarding path as templates. See [skills/README.md](skills/README.md).

## Repository status

| Profile | Example | Enforcer | Clean tree | Violation gallery | Verified |
|---|---|---|---|---|---|
| Python 3.12 | `examples/python` | `tools/acima_arch.py` | 0 findings | 23 rules / 33 findings | yes |
| TypeScript 5 / Node 22+ | `examples/typescript` | `tools/acima-arch.mjs` | 0 findings | 19 rules / 30 findings | yes |
| Go 1.22+ | `examples/go` | `tools/archtest` | 0 findings | 20 rules / 30 findings | yes |
| C# / .NET 8 | `examples/dotnet` | `tools/Acima.ArchTests` | 0 findings | 23 rules / 39 findings | yes |
| Java 21 | — | profile only | — | — | no |

"Verified" means the commands in the quickstart were executed against this revision and
`conformance/run.py` reported `ok`. The Java profile document describes the intended layout and
enforcer contract; it is not a tested artifact, and the conformance runner skips it explicitly
rather than reporting a pass. Service topology and absolute contract isolation (chapter 11) are the
default for new systems and are manually checkable in this revision; the reference examples implement
the legacy compatibility baseline (shared kernel allowed), not the default.

## Prior art and what ACIMA adds

ACIMA assembles documented practice rather than inventing it:

- **[Explicit Contract Projects](https://modularmonoliths.com/patterns/explicit-contract-projects/)** (ModularMonoliths) — module + contracts project split, contracts free of dependencies, cycles structurally prevented. *ACIMA adopts this whole, and names it P2/P3/P5.*
- **[NetArchTest](https://github.com/BenMorris/NetArchTest)** and **[ArchUnit](https://www.archunit.org/)** — architecture rules as executable tests. *ACIMA adopts the execution model and standardises the finding format and rule identifiers across languages.*
- **[Purview Architests](https://purview.dev/projects/architests/)** — project responsibilities and dependency directions as data, with reviewed, dated waivers and transitive assembly checks. *ACIMA adopts the policy-as-data model and the waiver discipline (P9).*
- **Clean Architecture / Hexagonal / Ports & Adapters**, **DDD** and **Modular Monoliths** — layering, aggregates, bounded contexts, composition roots. *ACIMA constrains them into rules that can be checked.*
- **[Microsoft library guidance](https://learn.microsoft.com/dotnet/standard/library-guidance/dependencies)** and MSBuild `PrivateAssets` — dependency minimisation and transitive control. *ACIMA uses these as the .NET expression of P3 and D008.*

What is genuinely new here is the **combination made normative and portable**: zero-dependency
contracts *and* contract immutability as build-blocking rules, autonomy extended past compile time
into persistence/configuration/state ownership, and one rule catalogue with one finding format
replicated across five languages so the same violation is caught the same way everywhere.

## Licence and governance of the standard itself

The standard is versioned (`major.minor.patch`). Adding a rule is a minor version; changing the
meaning of an existing rule or its identifier is a major version. Rule identifiers are permanent:
`ACIMA-D001` means the same thing in every language and every version.
