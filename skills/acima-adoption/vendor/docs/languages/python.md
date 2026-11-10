# Python profile

Python 3.12 · `src/` layout · packages per unit · `pytest` as the gate.

> **Reference example.** The tree below is the compiled example in `examples/python`. It uses the
default: every contracts package imports nothing and owns its value types; see
[section 6](#6-service-topology-profile).

## 1. Layout

```
src/acima/
  catalog/contracts/__init__.py     contracts   (__all__ is the surface)
  catalog/contracts/values.py       contract-owned Money and ids
  catalog/impl/*.py                 implementation
  customers/contracts/__init__.py   contracts
  customers/contracts/values.py     contract-owned customer view and id
  customers/impl/*.py               implementation
  orders/contracts/__init__.py      contracts
  orders/impl/*.py                  implementation  → catalog.contracts, customers.contracts, payments.contracts
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
source_modules = ["acima.catalog.contracts", "acima.orders.contracts", "acima.customers.contracts", "acima.payments.contracts"]
forbidden_modules = ["acima.catalog.impl", "acima.orders.impl", "acima.customers.impl", "acima.payments.impl", "acima.host"]

[[tool.importlinter.contracts]]
name = "No implementation coupling"
type = "forbidden"
source_modules = ["acima.orders.impl"]
forbidden_modules = ["acima.catalog.impl", "acima.customers.impl", "acima.payments.impl"]
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

### Explicit inputs (`D011`, `D012`)

Python makes the omission easy to write: `def __init__(self, clock=None)` and
`def place(self, notify=True)` are ordinary code. The reference enforcer reads `__init__` and function
signatures with `ast` and reports a parameter that carries a default. A nullable annotation **without**
a default is required and is not a finding — `clock: Callable[[], datetime] | None` forces the caller
to pass `None` explicitly. `@overload` stubs, dunders other than `__init__`, contracts, tests and
tooling are out of scope (chapter 13). `mypy --strict` does not catch the omission: an argument with a
default is optional to the type checker, which is exactly why the architecture rule is separate.

### Values and configuration (`A005`, `A006`)

Use module-level uppercase constants for fixed policy (`MANUAL_REVIEW_THRESHOLD`) and a frozen
dataclass for a component's settings. The host reads the environment and constructs
`OrdersSettings(retry_limit=...)`; `OrdersService` requires that object and never calls `os.getenv`.
The reference enforcer scans `implementation` and `adapter` units for `os.environ`/`os.getenv`
(`A005`). For `A006` it scans implementation, adapter and host roles for meaningful inline literals,
mutable meaningful bindings, and same-module duplicate immutable declarations. Uppercase named
constants are accepted; a lowercase module constant is also immutable but may not be rebound.
Local calls are traced to the callee's receiving parameter where both are in the same file, and
`capacity`, `threshold`, `secret` and similar names are candidate evidence. Every finding is a
candidate: semantic equivalence, units, ownership and configuration category require review.
Incidental literals are not findings; the rule is not a mandate to extract every number. Config
modules belong to the host, not to a package that a module imports for convenience.

### Composition and injection (`D013`, `D014`)

The host's `build()` is the composition boundary: `CatalogModule(InMemoryProductStore())` and
`OrdersModule(catalog=catalog.reader(), ...)` name every component and every dependency. Do not scan
packages with `pkgutil.walk_packages` or `importlib.import_module` to decide what exists; `D013`
reports those calls in a host unit. Do not declare `repo: Provide[...]` or `repo: Inject[...]` class
fields; `D014` reports them. Constructor injection and a module-owned composition function are both
explicit. A framework may activate a request handler, but the handler's application dependencies
must be constructor parameters.Both rules are automated candidates here, not proof of the runtime graph.

### Functional capture (`D015`, `D016`)

Pass collaborators as parameters, including through a curried outer function; a lambda may capture
an explicit parameter of its enclosing function. Do not read a module-level `order_repository` or an
enclosing local from a callback (`D015`). Keep `functools.partial` of a collaborator at the host, not
inside a component (`D016`). Pure closures over constants and transformations are allowed. The AST
scanner does not resolve `getattr`/`globals`; those remain manual review.

### Lifecycle and state ownership (`A007`–`A009`)

A module-level object is a process singleton in practice; a decorator such as `@lru_cache` adds a
shared cache with its own lifetime; a mutable default argument is shared by every call. Decide at the
host whether a component is shared, request/tenant scoped or transient, and pass request-bound values
as parameters rather than storing them. The reference scanner reads `register(... lifetime=...)` and
`add_singleton`/`add_scoped`/`add_transient` in host units: `A007` reports a stateless transient
service, `A008` reports a shared service whose constructor annotation names a scoped dependency, and
`A009` reports a shared service initialising a mutable container. Decorators, provider functions,
module-level construction and async task lifetimes are not resolved; use context managers for
resource ownership and record manual evidence for cleanup, concurrency and tenant isolation
(chapter 17).

### Intent-revealing naming (`N001`–`N003`)

Classes and protocols use `PascalCase`; functions, methods, variables, parameters and modules use
`snake_case`; constants use `UPPER_SNAKE_CASE`. A leading underscore marks a non-public name. Name
the responsibility (`OrderValidator`), not a generic role (`OrderHelper`). `N001` checks class-name
casing and `N002` checks generic class names; both are candidates. `N003` is manual: side effects,
boolean polarity, units, abbreviations, domain consistency and contextual naming are review
claims, not scanner output. Framework-required names and generated declarations need an owned
exception (chapter 18).

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
