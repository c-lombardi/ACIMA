# ACIMA Standard

**Autonomous, Contract-Isolated, Immutable Modular Architecture**, version `1.0.0-draft.1`.

ACIMA defines how to build a system out of modules that own their behaviour, expose nothing but
immutable contracts, and can be changed or extracted without touching their consumers — and how to
make a build fail when that stops being true.

## Start here

| Need | Read |
|---|---|
| See ACIMA working in five minutes | [Quickstart](start/quickstart.md) |
| Understand the before/after value | [Executable before/after](guides/before-after.md) |
| Apply it to an existing system | [Brownfield adoption](start/brownfield.md) |
| Know what is verified vs proposed | [Capability status](status.md) |
| Know what ACIMA promises consumers | [Product contract](product-contract.md) |
| Make the investment case | [For engineering leaders](guides/engineering-leadership.md) |
| Give an agent the constraints | [AI coding agents](guides/ai-agents.md) |

## Read in this order

| # | Chapter | You will learn |
|---|---------|----------------|
| 0 | [Preface](standard/00-preface.md) | Scope, normative language, status, relationship to prior art |
| 1 | [Principles](standard/01-principles.md) | The thirteen principles, each with its rationale and the rules or profile requirements that enforce it |
| 2 | [Vocabulary](standard/02-vocabulary.md) | The exact meaning of *module*, *contracts*, *unit*, *port*, *waiver* |
| 3 | [Module anatomy](standard/03-module-anatomy.md) | The four artifacts every module has, in every language |
| 4 | [Dependency model](standard/04-dependency-model.md) | The normative allowed-edge matrix and how tools classify units |
| 5 | [Contract design](standard/05-contract-design.md) | What may live in contracts, how to keep them immutable, how to evolve them |
| 6 | [Runtime boundaries](standard/06-runtime-boundaries.md) | Calls, events, outbox, transactions, configuration, composition root |
| 7 | [Executable governance](standard/07-executable-governance.md) | Rule ids, findings, waivers, CI gates, the harness contract |
| 8 | [Conformance](standard/08-conformance.md) | Levels L1–L3 and the checklist a repository must satisfy |
| 9 | [Adoption](standard/09-adoption.md) | Greenfield, brownfield, ratchets and migration |
| 10 | [FAQ](standard/10-faq.md) | The arguments you will actually have |
| 11 | [Service topology and layer contracts](standard/11-service-topology.md) | Service directories, independent layer contracts, absolute isolation, vendor adapters and product orientation |

## Then

- [Rule catalog](rules/index.md) — all 29 rules, with bad and good examples per language
- [Violation walkthrough](guides/violation-walkthrough.md) — a guided tour of everything ACIMA prohibits
- [Language profiles](languages/index.md) — C#, TypeScript, Python, Go, Java
- [Architecture tests](guides/architecture-tests.md) and [analyzers](guides/analyzers-and-linters.md)
- [Agent skill](../skills/acima-adoption/SKILL.md) — applying and auditing ACIMA with a coding agent
- [Review and decisions](guides/review-and-decisions.md) — faster reviews, auditable AI assistance, narrow scopes and fewer side effects
- [Service topology (default)](standard/11-service-topology.md) — the product-oriented service and layer model, with executable ST-1–ST-12 checks and a language section in every profile

## The shortest possible summary

1. Each module has `X.Contracts` (zero dependencies, immutable messages, promised capabilities) and `X` (private implementation).
2. Modules reference other modules' **contracts only** — never implementations, never each other's schemas, configuration or statics.
3. Contracts never reference contracts, and by default reference nothing at all: value types are local or primitive. The shared kernel is a legacy compatibility allowance.
4. Only the composition root knows every module.
5. Every rule above is a test, and every exception is a dated, owned waiver.
