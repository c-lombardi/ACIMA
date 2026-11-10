# 6. Runtime boundaries

Chapters 1–5 constrain the compile-time graph. This chapter constrains what happens when the system
runs: how modules call each other, what may share a transaction, who owns configuration, and what
changes when a team deliberately adopts the optional service-topology profile.

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

## 6.2.1 Retry ownership

A retry is an effect policy, not a generic resilience decoration. Where retries exist, one component
MUST own the decision and the caller MUST be able to tell whether it may retry (`P15.1`, `P15.2`;
`A010`, `A011`):

- the owner is the module or adapter that owns the effect, or a composition boundary's declared
  delivery policy;
- the policy is bounded and visible: which failures are retryable, the attempt limit, backoff,
  timeout and what happens when the budget is exhausted (`A006`);
- a retry of a command that may already have been applied requires a duplicate-execution rule
  (§6.3.1), not merely a retry count;
- an unknown outcome MUST NOT be retried as though the first attempt definitely failed. The owner
  either establishes the outcome or treats the retry as a duplicate-sensitive operation;
- retries MUST NOT multiply non-idempotent effects (charges, emails, inventory decrements) merely
  because the transport failed.

A library, framework or broker MAY implement the policy. Its presence is not evidence that ownership
is clear; the module's contract and failure semantics must still say what a retry means. This
obligation is conditional: an operation with no retry behaviour has no retry owner to declare.

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

## 6.3.1 Idempotency and duplicate execution

Where duplicate execution is possible and could affect correctness — retryable commands,
at-least-once delivery, webhook redelivery, user double-submission — the effect owner MUST define what
a duplicate does (`P15.2`; `A011`):

- the deduplication identity is derived from the business operation, not from a transport message id
  alone, and it is recorded in the owner's own persistence boundary (`A001`);
- the duplicate either has no additional effect or returns the original outcome; it MUST NOT perform
  the effect twice;
- the record has a retention period and a concurrency rule, so two simultaneous duplicates cannot
  both win;
- the consumer distinguishes “already applied” from “newly applied” where the caller needs to know;
- an idempotency key is not required for every operation. A naturally idempotent write, a read or a
  one-shot local operation may need no key at all.

No ACIMA rule claims exactly-once delivery. The obligation is explicit, owned duplicate behaviour,
with the storage and concurrency assumptions stated. Static analysis cannot establish that the key is
correct or that the dedup record is committed atomically; `A011` is therefore manual evidence.

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
| A module's transaction boundary is inside its implementation, never at a composition boundary. | The composition boundary does not know the invariants; it cannot decide what is atomic. |
| Cross-module consistency is eventual and explicit (saga, outbox, reconciliation). | "We'll just wrap it in a transaction" is the most common boundary breach in code review, because it looks like correctness. |
| Reads may cross modules, but only through contracts (a view). | A join is a write-shaped dependency: it makes the provider's schema part of the consumer. |

If a report needs data from three modules, the answer is a **projection**: a read model built by
subscribing to events, owned by the reporting module. It is slower to build than a three-table join and
survives the first schema change.

## 6.5.1 Transaction ownership

When a transaction is used, exactly one module owns it (`P15.1`; `A010`):

- the transaction begins and commits inside the owning implementation, around the state and outbox
  writes it is responsible for;
- a composition boundary MUST NOT open a transaction and pass it across modules, and a consumer MUST
  NOT enlist a provider's connection or unit of work;
- a cross-module workflow uses an outbox, a saga or reconciliation with an explicitly owned
  intermediate state, never a distributed transaction hidden behind a shared connection;
- the contract states whether a command is transactional, what it guarantees on return, and what a
  caller must do when the outcome is unknown (`A012`).

The choice of transaction API is not normative. A framework-managed request transaction is valid when
its boundary is the module's own work and the module can state its guarantees. “We use transactions”
is not evidence that the boundary is correct.

## 6.5.2 Atomicity and recovery

A multi-step operation MUST establish its consistency guarantee rather than assume that all-or-nothing
atomicity is available or appropriate (`P15.4`; `A013`). The owner chooses and documents one of:

- **atomic** — the state change and its required outbox or audit record commit together;
- **recoverable** — an intermediate state is durable and a later step can resume it;
- **compensating** — a committed step has an owned compensation for the failure path;
- **reconciled** — the system compares its state with the external source of truth and repairs drift.

Partial completion MUST be observable, and an interrupted workflow MUST have an owner who can resume,
compensate or reconcile it. A retry is not a recovery strategy by itself. Where the effect is critical,
the evidence required by `A013` is proportionate to the failure mode: a test of the partial-failure
path, a reconciliation report, an operational alert or a recorded review. This chapter does not require
distributed transactions, global locks or universal atomicity.

## 6.5.3 One owner per consistency boundary

`A015` asks a different question from §6.5.1 and §6.5.2: not *which API* opens a transaction, but
*who owns the guarantee*. A multi-step state change MUST name one owning component and state what the
caller can rely on when the operation returns — committed, accepted, recoverable, compensating or
unknown. The owner is normally the module that owns the state; a declared delivery policy at a composition
boundary may own a workflow, but it MUST NOT own a consistency decision whose invariants live inside
a module.

Review questions:

1. Which component decides that the step succeeded, and where is that decision recorded?
2. Which intermediate states can a concurrent reader observe, and are they legal?
3. If the operation stops between steps, who resumes, compensates or reconciles it?
4. Does the contract say which of those outcomes is possible, or does it imply all-or-nothing?

