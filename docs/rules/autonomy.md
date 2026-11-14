# Autonomy rules (`A`) and governance rules (`G`)

Fifteen rules. The `A` rules constrain what happens at runtime — data, configuration, values, state and lifetime.
The `G` rules constrain the standard's own bookkeeping, and they are what keep the other rules honest.

Full context: [Dependency model](../standard/04-dependency-model.md) ·
[Runtime boundaries](../standard/06-runtime-boundaries.md) ·
[Executable governance](../standard/07-executable-governance.md).

---

## ACIMA-A001 · Shared database ownership

**Severity** `error` · **Level** L3 · **Principle** P1, P7

> Each module owns its persistence: its own schema, tables, store and migrations. No other module reads
> or writes them.

### Violation

```sql
-- orders module
SELECT p.name, p.price FROM catalog.products p WHERE p.id = ?   -- ❌ reading Catalog's table
```

```python
# orders/impl/repository.py
self.db.execute("SELECT * FROM catalog_products WHERE id = %s", (product_id,))   # ❌
```

### Finding

```
ACIMA-A001  error  Orders queries the catalog schema (catalog.products); each module owns its own tables.
  src/acima/orders/impl/repository.py:42
  self.db.execute("SELECT * FROM catalog_products WHERE id = %s", (product_id,))
```

### Why

A shared table is the strongest coupling in software: it bypasses every contract, every version and
every boundary you built. Catalog cannot rename a column, split a table, change a type or move to a
different store without breaking Orders — and the compiler will never tell you.

This is the rule that turns "modular monolith" from a folder structure into an architecture, and it is
the one that makes extraction to a service possible at all.

### Fix

- Call the owner's provided port (`CatalogReader.Get(productId)`) for reads.
- Subscribe to the owner's events for data you need to keep (`ProductPriceChanged` → your own
  projection table).
- Give the consuming module its own schema for its own copy. Duplicated data with a clear owner is
  normal in ACIMA; shared data with no owner is not.

### Detection

Two levels:

1. **Static**: SQL string literals and ORM model definitions in a module that name another module's
   schema/table prefix. The reference enforcer checks string literals and `__tablename__` /
   `@Table` / `[Table]` declarations.
2. **Runtime (recommended)**: a database user per module, with grants only on its own schema. This is
   the only enforcement that cannot be bypassed, and it is worth doing at L3.

---

## ACIMA-A002 · Cross-module configuration key

**Severity** `warning` · **Level** L3 · **Principle** P1, P7

> A module MUST NOT read another module's configuration keys or secrets.

### Violation

```python
# orders/impl/shipping.py
rates_url = config["catalog.pricing.endpoint"]      # ❌ reading Catalog's configuration
```

### Finding

```
ACIMA-A002  warning  Orders reads the configuration key 'catalog.pricing.endpoint', which belongs to module catalog.
  src/acima/orders/impl/shipping.py:17
```

### Why

Configuration is part of a module's implementation surface. Reading another module's key means that
module can no longer rename, restructure or remove its settings, and that a deployment change in Catalog
silently breaks Orders. It also leaks secrets across module boundaries, which is a security issue rather
than an architectural one.

### Fix

Pass what the module needs as constructor configuration under its own namespace
(`orders.shipping.ratesUrl`), supplied by the host. If the value genuinely belongs to Catalog, ask
Catalog for it through a port — not through the configuration system.

### Detection

Key-prefix analysis: a read of a key whose first segment is another module's name. Warning severity
because shared infrastructure keys (`logging.*`, `otel.*`) are legitimate and must not fire.

---

## ACIMA-A003 · Cross-module mutable static state

**Severity** `error` · **Level** L3 · **Principle** P1, P7

> Modules MUST NOT communicate through shared mutable statics or global state.

### Violation

```csharp
public static class GlobalCache
{
    public static Dictionary<Guid, Product> Products { get; } = new();   // ❌ shared mutable state
}
```

```python
# catalog/impl/cache.py
PRODUCT_CACHE: dict[str, Product] = {}     # ❌ imported and mutated by Orders
```

### Finding

```
ACIMA-A003  error  orders imports and mutates the static state PRODUCT_CACHE owned by catalog.
  src/acima/orders/impl/pricing.py:9
```

### Why

Static state is a boundary crossing that no dependency graph can see, with no lifecycle, no ownership
and no isolation between tests. It also silently breaks the "extract to a service" promise: the state
cannot leave the process.

