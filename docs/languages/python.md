# Python profile

Python 3.12 · `src/` layout · packages per unit · `pytest` as the gate.

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