"We use a transaction" is not an answer to any of these. Neither is a caller wrapping two module
calls and calling the result atomic. The obligation is conditional: a single local write may need no
consistency discussion at all. `A015` is manual in every profile because ownership and guarantees
are design intent, not syntax.

## 6.6 Configuration ownership

Configuration is a boundary like any other (`A002`).

- Each module reads only its own namespace: `catalog:*`, `orders:*`, `payments:*`.
- The composition boundary passes configuration **into** the module's constructor or composition
  function; the module does not reach into a global configuration object for another module's keys.
- Secrets follow the same rule: a module never reads another module's secret.
- Shared infrastructure settings (connection pool sizes, log level) belong to the composition
  boundary's own namespace, not to a module's.

The composition boundary resolves and validates values once, groups related values into typed
settings, and passes them in. A module MUST NOT read `os.environ`, `process.env` or a global
configuration object for a value a caller could supply (`A005`). A meaningful timeout, retry, limit
or similar policy MUST have one identifiable, immutable declaration at its appropriate owner, or an
explicit configuration source (`A006`; chapter 14); equal literals do not establish equal meaning.

The test is mechanical: if you deleted a module, would the remaining configuration still make sense?
A key like `orders.database.catalog` answers no, and `A002` flags the shape even before you find the
reader.

## 6.7 The composition boundary in detail

```csharp
// composition boundary — the only place where implementations meet ports
var catalog  = new CatalogModule(new SqlCatalogStore(connectionString));
var payments = new PaymentsModule(new HttpPaymentGateway(options));
var orders   = new OrdersModule(catalog.Reader, payments.Gateway, clock);
```

Obligations:

- **Construction order is explicit.** A module receives its dependencies; it does not discover them.
  (`L004` forbids the container-as-registry shortcut.)
- **The graph is named at the boundary.** Register and construct module-owned components explicitly;
  a scan or convention that selects them is `D013` (chapter 15).
- **Dependencies arrive at construction.** Property and field injection are `D014`; a framework may
  activate an entry point, but its required dependencies belong in the declared constructor.
  Framework infrastructure registration is not module-owned construction.
- **Functional composition does not erase the dependency.** A closure or callback must receive its
  collaborator as a parameter or declared field (`D015`); partial application of a collaborator is
  boundary wiring, not component-internal setup (`D016`; chapter 16). Pure transformations are
  exempt.
- **No module is a singleton with global state** (`A003`). If two consumers need the same instance for
  performance (a cache, a connection pool), that instance is created at the composition boundary and
  passed in — it is a dependency, not a static.
- **Lifetime is decided at the composition boundary.** A module declaring a static instance of itself
  is a module that has decided it is a process. Stateless shared services SHOULD be shared rather
  than registered transient (`A007`); a shared component MUST NOT directly capture a scoped
  dependency (`A008`); and shared mutable state MUST have an explicit owner, isolation boundary and
  concurrency policy (`A009`). Thread safety, tenant isolation, resource cleanup and distributed
  consistency remain review obligations, not consequences of a registration (chapter 17).
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

## 6.9 Cancellation and partial completion

Cancellation is a request, not a guarantee. Where the execution environment supports it and an
operation is long-running or externally cancellable, the owner MUST define what cancellation means
(`P15.2`, `P15.3`; `A011`, `A012`):

- which states are cancellable, and what state is left behind after a cancellation request;
- whether cancellation is best-effort before a commit and impossible after it;
- how the caller learns that work completed, stopped partway, or continued despite the request;
- who performs cleanup or compensation for a partially completed effect;
- how cancellation interacts with retries and duplicate execution, so a cancelled attempt cannot be
  retried as a new effect without deduplication.

A component that cannot safely stop MUST report that honestly rather than acknowledge cancellation and
continue silently. A completed durable effect MUST NOT be reported as cancelled; it is a completed
effect with a separate compensation, if one exists. ACIMA does not require a cancellation parameter on
every method, and an unused or ignored token is not evidence of cancellation support.

## 6.10 Telemetry and observability

Logging, metrics and tracing are also runtime boundaries. They cross out of the module and may be
read by operators, auditors, customers and later code. `A014` requires them to *observe* behaviour:

- telemetry MUST NOT make a business decision. A logger, interceptor or metric callback that decides
  whether to proceed, what to return or whether a failure is swallowed has become business logic in
  the wrong place;
- telemetry MUST NOT replace a required output. A business event, a required audit record and an
  operational diagnostic are different things: the event carries a fact other components act on, the
audit record carries accountability and retention, and the diagnostic explains runtime behaviour.
  A best-effort log line is not an audit record;
- emission failure MUST have a declared behaviour. It must not silently change the business outcome,
  and it must not turn a successful effect into a reported failure unless the record is part of the
  effect's contract;
- telemetry MUST NOT conceal a meaningful nondeterministic input or external dependency. Logging the
  result that was computed is observation; computing the result inside the telemetry path is not.

ACIMA does not prescribe a logging framework, a metric taxonomy, a trace format, log levels or a
retention period. It requires the owner, the purpose and the failure behaviour of each category to be
reviewable. Chapter 14 governs secret and sensitive values: an operational diagnostic MUST NOT become
the place a secret is written. `A014` is manual in every profile because whether a call observes or
alters behaviour is a semantic judgement.
