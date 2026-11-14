# 17. Lifecycle and state ownership

> **Normative.** A module-owned component MUST have a lifecycle appropriate to its responsibilities.
> A stateless shared service SHOULD be shared rather than repeatedly constructed. A component's
> lifetime MUST be compatible with the lifetimes of the dependencies it captures. Shared mutable
> state MUST have an explicit owner, isolation boundary and concurrency policy, and a component that
> owns a resource MUST have an explicit initialisation, lifetime and cleanup story.

This chapter is about **deliberate instance lifetime and state ownership**, not singleton
maximisation. Registering every class as a singleton is not an architecture; it is a way to turn
every incidental field into process-wide state. The governing principle is:

> Use the longest appropriate lifecycle that preserves correctness, isolation, concurrency safety and
> resource ownership. Share stateless behaviour. Give mutable state an owner. Never let a longer-lived
> component retain state that belongs to a shorter-lived boundary.

Three portable rules carry the mechanically decidable part of this obligation:

| Rule | Finding | Default severity |
|---|---|---|
| `A007` | A stateless shared service is registered as transient | warning, `error` at `2.0.0` |
| `A008` | A shared/singleton component directly captures a scoped dependency | warning, `error` at `2.0.0` |
| `A009` | A shared component owns an unowned mutable container | warning, `error` at `2.0.0` |

Everything else in this chapter — thread safety, tenant isolation, distributed ownership, resource
cleanup and the correctness of a factory boundary — remains **manual review** unless a native
analyzer or runtime test establishes it. A clean scan is not a thread-safety proof.

This chapter and P15 answer different questions. Chapter 17 decides **which instance owns state and
how long it lives**; P15 decides **which component owns an external effect and what its execution,
duplicate and recovery semantics are**. A process-wide cache is a state-ownership question (`A009`);
a payment or outbox write is an effect-ownership question (`A010`–`A013`). Neither framework
substitutes for the other, and a transaction boundary does not make a shared cache tenant-safe.

## 17.1 Why lifetime is an architectural decision

Dependency direction is visible in imports. Lifetime is usually not: it lives in a registration
call, a module-level binding, a framework attribute, a closure or a container default. That makes it
easy to change behaviour without changing any type:

```typescript
register(PriceCalculator, { lifetime: 'transient' });
```

```python
container.add_transient(PriceCalculator)
```

Neither line says anything false. The defect appears later: an expensive validator is rebuilt for
every request, a "stateless" service accumulates a request id in a field, a singleton holds the
first tenant's currency, or a scoped repository is stored on a system-wide object. None of
those changes a constructor signature, so the dependency graph looks correct while the runtime
graph is not.

Lifetime also decides **ownership**. A component that lives for the process and holds a mutable map
has made that map part of the process's state, whether or not anyone wrote that down. A transient
component that owns a connection has decided that its caller is responsible for disposal. These are
architectural choices, and they belong in the same review as module boundaries and contracts.

## 17.2 The lifecycle decision model

The model is framework-independent. It asks what the component owns and what boundary its state
belongs to, not what a container calls its registration.

| Component characteristics | Preferred lifecycle | Why |
|---|---|---|
| Stateless, thread-safe service | Shared or singleton | no per-call state; construction cost is waste |
| Stateless service with expensive initialisation | Shared or explicitly cached | reuse the initialisation, not just the object |
| Request-specific state | Request or scope lifetime | state must die with the request |
| Transaction-specific state | Transaction lifetime | commit/rollback defines the boundary |
| Tenant-specific mutable state | Explicit tenant-owned lifecycle | tenant isolation must be structural |
| Independent short-lived object identity | Transient or operation lifetime | identity and equality are per-instance |
| Resource-owning component | Lifecycle appropriate to the resource | cleanup must match acquisition |
| Shared mutable state | Explicitly owned and concurrency-safe | sharing is a decision, not a default |

These are preferences with reasons, not unconditional registration rules. The model asks four
questions, in order.

### 17.2.1 Is the component stateless?

A component is **stateless for lifecycle purposes** when its behaviour does not depend on mutable
state retained between calls. Fields that hold injected collaborators are not state; a logger, a
repository or a clock is a dependency whose own lifecycle is evaluated separately. Nor is a local
variable state: it lives for one invocation by construction.

