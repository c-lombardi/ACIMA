# Python profile

Python 3.12 · `src/` layout · packages per unit · `pytest` as the gate.

> **Compatibility example.** The tree below is the legacy shape with a shared kernel. Under the
default, contracts reference nothing; see [section 6](#6-service-topology-profile).

## 1. Layout

```
src/acima/
  shared_kernel/money.py            shared-kernel
  catalog/contracts/__init__.py     contracts   (__all__ is the surface)
  catalog/impl/*.py                 implementation
  orders/contracts/__init__.py      contracts
  orders/impl/*.py                  implementation  → catalog.contracts, payments.contracts
  payments/contracts/__init__.py    contracts
  payments/impl/*.py                implementation
  host/main.py                      host
tools/acima_arch.py                 tooling
tests/test_architecture.py          the gate
violations/                         fixtures (excluded)
```

## 2. What the toolchain enforces without help

**Nothing.** Python has no visibility, no package boundaries, no dependency rules and no import
restrictions. `from acima.catalog.impl.repository import SqlProductRepository` succeeds from anywhere.

That is not a reason to skip ACIMA; it is the reason the architecture test *is* the architecture:

| Obligation | Mechanism |
|---|---|
| Module boundary | `acima_arch` import analysis (`D001`, `D009`) |
| Contracts surface | `__all__` in `__init__.py`, checked by `L003` |
| Zero-dependency contracts | import classification (`D004`) |
| Immutability | `@dataclass(frozen=True, slots=True)` + `tuple`/`MappingProxyType` (`C001`, `C002`) |
| Typing | `mypy --strict` on `contracts` packages (`C006`) |

`mypy --strict` on contracts is a strong, cheap half of L2: it rejects untyped payloads, mutable default
arguments and missing annotations before any custom rule runs.

## 3. Architecture tests

**Idiomatic:** [`import-linter`](https://github.com/seddonym/import-linter) declares contracts in
`pyproject.toml`, plus `pytest` for the rest.

```toml
# pyproject.toml (excerpt)
[tool.importlinter]
root_packages = ["acima"]

[[tool.importlinter.contracts]]
name = "Contracts are leaves"
type = "forbidden"
source_modules = ["acima.catalog.contracts", "acima.orders.contracts", "acima.payments.contracts"]
forbidden_modules = ["acima.catalog.impl", "acima.orders.impl", "acima.payments.impl", "acima.host"]

[[tool.importlinter.contracts]]
name = "No implementation coupling"
type = "forbidden"
source_modules = ["acima.orders.impl"]
forbidden_modules = ["acima.catalog.impl", "acima.payments.impl"]
```

**Reference enforcer (this repository):** `tools/acima_arch.py`, driven by `pytest`.

```bash
python3 -m pytest tests/test_architecture.py -q
python3 tools/acima_arch.py --root . --format json
```

It uses the `ast` module — so it sees `import`, `from … import`, string annotations under
`from __future__ import annotations`, and it can distinguish a module-level mutable assignment from a
class attribute. Everything it decides is derived from `acima.config.json`; there are no hard-coded
module names in the tool.

## 4. Analyzers and linters

| Tool | Catches | Notes |
|---|---|---|
| **`acima_arch`** | `D*`, `L*`, `C*`, `A001`, `G*` | the only boundary enforcement Python has |
| `import-linter` | `D001`–`D003`, `D009` | declarative, fast, good failure messages |
| `ruff` (`TID`, `ANN`, `PLR`) | annotation hygiene, import sorting | enable `TID` (flake8-tidy-imports) for banned imports |
| `mypy --strict` | `C006`, `C007` | run it *only* on contracts packages in CI, for speed |
| **custom pylint/ruff plugin** | `C001`, `C002` at author time | optional; the pytest gate is sufficient |

A `ruff` rule that bans `impl` imports from other packages uses `banned-api` or `flake8-tidy-imports`:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"acima.catalog.impl".msg = "ACIMA-D001: import acima.catalog.contracts instead."
"acima.orders.impl".msg = "ACIMA-D001: import acima.orders.contracts instead."
```

## 5. Idioms and pitfalls

| Trap | Rule | Fix |
|---|---|---|
| `@dataclass(frozen=True)` with `lines: list[...]` | `C002` | `tuple[...]` |
| `dict[str, Any]` payload | `C006` | a `dataclass(frozen=True)` per event |
| `from acima.orders.impl.order import Order` | `D009` | ask for an `OrderSummary` view |
| `datetime.now()` in a contract | `C004` | pass `now` in |
| `__all__` missing in contracts | `L003` | define the surface explicitly |
| Mutable default `lines: list = []` | `C001` | `field(default_factory=tuple)` — or better, require it |
| `Protocol` classes in contracts that the module does not promise | `P2` | provided ports only |
| Relative imports (`from ..impl import x`) | `D001` | the runner resolves them; it sees through the syntax |

### One Python-specific note

`from __future__ import annotations` makes annotations strings, which is good for import cycles and bad
for naive tools. The reference enforcer parses annotations through the AST, so it sees the real type
regardless of the future import — and `mypy` runs with the same setting, so the two agree.

## 6. Service topology profile

Chapter 11's naming maps to one distribution per layer:

```
services/orders/
  orders_api/                       orders.api
  orders_api_contracts/             orders.api.contracts
  orders_application/               orders.application
  orders_application_contracts/     orders.application.contracts
  orders_domain/                    orders.domain
  orders_infrastructure/            orders.infrastructure
  orders_integrations_stripe/       orders.integrations.stripe
  orders_integrations_stripe_contracts/
  orders_catalog/                   messages orders -> catalog
  orders_host/                      composition root

tests/orders/domain/
```

Import packages use underscores; distribution names keep the dots so the service name is still
visible in `pip list`.

### A contracts package with no dependencies

```toml
[project]
name = "orders.application.contracts"
version = "1.0.0"
dependencies = []

[tool.setuptools.packages.find]
include = ["orders_application_contracts*"]
```

```python
# orders_application_contracts/__init__.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class OrderLine:
    product_id: str
    amount: str          # decimal as a string at the boundary, parsed by the consumer
    currency: str
    quantity: int

@dataclass(frozen=True, slots=True)
class PlaceOrder:
    customer_id: str
    lines: tuple[OrderLine, ...]

@dataclass(frozen=True, slots=True)
class PlaceOrderResult:
    accepted: bool
    order_id: str | None = None
    rejection: str | None = None
```

Stdlib only: `dataclasses`, `typing`, `decimal` when a value is constructed locally. No `pydantic`,
no `attrs`, no shared kernel import. `__post_init__` may validate, but must not read a clock or
generate an id (C004).

### Layer references

| Package | May import | Never imports |
|---|---|---|
| `orders_api` | `orders_api_contracts`, `orders_application_contracts` | `orders_application`, `orders_domain` |
| `orders_application` | `orders_application_contracts`, `orders_domain`, `orders_integrations_stripe_contracts` | `orders_api`, `orders_infrastructure` |
| `orders_domain` | stdlib only | any contracts package, any third-party package |
| `orders_infrastructure` | `orders_domain` ports, driver packages | `orders_api` |
| `orders_integrations_stripe` | `orders_integrations_stripe_contracts`, `stripe` | `orders_domain` |
| `orders_host` | everything | — |

### Third-party isolation

`orders_integrations_stripe_contracts` defines `StripeGateway` and its request/result dataclasses,
with no dependencies. `orders_integrations_stripe` imports it plus the vendor SDK, implements the
gateway and maps vendor errors. A `stripe` import in `orders_domain` is an ST-8 failure.

### Domain tests

```bash
pytest tests/orders/domain --cov=orders_domain --cov-fail-under=100 --cov-branch
```

Domain tests use no fixtures that touch a database, network or clock. Test names state the rule
(`test_rejects_more_than_available_stock`). Put the coverage gate in the domain package's CI job, not
in a repository-wide config that other packages can dilute.

### What the toolchain checks without help

`pip show orders.application.contracts` lists no `Requires`. `import-linter` or `tach` can encode the
layer table as contracts; `mypy --strict` catches the type leaks; `pipdeptree` exposes a vendor
package that has crept into the domain.