### Fix

Make the cache an instance owned by the module, injected into whatever needs it. If two modules need the
same cache, the host constructs one instance and passes it — still a dependency, still injectable, still
replaceable in tests.

### Detection

Identify module-level mutable declarations (`static` fields, module-level dict/list assignments,
`global` statements) and flag any access from outside the owning module.

---

## ACIMA-A004 · Version-lock coupling

**Severity** `warning` · **Level** L3 · **Principle** P7

> Consumers depend on a contracts version, never on an implementation version.

### Violation

```json
// orders/package.json
"dependencies": { "@acima/catalog": "1.4.2" }        // ❌ implementation package
```

### Finding

```
ACIMA-A004  warning  Orders depends on the implementation package @acima/catalog; depend on @acima/catalog-contracts.
  src/orders/package.json:12
```

### Why

Depending on the implementation version forces the consumer to upgrade when the provider's internals
change, which is precisely the coupling a contracts boundary is meant to remove. In a monorepo with
project references this shows up as "we all rebuild together"; in a package-based setup it shows up as a
version conflict nobody can resolve.

### Fix

Depend on `X.Contracts` (or its package), with a version range. If a consumer needs something only the
implementation offers, the boundary is wrong — see `D001`.

### Detection

Package manifests: any dependency on another module's implementation package/artifact from within the
product graph.

---

## ACIMA-A005 · Configuration read outside the composition boundary

**Severity** `warning` · **Level** L3 · **Principle** P4.8, P7.2

> A module-owned component MUST NOT read deployment, operational or secret configuration from ambient
> environment variables or a global configuration object. A composition boundary resolves it and
> passes the value in.

### Violation

```python
# orders/impl/shipping.py
import os

rates_url = os.environ["ORDERS_RATES_URL"]      # ❌ resolved inside the module
```

```ts
// orders/impl/shipping.ts
export const ratesUrl = process.env.ORDERS_RATES_URL;   // ❌ resolved inside the module
```

### Finding

```
ACIMA-A005  warning  orders reads the process environment directly; resolve it at a composition boundary and pass the value into the component.
  src/orders/impl/shipping.py:4
```

### Why

A module that reads the environment is not constructible from its declared inputs. Its behaviour
changes with the process it happens to run in, its tests need ambient state, and the value has no
visible owner. In a monolith the coupling is hidden; after extraction it becomes a deployment
failure. A declared `host` unit is a composition boundary and is exempt by design.

### Fix

Resolve and validate the value once at the composition boundary, group related values into a typed settings object,
and require that object in the module constructor or composition function. If the value belongs to
another module, ask for it through that module's port (`A002`).

### Detection

Python and TypeScript scan `implementation` and `adapter` units for `os.environ`, `os.getenv`,
`process.env` and `import.meta.env`. The .NET enforcer scans the same roles for
`Environment.GetEnvironmentVariable(s)` and `ConfigurationManager.AppSettings`/`ConnectionStrings`;
injected `IConfiguration` reads remain review items. The Go enforcer scans implementation and adapter
units for `os.Getenv`, `os.LookupEnv`, `os.Environ`, `os.ExpandEnv`, `os.Args` and selectors in the
`flag` package (including aliased imports); local aliases and shadows are resolved through the AST.
Host and tooling units are excluded because they are composition or operator boundaries. The finding
is a confirmed access; whether the component should receive the value remains a review decision.
Java reports the rule as not executed and requires manual evidence.

---

## ACIMA-A006 · Meaningful value without one immutable owner

**Severity** `warning` → `error` at 2.0.0 · **Level** L3 · **Principle** P4.7

> A meaningful primitive value MUST have one identifiable, immutable declaration at its highest
> appropriate ownership boundary. Its identity is determined by what it represents, not by its
> literal value or identifier alone. Shared values MUST be supplied explicitly, and configuration
> MUST be classified deliberately.

### Violation

```python
# orders/impl/submission.py
def submit(order):
    retry_limit = 3              # ❌ mutable policy declaration
    return gateway.send(order, 3)  # ❌ inline literal; receiving parameter is retry_limit
```

```ts
// orders/impl/submission.ts
export function submit(order: Order): void {
  const retryLimit = 3;          // ✅ named immutable declaration
  let fallbackLimit = 3;          // ❌ unnecessarily mutable
  gateway.send(order, 3);         // ❌ inline literal; receiving parameter is retryLimit
}
```

