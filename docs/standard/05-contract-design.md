# 5. Contract design

Contracts are the only thing another team will ever see. This chapter says what may be in them, what
must never be, and how they change over time.

## 5.1 The seven contract types

| Type | Tense | Direction | Example |
|---|---|---|---|
| Command | imperative | consumer → provider | `PlaceOrder` |
| Query | imperative | consumer → provider | `GetOrderSummary` |
| Event | past | provider → subscribers | `OrderPlaced` |
| View | none | provider → consumer | `OrderSummary` |
| Value | none | anywhere | `ShippingAddress` |
| Provided port | capability | provider → consumer | `CatalogReader` |
| Result | outcome | provider → consumer | `PlaceOrderResult` |

If a type in a contracts unit does not fit one of these, it belongs in the implementation. The most
common offenders are "helper" classes, extension methods, constants, and anything with the word
`Manager` in it.

## 5.2 The immutability contract (`C001`–`C007`)

An immutable contract has these properties. Each maps to a rule.

| Property | Rule | Language expressions that satisfy it |
|---|---|---|
| State set at construction, never after | `C001` | C# `record` / `init` / `readonly` · TS `readonly` + `Readonly<>` · Python `@dataclass(frozen=True)` / `NamedTuple` · Go struct with unexported fields + constructor · Java `record` |
| Collections are immutable or copied | `C002` | C# `IReadOnlyList<T>` from `ToArray()` · TS `readonly T[]` / `ReadonlyArray` · Python `tuple` / `MappingProxyType` · Go slice copied into an unexported field with an accessor · Java `List.copyOf` |
| No behaviour beyond validation | `C003` | constructor checks, normalisation, derived read-only properties |
| No ambient state | `C004` | no `DateTime.Now`, `new Date()`, `datetime.now()`, `time.Now()`, `Instant.now()`, no `Guid.NewGuid()` at field initialiser |
| No persistence types | `C005` | no entities, no `DbContext`, `IQueryable`, `Session`, `QuerySet`, `*sql.DB` |
| Explicitly typed | `C006` | no `object`, `dynamic`, `any`, `dict[str, Any]`, `map[string]any`, `JSONObject` |
| Constructible in one step | `C007` | required members in the constructor; no "init then set" protocol |

### The three temptations

**1. "It's just a DTO, mutation is fine."** A mutated DTO is a message whose sender and receiver share
state. The bug that follows is never localised: handler A changes `order.Total` and handler B, running
on the same instance in a pipeline, sees the changed value. Immutability removes the class of bug.

**2. "The setter is only for the serializer."** Then the serializer owns your contract. Use a
constructor-based deserializer (System.Text.Json `[JsonConstructor]`, Jackson records, Python
`dataclass`, Go tagged struct with exported fields at the *adapter* level) — or map an internal
transport type to the contract, and keep the contract immutable.

**3. "A computed property is behaviour."** Derived read-only values are fine: `Total => Lines.Sum(l => l.Amount)`
is a view of state, not a decision. Anything that branches on business conditions, reads IO, or
depends on time is `C003`.

## 5.3 Collections

The rule is about **aliasing**, not about the type name.

```csharp
// ❌ C002 — the caller can mutate the order's lines
public sealed record OrderDraft(IReadOnlyList<OrderLine> Lines);

// ✅ C002 — copied at construction, exposed read-only
public sealed record OrderDraft
{
    public IReadOnlyList<OrderLine> Lines { get; }
    public OrderDraft(IEnumerable<OrderLine> lines) => Lines = lines.ToArray();
}
```

```python
# ❌ C002
@dataclass(frozen=True)
class OrderDraft:
    lines: list[OrderLine]      # frozen does not make the list immutable

# ✅
@dataclass(frozen=True)
class OrderDraft:
    lines: tuple[OrderLine, ...]
```

`frozen=True` on a dataclass prevents rebinding the attribute, not mutating the list. This is the most
common false sense of safety in Python and TypeScript codebases, and the reason `C002` is a separate
rule from `C001`.

## 5.4 Optionality and construction

`C007` is a `warning`, not an error, because some shapes legitimately need builders. The obligation is
that **required state is obvious**:

- required values are constructor parameters, and the constructor rejects invalid ones;
- optional values are explicit, not silently defaulted into an ambiguous state;
- no contract has a public parameterless constructor that produces a half-valid object;
- "update" messages are not partial mutations of a full message; if a command is a patch, its name and
  its shape say so (`ChangeShippingAddress`, not `Order` with nulls).

## 5.5 Value types and where they live

| Kind | Home | Example |
|---|---|---|
| Cross-boundary primitive with invariants | the contract project that needs it, duplicated (default); legacy shared kernel | `Money`, `Quantity`, `OrderId` |
| Module-specific value | that module's contracts | `ShippingAddress`, `PaymentReference` |
| Value used by exactly one message | inline in that contract's package | a small record used by one command |

Duplication is acceptable and sometimes correct: if `Catalog` and `Orders` both need a
`ProductSnapshot`, and neither can own it without the other importing its contracts (`D003`), then
**duplicating the shape at the boundary is better than sharing a model**. The two snapshots will
diverge for good reasons — that is not duplication, that is two concepts that happen to look alike
today.

## 5.6 Events

An event is a fact. Its shape is a promise to every subscriber, forever, because events are archived,
replayed and consumed by systems you have not written yet.

- **Name** it in the past tense, from the owner's perspective: `OrderPlaced`, not `PlaceOrderEvent` or
  `OrderServicePlacedOrder`.
- **Carry identity, not entities.** `OrderPlaced { OrderId, CustomerId, Total, PlacedAt, Lines }` is
  fine; a serialised aggregate with lazy-loaded navigation properties is not.
- **Carry the version**: `OrderPlacedV1` or an explicit `SchemaVersion` field, and treat additions
  carefully (see 5.7).
- **Carry the facts the event needs to be meaningful alone**, because a subscriber may process it three
  weeks later during a replay, when the source database no longer has the same state.
- **Never carry a request to do something.** `OrderPlaced` is a fact; `PleaseSendEmail` is a command
  wearing a past tense.

## 5.7 Evolution

Contract changes are classified before they are written:

| Change | Class | Action |
|---|---|---|
| Add an optional member with a safe default | additive | bump minor; update baseline |
| Add a new contract type / event version | additive | bump minor; update baseline |
| Rename a member | breaking | new event version or new major; keep the old one until consumers migrate |
| Change a member's type or meaning | breaking | new version; never in place |
| Remove a member | breaking | deprecate first, remove in the next major |
| Change validation to reject previously valid input | breaking in practice | treat as breaking even though the shape is unchanged |

`G004` turns the baseline into an artefact: `.acima/api-surface.json` records every public type,
member and signature in every contracts unit. A change that is not additive fails until the baseline
is regenerated **and reviewed**, which is the moment a human decides whether the change is allowed.

The baseline is deliberately a plain file in the repository, not a database: it is reviewed in the
same pull request as the change, which is the only point at which anyone has the context to judge it.

## 5.8 Serialization neutrality

Contracts must serialize *somewhere*, but they must not be owned by a serializer (`D004`, `L002`).

- No serializer-specific attributes in contracts where avoidable. Where unavoidable (Go struct tags),
  use the most portable form and treat it as syntax, not dependency — Go tags are strings, not imports,
  so they do not violate `D004`.
- Configure the serializer in the **host**, with a policy that matches the contracts' shape (for
  example: immutable objects via constructor binding, explicit `null` handling, no polymorphic type
  names).
- If a transport demands a different shape, define an adapter type in the **consumer or the host** and
  map. The contracts are the domain of the boundary; the wire format is a detail of one adapter.

## 5.9 Errors are contracts too

A command that can fail must say how, in the contract (`C006` forbids `object`-shaped errors):

- Prefer a typed result: `PlaceOrderResult.Success(OrderId)` / `PlaceOrderResult.Rejected(Reason)`.
- Model expected failures as values in the contract (out of stock, payment declined). Model unexpected
  failures as exceptions/errors, and let the host translate them.
- Never put a `bool Succeeded` plus a `string? ErrorMessage` in a public contract: it is untyped,
  untranslatable, and forces every consumer to parse English.