A component is **not** stateless merely because it has no fields. A module-level cache, a static
counter, a closure variable or a framework context object can all hold state that is invisible in the
class body. Conversely, a class with a field is not automatically stateful: an immutable value
assigned once at construction is a dependency or a constant.

### 17.2.2 Does the state belong to a boundary?

If state belongs to a request, transaction, tenant, operation or resource, its lifetime must be no
longer than that boundary. The place to enforce that is the composition boundary: construct or
resolve the state at the boundary and pass it down. Making the service transient does **not** make
the state appropriately scoped if the service still writes it to a shared object.

A request id, current user, correlation token, tenant identifier, unit of work, open transaction or
per-call cancellation token belongs to a boundary. A shared service must receive it as a
parameter or resolve it inside the scoped operation; it must not retain it in a field.

### 17.2.3 Does the component own a resource?

A component that opens a connection, pool, file handle, stream, subscription, background worker or
timer owns something the runtime must release. Resource ownership is separate from statelessness: a
service can be stateless in its domain fields and still own a resource. Its lifecycle follows the
resource's real requirements — shared and pooled, scoped to a unit of work, or transient and
explicitly disposed. Transient construction is not automatically safer; it often moves cleanup
responsibility to code that has no way to perform it.

### 17.2.4 Does identity matter?

Transient remains correct when each instance has independent identity, when a caller intentionally
constructs a fresh value object, when the object represents one operation, or when the object is a
short-lived resource whose disposal is part of its contract. A domain entity, command, event,
value object or job descriptor is not a shared service and is outside this rule.

## 17.3 The normative obligations

### R1 — Prefer shared instances for stateless services

Validators, calculators, mappers, domain policies, stateless shared services, stateless
infrastructure adapters and pure behaviour wrapped in a service abstraction SHOULD be shared at the
longest appropriate lifetime. A transient registration is a claim that per-instance identity or
state matters; when it does not, the claim is false and the construction cost is unnecessary.

This is a preference, not a prohibition. A stateless object may be transient because a framework
requires it, because the object is a short-lived value rather than a module-owned component, or
because construction is part of an intentional operation boundary. The reason must be defensible,
not merely "transient is the default".

### R2 — Justify the instance lifecycle

Every module-owned component MUST have an identifiable lifecycle appropriate to its
responsibilities. Acceptable boundaries include system, process, request, transaction, tenant,
operation, individual use and resource lifetime. A repository MUST NOT introduce repeated
construction of a module-owned component without a reason that survives review.

This does not require documenting every `new` expression or every value object. It applies to
module-owned components: services, adapters, repositories, handlers, workers, caches and
resource-owning objects.

### R3 — Separate behaviour from mutable state

Shared services SHOULD implement behaviour and delegate state ownership to explicitly
identified components: repositories, request or operation contexts, explicit state stores,
transaction boundaries, tenant state providers, dedicated caches or resource owners. A service that
accumulates incidental state is a service whose correctness depends on how often it is constructed
and how long it happens to live.

Making a service transient is not a substitute for defining where its state belongs. If the state is
written to a shared cache, a static, a module binding or an injected singleton, changing the
service's own registration leaves the defect intact.

### R4 — Explicitly own shared mutable state

Shared mutable state is permitted. Undocumented shared mutable state is not. Where it exists, the
architecture MUST establish:

- **Ownership** — which component owns the state and is allowed to change it;
- **Mutation authority** — which operations may write, and through which interface;
- **Concurrency safety** — the synchronisation or confinement strategy;
- **Isolation** — the tenant, request or resource boundary the state belongs to;
- **Initialisation** — when the state becomes valid and what happens before that;
- **Disposal or expiration** — when entries die and who removes them;
- **Failure behaviour** — what happens after a partial write, timeout or eviction;
- **Consistency expectations** — what readers may assume and for how long.

A mutable field is not automatically an architectural violation. It may be a legitimate counter
guarded by a lock, a per-instance buffer, an intentionally owned cache or an implementation detail
of a resource adapter. The finding asks for an owner and a policy; the reviewer decides whether the
policy is adequate.

