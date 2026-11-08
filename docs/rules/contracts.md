# Contract rules (`C`)

Seven rules about what a contract may contain and how it may change. Full context:
[Contract design](../standard/05-contract-design.md).

Each rule is a property of an **immutable contract**. If a type satisfies all seven, it can be
serialized, retried, replayed, compared, archived and versioned without surprises.

---

## ACIMA-C001 · Mutable contract state

**Severity** `error` · **Level** L2 · **Principle** P6

> Contract members are set at construction and never mutated afterwards.

### Violation

```csharp
public sealed class PlaceOrder                       // ❌ class with setters
{
    public Guid CustomerId { get; set; }
    public Money Total { get; set; }
}
```

```python
class PlaceOrder:                                    # ❌ plain class, mutable by default
    customer_id: str
```

### Finding

```
ACIMA-C001  error  Contract type PlaceOrder exposes mutable state via 'set' accessors.
  src/Acima.Orders.Contracts/PlaceOrder.cs:3
  public Guid CustomerId { get; set; }
```

### Why

A mutated message is shared state between the sender and every receiver in the pipeline. The failure
is not local: handler A normalises `Total`, handler B sees a different number than the one the client
sent, and nothing in the code says so. It also makes the message unusable as an event: an event that can
change after publication is not a fact.

### Fix

| Language | Idiom |
|---|---|
| C# | `record` with positional or `init` members, `sealed` |
| TypeScript | `readonly` members plus `Readonly<...>` where composed |
| Python | `@dataclass(frozen=True, slots=True)` or `NamedTuple` |
| Go | struct with unexported fields, constructor function, accessor methods |
| Java | `record` |

### Detection

C#: `set` accessors, public non-readonly fields, `record` without positional/`init` members.
TS: non-`readonly` properties in interface/class. Python: non-frozen dataclass, plain class attributes,
`NamedTuple` is fine. Go: exported mutable struct fields in a contracts package. Java: non-`record`
class with setters or public fields.

---

## ACIMA-C002 · Mutable collection exposure

**Severity** `error` · **Level** L2 · **Principle** P6

> Contracts expose immutable or defensively copied collections, never shared mutable state.

### Violation

```python
@dataclass(frozen=True)
class OrderDraft:
    lines: list[OrderLine]          # ❌ frozen only prevents rebinding
```

```typescript
export interface OrderDraft {
  readonly lines: OrderLine[];      // ❌ readonly field, mutable array
}
```

### Finding

```
ACIMA-C002  error  Contract type OrderDraft exposes a mutable collection (list) as 'lines'.
  src/acima/orders/contracts/order_draft.py:4
  lines: list[OrderLine]
```

### Why

This is the most common false sense of safety in Python and TypeScript. `frozen=True` and `readonly`
prevent *rebinding the attribute*; they do nothing about `draft.lines.append(...)`. The receiver mutates
the sender's list, and the sender's invariants no longer hold.

### Fix

| Language | Idiom |
|---|---|
| C# | `IReadOnlyList<T>` / `IReadOnlyDictionary<K,V>`, assigned from `ToArray()` / `ToImmutableArray()` in the constructor |
| TypeScript | `readonly T[]`, `ReadonlyArray<T>`, `ReadonlyMap<K,V>` |
| Python | `tuple[T, ...]`, `MappingProxyType({...})` |
| Go | unexported slice field; `Items() []T` returns a copy |
| Java | `List.copyOf(...)`, `Map.copyOf(...)` inside the canonical constructor |

### Detection

Python: `list`/`dict`/`set` annotations in contract types. TS: array/map types without `readonly`.
C#: `List<T>`, `T[]`, `ICollection<T>`, `IDictionary<K,V>` in a contract signature. Go: exported slice
or map fields. Java: mutable collection types assigned without a copy.

---

## ACIMA-C003 · Behaviour in contracts

**Severity** `error` · **Level** L2 · **Principle** P6

> Contracts carry data and validation only: no business logic, IO or orchestration.

### Violation

```csharp
public sealed record OrderDraft(IReadOnlyList<OrderLine> Lines)
{
    public Money Total() => Lines.Sum(l => l.Price * l.Quantity) * TaxRate(DateTime.UtcNow);  // ❌
    private decimal TaxRate(DateTime now) => now.Month == 12 ? 1.2m : 1.0m;
}
```

### Finding

```
ACIMA-C003  error  Contract type OrderDraft contains business behaviour (Total) and reads ambient time.
  src/Acima.Orders.Contracts/OrderDraft.cs:5
```

### Why

Behaviour in a contract is behaviour nobody owns. It cannot be tested against the module's invariants,
it cannot be changed without a contract version bump, and it runs in the consumer's process where the
module cannot observe it. When it reads the clock, it is also non-deterministic — see `C004`.

### Fix

Keep pure projections (`Total => Lines.Sum(...)`) if you must, and move anything that branches on
business conditions into the module's domain. If consumers need a computed value, compute it in the
module and put it in the view.

### Detection

This is the judgement rule. The enforcer flags: methods with branches/loops beyond a trivial fold, any
IO call, any `async`, any dependency on another type's behaviour, any constructor injection. A human
decides whether a helper is validation or business logic. The finding says which methods it suspects,
so the review starts from a list rather than a guess.

---

## ACIMA-C004 · Ambient or non-deterministic state in contracts

**Severity** `error` · **Level** L2 · **Principle** P6

> Contracts MUST NOT read clocks, generate identifiers, or touch static mutable state.

### Violation

```typescript
export class OrderPlaced {
  readonly placedAt = new Date();               // ❌ reads ambient time
  readonly eventId = crypto.randomUUID();       // ❌ generates identity
}
```