### Finding

```
ACIMA-A006  warning  orders declares the meaningful value retry_limit mutably; use an immutable constant, readonly field or immutable value object, or document why mutation is genuinely required.
  src/orders/impl/submission.py:3
  classification: candidate
```

### Why

An unexplained `3` cannot be reviewed: nobody knows whether it is a business decision, a vendor
limit, a temporary mitigation or a typo. The rule is not about occurrence count; a value used once
can still be important policy. A name alone is also insufficient: a mutable binding, a duplicate with
a different owner, or a deployment value masquerading as a source constant still obscures ownership.

Equal literals and matching names are not proof of equal meaning. `MaximumOrderAttempts = 3` and
`MaximumPaymentAttempts = 3` are different policies; two `Timeout` values may use different units.

### Fix

Name the value once in the scope that genuinely owns it, make the declaration immutable where the
language supports it, and keep distinct policies separate. If several declarations genuinely share
one meaning, consolidate at their highest appropriate common owner and pass the value explicitly. If
the value varies by environment or deployment, use the appropriate configuration mechanism. If the
literal is genuinely incidental, keep it local and be prepared to explain why at review.

### Detection

Python and TypeScript scan `implementation`, `adapter` and `host` units for meaningful names,
including timeout, retry, limit, threshold, TTL, interval, batch, rate, retention, capacity, delay,
quota, backoff, concurrency, attempts, workers, endpoint, URL, host, port, queue, topic, bucket,
duration, expiry, deadline, window, minimum, maximum, discount, tax, fee, secret, password and
credential. They report candidates for:

- inline literals traced to a local callee's receiving parameter;
- mutable meaningful bindings and writable properties;
- immutable declarations that appear to duplicate another declaration in the same module;
- configuration-looking and secret-looking literals.

Every A006 finding carries `"classification": "candidate"`. Static analysis cannot prove semantic
equivalence, infer units, choose the highest common owner or decide the correct configuration
category. Equal values with different names are not grouped; matching names and values still require
review. Duplicate checks never cross module boundaries. The rule does not rewrite source or perform
automatic refactoring.

Go and Java report the rule as not executed and require manual or AI-assisted review evidence with
source citations. The .NET detector scans `implementation`, `adapter` and `host` units for meaningful
mutable declarations, inline literals at source-declared calls, duplicate immutable values and
configuration/secret-looking literals; it does not infer receiving parameters across an unresolved
overload.

---

## ACIMA-A007 · Unnecessary transient lifetime

**Severity** `warning` → `error` at 2.0.0 · **Level** L3 · **Principle** P4.13

> A stateless application service SHOULD be shared at the longest appropriate lifetime rather than
> registered transient. A transient registration MUST have a defensible reason: independent
> identity, isolated mutable state, a short-lived resource or an operation boundary.

### Violation

```typescript
class OrderValidator {
  validate(order: Order): boolean {
    return order.lines.length > 0;
  }
}

register(OrderValidator, { lifetime: 'transient' });   // ❌ no per-instance state
```

```python
class OrderValidator:
    def validate(self, order):
        return bool(order.lines)

container.add_transient(OrderValidator)                 # ❌ rebuilt for every use
```

### Finding

```
ACIMA-A007  warning  lifecycle.host registers the stateless shared service OrderValidator as transient;
                     share it at the longest appropriate lifetime.
  src/host/registrations.ts:14
  register(OrderValidator, { lifetime: 'transient' });
```

### Why

A service with no per-instance state has no reason to be rebuilt. Transient construction is not
free: it repeats initialisation, defeats caching, makes identity unstable and hides the fact that
the component is safe to share. The common cause is a container default, not a design decision.

This is not a rule that everything should be a singleton. A transient component is correct when
identity matters, when mutable state must be isolated, when the object represents one operation or
when it owns a short-lived resource. The finding is about the absence of such a reason.

### Fix

Share the service at the longest appropriate lifetime (application, process or scope). If the
service must stay transient, state the reason and make sure no shared component retains it. If the
service has mutable state, do not simply promote it to singleton: give the state an owner first
(`A009`), and check that concurrent calls are safe.

### Detection