### R5 — Prevent cross-scope state leakage

A longer-lived component MUST NOT retain state belonging to a shorter-lived boundary. Typical
failures:

- a singleton stores the current request id, user or cancellation token;
- a shared service keeps tenant-specific mutable data in an instance field or module-level map;
- a system-wide cache has no tenant key and no eviction policy;
- a background worker holds a stale request context after the request ends;
- a transient object captures a scoped dependency and is stored somewhere longer-lived.

The last case is the **captive dependency**: the object is transient, but a shared component stores
it, so it now lives for the shared component's lifetime. The problem is not the transient
registration; it is the retention path.

### R6 — Require compatible dependency lifetimes

A component's lifecycle MUST be compatible with the lifecycle of its dependencies. In particular, a
singleton or otherwise shared component MUST NOT directly capture a scoped dependency in a way that
causes the dependency to outlive its boundary.

Where a longer-lived component legitimately needs shorter-lived dependencies, it MUST use an
explicit lifecycle-aware mechanism: a factory that the caller invokes inside the scope, an explicit
scope boundary, a provider passed as a dependency, or a method parameter supplied at the operation
site. A service locator or an untyped `get()` call is not a lifecycle mechanism; it conceals the
dependency (`L004`) and usually moves the mismatch to runtime.

Factories are allowed, but they do not license hidden dependencies. A factory that receives its
dependencies as parameters and is constructed at the composition boundary is explicit. A factory
that closes over a scoped component, or resolves one from a global container when invoked, has
replaced a compile-time dependency with a runtime one. ACIMA's existing explicit-construction
requirements (`D010`–`D016`) still apply.

### R7 — Make resource ownership explicit

A component that owns a resource MUST have identifiable initialisation, lifetime and cleanup.
Examples include database connections and pools, HTTP clients and connection pools, file handles,
streams, background workers, external subscriptions and disposable objects.

The lifecycle follows the resource, not the component's domain statelessness. A shared HTTP client
is usually correct; a shared connection with per-request transaction state is not. A transient
connection whose caller never disposes it is not safer than a scoped one. The review asks:

1. Who acquires the resource?
2. Who is allowed to use it concurrently?
3. Who releases it, and on which path — success, failure, cancellation, shutdown?
4. What happens when release fails or is delayed?
5. Does the chosen lifetime pool, share or isolate the resource intentionally?

Static analysis can sometimes see `IDisposable` or a context manager, but presence of a cleanup
method does not prove that it is called. Resource ownership is therefore a review obligation unless a
runtime test or native analyzer supplies evidence.

## 17.4 Total Visibility for lifetime and state

The existing Total Visibility principle says a reader must be able to determine what a component
depends on, where it comes from and how it is constructed. Lifecycle extends that list:

1. What the component depends on.
2. Where each dependency originates.
3. How and where the component is constructed or registered.
4. How long it exists.
5. Whether it contains mutable state.
6. Who owns that state.
7. Whether sharing it is safe.
8. How its resources are released.

For every module-owned component, these answers must be available from the composition boundary,
the component's constructor and its registration — not inferred from a container's default
convention. "It is a singleton because that is the default" and "it is transient because that is
the default" are both failures of visibility.

The same obligation applies to functional construction. A long-lived closure that captures a
short-lived request object, a shared delegate that captures mutable tenant data, a factory that
retains a scoped component, a curried function that keeps module state between invocations and
a callback registration that retains a resource past its intended lifetime are all lifecycle
defects even though no class field is involved. Chapter 16 defines the dependency-visibility rules;
this chapter adds the lifetime question: *how long does the captured value live, and who owns it
then?*

## 17.5 The captive dependency

A captive dependency occurs when a longer-lived component holds a shorter-lived one. The classic
form is a singleton that receives a scoped service through its constructor:

```csharp
// ❌ the singleton keeps the first request's context forever
public sealed class OrderProcessor
{
    private readonly RequestContext _context;

    public OrderProcessor(RequestContext context) => _context = context;
}
```

```typescript
// ❌ same defect without a framework: module-level instance retains a request object
class OrderProcessor {
  constructor(private readonly context: RequestContext) {}
}

export const processor = new OrderProcessor(currentRequestContext);
```