## 5.10 Checklist for a contract review

- [ ] Does every type fit one of the seven kinds in 5.1?
- [ ] Is every type immutable, with collections copied or truly immutable (`C001`, `C002`)?
- [ ] Is the type constructible atomically, with validation in the constructor (`C007`)?
- [ ] Does it import anything other than the language core (`D004`, `L002`)? The kernel is legacy.
- [ ] Does it name another module's types (`D003`)?
- [ ] Does it expose persistence, transport or hosting types (`C005`, `L002`)?
- [ ] Is every failure a typed outcome rather than a string or an untyped bag (`C006`)?
- [ ] Are events past-tense facts with stable names and versions (5.6, `G004`)?
- [ ] Is the contract documented, including its invariants (`G003`)?

## 5.11 Layer contracts and absolute isolation

Chapter 11's profile makes two changes to contract design.

**Each layer owns its contract surface.** `Orders.Api.Contracts` holds HTTP DTOs;
`Orders.Application.Contracts` holds commands, queries, results and ports. Neither references the
other. The API maps its request into an application command; the application maps its result into an
API response. A contract project is never the boundary type of two layers.

**Contracts reference nothing.** By default, the shared-kernel exception in P3.5 does not apply. A
contract project has zero project and package references, including the kernel. Value types
are primitives (`decimal` + currency code) or records declared inside the contract project and
duplicated where another contract needs them. Serializer, ORM, DI and validation-framework
attributes are forbidden; configure those outside the contract.

Consequences for a contract review:

- [ ] Does the contracts project compile alone, with no other project on the build path (`ST-5`)?
- [ ] Is every DTO owned by exactly one layer (`ST-4`)?
- [ ] Does the caller map into the callee's contract, rather than passing its own DTO (`ST-6`)?
- [ ] Is there any kernel, vendor or framework type in the contract (P12)?
- [ ] Is serialization configured by the consumer, not by attributes on the contract?

Immutability, typed failures and documented invariants do not change. The profile narrows what a
contract may reference; it does not loosen what it may contain.

## 5.12 Ports for integration libraries

A **port** is a contracts unit declaring a capability the system needs, in the system's vocabulary.
It is the consumer-facing half of an integration seam; the adapter is the other half (chapter 4
§4.10, chapter 11 §11.7).

```ts
/** The capability the application needs from a code editor. */
export interface EditorPort {
  open(note: string): EditorHandle;
  read(handle: EditorHandle): string;
}
```

Three things about that shape are deliberate:

- **It carries no vendor type.** `EditorHandle` is the port's own value type. The adapter converts
  to and from `monaco.editor.IStandaloneCodeEditor`; the application never sees the conversion.
  A port that imports the vendor is `D010`.
- **It may be behavioural.** A port is a capability, so a method signature is the normal case. No DTO
  is required: do not invent a `OpenNoteRequest`/`OpenNoteResponse` pair to satisfy a shape nobody
  asked for. Messages are required for *events and commands that cross a module boundary*
  (chapter 5 §5.1), not for a port.
- **`C007` does not apply.** One-step construction is a rule about contract *types* whose required
  state must be obvious; an interface has no construction. `C007`'s catalogue entry marks it
  `automation: manual`, and its review question is answered by "not applicable" for an interface.

What a port *does* inherit from contracts: it is immutable in shape, it documents its invariants
(`G003`), it names nothing another module owns (`D003`), it exposes no persistence or framework type
(`C005`, `L002`), and it is dependency-free (`D010`, the port counterpart of `D004`).

### Port or provided port?

Both exist in ACIMA and they are not the same decision:

- A **provided port** is a capability a module promises to fulfil for its consumers; it lives in that
  module's contracts unit (`catalog.contracts.CatalogReader`).
- A **port for an integration library** declares what the system needs *from a vendor*. Its owner is
  the consuming module or a dedicated `editor.port` unit, and its implementation is an adapter that
  nobody else may reference.

The test is who changes when the port changes. A provided port changes when the provider's capability
changes. An integration port changes when the consumer's need changes — not when the vendor ships.
