# 2. Vocabulary

ACIMA's rules are only checkable if its words are exact. This chapter fixes the meaning of every term
used normatively. Where a term also has a looser everyday meaning, the difference is called out.

## 2.1 Unit

A **unit** is an artifact that the language's build system or repository layout can identify: a
project, a package, a namespace, a compilation root, a directory, or an explicit source set declared
by the architecture configuration. A unit is a representation, not an ownership boundary.

Every unit has exactly one **role**. Every `contracts` or `implementation` unit names the module it
represents. A module may span several units, and no unit is assumed to be a module:

| Role | Meaning | May depend on |
|------|---------|---------------|
| `contracts` | A module's public surface | nothing (default); the shared kernel is legacy |
| `implementation` | A module's private code | its own contracts, other modules' contracts, the kernel (legacy) |
| `host` | A declared composition boundary; it may be executable or non-executable (see §2.5) | anything |
| `shared-kernel` | Dependency-free value types used by every module | nothing |
| `test` | Verification of one module | anything that module may depend on, plus the module itself |
| `tooling` | Analyzers, generators, build scripts | whatever the tool needs; never part of the product graph |

> **Not to be confused with:** a *module* is the ownership boundary, not the artifact that represents
> it. One module may be represented by a project, package, namespace, directory, assembly, library,
> service or another suitable mechanism. Those are implementation representations; they do not define
> what a module is, and there is no required one-to-one correspondence between modules and any of
> them.

## 2.2 Module

A **module** is an identifiable architectural ownership boundary. It:

- owns its implementation;
- owns its internal state and data;
- exposes explicitly defined contracts;
- controls access to its implementation;
- declares its dependencies;
- participates in an explicit composition model;
- has identifiable lifecycle and side-effect responsibilities.

A module has a name, one or more contracts and implementation representations, its own persistence
and configuration where applicable, and a coherent set of responsibilities. It may be represented by
a project, package, namespace, directory, assembly, library, service or another mechanism, but it is
defined by ownership, not by any of them.

A module is not defined by:

- a programming-language construct;
- a project or directory structure;
- a package or distribution format;
- a deployment unit, process boundary or runtime host;
- an application architecture or organisational structure.

A module need not be independently deployable, executable or hosted. Those are properties of a
particular representation, not requirements of the standard. ACIMA is deliberately neutral about
whether a module is ever extracted into a separately deployed service: a module that satisfies P1–P7
keeps that option open, and one that does not cannot.

> **Not to be confused with:** an *assembly*, *jar*, *npm package*, *Go package* or *service* — those
> are units or deployment representations. A module often spans several. Also not to be confused
> with a *layer* (domain, application, infrastructure): layers are internal roles inside a module or
> a service profile, not ownership boundaries.

**Modes and ownership.** `acima.config.json.mode` selects how this definition is applied. In
`base` mode the module is the ownership unit and has exactly one contracts unit (P2.1), with the
legacy shared-kernel allowance (P3.5). In `service-topology` mode the service is the ownership
envelope; the service is the unit for P1/P7 ownership, each outward-facing layer has one contracts
project, the domain has none, and contracts reference nothing (P11.1/P11.4, P12.2). P2.1 and P3.5
are **superseded**, not reinterpreted. Every other P1–P9 obligation still applies.

## 2.3 Contracts

A **contracts unit** is the complete, deliberate public surface of a module. It contains:

| Kind | Definition | Example |
|------|------------|---------|
| **Command** | An instruction to do something, addressed to the owning module. Imperative name. | `PlaceOrder` |
| **Query** | A request for a read model. Returns a **view**, never an entity. | `GetOrderById` |
| **Event** | A statement that something happened, in the past tense, published by the owner. | `OrderPlaced` |
| **View** | A read-only projection returned to a caller. Immutable. | `OrderSummary` |
| **Value** | A small value type used by the above. Declare it locally or use primitives; the kernel is legacy. | `ShippingAddress` |
| **Provided port** | An interface the module promises to satisfy. | `ICatalogReader` |
| **Result / error** | A typed outcome, including failure cases the caller must handle. | `PlaceOrderResult` |

A contracts unit is **not** a shared model. It contains no entities, no persistence types, no
framework types, no cross-module composition. If a type is in contracts, the module is promising it
for as long as that contract version lives.

> **Not to be confused with:** a *contract* in the legal sense of "an OpenAPI document". ACIMA
> contracts are language-level types. When a boundary becomes a network boundary, those types are what
> the OpenAPI document or message schema is generated from, or validated against.

## 2.4 Implementation

An **implementation unit** is where a module's actual work happens: domain entities and aggregates,
application services, handlers, persistence, adapters, mappers, migrations, background jobs.

