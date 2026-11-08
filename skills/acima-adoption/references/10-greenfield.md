# Greenfield playbook

Greenfield means there is no legacy to fight. The only mistake available is **deferring the
contract split until there are two teams**, by which point both modules already reference each
other's internals and the cheap version of this work is gone.

Rule: the gate exists before the second module does.

## Day 0 — the order is fixed

```
1. repository skeleton + build
2. shared kernel                     (one file: Money, ids)
3. module A contracts                (types only, no behaviour)
4. module B contracts                (types only, no behaviour)
5. module A implementation           (depends on A.contracts, kernel)
6. module B implementation           (depends on B.contracts, A.contracts, kernel)
7. host / composition root           (depends on everything)
8. acima.config.json + empty waivers (same commit as the skeleton)
9. enforcer in CI                    (before module C exists)
10. declare L3
```

Steps 3 and 4 before 5 and 6 is the whole discipline. Writing both contracts first forces the
question "what does B need from A?" while the answer is still a design decision rather than an
import statement.

## What goes in each unit

| Unit | Contains | May depend on |
|---|---|---|
| `<module>.contracts` | immutable messages, commands, queries, views, events, the capability interface | language core + shared kernel |
| `<module>` | aggregates, services, adapters, persistence | its own contracts, **other modules' contracts**, shared kernel |
| `shared-kernel` | value types with invariants and no IO (`Money`, ids) | language core only |
| `host` | composition root, configuration, transport | everything |

Nothing else. A "common" or "shared" project beyond the kernel is the first violation, even
before it has a name that sounds like one.

## Minimal skeletons

### C#

```csharp
// Kernel/Money.cs — readonly struct, validation in the factory, no IO.
public readonly struct Money
{
    private Money(decimal amount, Currency currency) { Amount = amount; Currency = currency; }
    public decimal Amount { get; }
    public Currency Currency { get; }
    public static Money Of(decimal amount, Currency currency) { /* guard */ return new(amount, currency); }
}
```

```csharp
// Orders.Contracts/PlaceOrder.cs — data only, no services, no DbContext.
public sealed record OrderLine(ProductId ProductId, Money UnitPrice, int Quantity);
public sealed record PlaceOrder(string CustomerId, IReadOnlyList<OrderLine> Lines);
public interface IOrders { PlaceOrderResult Place(PlaceOrder command); }
```

`.csproj` shape: contracts reference the kernel and nothing else; implementations reference
contracts; the host references implementations. If a `PackageReference` appears in a contracts
project, `ACIMA-D004` is already true even if nothing imports it yet.

### TypeScript

```ts
// orders/contracts/index.ts
import type { Money, ProductId } from '../../shared-kernel/money.ts';

export interface OrderLine { readonly productId: ProductId; readonly unitPrice: Money; readonly quantity: number; }
export interface PlaceOrder { readonly customerId: string; readonly lines: readonly OrderLine[]; }
export interface Orders { place(command: PlaceOrder): OrderSummary | OrderRejected; }
```

`readonly` on every member, `readonly T[]` for collections, and no imports outside the kernel.
`import type` keeps the runtime graph honest.

### Python

```python
# orders/contracts/__init__.py
from dataclasses import dataclass
from acima.shared_kernel import Money, ProductId

@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: ProductId
    unit_price: Money
    quantity: int

@dataclass(frozen=True, slots=True)
class PlaceOrder:
    customer_id: str
    lines: tuple[OrderLine, ...]
```

Frozen dataclasses, tuples rather than lists, no imports from `impl/`, no framework imports.

### Go

```go
// internal/orders/contracts/contracts.go
package orderscontracts

type OrderLine struct {
    ProductID sharedkernel.ProductID
    UnitPrice sharedkernel.Money
    Quantity  int
}

type PlaceOrder struct {
    CustomerID string
    Lines      []OrderLine
}
```

Go has no immutability keyword: value semantics plus no pointer fields is the contract shape.
`internal/` gives you the boundary for free; the enforcer checks that the *contracts* package
does not reach back into an implementation.

## acima.config.json

Start from [`../assets/acima.config.template.json`](../assets/acima.config.template.json).
Every unit needs `id`, `role`, `paths`, and `module` for contracts and implementations. Put the
file at the repository root and commit it with the skeleton, not later.

```json
{
  "standard": "1.0.0-draft.1",
  "language": "typescript",
  "level": "L3",
  "units": [
    { "id": "shared-kernel", "role": "shared-kernel", "paths": ["src/shared-kernel"] },
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/catalog/impl"] },
    { "id": "host", "role": "host", "paths": ["src/host"] }
  ],
  "exclude": ["node_modules", "tests", "violations"],
  "waivers": ".acima/waivers.json"
}
```

Declare L3 immediately. There is no legacy, so there is no reason to start at L1; starting low
signals that the rules are optional, and they never become mandatory later.

## CI gate

The gate is one command plus an exit-code check. Examples per language are in
[../../../docs/guides/architecture-tests.md](../../../docs/guides/architecture-tests.md).

For greenfield the gate should also prove it is alive: assert that the enforcer discovered the
expected number of units. A run that finds nothing exits 0 and proves nothing.

## First two weeks

| Day | Outcome |
|---|---|
| 1 | skeleton, kernel, two contracts, config, empty waivers — one commit |
| 2 | first implementations, host wiring, end-to-end test |
| 3 | enforcer in CI, deliberately broken branch to prove the gate fails, then reverted |
| 4–5 | second module's contract reviewed by the first module's owner |
| week 2 | first contract evolution: add a field, deprecate one, keep consumers compiling |

The deliberate-break exercise matters more than it sounds. A gate nobody has seen fail is a gate
the team will assume is decorative.

## Greenfield anti-patterns

| Symptom | What it becomes |
|---|---|
| A `shared` or `common` project appears | an unowned module that everyone depends on; `D001`/`D007` in six months |
| Contracts contain a service class | `C003`; contracts become a second implementation |
| `IReadOnlyList` replaced by `List` "for convenience" | `C002`; callers mutate shared state |
| Contracts importing a validator or an ORM attribute | `D004`; every consumer inherits the dependency |
| Level starts at L1 "to be safe" | the gate is never raised, because raising it is now a project |
| Waivers created in week one | there is nothing to waive; a waiver here is a design decision made silently |

## Definition of done

- [ ] every module has a contracts unit and an implementation unit
- [ ] the module graph is acyclic, and the enforcer proves it
- [ ] contracts import only the kernel
- [ ] `acima.config.json` is committed and declares L3
- [ ] the waiver file exists and is empty
- [ ] CI fails on a deliberately introduced violation (verified, then reverted)
- [ ] one contract has already evolved without breaking a consumer
