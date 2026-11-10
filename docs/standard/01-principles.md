# 1. Principles

Fifteen principles. Each states an obligation, the reasoning behind it, and the rules, profile
requirements or manual-evidence obligations that verify it. Automated rules fail a build; manual
rules fail a full conformance claim when their evidence is missing. The principles are ordered so
that each one is only achievable because of the ones before it.

P1–P9, P14 and P15 are the base standard. P10–P13 belong to the service topology profile in
[chapter 11](11-service-topology.md); they are checked by the profile runner as `ACIMA-S001`–`S012`.
P14 is numbered after the profile so that the existing profile identifiers keep their meaning.

| # | Principle | Enforced by |
|---|-----------|-------------|
| P1 | [Module Ownership](#p1-module-ownership) | `D001` `D009` `L003` `A001` `A002` `A003` `C008` |
| P2 | [Contract Isolation](#p2-contract-isolation) | `D002` `D006` `D009` `L003` `G003` |
| P3 | [Zero-Dependency Contracts](#p3-zero-dependency-contracts) | `D003` `D004` `D008` `L002` `C005` |
| P4 | [Dependency Inversion](#p4-dependency-inversion) | `D002` `D013` `D014` `D015` `D016` `L003` `L004` `G003` |
| P5 | [Strict Dependency Boundaries](#p5-strict-dependency-boundaries) | `D001` `D005` `D008` `L001` |
| P6 | [Immutable by Default](#p6-immutable-by-default) | `C001`–`C007` |
| P7 | [Independent Evolution](#p7-independent-evolution) | `A001`–`A006` `G004` |
| P8 | [Executable Governance](#p8-executable-governance) | `G001`–`G005`, the harness contract and the claim model |
| P9 | [Explicit Exceptions](#p9-explicit-exceptions) | `G001` `G002` |
| P10 | [Service-Aligned Topology](#p10-service-aligned-topology) | `ST-1`–`ST-3` `ST-7` (profile, automated) |
| P11 | [Layer Contract Independence](#p11-layer-contract-independence) | `ST-4` `ST-6` (profile, automated) |
| P12 | [Absolute Contract Isolation](#p12-absolute-contract-isolation) | `ST-5` (profile, automated) |
| P13 | [Product-Oriented Services](#p13-product-oriented-services) | `ST-11` `ST-12` (profile, automated) |
| P14 | [Intent-Revealing Naming](#p14-intent-revealing-naming) | `N001` `N002`, `N003` review |
| P15 | [Owned Effects](#p15-owned-effects) | `A010`–`A015` review |

---

## P1. Module Ownership

> **Every module owns its implementation, its abstractions, its dependencies and its domain. No other
> module may own, share or reach into them.**

A module is a unit of ownership before it is a unit of code. It owns:

- its **domain model** — the entities, aggregates and invariants that only it may decide;
- its **implementation** — handlers, services, persistence, integrations, adapters;
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
- **P1.7** An operation exposed at a boundary MUST make its business behaviour visible: the outcome it
  produces, its material preconditions and failure semantics, and the observable effects it may have.
  Visibility is documentation and typed result semantics; it MUST NOT be used to move business rules
  into a contract (`C008`; chapter 6 §6.1).

### The failure it prevents

The `Common`/`Shared`/`Core` project. It starts as five extension methods, becomes the de-facto
domain model, and ends up referenced by everything — at which point ownership is diffuse and every
change is a coordination event. In the default there is no cross-module unit at all: value types live
in the contract that publishes them. A legacy **shared kernel** remains only as a migration allowance
(P3.5), and it is deliberately hostile to growth (`D007`).

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
- **P4.5** Cross-module wiring — deciding which implementation satisfies which port — MUST happen at
  an identifiable composition boundary, not inside a consuming module (`D006`). A module MAY publish
  a composition function for its own internal graph.
- **P4.6** A required input MUST be supplied explicitly at construction and at invocation. An
  optional parameter, a default value or an implicit fallback MUST NOT conceal a dependency or a
  decision the caller owns (`D011`, `D012`; chapter 13). A nullable parameter **without** a default
  is required and permitted: the caller chooses the absence explicitly.
- **P4.7** A meaningful value MUST have one identifiable, immutable declaration at its highest
  appropriate ownership boundary and an intentional classification: a local literal, a named
  constant, a system constant, shared configuration, runtime configuration, deployment
  configuration or a secret (`A006`; chapter 14). Its identity comes from what it represents, not
  from its literal value or identifier alone. Shared values MUST be supplied explicitly. Identical
  text does not establish identical meaning, matching names do not prove equivalence, and
  occurrence count is not an ownership criterion.
- **P4.8** Configuration MUST be resolved and validated at the composition boundary and passed into
  the component that consumes it. A module MUST NOT read ambient environment variables or a global
  configuration object to discover a value a caller could supply (`A005`, `A002`; chapter 14).
- **P4.9** Module-owned components MUST be registered and constructed at an identifiable
  composition boundary. Automatic scanning, convention registration or dynamic discovery MUST NOT
  hide which components exist or which implementation is selected (`D013`; chapter 15).
- **P4.10** Dependencies MUST arrive through a constructor or composition function, not through
  property/field injection, post-construction assignment or a global service locator (`D014`,
  `L004`; chapter 15). A framework MAY activate a component, but it MUST NOT conceal the
  component's declared dependencies.
- **P4.11** A closure, lambda, callback or returned function MUST NOT capture a module-owned
  dependency from a module or enclosing local. The dependency MUST be an explicit parameter or a
  declared field; pure closures over values and transformations remain permitted (`D015`;
  chapter 16).
- **P4.12** Currying and higher-order composition are permitted when every module-owned dependency
  is a parameter. Partial application or method binding of a module-owned dependency MUST happen at
  the composition boundary, not inside a component (`D016`; chapter 16).
- **P4.13** A stateless shared service SHOULD be shared at the longest appropriate lifetime rather
  than repeatedly constructed. A transient lifetime remains valid when per-instance identity,
  isolated mutable state, a short-lived resource or an operation boundary requires it (`A007`;
  chapter 17).
- **P4.14** A component's lifetime MUST be compatible with the lifetimes of the dependencies it
  captures. A shared/singleton component MUST NOT directly capture a scoped dependency; a
  longer-lived component that needs shorter-lived state MUST use an explicit scope, factory or
  operation parameter rather than a service locator (`A008`; chapter 17).
- **P4.15** Shared mutable state MUST have an explicit owner, mutation authority, isolation
  boundary and concurrency policy, and a resource-owning component MUST have an explicit
  initialisation, lifetime and cleanup story. Transient construction is not a substitute for state
  ownership  (`A009`; chapter 17). Thread safety, tenant isolation, resource cleanup and distributed
  consistency remain review obligations, not static-analysis claims.
- **P4.16** A factory, higher-order function or returned component MUST NOT conceal a module-owned
  dependency or its lifecycle ownership. A dependency is declared as a parameter or field whether
  the component is a class, a closure or a factory product, and a factory that resolves a dependency
  from a global container at invocation is a service locator (`D015`, `D016`, `L004`; chapters 16
  and 17). Framework-managed activation remains legitimate when the required dependencies and
  activation path are inspectable (`P4.10`). Pure currying, partial application and higher-order
  composition over values remain permitted.

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
- **P5.5** A module MUST NOT reference a composition boundary, including a host (`D006`).

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
be represented as a service, if the team chooses, without redesign, because the seam already exists.

### Evolutionary pressure this creates

P7 forces the question *who owns this concept?* earlier than most teams ask it. That is the point.
Shared concepts are either value types (kernel), owned by exactly one module (contract), or a process
spanning modules (saga/policy). There is no fourth answer, and the fourth answer is what
`A001`–`A006` exist to prevent.

---

## P8. Executable Governance

> **Architectural violations fail the build. A rule that is not executed is not a rule.**

### Obligations

- **P8.1** Every rule required by the declared conformance level MUST be accounted for in the
  conformance assessment on every change. An automated rule MUST execute through its designated
  enforcement mechanism (`P8.2`); a rule that cannot execute MUST be covered by accepted, current,
  repository-scoped manual evidence. A catalog-manual rule MUST NOT be counted as executed, because
  no portable enforcer decides it. Missing or expired evidence, an unsupported check reported as
  passing, or an incomplete execution map makes the result a **PARTIAL ASSESSMENT**; none of them
  can support a full conformance claim (chapter 8 §8.4, §8.6, §8.9).
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

Manual evidence does not soften P8; it completes it. Some obligations — whether a contract hides
business behaviour, whether an effect owner reports an unknown outcome truthfully, whether recovery
evidence is adequate — cannot be decided from source text. Pretending otherwise would let a clean
automated run stand in for a review nobody performed. P8 therefore requires every required rule to
be *accounted for*, not every rule to be machine-decided: automated rules execute, manual rules carry
named, current, repository-scoped evidence, and the claim layer refuses to call the result full
conformance while either is missing.

---

## P9. Explicit Exceptions

> **Every departure from the standard is owned, justified, scoped and dated. Silent suppression is a
> violation of the standard itself.**

### Obligations

- **P9.1** Every waiver MUST name the rule it waives, the unit or path it applies to, the exact
  finding fingerprint, an accountable owner, a written justification and an expiry date (`G001`).
- **P9.2** An expired waiver MUST fail the build (`G002`). Renewing is an explicit act.
- **P9.3** A waiver MUST be as narrow as possible: one rule, one unit, one reason. Repository-wide
  rule disabling is not a waiver and MUST NOT be used.
- **P9.4** Waivers MUST be reviewed on the cadence their expiry implies — they are debt with a due
  date, not a permission.
- **P9.5 (advisory)** A waiver for contract immutability (`C001`–`C006`) SHOULD NOT outlive one
  minor version and MUST be reviewed at every contract release. Draft 1 does not define a
  standard-version or contract-version field, so this is a review obligation rather than a
  machine-checked rule; `G004` still handles breaking API changes.

### The waiver record

```json
{
  "rule": "ACIMA-D009",
  "scope": "unit:reports",
  "fingerprint": "sha256:1f0c…",
  "owner": "team-reporting",
  "reason": "The reporting module reads Orders' read-model view until the analytics migration lands in Q2.",
  "expires": "2027-03-31",
  "reviewedOn": "2026-11-01",
  "ticket": "ARCH-412"
}
```

The fingerprint is what makes the exception finding-specific: a unit or path alone would suppress
future findings in that scope. The value is not the file. The value is that the exception appears in
a report with an owner, a date and an exact finding, so it is *impossible to forget* and
*impossible to hide*. The most common outcome of writing
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
> is the profile's total-isolation rule and applies only when service topology is explicitly
> selected.**

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
service-topology profile removes that exception because absolute isolation is checkable in one line
and because a kernel reference makes every contract release depend on the kernel's release. Repositories that have
not migrated remain governed by P3.5; new repositories MUST use absolute isolation.

## P13. Product-Oriented Services

> **Services serve product outcomes: UI and API enforce the same workflow, core rules live in the API
> domain, and service shape follows the user experience and scaling needs rather than the
> infrastructure.**

> **Applicability.** P13 applies only in the `service-topology` profile and only when that profile
> is explicitly adopted. Base ACIMA does not require every system to organise around
> product-oriented services, to enforce UI/API workflow parity, or to apply P13.4's service-shape
> requirement. The obligations below are checked as `ST-11`/`ST-12` when the profile is in force.

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

## P14. Intent-Revealing Naming

> **Names communicate responsibility, behaviour, domain meaning and relevant units. Naming syntax
> follows the language; naming semantics follow the architecture.**

This principle applies to every construct a reader navigates by: modules, classes, interfaces,
methods, functions, properties, variables, parameters, constants, events, commands, queries,
enums and exceptions. It does not impose universal casing; it requires that the name and the thing
agree.

### Obligations

- **P14.1** A type, module or component name MUST identify a responsibility or domain concept, not
  merely a generic role. `Helper`, `Manager`, `Processor`, `Utility`, `Common`, `Base`, `Default`
  and `Generic` are not substitutes for a responsibility; a generic role is permitted only when
  the surrounding abstraction makes it precise (`N002`; chapter 18).
- **P14.2** An operation name MUST state the action and its meaningful outcome. A name MUST NOT
  conceal a mutation or external interaction behind a read-named operation; where a side effect
  matters, the name communicates it (`N003`; chapter 18).
- **P14.3** The same domain concept MUST use consistent terminology across contracts,
  implementations, events, commands, queries, persistence abstractions and API boundaries, unless
  a genuinely different concept justifies a different term (`N003`; chapter 18).
- **P14.4** Boolean identifiers SHOULD express a positive condition or decision. Values whose unit,
  scale or distinction is not established by their type MUST communicate it in the name. Unexplained
  local abbreviations MUST NOT replace the domain vocabulary (`N003`; chapter 18).
- **P14.5** Language-specific casing, prefixes and suffixes are conventions, not architecture. They
  MUST follow the target language's established practice, and they MUST NOT be imposed uniformly
  across languages. Semantic naming quality remains a review decision, not a static-analysis proof
  (`N001`, `N003`; chapter 18).

## P15. Owned Effects

> **Every externally visible effect has one identifiable owner, an explicit execution boundary, a
> truthful outcome and evidence proportionate to its criticality.**

An **effect** is anything outside the module's own memory that another actor can observe: a database
write, message publication, payment, email, file write, cache invalidation, audit record or call to a
vendor. ACIMA does not require every effect to be transactional, retryable, cancellable or
idempotent. It requires the architectural decisions that *do* apply to be owned and visible rather
than accidental.

This principle extends P1 (ownership), P7 (independent evolution) and P8 (executable governance) to
the runtime boundary. It does not replace the persistence, configuration and statics obligations in
P7, and it does not prescribe a framework, a messaging product or a distributed transaction.

### Obligations

- **P15.1** Every externally visible effect MUST have an identifiable owning component and execution
  boundary. A caller MUST NOT perform a provider's effect on its behalf, and an effect MUST NOT be
  hidden behind a read-shaped abstraction (`A010`; chapter 6 §6.2.1).
- **P15.2** An operation that owns an effect MUST make the effect's semantics visible: ordering,
  failure and partial-completion behaviour, duplicate handling, retry policy and consistency
  expectations where they apply (`A011`; chapter 6 §6.3.1, §6.5, §6.9).
- **P15.3** An effect owner MUST report a truthful outcome. It MUST NOT report success before the
  effect is durable or accepted, MUST NOT report failure after an irreversible commit as though
  nothing happened, and MUST distinguish an unknown outcome from both success and failure (`A012`).
- **P15.4** An effect whose failure could corrupt data, duplicate a charge, lose a required record or
  leave an operation unrecoverable MUST have evidence proportionate to that risk: a test, a
  reconciliation check, an operational signal or a recorded review. A clean static scan alone is not
  evidence that the effect is correct (`A013`; chapter 6 §6.5.2).
- **P15.5** A meaningful state mutation MUST occur through an identifiable ownership boundary. A
  persistent or shared architectural state mutation belongs to the module or component that owns
  that state, under the persistence and shared-state obligations (`A001`, `A009`; chapter 17).
  Ordinary local mutation inside an owned aggregate, value or operation is normal design and needs
  no separate state-ownership mechanism; this obligation is about state that crosses or outlives the
  operation.
- **P15.6** A multi-step state change or transaction MUST have exactly one identifiable owner and a
  declared consistency guarantee on return. Atomicity is one valid strategy; a recoverable
  intermediate state, an owned compensation or reconciliation are equally valid where the domain
  requires them (`A015`; chapter 6 §6.5.1–§6.5.3).
- **P15.7** Logging, metrics and telemetry MUST observe system behaviour without concealing it,
  replacing a business decision or materially changing the outcome. Operational diagnostics, business
  events and required audit records MUST be distinguishable by owner and purpose (`A014`;
  chapter 6 §6.10).

### What this does not require

- Every multi-step change does not need all-or-nothing atomicity. A workflow may define a recoverable
  intermediate state, a compensating action or a reconciliation process instead.
- Every command does not need an idempotency key. The obligation applies where duplicate execution is
  possible and could affect correctness.
- Every method does not need a cancellation parameter. Cancellation applies where the execution
  environment supports it and the operation is long-running or externally cancellable.
- Every module does not need its own broker, outbox or saga framework. The owner may be a
  composition-boundary policy, an adapter, a library or a managed platform capability, provided the
  ownership is visible.
- A local mutation inside an aggregate does not need a separate state-ownership mechanism. P15 is about
  observable effects and the consistency contract around them; ordinary in-memory mutation remains
  governed by the module's internal design (chapter 17).
- Every log line does not need a business-event schema or a tracing abstraction. Operational
  diagnostics remain operational; the obligation is that telemetry is not the place where a business
  decision is made, a failure is swallowed or a required audit record is replaced by a best-effort
  message.

### Why a thin principle rather than nine rules

The existing principles already establish who owns data, configuration, dependencies and contracts.
Side effects, retries, transactions, idempotency and cancellation are runtime consequences of those
ownership decisions, not a second architecture. P15 makes the consequences explicit while leaving the
choice of mechanism to the team and the domain. A retry policy is required only when retries exist; a
transaction boundary only when consistency requires one; an idempotency key only when duplicates can
harm. This is the same conditional style as P7's configuration ownership: the obligation is triggered
by the design, not imposed on every operation.

### Enforcement boundary

The P15 obligations are assessed through `A010`–`A015`, all manual-evidence rules. No portable
static analysis can prove that an effect owner is correct, that an unknown outcome is represented,
that a consistency boundary has one owner, or that telemetry does not alter behaviour. The enforcers
report those rules as `executed: false`; a full claim needs repository-scoped manual evidence. A
source scan that merely finds a retry library, a transaction API, a cancellation token or a logging
call proves none of the obligations.