Two invariants:

1. Its public types are **invisible** outside the module — unreachable by the language, by
   convention plus rule, or both.
2. Its dependencies — packages, infrastructure choices, versions — are **its own**. Another module
   never inherits them.

> **Not to be confused with:** "the code that isn't an interface". A module's implementation includes
> its domain model, which is the most important code it has. The word is structural, not pejorative.

## 2.5 Composition boundary and host

A **composition boundary** is an identifiable place where dependencies are selected and module
graphs are assembled. It may be:

- a library consumer constructing dependencies;
- a package initialisation function or public factory;
- an executable entry point;
- a framework integration point;
- a plugin host or loader;
- a service composition mechanism;
- a test fixture; or
- another explicitly designated construction boundary.

A **host** is one optional representation of a composition boundary: an executable or delivery unit
that wires modules together and adapts them to the outside world. Process entry points, HTTP
endpoints, message consumers and scheduled jobs are host concerns; they are not the only valid
composition surfaces.

There MAY be more than one composition boundary. Each MUST declare its scope, and together they MUST
make the system's construction inspectable. There is no requirement for one global application-level
composition root. Modules MUST NOT know a composition boundary exists (`D006`); a module MAY publish a
composition function for its own internal graph.

The `host` role in `acima.config.json` denotes a declared composition boundary. It does not imply a
process, executable or deployment: a package initializer, library factory, plugin loader, test
composition unit or other designated surface may use the same role.

> **Not to be confused with:** a module's local `main`/`Program` file for development. If a module can
> start by itself, that entry point is a `host`-role composition unit, not part of the module's
> implementation.

## 2.6 Shared kernel

The **shared kernel** is a legacy compatibility unit. It holds dependency-free value types that
genuinely cross all boundaries: money, currency, quantity, strongly typed identifiers, and occasionally
a `Result` type. Under the default, contracts do not reference it; value types are declared inside the
contract project that needs them, or represented by primitives.

Constraints (`D007`):

- no references to modules, contracts or third-party packages;
- no business behaviour — construction, validation, equality and pure value arithmetic only;
- no IO, no clock, no ambient state;
- versioned like a contract, because the whole system depends on it.

> **Not to be confused with:** a "common", "shared", "core" or "utils" project. Those are the
> anti-pattern the kernel exists to bound. The test: **would removing this type from the kernel force
> any module to know another module's model?** If not, it does not belong there.

## 2.7 Boundary crossing

A **boundary crossing** is any reference from one module to another. There are exactly four permitted
kinds, all through contracts:

| Kind | Direction | Coupling | Use when |
|------|-----------|----------|----------|
| **Command dispatch** | consumer → provider | consumer knows the provider exists | the consumer needs work done now |
| **Query** | consumer → provider | consumer knows the provider and reads its view | the consumer needs data now |
| **Event publication** | provider → everyone | the provider knows nobody | something happened that others may care about |
| **Port call** | consumer → provider | consumer depends on a promised interface | a capability is genuinely shared and synchronous |

Everything else — reading a table, importing a type, touching a static — is not a boundary crossing.
It is a boundary breach.

## 2.8 Provided port and consumer-owned port

- **Provided port** — an interface in the provider's contracts unit that the provider implements. A
  promise: "I will do this, with this shape, for as long as this version lives."