Python and TypeScript read explicit host registrations (`register(... lifetime=...)`,
`add_singleton`/`add_scoped`/`add_transient`, `register(Class, { lifetime })` and
`addSingleton`/`addScoped`/`addTransient`). A transient registration fires when the class is
**behaviorally stateless**: there is one required construction path, no mutable instance or static
state, no property setter and no field assignment outside that constructor. A readonly field or
parameter property populated from a constructor parameter is a dependency, not state, so a service
that injects a repository, clock or logger can still be reported as stateless.

Python accepts fields assigned directly from an `__init__` parameter; it rejects a second
`__init__`, defaults, `*args`/`**kwargs`, mutable containers, reassignment, augmented assignment and
`@setter`. A frozen dataclass with no defaulted fields and no `__post_init__` is accepted. TypeScript
accepts `readonly` fields and `readonly` constructor parameter properties, and rejects non-readonly
or mutable-container fields, setters, optional/rest/defaulted parameters, multiple constructors and
assignments outside the constructor. C# accepts `readonly` fields, get-only properties and primary
constructor parameters without defaults; it rejects setters/`init`, mutable fields or statics,
multiple constructors and assignments outside the constructor. D011 independently owns defaulted
constructor parameters; A007 declines to call such a constructor stateless rather than duplicating
the finding.

That is evidence of behavioral statelessness, not proof of thread safety. Domain objects and
unregistered classes are not evaluated. Go and Java report `executed: false`.

---

## ACIMA-A008 · Captive scoped dependency

**Severity** `warning` → `error` at 2.0.0 · **Level** L3 · **Principle** P4.14

> A shared/singleton component MUST NOT directly capture a scoped dependency in a way that lets the
> dependency outlive its intended boundary. A longer-lived component that needs shorter-lived state
> MUST use an explicit scope, factory or operation parameter.

### Violation

```typescript
class RequestContext {}

class OrdersService {
  constructor(private readonly context: RequestContext) {}
}

register(RequestContext, { lifetime: 'scoped' });
register(OrdersService, { lifetime: 'singleton' });   // ❌ retains the first request's context
```

```csharp
// ❌ the singleton keeps the first request's context forever
public sealed class OrdersService
{
    private readonly RequestContext _context;
    public OrdersService(RequestContext context) => _context = context;
}
```

### Finding

```
ACIMA-A008  warning  lifecycle.host shares OrdersService, which captures the scoped dependency
                     RequestContext; shorten the lifetime or resolve it at the correct scope boundary.
  src/host/registrations.ts:18
  register(OrdersService, { lifetime: 'singleton' });
```

### Why

A scoped dependency is a promise that its state dies at the end of the request, transaction or
operation. When a singleton captures it, the object survives and the promise is false. The first
request's user, tenant, unit of work or cancellation token silently becomes the process's state.
The defect is easy to miss because the constructor signature is correct and the container may
resolve it without complaint.

### Fix

Choose the correction that matches the state:

- make the consumer scoped when its own behaviour is request-bound;
- pass the scoped value as an operation parameter instead of storing it;
- resolve the dependency inside the scope through an explicit factory/provider that the composition
  boundary wires;
- split a shared stateless part from a scoped stateful part.

Do not replace the constructor with a service locator. A global `get()` hides the lifecycle mismatch
and is `L004`.

### Detection

Python and TypeScript compare explicit host registrations. A shared/singleton class fires when its
constructor declares a dependency that is registered scoped in the same host. Only direct
constructor annotations are resolved. Framework proxies, property injection, factory closures,
decorator scopes and runtime resolution are manual-review items. Go and Java report `executed: false`.
The .NET enforcer resolves direct constructor/primary-constructor dependencies through its host
registration map for `AddSingleton`/`AddScoped`/`TryAdd*`; factories, keyed services and open generics
remain manual, and native container validation is not this rule.

---

## ACIMA-A009 · Shared mutable state without ownership

**Severity** `warning` → `error` at 2.0.0 · **Level** L3 · **Principle** P4.15

> A shared component MUST NOT own a mutable container without an explicit owner, isolation boundary,
> concurrency policy and disposal or expiration rule.

### Violation

```typescript
class PriceCache {
  private values = new Map<string, number>();   // ❌ process-wide, unbounded, unsynchronised
}

register(PriceCache, { lifetime: 'singleton' });
```

```python
class PriceCache:
    def __init__(self):
        self.prices = {}        # ❌ no owner, key space, eviction or lock policy

container.add_singleton(PriceCache)
```