The correction is not "make everything transient". It is to remove the retention path:

- make the consumer scoped as well, if its own state is request-bound;
- resolve the dependency inside the operation from an explicit scope/factory;
- pass the request-bound value as a method parameter;
- split the component into a shared stateless part and a scoped stateful part.

`A008` reports the direct constructor-capture form where a host registration makes the lifetimes
visible. It cannot see framework-produced proxies, property injection, factory closures, service
locators or runtime resolution. Those are manual-review items, and a framework that validates
captive dependencies at startup is preferable to a source scan.

## 17.6 State isolation and multi-tenancy

A shared component may serve many tenants only if its state is either immutable, tenant-keyed and
properly isolated, or confined to the operation. Sharing a cache is not automatically a
tenant-isolation defect; sharing a cache with no tenant dimension is.

The review must identify:

- **the isolation key** — tenant, customer, request or resource id;
- **the ownership of the key** — who supplies it and whether it can be spoofed;
- **the storage boundary** — per-tenant instance, keyed map, per-tenant schema or external store;
- **the eviction boundary** — whether one tenant's data can expire or overwrite another's;
- **the failure boundary** — whether a failed lookup falls back to another tenant's data.

A request-scoped service is not automatically safe either: if it writes to a shared repository
without a tenant predicate, the scope changed but the data boundary did not. ACIMA can report a
shared mutable container (`A009`) and a directly captured scoped dependency (`A008`); it cannot prove
tenant isolation. That claim requires tests, schema constraints, row-level security or an
independent review. The report MUST NOT say "tenant-safe" because no finding fired.

## 17.7 Distributed systems: a singleton is process-local

A process singleton is local to one process, worker or container replica. It is not a
distributed singleton, a cluster-wide lock, a shared cache or a single source of truth. In a
multi-replica deployment, each replica gets its own instance, so:

- in-memory state is per replica, not globally consistent;
- a "singleton" cache can return different values on different replicas;
- a background worker may run once per replica unless leadership is coordinated;
- a lock held in process memory does not exclude another process;
- a sequence generated in memory is not globally ordered.

ACIMA does not mandate distributed coordination, a central state store or a particular deployment
topology. It requires the architecture to say which guarantee it relies on. If a component needs
cross-replica consistency, that is a distributed-systems decision with its own consistency,
partitioning and failure semantics — not a DI lifetime choice. If it does not, process-local state
must be documented as such and must not be described as globally shared.

## 17.8 Resource ownership patterns

| Resource | Typical correct lifecycle | Common defect |
|---|---|---|
| Database connection | Pooled and shared; transaction scoped per unit of work | transient connection per call, never disposed |
| HTTP client | Shared/pooled, long-lived | new client per request, socket exhaustion |
| File handle / stream | Operation scoped, disposed on every path | shared handle with interleaved readers |
| Background worker | Process lifetime, explicit start/stop | request-scoped worker that outlives the request |
| Subscription / callback | Registered for a defined lifetime, unsubscribed on shutdown | registration retains a scoped object |
| Cache | Shared with eviction and isolation policy | unbounded map, no tenant key, no expiry |
| Unit of work | Transaction or request scoped, explicitly completed | stored on a singleton |

A cleanup method is not evidence that cleanup happens. The review needs an owner, a trigger and a
test for the failure path. Conversely, a component without a `Dispose` method is not automatically
leaking: it may own nothing, or its resource may be owned by a narrower scope.

## 17.9 Language profiles

The decision model is portable; the detectable syntax is not. The reference enforcers read explicit
host registrations only, and they differ in what "explicit" means.

