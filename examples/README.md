# Reference implementations

Four small products — an ordering system — written four times, once per implemented language. They exist to prove that the ACIMA rules are checkable in a real language, and to give the adoption skill something executable to point at.

They are **not** production application templates and **not** evidence that ACIMA fits every codebase.

## What each example contains

Every implementation has the same shape:

| Part | Purpose |
|---|---|
| `src/.../contracts` | the only cross-module surface, zero dependencies, immutable |
| `src/.../impl` | domain, application and persistence per module |
| host | composition root; the only unit that knows every module |
| `tools/` | the reference enforcer for that language |
| `violations/` | one fixture per rule plus `expected.json` |
| `tests/` | behaviour tests (not architecture tests) |
| `acima.config.json`, `acima.gallery.config.json` | unit map for the clean tree and for the gallery |

| Language | Modules | Enforcement mechanism |
|---|---|---|
| Python | Catalog, Orders, Customers, Payments | nothing in the language; the rule engine is the boundary |
| TypeScript | Catalog, Orders, Payments | `exports` map plus rules over the import graph |
| Go | Catalog, Orders, Payments | `internal/` compile-time isolation plus rules |
| .NET | Catalog, Orders, Payments | separate projects, `internal`, `PrivateAssets` |

## Requirements they demonstrate

| Requirement | Where to look |
|---|---|
| R1 module ownership | an implementation that is unreachable from another module (`D001`, `D009`) |
| R2 explicit contracts | contracts units with messages, values, ports and typed results |
| R3 dependency isolation | contracts with no project/package references; an acyclic graph |
| R4 data and configuration ownership | per-module stores and configuration namespaces (`A001`–`A003`) |
| R5 controlled composition | the host wiring everything; no module referencing it (`D006`) |

## Run them

```bash
cd examples/python     && python3 tools/acima_arch.py --root . --format json      # clean tree
cd examples/python     && python3 tools/acima_arch.py --config acima.gallery.config.json --format json  # gallery
cd examples/typescript && node tools/acima-arch.mjs --root . --format json
cd examples/go         && go run ./tools/archtest --root .
cd examples/dotnet     && dotnet run --project tools/Acima.ArchTests -- --root .
```

The whole set, with drift checking, is [`../conformance/run.py`](../conformance/README.md). The Python behaviour suite is `python3 -m unittest discover -s tests`.

## How they are used

- **Conformance:** each example is the positive fixture, and its `violations/` gallery is the negative fixture. A rule counts as implemented only when both exist.
- **Adoption:** the skill points agents at these trees as the target shape, and `test_injected_violation.py` proves a clean result by injecting a violation into a copy.
- **Not** used as a benchmark of application quality, and not a claim that the four implementations are feature-equivalent.