### Finding

```
ACIMA-A009  warning  lifecycle.host shares PriceCache, which owns mutable state; give that state an
                     explicit owner, isolation boundary and concurrency policy.
  src/host/registrations.ts:22
  register(PriceCache, { lifetime: 'singleton' });
```

### Why

A mutable container on a shared component is process-wide state by accident. Its ownership is
implicit, its key space may mix tenants, its growth may be unbounded, and its access may race.
Making the component transient does not fix this if the container is written to a shared cache or
static; the ownership question remains.

Shared mutable state is not forbidden. A guarded cache, a request-scoped buffer, a per-instance
accumulator or an intentionally owned resource are all legitimate when their owner, isolation,
synchronisation and lifetime are stated.

### Fix

Choose one:

1. remove the state from the service and delegate it to an explicitly owned store, cache or
   repository;
2. scope the component to the boundary that owns the state;
3. keep the container shared, but document the owner, mutation authority, synchronization,
   tenant/request key, initialization, eviction and failure behaviour, and test the concurrency and
   isolation claims.

A lock alone is not a complete policy: unbounded growth, tenant mixing and stale data remain
defects.

### Detection

Python and TypeScript inspect the class body of a shared/singleton registration for a mutable
container initialised as a field: `list`/`dict`/`set`, `Map`/`Set`/array/object literal, or an
assignment to `this`/`self`. A mutable field is not proof of a race; it is evidence that a policy
must be stated. Legitimate owned and synchronized state is reviewed rather than automatically
rejected. Go and Java report `executed: false`. The .NET enforcer reports a shared class whose instance
field or property is a mutable container (`List`, `Dictionary`, `HashSet`, `Collection`, `Concurrent*`,
an array); static state remains `A003`, and the finding is an ownership question, not proof of a race.

---

## ACIMA-A010 · Effect boundary is unowned

**Severity** `error` · **Level** L3 · **Principle** P15.1 · **Automation** manual

> Every externally visible effect MUST have an identifiable owner and an execution boundary.

### Violation

```csharp
// Host opens a transaction, calls two modules, and commits both inside it.
using var tx = db.BeginTransaction();          // ❌ host owns effects it does not understand
await orders.PlaceAsync(command, tx);
await payments.ChargeAsync(payment, tx);
tx.Commit();
```

```python
class PricingService:
    def price(self, product):
        self.audit.append(product.id)          # ❌ a read-shaped method hides an audit effect
        return self.calculator.price(product)
```

### Finding

Manual rules do not produce a source finding. The enforcer reports:

```
ACIMA-A010  info  Effect boundary is unowned: manual evidence required.
  execution map: executed=false
```

### Why

The caller cannot know the provider's invariants, so a transaction or write opened by the host is a
boundary breach disguised as consistency. A read-shaped method that writes an audit record hides an
effect from every consumer and every test. Ownership must be nameable before retry, transaction or
recovery behaviour can be correct.

### Fix

Move the effect into the module that owns the affected state, and expose a command or operation whose
contract states the effect. Let one module own its transaction and outbox writes. Name a host delivery
policy only when the host genuinely owns the effect, and document that decision.

### Evidence

Record a repository-scoped manual review that names each critical effect owner and its boundary. The
review must identify at least one attempted cross-boundary effect or explain why none exists. A clean
scan is not evidence; `A010` has no portable detector.

---

## ACIMA-A011 · Effect semantics are hidden

**Severity** `error` · **Level** L3 · **Principle** P15.2 · **Automation** manual

> An effect-owning operation MUST state the retry, duplicate, consistency, partial-completion and
> cancellation semantics that apply to it.

### Violation

```typescript
// Contract says only “returns true on success”. Nothing says what a retry does.
async placeOrder(command: PlaceOrder): Promise<boolean>;
```

### Finding

Manual rules do not produce a source finding. A review records the missing semantics and the contract
or design change that resolves it.

### Why

Two consumers can read the same signature and make incompatible assumptions: one retries a timeout,
one treats it as a permanent failure. The operation's real semantics become folklore. Conditional
requirements matter here: a read-only query has no duplicate or retry semantics to document; a payment
command does.

### Fix

State the applicable subset in the contract or its documentation: retryability, duplicate identity and
effect, the consistency guarantee, what a partial outcome looks like, and whether cancellation can
change the result. Use typed outcomes rather than a bare boolean. Do not add every possible parameter
to every method.