| Language | Lifecycle mechanisms | Automated coverage in this revision | Limits |
|---|---|---|---|
| TypeScript/JavaScript | module bindings, DI containers, request-scoped providers, closures, caches, callbacks | `A007`–`A009` for `register(Class, { lifetime })` and `addSingleton`/`addScoped`/`addTransient` | no framework container; no factory closures or module-level instances |
| Python | module singletons, provider functions, scopes, decorators, context managers, mutable defaults | `A007`–`A009` for `register(... lifetime=...)` and `add_singleton`/`add_scoped`/`add_transient` | no runtime container; no decorator/factory retention |
| C#/.NET | singleton/scoped/transient registrations, `IDisposable`, `IHostedService`, statics, delegates | `A007`–`A009` for direct `AddSingleton`/`AddScoped`/`AddTransient`/`TryAdd*` registrations | no factory/keyed/open-generic graph; A007 accepts readonly constructor dependencies; concurrency, tenant isolation and cleanup remain manual |
| Go | package-level values, constructor functions, goroutines, `context.Context`, mutexes | none executed; catalog entries report `executed: false` | manual review; no goroutine or lock analysis |
| Java | singleton/prototype/request scopes, static state, functional interfaces | no reference enforcer | manual review; profile only |

### 17.9.1 TypeScript and JavaScript

Module-level instances are the most common accidental singleton. A service exported as
`export const orders = new OrdersService(...)` is shared by every importer, regardless of the DI
framework. That can be correct for a stateless adapter and wrong for anything holding request or
tenant state. The scanner only evaluates explicit host registrations; a module-level instance and a
container's decorator-based scope are manual-review items.

Closures and callbacks carry lifetime too. A callback registered at startup that captures a
request-scoped repository keeps that repository alive for the process. A shared delegate that
mutates captured request data is a data race with a friendly syntax. Chapter 16 covers whether the
dependency is visible; this chapter asks how long the capture lives.

### 17.9.2 Python

A module-level object is a process singleton for practical purposes. A decorator such as
`@lru_cache` on a shared service creates a cache with an implicit lifetime and no
tenant boundary. A default argument such as `def handle(order, context=RequestContext())` creates
one mutable object shared by every call. Context managers are the normal resource-ownership
mechanism; an object that opens a resource in `__init__` and has no `close`/`__exit__` path needs a
review.

The scanner evaluates explicit registrations in host units. It does not resolve decorators,
provider functions, module-level construction, FastAPI/Flask dependency injection or async task
lifetimes.

### 17.9.3 C#/.NET

`AddSingleton`, `AddScoped` and `AddTransient` are explicit enough to review, and the framework can
validate some captive dependencies at startup. A singleton constructor that takes a scoped service
is the canonical `A008`; a singleton holding a `Dictionary` mutated after construction is the
canonical `A009`. `IDisposable`/`IAsyncDisposable` establish a cleanup contract, not a guarantee;
`IHostedService` owns a worker lifecycle that must stop on shutdown. Static fields are process-wide
and are already constrained by `A003` when they cross modules; they remain shared mutable state
within a module.

The .NET enforcer executes `A007`–`A009` from Roslyn syntax for direct registrations. `A007` treats
a class as behaviorally stateless when it has one required construction path, no mutable instance or
static state, no setter or `init` accessor and no field/property assignment outside its constructor;
a readonly field or get-only property populated from a constructor parameter is a dependency, not
state. `A008` resolves direct constructor dependencies through the host lifetime map. `A009` reports
a shared class with a mutable container field or property. The check is syntactic; factories, keyed
services, open generics, decorators, proxies, tenant isolation, thread safety and cleanup remain
manual evidence.

### 17.9.4 Go

Go has no container scope by default: shared state is a package-level variable, a field on a
long-lived struct or a value captured by a goroutine. `context.Context` is the normal request-scope
carrier and must not be stored on a long-lived struct. A goroutine that outlives its request and
keeps a request value is the captive-dependency shape; a shared map without a mutex is shared
mutable state. Constructor functions make ownership visible, but they do not enforce it.

The Go enforcer does not execute `A007`–`A009` in this revision. The rules are catalogued and
report `executed: false`; manual evidence is required for a full claim.

### 17.9.5 Java

Spring and similar containers distinguish singleton, prototype and request scopes. A singleton bean
that depends on a request-scoped bean needs a scoped proxy or an explicit provider; a field holding
mutable state in a singleton is shared across requests. Static mutable state is process-wide.
Functional interfaces and lambdas can capture a service or context just as in TypeScript.

There is no reference Java enforcer. The profile documents the obligation; an assessment that
selects Java fails closed rather than reporting clean.

## 17.10 Exceptions and legitimate transients

