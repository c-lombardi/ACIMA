# 6. Runtime boundaries

Chapters 1–5 constrain the compile-time graph. This chapter constrains what happens when the system
runs: how modules call each other, what may share a transaction, who owns configuration, and what
changes when a module becomes a service.

## 6.1 Three ways to cross a boundary

| Mechanism | Coupling | Transaction | Use when |
|---|---|---|---|
| **Port call** (synchronous, contract interface) | consumer depends on provider's promise | one transaction, provider owns it | the consumer genuinely needs an answer now |
| **Command dispatch** | consumer knows the provider | provider's transaction | the consumer needs work done, not necessarily a result |
| **Event publication** | provider knows nobody | provider's transaction + outbox | the consumer's reaction is *not* required for correctness of the fact |

Rule of thumb: **the more a consumer can tolerate not knowing, the weaker the mechanism it should use.**
Most teams reach for a synchronous port call when an event would do, and pay for it in availability,
latency and coupling.

## 6.2 Synchronous calls and availability

A port call means the consumer's request now depends on the provider being up and fast (`P7`). ACIMA
does not forbid it — some questions need answers — but requires that the dependency be *visible*:

- The port must be in the provider's contracts, so the coupling is declared, not incidental.
- The consumer must have a defined behaviour when the provider fails (degrade, fail, retry, fall back).
  A synchronous call with no failure path is an outage waiting to be shared.
- The call must not happen inside the consumer's own database transaction. If it does, the consumer's
  transaction is now as long as the provider's latency, and locks are held across a network hop.

**Never**: a synchronous call back into a module that is already in the call stack. That is the
runtime shape of a compile-time cycle (`D005`), and it produces deadlocks and timeout cascades
rather than a design conversation.

## 6.3 Events and the outbox

An event is published **as part of the transaction that produced the fact**. In-process, that is
straightforward: collect events on the aggregate, dispatch after the transaction commits. Across
processes, it requires an outbox: the event row is written in the same transaction as the state change,
and a relay publishes it afterwards.

```
BEGIN
  UPDATE orders SET status = 'placed'
  INSERT INTO orders.outbox (event_id, type, payload)
COMMIT
-- relay reads orders.outbox and publishes
```

The outbox table belongs to the **publishing module's schema** (`A001`). No other module reads it; they
consume the event.

Delivery is at-least-once, so **every consumer must be idempotent**. That is why contracts carry stable
identities (an event id, an aggregate id) and why `P6`'s value equality matters: a duplicate is
recognisable only if the message is comparable.

## 6.4 Sagas, process managers, and the "who owns this decision" question

When a workflow spans modules and cannot be a single transaction, one module owns the workflow as a
**process manager**: it subscribes to the events it needs and issues the commands it decides on.

- The process manager's state is owned by the module that hosts it (`A001`).
- It reacts to facts; it does not read other modules' databases to decide.
- It carries compensating actions for partial failure (refund, cancel, release stock).
- It is the answer to "A and B need each other" — the *reason* the cycle in `D005` is almost always a
  missing process manager.

A saga is more work than a transaction. That is the price of a boundary, and the boundary is the thing
paying for your ability to change one module without changing the other.

## 6.5 Transactions

| Rule | Why |
|---|---|
| One module, one transaction. A write never spans two modules' data. | Two-phase commit across modules reintroduces the coupling the boundary removed. |
| A module's transaction boundary is inside its implementation, never in the host. | The host does not know the invariants; it cannot decide what is atomic. |
| Cross-module consistency is eventual and explicit (saga, outbox, reconciliation). | "We'll just wrap it in a transaction" is the most common boundary breach in code review, because it looks like correctness. |
| Reads may cross modules, but only through contracts (a view). | A join is a write-shaped dependency: it makes the provider's schema part of the consumer. |

If a report needs data from three modules, the answer is a **projection**: a read model built by
subscribing to events, owned by the reporting module. It is slower to build than a three-table join and
survives the first schema change.

## 6.6 Configuration ownership

Configuration is a boundary like any other (`A002`).

- Each module reads only its own namespace: `catalog:*`, `orders:*`, `payments:*`.
- The host passes configuration **into** the module's constructor or composition function; the module
  does not reach into a global configuration object for another module's keys.
- Secrets follow the same rule: a module never reads another module's secret.
- Shared infrastructure settings (connection pool sizes, log level) belong to the host's own namespace,
  not to a module's.

The test is mechanical: if you deleted a module, would the remaining configuration still make sense?
A key like `orders.database.catalog` answers no, and `A002` flags the shape even before you find the
reader.

## 6.7 The composition root in detail

```csharp
// host — the only place where implementations meet ports
var catalog  = new CatalogModule(new SqlCatalogStore(connectionString));
var payments = new PaymentsModule(new HttpPaymentGateway(options));
var orders   = new OrdersModule(catalog.Reader, payments.Gateway, clock);
```

Obligations:

- **Construction order is explicit.** A module receives its dependencies; it does not discover them.
  (`L004` forbids the container-as-registry shortcut.)
- **No module is a singleton with global state** (`A003`). If two consumers need the same instance for
  performance (a cache, a connection pool), that instance is created by the host and passed in — it is
  a dependency, not a static.
- **Lifetime is decided once, in the host.** A module declaring a static instance of itself is a
  module that has decided it is a process.
- **Modules must be constructible in isolation** for tests: the reference implementations do this
  (`CatalogModule(store)` needs nothing else), and that property is what makes the architecture
  testable rather than merely enforced.

## 6.8 When a module becomes a service

ACIMA's claim is that P1–P7 make extraction cheap. Concretely, extraction requires:

| Step | Already true because |
|---|---|
| Give the module its own process | it has no compile-time dependency on another implementation (`D001`) |
| Give it its own database | it already owns its schema (`A001`) |
| Replace in-process port calls with HTTP/gRPC | the port is already an interface in contracts, with immutable messages (`P2`, `P6`) |
| Replace direct event dispatch with a broker | events are already immutable, versioned facts (`C001`, `5.6`) |
| Version the API | contracts already are the public surface, with a baseline (`G004`) |

What is *not* free: distributed transactions (there are none to convert), latency, partial failure,
and the operational cost of a second deployment. Extraction is cheap in design terms and expensive in
operational terms — which is exactly the trade you want to decide deliberately rather than discover.

The opposite direction is equally important: a service that must be extracted can also be **merged
back**. ACIMA modules are the same shape at either scale, so the decision is reversible.