### Evidence

Record the operations reviewed, the semantics chosen, and why the others are not applicable. Include
the duplicate and retry cases where they exist. An unused cancellation token or the presence of a retry
library is not evidence.

---

## ACIMA-A012 · Effect outcome is untruthful

**Severity** `error` · **Level** L3 · **Principle** P15.3 · **Automation** manual

> An effect owner MUST report success only after the effect is durable or accepted, and MUST distinguish
> failure, unknown and partial completion.

### Violation

```python
def publish(event):
    queue.put_nowait(event)       # ❌ not durable; may be lost on crash
    return "published"            # ❌ reports success for an accepted-in-memory write
```

```typescript
// The HTTP timeout throws, but the charge may already have succeeded.
await gateway.charge(card, amount);
return { status: "failed" };       // ❌ unknown outcome reported as failure
```

### Finding

Manual rules do not produce a source finding. A review records the untruthful outcome, its blast
radius and the correction.

### Why

A false success loses work; a false failure invites a duplicate. An unknown outcome is not an error
message — it is a distinct state that requires idempotent recovery or reconciliation. Returning it
truthfully is what makes retry and compensation safe.

### Fix

Return a typed outcome with `succeeded`, `failed`, `unknown` and `partial` states where they are
possible. Commit before reporting durable success. After a commit, report completion even if a
subsequent notification fails, or report the partial state explicitly. Do not catch an exception and
assert that nothing happened.

### Evidence

Record the critical effects reviewed, their outcome mapping, and the tests or operational signals that
prove the unknown and partial paths. A passing happy-path test does not establish outcome truthfulness.

---

## ACIMA-A013 · Critical effect has no evidence

**Severity** `warning` · **Level** L3 · **Principle** P15.4 · **Automation** manual

> A critical effect MUST have evidence proportionate to its failure impact.

### Violation

A payment capture, inventory decrement or required audit write has no partial-failure test, no
reconciliation check and no operational signal. The only evidence is a clean architecture scan.

### Finding

Manual rules do not produce a source finding. The review records the missing evidence and the risk it
leaves.

### Why

Static boundaries say where code lives; they do not say what happens when a vendor times out after
committing, a relay crashes between database and broker, or a retry duplicates a charge. Evidence is
the only way to distinguish an owned effect from a hopeful one. The obligation is proportionate: a
low-impact cache invalidation does not need the same evidence as a payment.

### Fix

Add the smallest evidence that matches the failure mode: a test that injects failure between steps, an
idempotency test, a reconciliation query and alert, a documented manual recovery runbook, or a
recorded review of why the effect is not critical. Name the owner and the review date.

### Evidence

The evidence file names the effect, its criticality, the failure mode and the artefact that covers it.
A test that only exercises the success path does not satisfy the rule.

---

## ACIMA-A014 · Telemetry conceals or alters business behaviour

**Severity** `error` · **Level** L3 · **Principle** P15.7 · **Automation** manual

> Logging, metrics and telemetry MUST observe behaviour without concealing it, replacing a business
> decision or materially changing the outcome, and the diagnostic, business-event and audit-record
> purposes MUST be distinguishable.

### Violation

```python
def place_order(order):
    result = orders.place(order)
    logger.info("order failed")       # ❌ a diagnostic that contradicts the business outcome
    return result
```

```typescript
// The audit record is a best-effort log line; nobody owns its retention or failure.
logger.info(`refund approved by ${approver} for ${amount}`);
await refunds.approve(refund);       // ❌ the required record is not part of the effect
```

### Finding

Manual rules do not produce a source finding. A review records the call, what it observes, and what
it conceals, replaces or changes.

### Why

Telemetry is code that runs in the middle of a business operation. When it decides whether to proceed,
swallows an exception, computes the value it reports or stands in for an audit record, the observable
behaviour and the actual behaviour diverge. Operators then trust a record that was never accountable
for the fact it claims.

### Fix

Log the outcome the business decision produced rather than deciding it inside the logger. Keep
emission failure from changing the business result unless the record is part of the effect's contract.
Emit business events and required audit records as owned outputs with their own retention and failure
semantics; do not treat a diagnostic log as either. Never write a secret or sensitive value as an
operational diagnostic (chapter 14).

### Evidence