The standard does not prohibit transient components. The following are legitimate unless a specific
rule says otherwise:

- domain entities, value objects, commands, events, jobs and other short-lived data carriers;
- immutable objects with harmless independent allocation;
- per-operation objects whose identity or isolated mutable state is meaningful;
- framework-required lifetimes that the system documents and tests;
- scoped services that are used within their scope and not captured;
- shared state that is explicitly owned, synchronised and isolated;
- resource-owning components with a documented acquisition and cleanup path.

A framework-required lifetime is an explanation, not an exemption. If a framework constructs a
controller per request, that is its contract; the controller must still not store request state in a
static, and its scoped dependencies must not escape into a singleton.

An exception to a rule needs an owner, scope, reason, review date and expiry (`G001`), just like any
other waiver. "The container made it easy" is not a reason.

## 17.11 Enforcement and limits

`A007`, `A008` and `A009` execute in the Python, TypeScript and .NET reference enforcers. They
read explicit host registrations and inspect the registered class body:

- **A007** fires when a transient registration targets a behaviorally stateless class: one required
  construction path, no mutable instance or static state, no property setter and no assignment
  outside that constructor. Readonly constructor-injected dependencies are allowed. That is evidence
  of statelessness, not proof of thread safety; a class may be stateless and still use a
  non-thread-safe global.
- **A008** fires when a shared/singleton registration targets a class whose constructor declares a
  dependency that is registered scoped in the same host. It follows direct constructor annotations
  only; it does not see framework proxies, factories, property injection or runtime resolution.
- **A009** fires when a shared/singleton registration targets a class that initialises a mutable
  container (`list`, `dict`, `set`, `Map`, `Set`, array or object literal). A container field is not
  proof of a race; it is evidence that an ownership and concurrency policy must be stated.

The rules deliberately do **not** flag:

- ordinary transient domain objects;
- immutable objects and stateless objects with independent allocation;
- framework-required lifetimes;
- legitimate scoped services;
- safely synchronised or explicitly owned shared state;
- resource-owning components with documented cleanup.

They also do not execute for Go or Java. Those profiles report the rules `executed: false`, and a
full claim needs repository-scoped manual evidence. The .NET enforcer executes the three rules from
direct host registrations, with the conservative limits above. The report MUST distinguish:

1. a confirmed syntactic registration mismatch;
2. a potential mismatch in framework-managed code;
3. a reviewed, documented lifecycle decision;
4. an unsupported profile;
5. a manual-review requirement for thread safety, tenant isolation or resource cleanup.

A zero-finding run does not prove that a component is safe to share, that state is isolated across
tenants, that resources are released, or that the runtime container graph matches the source. Those
are separate evidence questions, and the standard does not let a static scan answer them by
implication.

## 17.12 Examples

### 17.12.1 Violation: a stateless validator registered transient

```typescript
class OrderValidator {
  validate(order: Order): boolean {
    return order.lines.length > 0;
  }
}

register(OrderValidator, { lifetime: 'transient' });
```

Finding: `ACIMA-A007`. The validator has no per-instance state; share it. If the framework requires
transient registration, document why and record the decision.

### 17.12.2 Correction: shared stateless service

```typescript
register(OrderValidator, { lifetime: 'singleton' });
```

The service remains stateless; sharing it removes repeated construction. This does not make it
thread-safe by declaration — it must still be safe for concurrent calls, which a stateless
implementation with no shared mutable fields normally is.

### 17.12.3 Violation: a singleton captures a scoped context

```typescript
class RequestContext {}

class OrdersService {
  constructor(private readonly context: RequestContext) {}
}

register(RequestContext, { lifetime: 'scoped' });
register(OrdersService, { lifetime: 'singleton' });
```

Finding: `ACIMA-A008`. `OrdersService` lives for the process and retains the first request's
context. Make the service scoped, or pass the context to the operation that needs it.

### 17.12.4 Correction: explicit operation-scoped access

```typescript
class OrdersService {
  process(order: Order, context: RequestContext): void {
    context.trace('orders.process', order.id);
  }
}
```

The service can now be shared safely because the request-bound value is a parameter, not retained
state.

