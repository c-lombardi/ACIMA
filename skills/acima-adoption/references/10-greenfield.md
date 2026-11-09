# Greenfield playbook

Greenfield means there is no legacy to fight. The only mistake available is **deferring the
contract split until there are two teams**, by which point both modules already reference each
other's internals and the cheap version of this work is gone.

Rule: the gate exists before the second module does.

> **Consent gate.** This playbook is Phase 4 (approved implementation). Phase 1 may inspect and
> plan; Phase 2 must present the exact files, level and maintenance in the proposal; Phase 3 must
> receive an explicit answer. Do not scaffold source, config, waivers or CI until the owner approves
> that list. If the approved scope is assessment only, stop after the proposal. Do not create an
> adoption plan or communication plan unless the owner asks for one.

## Day 0 — the order is fixed

```
1. repository skeleton + build
2. module A contracts                (types only, no behaviour, no imports)
3. module B contracts                (types only, no behaviour, no imports)
4. module A implementation           (depends on A.contracts)
5. module B implementation           (depends on B.contracts, A.contracts)
6. host / composition root           (depends on everything; the DI layer)
7. acima.config.json + empty waivers (same commit as the skeleton)
8. enforcer in CI                    (before module C exists)
9. declare L3
```

Steps 3 and 4 before 5 and 6 is the whole discipline. Writing both contracts first forces the
question "what does B need from A?" while the answer is still a design decision rather than an
import statement.

## What goes in each unit

| Unit | Contains | May depend on |
|---|---|---|
| `<module>.contracts` | immutable messages, commands, queries, views, events, the capability interface, local value types | language core only |
| `<module>` | aggregates, services, adapters, persistence | its own contracts, **other modules' contracts** |
| `host` | composition root, configuration, transport, DI wiring | everything |

Nothing else. There is no shared kernel in the default: `Money` and identifiers live in the
contracts project that publishes them and are duplicated where another contract needs the same
shape. A "common" or "shared" project is the first violation, even before it has a name that sounds
like one.

## Minimal skeletons

### C#

```csharp
// Catalog.Contracts/Money.cs — contract-owned; duplicate the shape in Orders.Contracts, never share it.
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

`.csproj` shape: contracts reference nothing; value types are declared locally. Implementations
reference contracts; the host references implementations and is the only project that wires them. If a
`PackageReference` appears in a contracts project, `ACIMA-D004` is already true even if nothing imports
it yet.

### TypeScript

```ts
// orders/contracts/values.ts — owned here; duplicate the shape where another contract needs it.
export type Currency = 'EUR' | 'USD';
export class Money {
  constructor(readonly amount: number, readonly currency: Currency) {}
  times(quantity: number): Money { return new Money(this.amount * quantity, this.currency); }
}
export interface ProductId { readonly value: string; }
```

```ts
// orders/contracts/index.ts
import type { Money, ProductId } from './values.ts';

export interface OrderLine { readonly productId: ProductId; readonly unitPrice: Money; readonly quantity: number; }
export interface PlaceOrder { readonly customerId: string; readonly lines: readonly OrderLine[]; }
export interface Orders { place(command: PlaceOrder): OrderSummary | OrderRejected; }
```

`readonly` on every member, `readonly T[]` for collections, and imports only from this contract
package. `Money` and `ProductId` are declared in `values.ts`; another module that needs the same
shape declares its own. `import type` keeps the runtime graph honest.

### Python

```python
# orders/contracts/values.py — owned here; duplicate the shape where another contract needs it.
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

@dataclass(frozen=True, slots=True)
class ProductId:
    value: str
```

```python
# orders/contracts/__init__.py
from dataclasses import dataclass
from .values import Money, ProductId

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

Frozen dataclasses, tuples rather than lists, imports only from this contract package, no `impl/`,
no framework imports.

### Go

```go
// internal/orders/contracts/values.go — owned here; duplicate the shape where another contract needs it.
package orderscontracts

import "errors"

type ProductID string

type Money struct {
    amountMinor int64
    currency    string
}

func NewMoney(amountMinor int64, currency string) (Money, error) {
    if amountMinor < 0 || currency == "" {
        return Money{}, errors.New("invalid money")
    }
    return Money{amountMinor: amountMinor, currency: currency}, nil
}
```

```go
// internal/orders/contracts/contracts.go
package orderscontracts

type OrderLine struct {
    ProductID ProductID
    UnitPrice Money
    Quantity  int
}

type PlaceOrder struct {
    CustomerID string
    Lines      []OrderLine
}
```

Go has no immutability keyword: value semantics plus unexported fields and no pointer fields is
the contract shape. `internal/` gives you the boundary for free; the enforcer checks that the
*contracts* package does not reach back into an implementation.

## acima.config.json

Start from [`../assets/acima.config.template.json`](../assets/acima.config.template.json) **only if
configuration is in the approved scope**. Every unit needs `id`, `role`, `paths`, and `module` for
contracts and implementations. Put the file at the repository root and commit it with the skeleton,
not later — but do not create it before consent.

```json
{
  "standard": "1.0.0-draft.1",
  "language": "typescript",
  "level": "L3",
  "units": [
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/catalog/impl"] },
    { "id": "host", "role": "host", "paths": ["src/host"] }
  ],
  "exclude": ["node_modules", "tests", "violations"],
  "waivers": ".acima/waivers.json"
}
```

Propose L3 immediately: there is no legacy, so there is no technical reason to start at L1. The
owner still approves the level explicitly; if they choose L1 or L2, record that decision and do not
claim L3.

## CI gate

The gate is one command plus an exit-code check. Examples per language are in
[../vendor/docs/guides/architecture-tests.md](../vendor/docs/guides/architecture-tests.md).

For greenfield the gate should also prove it is alive: assert that the enforcer discovered the
expected number of units. A run that finds nothing exits 0 and proves nothing.

## First two weeks

| Day | Outcome |
|---|---|
| 1 | approved skeleton, two contracts, config, empty waivers — one commit |
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
- [ ] contracts import nothing and declare their value types locally (`ST-5`)
- [ ] `acima.config.json` is committed and declares L3
- [ ] the waiver file exists and is empty
- [ ] CI fails on a deliberately introduced violation (verified, then reverted)
- [ ] one contract has already evolved without breaking a consumer