The review names each telemetry call adjacent to a business decision, its category (diagnostic,
business event or required audit record), its owner, its failure behaviour, and whether the absence of
emission changes the outcome. A clean scan does not establish any of it.

---

## ACIMA-A015 · Unowned consistency boundary

**Severity** `error` · **Level** L3 · **Principle** P15.6 · **Automation** manual

> A multi-step state change or transaction MUST have exactly one identifiable owner and a declared
> consistency guarantee on return; atomicity is one strategy, not a universal requirement.

### Violation

```python
# The host owns the boundary, but the invariants live inside two modules.
with db.transaction():
    orders_repo.save(order)
    payments.charge(order.total)
```

### Finding

Manual rules do not produce a source finding. A review records the unowned boundary, the callers that
believe it is atomic, and the correction.

### Why

A consistency boundary is where the system decides what "done" means. If the caller, the host and the
module all believe they own it, the first partial failure discovers the disagreement. Conversely,
requiring all-or-nothing atomicity everywhere is equally wrong: a durable intermediate state with an
owned resume, compensation or reconciliation is often the better design.

### Fix

Name one owning component. State whether the operation is atomic, recoverable, compensating or
reconciled, what a caller may observe on return, and which intermediate states are legal. Move the
transaction inside the module that owns the state and its outbox writes; use an outbox, a saga or
reconciliation across modules instead of a shared connection. Record who resumes, compensates or
reconciles an interrupted workflow.

### Evidence

For each multi-step change, record the owner, the guarantee on return, the observable intermediate
states and the recovery path with its owner. A transaction API in the code proves none of these.

---

## Governance (`G`)

---

## ACIMA-G001 · Undocumented exception

**Severity** `error` · **Level** L1 · **Principle** P9

> Every waiver carries an owner, a reason, a scope, a review date and an expiry date.

### Violation

```json
{ "rule": "ACIMA-D001", "scope": "unit:orders" }        // ❌ no owner, reason or date
```

### Finding

```
ACIMA-G001  error  Waiver for ACIMA-D001 on unit:orders is missing owner, reason, expires, reviewedOn.
  acima/evidence/waivers.json:4
```

### Why

An exception without an owner is nobody's problem; without a reason it cannot be reviewed; without an
expiry it is permanent. Undocumented exceptions are how a standards-compliant repository becomes a
non-compliant one with a clean build.

### Fix

Write every field, including the finding fingerprint. If you cannot name an owner or a date, the
exception is not a decision yet. A unit or path waiver without a fingerprint is rejected: it would
hide every future finding in that scope, not just the measured baseline.

### Detection

Validate the waivers file against its schema. Also validate that every waived rule id exists in the
catalogue — a typo must not silently excuse nothing.

---

## ACIMA-G002 · Expired waiver

**Severity** `error` · **Level** L1 · **Principle** P9

> An expired waiver no longer suppresses anything; the finding returns until it is fixed or renewed.

### Violation

```json
{ "rule": "ACIMA-C001", "scope": "unit:legacy", "fingerprint": "sha256:…",
  "owner": "team-a", "reason": "…", "expires": "2026-01-01", "reviewedOn": "2025-01-01" }
```

### Finding

```
ACIMA-G002  error  Waiver for ACIMA-C001 on unit:legacy expired on 2026-01-01 (owner: team-a).
  acima/evidence/waivers.json:11
```

### Why

Expiry is the mechanism that makes waivers debt rather than permission. Without it, the file grows
monotonically and the architecture is whatever was true three years ago.

### Fix

Fix the code, or renew the waiver with a new date and a fresh review — and expect to explain why a year
was not enough.

### Detection

Compare `expires` to the current date at analysis time. Report expired waivers even when the underlying
finding no longer occurs: a stale waiver is also a finding, because it means nobody is reading the file.

---

## ACIMA-G003 · Undocumented contract surface

**Severity** `warning` · **Level** L2 · **Principle** P2

> Every public contract type documents its meaning, and its invariants where they exist.

### Violation

```csharp
public sealed record PlaceOrder(Guid CustomerId, IReadOnlyList<OrderLine> Lines);   // ❌ no docs
```

### Finding

```
ACIMA-G003  warning  Contract type PlaceOrder has no documentation.
  src/Acima.Orders.Contracts/PlaceOrder.cs:1
```

### Why

A contract is a promise; a promise nobody explained is a guess. Consumers will infer semantics from
names and types, and infer them wrong — particularly around units, nullability, idempotency and what
happens on failure.