- **Consumer-owned port** — an interface declared inside the consumer's implementation, shaped exactly
  as the consumer needs, satisfied by an adapter written by the consumer or at a composition
  boundary. A
  need, not a promise. See [P4](01-principles.md#p4-dependency-inversion).

A consumer-owned port never appears in any contracts unit. If it does, it has become a provided port
by accident, and the consumer now owns part of the provider's public surface.

## 2.9 Waiver

A **waiver** is the only permitted way to depart from a MUST-level rule. Its shape is defined in
[P9](01-principles.md#p9-explicit-exceptions): rule, scope, owner, reason, expiry, review date,
ticket.

> **Not to be confused with:** an inline suppression comment (`# noqa`, `// NOSONAR`,
> `@SuppressWarnings`). Inline suppression is invisible at the architecture level and is therefore a
> violation of P9.1 wherever an ACIMA rule is what is being suppressed.

## 2.10 Finding

A **finding** is one rule violation produced by a tool, in this format:

```json
{
  "rule": "ACIMA-D001",
  "severity": "error",
  "message": "Orders imports the implementation unit catalog (expected catalog.contracts).",
  "path": "src/orders/impl/place_order.py",
  "line": 4,
  "evidence": "from acima.catalog.impl.repository import ProductRepository"
}
```

`severity` is `error`, `warning` or `info`. The finding format is normative because it is what makes
one CI gate, one report and one conformance runner work across five languages.

## 2.11 Conformance level

L1 **Structural**, L2 **Immutable**, L3 **Autonomous**. Each is a superset of the previous one and
each names the rule categories that must pass. See [Conformance](08-conformance.md).

## 2.12 Service

A **service** is the top-level product ownership envelope defined by the service topology profile
(chapter 11): one responsibility in the product domain, one directory, one name, and the layers and
contracts that deliver it.

A service contains one primary module and its layers. It is not necessarily a network service and not
necessarily deployed alone; it is the thing a team owns, versions and scales. If a service needs two
bounded contexts, it is two services.

> **Not to be confused with:** an HTTP endpoint, a DI registration, a domain service class or a
> microservice. Those are implementation details or deployment choices; the service is the ownership
> boundary.

## 2.13 Layer

A **layer** is a slice inside a service that faces one direction:

| Layer | Faces |
|---|---|
| `Api` | the transport boundary |
| `Application` | the use-case boundary |
| `Domain` | the business rules |
| `Infrastructure` | persistence and runtime adapters |
| `Integrations.<Vendor>` | one third-party integration |

Layers are not modules and are never shared across services. A layer project is named
`<Service>.<Layer>` and lives under that service's directory.

## 2.14 Layer contract

A **layer contract** is the DTO and port surface one layer exposes to its caller, in
`<Service>.<Layer>.Contracts`. It has zero references (P12) and contains only boundary types. It is
not shared with another layer; the caller maps into it.

## 2.16 Required input

A value a component or operation needs in order to behave as specified. A required input is supplied
by its caller at construction or invocation; it is not resolved by the component, defaulted into
existence, or inferred from absence. A nullable value may be a required input: `DeliveryDate?` with
no default still requires the caller to pass `null` deliberately. Chapter 13 defines the obligation;
`D011` and `D012` enforce it.

**Not:** an optional parameter with a default. That is an *omitted* input, and the implementation
chooses the value — the opposite of a required input.

## 2.15 Inter-service contract

An **inter-service contract** is the message vocabulary one service sends to another, in a project
named `<Source>.<Target>`. It contains data only, exactly two service names, and a direction. It is
owned by the source and reviewed by the target.

## 2.16 Vendor contracts and adapter

A **vendor contracts project** is the seam between a service and a third-party library:
`<Service>.<Vendor>.Contracts`. It declares the port and the request/result types in the service's
vocabulary, with zero references. The **adapter**, `<Service>.<Vendor>`, implements the port using
the vendor SDK and translates vendor types and failures.

## 2.17 Transform

A **transform** is the explicit mapping at a boundary from the caller's DTO to the callee's contract.
It is pure, testable, owned by the calling layer, and carries no business rules. A transform is what
makes layer contract independence real rather than aspirational.

## 2.18 Adapter

An **adapter** is an implementation unit that holds exactly one declared third-party package. It
implements a port, maps vendor types to the port's types, and translates vendor failures into the
contract's typed failures. Nothing else may import the vendor (`L005`), and no vendor type may leave
the adapter (`L007`).

> **Not to be confused with:** a wrapper class that merely renames vendor methods. An adapter converts
> vocabulary; a wrapper forwards it.

## 2.19 Integration port

An **integration port** is a contracts unit declaring a capability the system needs from a vendor, in
that system's own types. It is dependency-free (`D010`); its implementation is one adapter. It is not
required to be a DTO, and `C007` does not apply to it (chapter 5 §5.12).

> **Not to be confused with:** a *provided port*, which is a capability a module promises to its
> consumers. The test is who changes when it changes: the provider's capability, or the consumer's
> need.

## 2.20 Third-party tier

A **tier** is the declared role of a package: `platform` (runtime or framework surface, banned from
contracts, no adapter), `integration` (IO, state, wire format or third-party surface; one adapter and
one port), or `utility` (pure, free inside implementations, but its types may not cross a contract or
port). Tiers live in `externals` in `acima.config.json` and are reviewed, never inferred (`G006`).

## 2.21 Words ACIMA avoids

| Avoided | Why |
|---------|-----|
| "Layer" as a synonym for module | Layers are internal roles inside a module, or slices inside a **service** under chapter 11. A module is an ownership boundary; a layer is not. |
| "Shared" | It names a hope, not an owner. Use *shared kernel* with its constraints, or name the owning module. |
| "Service" used loosely | It can mean HTTP service, DI registration, domain service and business unit. Chapter 11 defines it precisely: the top-level product ownership envelope. Use *module* for the contract boundary and *provided port* for the capability. |
| "Contract" meaning "interface" | An interface is one kind of contract type. Using the words interchangeably is how implementations end up in contracts. |

## 2.22 Configuration category

A **configuration category** is the declared nature and change model of a value: local literal, named
constant, system constant, shared configuration, runtime-adjustable configuration,
deployment/environment configuration, or secret. The category determines who owns the value, whether
it may change without a deployment, and what validation and audit it needs (chapter 14 §14.4).

## 2.23 Meaningful value

A **meaningful value** is a primitive value whose exact content influences behaviour, a business or
security decision, an operational limit, an integration identity or a protocol. It is identified by
what it represents, not by its literal text or occurrence count. It must have one identifiable,
immutable declaration at its highest appropriate ownership boundary, or an explicit configuration
source (`A006`; chapter 14).

An **immutable declaration** is a named binding whose value cannot be rebound or mutated through
that declaration. The language mechanism may be a compile-time constant, a static readonly field, a
final field, a frozen value object or an immutable configuration snapshot. A readonly reference to a
mutable object is not an immutable value.

**Semantic identity** is the meaning a value carries in its domain, including its units, type,
ownership, downstream use and expected change relationship with other values. It is not established
by equal literals or matching identifiers alone.

An **operational value** is a meaningful value that changes how a component behaves under load or
failure — a timeout, retry count, limit, threshold, rate, batch size, retention period, capacity or
concurrency limit. It must have a named owner or an explicit configuration source (`A006`), not
merely a literal at the point of use.

## 2.24 Effect

An **effect** is an externally observable change or interaction: a persistent write, message
publication, payment, email, file write, cache invalidation, audit record or vendor call. Ordinary
in-memory mutation of an object is not an effect in this sense; it is governed by the module's state
ownership. The catalogue uses “effect” for the runtime consequence that must have an owner (`P15`).

> **Not to be confused with:** a domain event. An event is a fact a module publishes; the effect is
> the act of publishing it and the changes that surround that act.

## 2.25 Effect owner

An **effect owner** is the component with authority to perform an effect and to decide its failure,
retry, duplicate and recovery semantics. It is usually the module that owns the affected state, or a
declared adapter or composition-boundary delivery policy acting for that module. Ownership is
straightforward when a reader
can name the owner and locate its boundary; it is not established by the presence of a library.

## 2.26 Execution boundary

An **execution boundary** is the scope within which an effect's ordering and consistency are defined:
a transaction, an outbox write, a single request, an idempotent consumer, a workflow step or a
compensating action. The boundary is part of the operation's contract, not an incidental property of
the framework that happens to invoke it.

## 2.27 Retry owner

A **retry owner** is the component that decides whether a failed effect may be attempted again, with
which backoff and limit, and what the caller sees when the budget is exhausted. The owner may delegate
the mechanism to a library or broker, but remains accountable for the policy (`A006`, `A010`).

## 2.28 Transaction owner

A **transaction owner** is the single module whose implementation begins and commits a transaction
around its own state and outbox writes. A host, consumer or orchestration layer may request work but
MUST NOT own a transaction that spans modules (`A010`; chapter 6 §6.5.1).

## 2.29 Idempotency key

An **idempotency key** is a value that identifies a business operation for duplicate detection. Its
scope, storage, retention and concurrency rule belong to the effect owner. ACIMA does not require a
key for every operation; it requires explicit duplicate behaviour where duplicate execution is
possible and could affect correctness (`A011`).

## 2.30 Partial completion

**Partial completion** is the state in which some steps of a multi-step operation succeeded and others
did not. It must be representable and observable, with a named owner for resumption, compensation or
reconciliation. Partial completion is not evidence of a defect by itself; hiding it is (`A012`, `A013`).

## 2.31 Cancellation

**Cancellation** is a request to stop an operation. It may be best-effort and may arrive after an
irreversible commit. The owner must state whether the operation stopped, completed or continued, and
must not report a durable effect as cancelled (`A011`, `A012`).

## 2.32 Critical effect

A **critical effect** is an effect whose failure could corrupt data, duplicate a charge or other
irreversible commitment, lose a required audit record, or leave a workflow unrecoverable without
manual intervention. Criticality is a property of the effect and its context, not of the component's
size; it determines the evidence required by `A013`.

## 2.33 Business behaviour visibility

**Business behaviour visibility** means a boundary operation states the business outcome it produces,
its material preconditions and failure semantics, and the effects it may trigger. It is a property of
the contract and its documentation (`P1.7`, `C008`), not a requirement to place business logic in the
contract or to make every domain function pure.
