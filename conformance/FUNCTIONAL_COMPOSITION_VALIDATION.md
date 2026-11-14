# Functional composition validation — 1.5.0-draft.1

> **Historical record.** This report preserves the coverage measured for 1.5.0-draft.1. Catalog
> counts, manual-rule classifications and toolchain availability have since changed. Current
> coverage is in [`coverage.json`](coverage.json) and [`docs/status.md`](../docs/status.md).

This report covers `ACIMA-D015` (closed-over module-owned dependency) and `ACIMA-D016` (partial
application of a module-owned dependency). It is evidence about the reference implementation in
this repository, not a claim that an adopting application's runtime closures have been proved.

## Coverage

| Profile | Rules executed | Rules not executed | Functional evidence |
|---|---:|---:|---|
| Python | 36 / 36 | 6 manual | `D015`, `D016` automated; violations and positive fixture |
| TypeScript | 36 / 36 | 6 manual | `D015`, `D016` automated; violations and positive fixture |
| Go | 25 / 36 | 13 | `D015` automated for package-binding captures; `D016` reports `executed: false` |
| .NET | 23 / 36 | 13 | catalog entries only; `D015`, `D016` report `executed: false` |
| Java | — | — | no reference enforcer; manual review only |

The six manual rules remain `C003`, `C007`, `L004`, `A002`, `A004` and `G004`.

## Controlled fixtures

- Python violations: `examples/python/violations/d015_closure_capture.py` and
  `d016_partial_dependency.py`.
- TypeScript violations: `examples/typescript/violations/d015_closure_capture.ts` and
  `d016_partial_dependency.ts`.
- Positive fixtures: `conformance/fixtures/functional-composition/{python,typescript}` cover
  explicit parameters, legal currying, pure higher-order functions and host composition.
- Both galleries fire at the expected paths. Current totals: Python 49 findings / 36 rules;
  TypeScript 48 findings / 36 rules.

## Commands run

```bash
python3 conformance/run.py python typescript topology tools
python3 conformance/test_functional_capture.py
python3 tools/bundle_skill.py --check
python3 skills/acima-adoption/scripts/preflight.py --project .
git diff --check
```

Result: all selected profiles conform; all five functional-capture tests pass; the bundle matches
its sources; preflight exits `0`; the diff check is clean.

## What the detectors decide

- Python compares direct loads in a function/lambda with its parameters and locals, then walks
  enclosing scopes. Module bindings and enclosing locals are captures; enclosing **parameters** are
  the explicit curried form and are allowed. `partial`/`functools.partial` in an implementation or
  adapter is `D016` when an argument names a dependency.
- TypeScript uses a lightweight function-scope model over arrows and function declarations.
  `partial(...)`/`.bind(...)` in an implementation or adapter is `D016` when an argument names a
  dependency.
- Pure closures over value parameters/constants and pure higher-order functions are not findings.
  Host-side binding is not a finding.
- These are syntax-level candidates, not a type checker and not a runtime graph proof.

## Remaining manual checks

- Confirm callbacks registered through a framework receive their application dependencies explicitly,
  or are registered at the composition boundary with the dependencies named there.
- Confirm dynamic dispatch (`getattr`, `globals`, reflection, generated wiring) is backed by a
  deterministic source and a boot test.
- Confirm a factory that constructs its own collaborator has a reviewed lifetime and ownership.
- Confirm `bind`/`partial` of a dependency is at the composition boundary, including through
  framework-specific wrappers.
- For Go, `.NET` and Java, record manual evidence for `D016` until a validated native analyzer
  exists.

## Toolchain limitation

No Go or .NET toolchain and no Java reference enforcer are available in this environment. Their
catalog and coverage entries are checked statically, but those enforcers were not compiled or
executed. The Python/TypeScript result cannot be extended to them.