```go
type OrderPlaced struct {
    PlacedAt time.Time   // fine as a field...
}
func NewOrderPlaced(id string) OrderPlaced {
    return OrderPlaced{PlacedAt: time.Now()}    // ❌ ...but not generated here
}
```

### Finding

```
ACIMA-C004  error  Contract type OrderPlaced reads ambient state (new Date) at construction.
  src/orders/contracts/order_placed.ts:2
  readonly placedAt = new Date();
```

### Why

A contract that reads the clock produces a different value on every construction, which breaks
equality, replay, deduplication and tests. A contract that generates its own id cannot be reconstructed
from a persisted event. Both make the message unreproducible — and reproducibility is the whole reason
events are useful.

### Fix

Take time and identity as constructor parameters, supplied by the module (or the host) that owns the
fact. `new OrderPlaced(orderId, placedAt)` — the clock lives in the implementation, where it can be
faked and where `C004` does not apply.

### Detection

A per-language denylist applied to contract type bodies and field initialisers: `DateTime.Now`,
`DateTime.UtcNow`, `Guid.NewGuid()`, `new Date()`, `Date.now()`, `crypto.randomUUID()`,
`datetime.now()`, `uuid4()`, `time.Now()`, `rand.Int()`, `Instant.now()`, `LocalDateTime.now()`,
`UUID.randomUUID()`, `Math.random()`.

---

## ACIMA-C005 · Persistence type leak

**Severity** `error` · **Level** L2 · **Principle** P3, P6

> Contracts MUST NOT expose entities, sessions, queryables or database types.

### Violation

```csharp
public sealed record OrderQuery(IQueryable<Order> Orders);          // ❌
public sealed record ProductView(Product Product);                  // ❌ EF entity
```

```python
@dataclass(frozen=True)
class ProductView:
    model: Base            # ❌ SQLAlchemy model in a contract
```

### Finding

```
ACIMA-C005  error  Contract type OrderQuery exposes a persistence type (IQueryable).
  src/Acima.Orders.Contracts/OrderQuery.cs:1
```

### Why

`IQueryable` in a contract hands the consumer a query that executes against the provider's database,
with the provider's mapping and the provider's transaction. That is not a boundary crossing; it is a
boundary deletion. An entity in a contract is the same problem with better manners: it carries lazy
loading, change tracking and invariants the consumer can now mutate.

### Fix

- A query is a *request*, not a query object: `GetOrders(OrderStatus Status, int Page)`.
- A view is a *projection*: a flat, immutable record built by the module.
- If a consumer needs filtering, add parameters to the query contract, not an expression tree.

### Detection

Denylist by language: `DbContext`, `DbSet`, `IQueryable`, SQLAlchemy `Session`/`Query`/`Base`,
Django `QuerySet`/`Model`, `*sql.DB`/`*sql.Tx`/`gorm.DB`, `EntityManager`, `JdbcTemplate`,
`Connection`, `Repository` types from the implementation.

---

## ACIMA-C006 · Untyped payload

**Severity** `error` · **Level** L2 · **Principle** P6

> Contracts MUST be explicitly typed. `object`, `dynamic`, `any`, bare dictionaries and JSON nodes are
> not contracts.

### Violation

```csharp
public sealed record IntegrationEvent(string Type, object Payload);        // ❌
```

```python
@dataclass(frozen=True)
class IntegrationEvent:
    type: str
    payload: dict[str, Any]                                             # ❌
```

### Finding

```
ACIMA-C006  error  Contract type IntegrationEvent has an untyped payload (object).
  src/Acima.Orders.Contracts/IntegrationEvent.cs:1
```

### Why

An untyped payload moves every validation, every versioning decision and every breaking change to
runtime, in every consumer, forever. It also defeats the compiler, which is the only tool that could
have caught the producer's mistake. A generic envelope with `object` is the canonical way to build a
"contract" that no one can safely consume.

### Fix

Make the payload a typed contract per event (`OrderPlaced`, `PaymentAuthorized`), and let the transport
envelope be a host concern (a discriminated union in the host's serializer, not in contracts). If a
generic envelope is genuinely required for transport, its `Payload` lives in the host, and the contracts
remain typed.

### Detection

C#: `object`, `dynamic`, `JsonElement`, `JObject`, `IDictionary<string, object>`. TS: `any`, `unknown`
in a public member, `Record<string, any>`, `object`. Python: `Any`, `object`, bare `dict`/`dict[str, Any]`,
`Mapping[str, Any]`. Go: `interface{}`, `map[string]any`, `json.RawMessage`. Java: `Object`,
`JsonNode`, `Map<String, Object>`.

---

## ACIMA-C007 · Contract cannot be constructed in one step

**Severity** `warning` · **Level** L2 · **Principle** P6

> A contract type must make its required state obvious and constructible atomically.

### Violation

```csharp
public sealed class PaymentAuthorized
{
    public PaymentAuthorized() { }                   // ❌ half-valid object exists
    public string Reference { get; init; } = "";
    public Money Amount { get; init; } = Money.Zero; // ❌ a "zero" amount is not a real state
}
```

### Finding

```
ACIMA-C007  warning  Contract type PaymentAuthorized has a parameterless constructor and no required members.
  src/Acima.Payments.Contracts/PaymentAuthorized.cs:3
```

### Why

A contract with a public parameterless constructor can always be created in an invalid state, and every
consumer must then defend against it. It also makes the type's meaning ambiguous: which members are
required? The compiler cannot say, so every reader guesses.

### Fix

Required values in the constructor; optional values explicit; no public parameterless constructor unless
the type has no required state. If a builder is genuinely needed (many optional parameters), put it in
the implementation and construct the immutable contract only when it is complete.

### Detection

Flags contract types with a public parameterless constructor plus settable or defaulted members, and
types where every member is optional (a "bag" with no required state). Warning, because some shapes are
legitimate.
