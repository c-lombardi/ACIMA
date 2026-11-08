# 1. Principles

Thirteen principles. Each states an obligation, the reasoning behind it, and the rules — or profile
requirements — that make it fail a build. The principles are ordered so that each one is only achievable because of the ones before it.

P1–P9 are the base standard. P10–P13 belong to the service topology profile in
[chapter 11](11-service-topology.md); they are checked manually in this revision.

| # | Principle | Enforced by |
|---|-----------|-------------|
| P1 | [Service Ownership](#p1-service-ownership) | `D001` `D009` `L003` `A001` `A002` `A003` |
| P2 | [Contract Isolation](#p2-contract-isolation) | `D002` `D006` `D009` `L003` `G003` |
| P3 | [Zero-Dependency Contracts](#p3-zero-dependency-contracts) | `D003` `D004` `D008` `L002` `C005` |
| P4 | [Dependency Inversion](#p4-dependency-inversion) | `D002` `L003` `L004` `G003` |
| P5 | [Strict Dependency Boundaries](#p5-strict-dependency-boundaries) | `D001` `D005` `D008` `L001` |
| P6 | [Immutable by Default](#p6-immutable-by-default) | `C001`–`C007` |
| P7 | [Independent Evolution](#p7-independent-evolution) | `A001`–`A004` `G004` |
| P8 | [Executable Governance](#p8-executable-governance) | `G001`–`G005` and the harness contract |
| P9 | [Explicit Exceptions](#p9-explicit-exceptions) | `G001` `G002` |
| P10 | [Service-Aligned Topology](#p10-service-aligned-topology) | `ST-1`–`ST-3` `ST-7` (profile, manual) |
| P11 | [Layer Contract Independence](#p11-layer-contract-independence) | `ST-4` `ST-6` (profile, manual) |
| P12 | [Absolute Contract Isolation](#p12-absolute-contract-isolation) | `ST-5` (profile, manual) |
| P13 | [Product-Oriented Services](#p13-product-oriented-services) | `ST-11` `ST-12` (profile, manual) |

---

## P1. Service Ownership

> **Every module owns its implementation, its abstractions, its dependencies and its domain. No other
> module may own, share or reach into them.**

A module is a unit of ownership before it is a unit of code. It owns:

- its **domain model** — the entities, aggregates and invariants that only it may decide;
- its **implementation** — application services, persistence, integrations, adapters;
- its **dependencies** — the packages it chose, at the versions it chose;
- its **abstractions** — the interfaces through which it talks to databases, queues, clocks and peers;
- its **data** — the tables, schemas, buckets and caches that hold its state (see P7 and `A001`).

### Obligations

- **P1.1** A module MUST NOT require another module's implementation to be present, compiled or
  version-aligned in order to build (`D001`, `D008`).
- **P1.2** A module's non-contract types MUST NOT be reachable from outside it (`D009`, `L003`).
- **P1.3** A module MUST NOT read or write another module's persistent state, and MUST NOT share a
  database schema with it (`A001`).
- **P1.4** A module MUST NOT read another module's configuration keys (`A002`).
- **P1.5** A module and another module MUST NOT communicate through shared mutable static state
  (`A003`).
- **P1.6** Abstractions over infrastructure (repositories, gateways, clocks, message buses) belong to
  the module that uses them, in its implementation — never in a cross-module "core" project.

### The failure it prevents

The `Common`/`Shared`/`Core` project. It starts as five extension methods, becomes the de-facto
domain model, and ends up referenced by everything — at which point ownership is diffuse and every
change is a coordination event. In ACIMA the only cross-module unit that may exist is a
dependency-free **shared kernel** (P3), and it is deliberately hostile to growth (`D007`).

---

## P2. Contract Isolation

> **Every module owns its public contracts. The contracts unit is the module's complete and only
> public surface.**

### Obligations

- **P2.1** Every module MUST expose exactly one contracts unit, named after the module.
- **P2.2** The contracts unit MUST contain only: message types (commands, queries, events, views),
  value types those messages need, and the **provided ports** — the capabilities the module promises
  to fulfil.
- **P2.3** A contracts unit MUST NOT expose any implementation type, internal namespace, ORM entity,
  framework object or transport concern (`L002`, `C005`, `D009`).
- **P2.4** A module's implementation MUST NOT publish public types outside its contracts unit
  (`L003`). Inside the module, everything is as private as the language allows.
- **P2.5** Public contract types SHOULD be documented, because a contract without a documented
  invariant is a guess (`G003`).

### Why "only public surface" matters

If implementation types are also public, the contract is a fiction: consumers will use whatever
compiles. The contract only becomes a real boundary when the alternative is unavailable. This is the
difference between a boundary that is *documented* and a boundary that is *structural*.

---

## P3. Zero-Dependency Contracts

> **Contracts reference nothing: not other modules, not other contracts, not third-party packages,
> not the shared kernel — only the language's core library. This is the default.**

### Obligations

- **P3.1** A contracts unit MUST NOT reference a third-party package (`D004`).
- **P3.2** A contracts unit MUST NOT reference another contracts unit (`D003`).
- **P3.3** A contracts unit MUST NOT reference an implementation, its own included (`D002`).
- **P3.4** A contracts unit MUST NOT expose framework types — hosting, transport, ORM, or
  serialization attributes that bind the type to a library (`L002`, `C005`).
- **P3.5** The **shared kernel** is a legacy compatibility allowance, not a default dependency. New
  contracts MUST NOT reference it; existing repositories may retain it until migration (`ST-5`).

### The reasoning, precisely

Zero-dependency contracts are what make the graph acyclic *by construction* rather than by
discipline. If contracts may depend on contracts, you have re-created the original problem one level
up: `A.Contracts → B.Contracts → A.Contracts` is a cycle, and in languages that forbid circular
project references it becomes a build error you cannot work around.

There is a second, less obvious reason: **a dependency is a coupling you inherit**. A contracts
package that references a JSON library dictates the serializer to every consumer; one that references
a validation library dictates the validation model; one that references an observability library
dictates the tracer. Zero dependencies means the consumer chooses the technology, which is what
independent evolution (P7) requires.

### What about shared enums, ids and money?

By default they are declared **inside the contract project that needs them** (or represented by
primitives) and duplicated where another contract needs the same value. The **shared kernel** — a
tiny, dependency-free, behaviour-poor unit — is a legacy compatibility allowance for value types that
genuinely cross every boundary (`Money`, `Currency`, `Quantity`, strongly-typed ids). Where it is still
used during migration, it has hard limits (`D007`):

- it MUST NOT reference any module;
- it MUST NOT contain business rules or orchestration;
- it SHOULD be small enough to read in one sitting and stable enough to bump rarely;
- it MUST be versioned like a contract, because everything depends on it.

If a type is needed by two modules and is not a value type, it is a **model shared by accident**. The
answer is not the kernel — it is duplication at the boundary, or a redesign of who owns the concept.

---

## P4. Dependency Inversion

> **Consumers own their integration abstractions. Providers own their promises. Neither dictates the
> other's internals.**

P4 is the principle most often misread as "put interfaces in a shared project". It means the opposite.

ACIMA distinguishes two kinds of abstraction at a boundary:

| Kind | Owner | Lives in | Example |
|------|-------|----------|---------|
| **Provided port** — a capability the module promises | the provider | its contracts unit | `ICatalogReader`, `IPaymentGateway` |
| **Consumer-owned port** — the exact shape *this* consumer needs | the consumer | its implementation | an internal `IPriceLookup` adapted from `ICatalogReader` |

### Obligations

- **P4.1** A module MUST declare what it needs through explicit constructor or initialisation
  parameters. Runtime resolution of a peer module from a container or global registry is a violation
  (`L004`).
- **P4.2** A provider's contracts MUST NOT be shaped around a single consumer's needs: no consumer
  names, consumer-specific views, or consumer-driven optional parameters in contract types
  (`G003` review, `C007`).
- **P4.3** When a consumer needs a narrower or differently-shaped capability than the provider
  promises, the consumer MUST declare that port in its own implementation and adapt — it MUST NOT
  demand a new contract type.
- **P4.4** Abstractions over infrastructure MUST live in the module that uses them, never in a
  cross-module project (`D002` if published, `L003` if leaked).
- **P4.5** Wiring — deciding which implementation satisfies which port — MUST happen in the
  composition root, not inside modules (`D006`).

### The test

Ask: *if this consumer disappeared tomorrow, would the provider's contract change?* If yes, the
contract is consumer-shaped (P4.2 violated). Ask: *if this provider changed its internals, would the
consumer change?* If yes, the boundary is leaking.

---

## P5. Strict Dependency Boundaries

> **No module references another module's implementation. No cycles. Layering inside a module holds
> in one direction only.**

### Obligations

- **P5.1** A module MUST depend on other modules only through their contracts units (`D001`).
- **P5.2** The module dependency graph MUST be acyclic (`D005`).
- **P5.3** A reference MUST NOT deliver an implementation transitively (`D008`).
- **P5.4** Inside a module, domain and application logic MUST NOT depend on infrastructure or
  delivery mechanisms (`L001`). Dependencies point inward, to the domain.
- **P5.5** A module MUST NOT reference the host or composition root (`D006`).

### Required reading of "acyclic"

Acycle is not a style preference. A cycle means the two modules are one module with extra steps:
neither can be tested alone, versioned alone, or extracted alone, and any change to either is a change
to both. ACIMA treats a cycle as a **design error, not a build inconvenience** — if `Orders` and
`Payments` need each other's decisions, one of three things is true:

1. one of them owns a concept it has not been given (usually a process manager or policy);
2. the interaction is a domain event, not a synchronous call (see
   [Runtime boundaries](06-runtime-boundaries.md));
3. the two modules are actually one bounded context and should merge.

`D005` reports the cycle with the exact path, so the conversation starts from evidence.

---

## P6. Immutable by Default

> **Contracts, messages, commands, queries and value objects are immutable. State is set once, at
> construction, and never changes.**

### Obligations

- **P6.1** A contract type MUST NOT expose setters, mutable public fields or any member that changes
  state after construction (`C001`).
- **P6.2** A contract type MUST NOT expose a mutable collection; it exposes an immutable or
  defensively copied one (`C002`).
- **P6.3** A contract type MUST NOT contain business behaviour, IO, orchestration or lifecycle hooks
  — only construction, validation and normalisation (`C003`).
- **P6.4** A contract type MUST NOT read ambient or non-deterministic state: clocks, random sources,
  identifier generators or static mutable caches (`C004`).
- **P6.5** A contract type MUST NOT expose persistence types or query abstractions (`C005`).
- **P6.6** A contract type MUST be explicitly typed: no `object`, `dynamic`, `any` or bare
  dictionaries at a boundary (`C006`).
- **P6.7** A contract type SHOULD be constructible in one step, with required state obvious from its
  constructor (`C007`).

### Why this is not fussiness

A mutable message crossing a module boundary has three properties that are individually fine and
together fatal: it **can be changed by the receiver**, so the sender's state is now shared; it **has
an unbounded lifetime**, so it can be retained, cached or logged after the fact; and it **cannot be
reasoned about concurrently**, so any handler is a data race waiting to be discovered in production.

Immutability also makes the contract *comparable* — value equality means "same request" and "same
event" are decidable, which is what makes idempotency, deduplication, replay and testing tractable.
It makes an event safe to publish twice, retry or archive.

There is a governance benefit too: an immutable contract is much easier to version safely, because
"the shape changed" is a compile-time event rather than a runtime surprise.

### Immutability is about the boundary, not the whole codebase

Inside an implementation, use whatever the language offers: mutable aggregates, ORM-tracked entities,
builders, object mappers. ACIMA constrains what crosses the boundary. The reference implementations
keep domain entities mutable precisely to make this distinction visible.

---

## P7. Independent Evolution

> **A module can change its implementation and its dependencies, and ship, without coordinating with
> its consumers — provided it keeps its contracts' promises.**

### Obligations

- **P7.1** Each module MUST own its persistence: its own schema, tables, migrations, buckets and
  caches (`A001`).
- **P7.2** Each module MUST own its configuration namespace (`A002`).
- **P7.3** Modules MUST NOT communicate through shared mutable statics or global state (`A003`).
- **P7.4** Consumers MUST depend on a contracts version, never on an implementation version
  (`A004`).
- **P7.5** Contract changes MUST be classified as additive or breaking, and a breaking change MUST be
  reflected in the version and the API baseline (`G004`).
- **P7.6** A contracts unit MUST be independently releasable: publishing `X.Contracts` MUST NOT
  require publishing `X`.

### What independence buys you

Independence is not an aesthetic goal; it is an operational one. It is the difference between
"Catalog upgraded its ORM, so we all upgraded" and "Catalog upgraded its ORM, nothing else changed".
It is also the precondition for extraction: a module that already owns its data and its contracts can
become a service without redesign, because the seam already exists.

### Evolutionary pressure this creates

P7 forces the question *who owns this concept?* earlier than most teams ask it. That is the point.
Shared concepts are either value types (kernel), owned by exactly one module (contract), or a process
spanning modules (saga/policy). There is no fourth answer, and the fourth answer is what
`A001`–`A003` exist to prevent.

---

## P8. Executable Governance

> **Architectural violations fail the build. A rule that is not executed is not a rule.**

### Obligations

- **P8.1** Every rule required by the declared conformance level MUST be executed in CI on every
  change.
- **P8.2** Architecture tests MUST produce findings in the standard finding format, so one CI gate
  and one report work for every language.
- **P8.3** A failing architecture test MUST NOT be silenced by disabling the rule; it is fixed or
  waived (P9).
- **P8.4** Every module MUST be declared in the architecture configuration; unclassified production
  source is a violation (`G005`).
- **P8.5** The configuration file, the rule catalog version and the waivers file MUST be version
  controlled with the code.

### Why the mechanism has to be the build

Review attention is a finite resource spent unevenly, and architecture rules are exactly the kind of
thing that is easy to agree with and hard to remember under deadline. NetArchTest, ArchUnit and
Purview exist because teams discovered the same thing: the only architectural decision that survives
is the one the compiler or the test suite refuses to let you break.

P8 is also what makes P9 meaningful. Waivers matter *because* the rules are otherwise absolute: an
explicit exception to an enforced rule is a decision; a comment saying "we know, it's fine" is not.

---

## P9. Explicit Exceptions

> **Every departure from the standard is owned, justified, scoped and dated. Silent suppression is a
> violation of the standard itself.**

### Obligations

- **P9.1** Every waiver MUST name the rule it waives, the unit or path it applies to, an accountable
  owner, a written justification and an expiry date (`G001`).
- **P9.2** An expired waiver MUST fail the build (`G002`). Renewing is an explicit act.
- **P9.3** A waiver MUST be as narrow as possible: one rule, one unit, one reason. Repository-wide
  rule disabling is not a waiver and MUST NOT be used.
- **P9.4** Waivers MUST be reviewed on the cadence their expiry implies — they are debt with a due
  date, not a permission.
- **P9.5** A waiver MUST NOT permit a violation of contract immutability (`C001`–`C006`) for longer
  than one minor version; those are breaking changes, handled by `G004`.

### The waiver record

```json
{
  "rule": "ACIMA-D009",
  "scope": "unit:reports",
  "owner": "team-reporting",
  "reason": "The reporting module reads Orders' read-model view until the analytics migration lands in Q2.",
  "expires": "2027-03-31",
  "reviewedOn": "2026-11-01",
  "ticket": "ARCH-412"
}
```

The value is not the file. The value is that the exception appears in a report with an owner and a
date, so it is *impossible to forget* and *impossible to hide*. The most common outcome of writing
one of these is that the author solves the problem instead.

---

## P10. Service-Aligned Topology

> **A service is one product responsibility, one directory and one naming root. Every project is
> named for the service that owns it.**

### Obligations

- **P10.1** Every service MUST live under `services/<Service>/`, and every project under that
  directory MUST start with `<Service>.` (`ST-1`, `ST-3`).
- **P10.2** A project name MUST contain exactly one service name; a vendor project adds exactly one
  vendor qualifier (`<Service>.<Vendor>`), and an inter-service contract contains exactly two service
  names (`<Source>.<Target>`) (`ST-7`).
- **P10.3** A service MUST have one responsibility. If its description needs "and", it is two
  services (`ST-2`).
- **P10.4** A service MUST be deployable independently of the platform it runs on; deployment
  choices belong to the host and adapters (`ST-12`).

### Why names are architecture

A project name is the first thing a reviewer reads and the last thing a new joiner learns. When names
do not identify the owner, ownership is discovered by asking people. When they do, the graph is
readable from the directory tree, and a misplaced project is visible before it compiles.

## P11. Layer Contract Independence

> **Every outward-facing layer owns its contract surface. No contract project serves two layers.
> Every boundary has an explicit transform.**

### Obligations

- **P11.1** Every outward-facing layer MUST have its own contracts project named
  `<Service>.<Layer>.Contracts`, with zero references (`ST-4`, `ST-5`).
- **P11.2** A contracts project MUST NOT be the boundary type of two layers, and MUST NOT be
  re-exported, inherited from or aliased by another layer (`ST-4`).
- **P11.3** The caller MUST map its own DTO to the callee's contract at every boundary; the callee
  MUST NOT reference the caller's contracts (`ST-6`).
- **P11.4** The domain layer MUST NOT have a contracts project. The domain model is internal; a
  concept that crosses a boundary is copied into that boundary's contract (`ST-4`, `ST-9`).
- **P11.5** A transform MUST be pure, testable and owned by the calling layer; it carries no business
  rules.

### Why independence beats a shared DTO

A DTO shared by two layers is a schema two release cycles now have to agree on. The first shared
field is convenience; the second is a coordinated deploy. Two small DTOs and a mapper cost less,
and they make the boundary visible in code rather than implicit in a type both sides happen to
import.

## P12. Absolute Contract Isolation

> **Contracts reference nothing at all — no project, no package, no shared kernel, no framework. This
> is the default for new systems.**

### Obligations

- **P12.1** A contracts project MUST have zero project, package and module references (`ST-5`).
- **P12.2** The shared kernel MUST NOT be referenced from a contracts project. Value types are
  primitives or types declared inside the contract project and duplicated where needed.
- **P12.3** Contracts MUST NOT carry serializer, ORM, DI or validation-framework attributes. Serialization
  and validation frameworks are configured outside the contract.
- **P12.4** Constructor or factory validation is permitted; business behaviour, IO and ambient state
  are not.
- **P12.5** Every contracts project MUST compile alone, with no other project on the build path.

### Relationship to P3

Base ACIMA permits the shared kernel in contracts (P3.5) as a legacy compatibility allowance. The
default removes that exception because absolute isolation is checkable in one line and because a
kernel reference makes every contract release depend on the kernel's release. Repositories that have
not migrated remain governed by P3.5; new repositories MUST use absolute isolation.

## P13. Product-Oriented Services

> **Services serve product outcomes: UI and API enforce the same workflow, core rules live in the API
> domain, and service shape follows the user experience and scaling needs rather than the
> infrastructure.**

### Obligations

- **P13.1** UI and API MUST enforce the same workflow: the same states, transitions, validations,
  permissions and error semantics (`ST-11`).
- **P13.2** The API domain MUST enforce the core product rules. A UI MAY pre-validate for speed, but
  MUST NOT be the only place a rule exists.
- **P13.3** Deployment and vendor SDKs MUST appear only in adapters and the host; no cloud, queue,
  database or vendor type may appear in api, application, domain or contracts (`ST-12`).
- **P13.4** A service boundary MUST follow a product outcome and its scaling needs, not a database
  schema, a framework module or an org chart.

### Why the product comes first

A rule enforced only in the UI is a suggestion; a service shaped by its database is a schema with
endpoints. The product outcome is the unit of design, and the architecture exists to keep that
outcome enforceable as the system grows.
