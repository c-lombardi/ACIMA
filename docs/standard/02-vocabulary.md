# 2. Vocabulary

ACIMA's rules are only checkable if its words are exact. This chapter fixes the meaning of every term
used normatively. Where a term also has a looser everyday meaning, the difference is called out.

## 2.1 Unit

A **unit** is any boundary the language's build system can see: a project, a package, a module, a
compilation root, or a directory the architecture configuration declares.

Every unit has exactly one **role** and, except for the kernel and the host, exactly one **module**:

| Role | Meaning | May depend on |
|------|---------|---------------|
| `contracts` | A module's public surface | the shared kernel only |
| `implementation` | A module's private code | its own contracts, other modules' contracts, the kernel |
| `host` | The composition root and delivery mechanism | anything |
| `shared-kernel` | Dependency-free value types used by every module | nothing |
| `test` | Verification of one module | anything that module may depend on, plus the module itself |
| `tooling` | Analyzers, generators, build scripts | whatever the tool needs; never part of the product graph |

> **Not to be confused with:** a *module* is the set of units sharing a module name
> (`catalog` → `catalog.contracts` + `catalog`). A module is an ownership concept; units are how that
> concept becomes visible to a compiler.

## 2.2 Module

A **module** is the smallest part of the system that one team owns, can change without coordinating
with another team, and could in principle be extracted. It has:

- a name, used in every unit and in every finding;
- a contracts unit;
- one or more implementation units;
- its own persistence and configuration;
- a bounded context's worth of meaning.

A module is what a microservice would be if you stopped. ACIMA is deliberately neutral about whether
it ever becomes one: a module that satisfies P1–P7 can be extracted without redesign, and one that
does not, cannot.

> **Not to be confused with:** an *assembly*, *jar*, *npm package* or *Go package* — those are units.
> A module often spans several. Also not to be confused with a *layer* (domain, application,
> infrastructure): layers live **inside** a module.

## 2.3 Contracts

A **contracts unit** is the complete, deliberate public surface of a module. It contains:

| Kind | Definition | Example |
|------|------------|---------|
| **Command** | An instruction to do something, addressed to the owning module. Imperative name. | `PlaceOrder` |
| **Query** | A request for a read model. Returns a **view**, never an entity. | `GetOrderById` |
| **Event** | A statement that something happened, in the past tense, published by the owner. | `OrderPlaced` |
| **View** | A read-only projection returned to a caller. Immutable. | `OrderSummary` |
| **Value** | A small value type used by the above. Prefer the shared kernel for cross-cutting ones. | `ShippingAddress` |
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

## 2.5 Host and composition root

The **host** is the executable that wires modules together and adapts them to the outside world:
process entry point, HTTP endpoints, message consumers, scheduled jobs, dependency injection
registration, configuration binding.

The **composition root** is the one place where the object graph is assembled. It MUST live in the
host, and modules MUST NOT know it exists (`D006`).

The host is allowed to reference everything. This is by design: the host is where knowledge of the
whole system is allowed to concentrate, which is exactly what keeps it out of the modules.

> **Not to be confused with:** a module's local `main`/`Program` file for development. If a module can
> start by itself, that entry point is a `host`-role unit, not part of the module's implementation.

## 2.6 Shared kernel

The **shared kernel** is the only unit every module may reference beyond its language's core library.
It holds dependency-free value types that genuinely cross all boundaries: money, currency, quantity,
strongly typed identifiers, and occasionally a `Result` type.

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
  as the consumer needs, satisfied by an adapter written by the consumer or the composition root. A
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

## 2.12 Words ACIMA avoids

| Avoided | Why |
|---------|-----|
| "Layer" as a synonym for module | Layers are slices inside a module; modules are ownership boundaries. Confusing them produces "the Domain project" that every module references. |
| "Shared" | It names a hope, not an owner. Use *shared kernel* with its constraints, or name the owning module. |
| "Service" | Means HTTP service, DI registration, domain service and business unit. ACIMA says *module* for the boundary and *provided port* for the capability. |
| "Contract" meaning "interface" | An interface is one kind of contract type. Using the words interchangeably is how implementations end up in contracts. |