### 17.12.5 Violation: unowned shared mutable state

```python
class PriceCache:
    def __init__(self):
        self.prices = {}

container.add_singleton(PriceCache)
```

Finding: `ACIMA-A009`. The cache is process-wide, unbounded and has no concurrency or tenant policy.
Give it an explicit owner, a key space, an eviction rule and a synchronisation strategy — or make it
request-scoped if the data is request-bound.

### 17.12.6 Legal: owned, synchronised state

```python
class PriceCache:
    def __init__(self, clock, ttl):
        self._prices = {}
        self._lock = threading.Lock()
        self._clock = clock
        self._ttl = ttl

    def get(self, key):
        with self._lock:
            entry = self._prices.get(key)
            if entry is None or entry.expires_at <= self._clock.now():
                return None
            return entry.value
```

`A009` may still report the container because the scanner cannot prove the policy. The review
records the owner (`PriceCache`), the mutation authority (the locked methods), the isolation key
(product id), the eviction rule (TTL) and the concurrency policy (the lock). The finding is then
triaged as reviewed, not silently waived.

### 17.12.7 Legal: transient with independent identity

```typescript
class OrderLine {
  constructor(readonly productId: string, readonly quantity: number) {}
}
```

A value object constructed per use is not a shared service. `A007` does not apply, even if the class
has no mutable fields, because it is not registered as a module-owned component.

## 17.13 Generality across architecture families

| Architecture | Shared form | Scope form | Watch for |
|---|---|---|---|
| Modular monolith | shared service, stateless adapter | request/transaction context | singleton retaining a request context |
| Microservices | per-service client/pool | per-request handler state | replica-local cache presented as global |
| Event-driven | consumer/adapter shared | message or transaction scope | callback retaining a consumed message |
| Functional | partially applied function with explicit dependencies | per-invocation context | closure retaining request data |
| Library | documented shared stateless helper | caller-owned scope | hidden module-level cache |
| Plugin | host-owned capability | plugin operation scope | plugin registry retaining a disposed plugin |
| Serverless | module-scope client reused within an instance | invocation scope | instance state assumed to be global |
| Multi-tenant SaaS | tenant-keyed shared services | tenant/request scope | cache without tenant isolation |
| Background processing | worker shared for process lifetime | job/operation scope | worker retaining a completed job's context |
| No DI container | explicit constructor/parameter passing | explicit scope object | module-level singleton by accident |

The model does not require a container. A codebase that constructs everything with `new` still has
lifetimes: module-level objects, long-lived structs, closures and static state are registrations in
all but name. The review question is the same: who owns this instance, how long does it live, and
what state does it retain?

## 17.14 Review checklist

- [ ] Is every module-owned component stateless, stateful, resource-owning or scope-dependent — and
      is that classification stated?
- [ ] Is a stateless service shared at the longest appropriate lifetime (`A007`)?
- [ ] Is a transient registration justified by identity, isolated state, a short-lived resource or an
      operation boundary?
- [ ] Does a shared component capture a scoped dependency (`A008`)?
- [ ] Does a shared component own a mutable container without a stated owner, isolation key,
      synchronisation policy and eviction rule (`A009`)?
- [ ] Does any singleton retain a request id, user, tenant, transaction, cancellation token or
      request context?
- [ ] Is tenant-specific state keyed and isolated, with a failure path that cannot cross tenants?
- [ ] Does every resource-owning component have an owner, an acquisition point and cleanup on
      success, failure, cancellation and shutdown?
- [ ] Is a factory or closure retaining a dependency beyond its intended scope?
- [ ] Is shared mutable state synchronised or confined, and is the policy documented?
- [ ] Is process-local state described as process-local rather than globally consistent?
- [ ] Are Go and Java lifecycle claims backed by manual evidence rather than a clean portable run,
      and are .NET factory, keyed-service and concurrency claims backed by review?
- [ ] Does the report separate a confirmed registration mismatch from a manual review of thread
      safety, isolation, resource cleanup and distributed consistency?

The objective is not the most singletons. It is the fewest surprises: an instance that lives exactly
as long as its responsibilities require, state that belongs to a named owner, and a boundary that
does not leak when the request, tenant or resource ends.
