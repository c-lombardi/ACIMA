# Before and after

This is the practical difference ACIMA is designed to make. The reference application is
a small ordering system: Catalog owns products, Orders owns orders, Payments owns
authorization, and a customer identity crosses the order boundary as a value.

## Before: the coupling that looks convenient

```text
Orders ──> Catalog implementation (CatalogModule, SQL repository)
   │
   ├────> shared mutable DTO from Common
   │
   └────> direct SQL against catalog_products

Payments ──> Orders implementation, because the type was "already there"
```

Symptoms:

- Orders cannot compile, test or deploy without Catalog's implementation.
- A change to Catalog's repository becomes an Orders change.
- A mutable message is changed by one consumer and observed by another.
- Two modules read and write the same table.
- A cycle appears when Payments is made to depend on Orders as well.
- An exception is added as a comment or an incomplete waiver and is forgotten.

## After: the boundary is structural

```text
Orders ──> Catalog.Contracts (ProductView, CatalogReader)
   │
   ├────> its own value types (OrderId, Money, OrderLine)
   │
   └────> its own orders schema

Catalog ──> its own catalog schema
Payments ──> Payments.Contracts and its own schema
Host ─────> constructs every module; modules never construct each other
```

The host is the only place that knows every implementation. A module can be tested with a
tiny fake port. The dependency graph is acyclic, contracts are immutable, and each schema
has one owner.

## The violations, the evidence, and the correction

| Failure mode | Rule | Executable evidence | Correction |
|---|---|---|---|
| Orders imports Catalog's implementation | `ACIMA-D001` | `tools/acima_walkthrough.py`; `examples/python/violations/d001_orders_imports_catalog_impl.py` | Depend on `catalog.contracts`; map at the boundary. |
| Contracts import another module's contracts | `ACIMA-D003` | `examples/python/violations/d003_contracts_import_contracts.py` | Declare local value types or carry identity. |
| Mutable message or collection | `ACIMA-C001`, `C002` | `examples/python/violations/c001_mutable_contract.py`, `c002_mutable_collection.py` | Frozen dataclass, readonly fields, immutable collections. |
| Shared persistence access | `ACIMA-A001` | `examples/python/violations/a001_shared_table.py` | One schema owner; use a contract or an event. |
| Uncontrolled configuration ownership | `ACIMA-A002` (warning) | **Not evaluated by the portable runner** | Pass namespaced configuration into the module; review manually. |
| Ambient configuration read inside a component | `ACIMA-A005` (warning) | Python/TypeScript automated; manual elsewhere | Resolve and validate it in the host; inject typed settings. |
| Unnamed operational literal | `ACIMA-A006` (warning) | Python/TypeScript candidate scanner; manual elsewhere | Name the value in its owner or inject it from configuration. |
| Discovery chooses module-owned components | `ACIMA-D013` (warning) | Python/TypeScript automated; manual elsewhere | Name registrations/constructors; keep discovery only in a reviewed, proven exception. |
| Dependency injected into a property or field | `ACIMA-D014` (warning) | Python/TypeScript automated; manual elsewhere | Move the dependency to the constructor and supply it from the host. |
| Collaborator captured by a closure or callback | `ACIMA-D015` (warning) | Python/TypeScript automated; manual elsewhere | Pass it as a parameter or declared field; keep pure closures. |
| Dependency partially applied inside a component | `ACIMA-D016` (warning) | Python/TypeScript automated; manual elsewhere | Move `bind`/`partial` to the composition boundary or keep it as a parameter. |
| Dependency cycle | `ACIMA-D005` | `examples/python/violations/d005_cycle_orders.py`, `d005_cycle_payments.py` | Invert the dependency, publish an event, or merge the modules. |
| Unapproved architectural exception | `ACIMA-G001`, `G002` | `examples/python/violations/waivers.json` | Owner, reason, scope, expiry, review date. |

The `A002` row is deliberately not claimed as detected. The report lists it under
**Not evaluated**; a human must review configuration access. `A005` and `A006` are automated only
where a language profile implements them, and their findings are candidates that still need an
ownership decision. The same applies to `D013` and `D014`: they identify construction patterns, not a
runtime graph. A framework-managed controller with constructor injection is compliant even though
application code does not instantiate it. `D015` and `D016` likewise identify a syntactic capture or
pre-binding, not proof of the runtime dependency graph. That distinction is part of the standard.

## Run the demonstration

From the repository root:

```bash
# Inject a real D001 violation, show the finding, correct it, verify clean.
python3 tools/acima_walkthrough.py

# See the full gallery of deliberate violations.
python3 examples/python/tools/acima_arch.py \
  --root examples/python \
  --config acima.gallery.config.json

# Produce an evidence report with explicit unevaluated rules.
python3 tools/acima.py report --root examples/python
```

The walkthrough output is the real enforcer output, not a mock:

```text
before: clean ordering application — 0 findings
introduced: Orders imports Catalog's implementation (src/acima/orders/impl/reach_into_catalog.py)
finding: ACIMA-D001 — Module orders imports the implementation unit catalog (expected catalog.contracts).
  src/acima/orders/impl/reach_into_catalog.py:1  from acima.catalog.impl.repository import InMemoryProductStore
fixed: depend on Catalog's contract instead of its implementation
after: 0 findings
result: violation detected, corrected, and verified
```

The bad and fixed code are both small enough to review:

```python
# before: couples Orders to Catalog's storage and constructor
from acima.catalog.impl.repository import InMemoryProductStore

def leaked_store() -> InMemoryProductStore:
    return InMemoryProductStore()
```

```python
# after: depends only on Catalog's published capability
from acima.catalog.contracts import CatalogReader

def catalog_reader(catalog: CatalogReader) -> CatalogReader:
    return catalog
```

## Scope and limits

The Python reference application has four modules: Catalog, Orders, Customers and
Payments. Orders validates the customer through the Customers contract and stores the
customer identity in its own values; it does not import the Customers implementation.
The TypeScript, Go and .NET examples carry `customer_id` as a value and do not yet ship
the fourth module. Adding it follows the same shape: the module owns its customer view,
and consumers depend only on its contract.

The walkthrough demonstrates one D001 path end to end. The galleries cover the other
portable rules. Rules that need native analyzers or architectural judgement are listed in
[Capability status](../status.md) and in the CLI report; they are not silently counted as
passes.

## What this buys a team

- A compile-time or gate-time answer to “may this dependency exist?”
- A contract surface that can be versioned independently.
- A smaller blast radius for a change.
- An exception process that expires instead of becoming permanent.
- A machine-readable finding an agent can act on without guessing.

It does not prove runtime autonomy, deployment independence or organizational ownership.
Those require the runtime-boundary work and human decisions described in the standard.