### Fix

Document what it means and what must be true: units, required invariants, idempotency, failure
semantics. One or two sentences is enough; the rule is about presence, not volume.

### Detection

Presence of a doc comment (`///`, `/** */`, `"""`, Go doc comment, Javadoc) on every public type in a
contracts unit. Warning severity: it must be reported, not block a hotfix.

---

## ACIMA-G004 · Unreviewed contract change

**Severity** `error` · **Level** L2 · **Principle** P7

> A change to a published contracts surface is captured in the versioned API baseline.

### Violation

A breaking change (`ProductView.Price` changed from `Money` to `decimal`) with an unchanged
`acima/evidence/api-surface.json`.

### Finding

```
ACIMA-G004  error  Breaking change to catalog.contracts: ProductView.Price (Money -> decimal).
  baseline: acima/evidence/api-surface.json:14
```

### Why

Breaking a published contract is the one change that reaches beyond the repository. Capturing the
surface in a reviewed file means the change is visible in the pull request that causes it, which is the
only moment anyone has the context to decide whether it is acceptable.

### Fix

Either make the change additive (add a member, do not change one), or regenerate the baseline in the
same commit and mark the release as breaking. Both are fine; doing it silently is not.

### Detection

Compute the current public surface of every contracts unit, compare with the baseline; classify each
difference as additive or breaking. Regeneration is an explicit command, never automatic.

---

## ACIMA-G005 · Unclassified source

**Severity** `error` · **Level** L1 · **Principle** P8

> Every production source file belongs to a declared unit.

### Violation

A new directory `src/acima/analytics/` appears with no entry in `acima.config.json`.

### Finding

```
ACIMA-G005  error  Source file is not part of any declared unit: src/acima/analytics/report.py
  src/acima/analytics/report.py:1
```

### Why

A file that belongs to no unit is checked by no rule, and the architecture test still passes — which is
the most dangerous outcome, because it looks like success. Undeclared modules are how a compliant
codebase quietly acquires a non-compliant one.

### Fix

Declare the unit, with a role and a module name. If it is a new module, follow the checklist in
[Module anatomy](../standard/03-module-anatomy.md#36-adding-a-module-the-checklist).

### Detection

After classification, any production source file with no unit is a finding. `exclude` patterns are
applied first, so fixtures and tests never fire this.

---

## ACIMA-G006 · Undeclared external dependency

**Severity** `warning` → `error` at 2.0.0 · **Level** L1 · **Principle** P8

> Every package in a declared manifest has an `externals` entry with tier, owner, reason, review date
> and expiry, and no entry is past its review date.

### Violation

`package.json` declares `left-pad`, and `externals` in `acima.config.json` does not mention it; or an
entry's `expires` date has passed.

### Finding

```
ACIMA-G006  warning  manifest dependency left-pad has no externals entry: declare its tier, owner
                      and review date.
  package.json:7
  "left-pad"
```

### Why

`G005` says a source file outside every unit is checked by no rule. `G006` is that sentence for
packages: a dependency nobody declared has no tier, so no rule knows whether it is a platform
surface, an integration needing a seam, or a utility — and the gate cannot tell a reviewed choice
from an accident. The review date is the second half: a dependency that was a reasonable utility
three years ago is often an abandoned one now.

### Fix

Run `python3 tools/acima.py externals --write-draft --root .` to generate the declaration from the
manifest, then set the tier, owner and reason for each package and complete `adapter`/`port` for the
integration ones. Renew an expired entry individually; an entry that is renewed in bulk has stopped
being a review.

### Detection

Read every manifest named by the config's `manifests` list, or `package.json`, `pyproject.toml` and
`requirements.txt` when the list is absent. For .NET, `.csproj` files are read and their direct
`PackageReference` entries are checked. For Go, `go.mod` is read and its direct `require` entries are
checked against `approvedDependencies`; entries marked `// indirect` are ignored. `dependencies` and
requirements entries are checked; `devDependencies` are not, because they do not ship. An entry with
an unknown tier, a missing field or a non-ISO date is `G001`. When `externals` is absent the rule
reports `executed: false` for Python, TypeScript and .NET, and when `approvedDependencies` is absent
it reports `executed: false` for Go — package governance was not declared, and a silent pass would be
a false one. **Implemented for Python, TypeScript, .NET and Go.**
