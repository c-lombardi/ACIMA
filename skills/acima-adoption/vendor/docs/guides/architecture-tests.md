# Architecture tests

An architecture test is the mechanism that turns ACIMA from prose into a build step. It has
one job: read the source tree, classify every file into a unit, evaluate the automated rules,
and fail the build when a rule is broken and not waived. Automated success does not decide the
fourteen manual rules; the report must say so.

This guide covers the contract every enforcer implements, how to wire it into CI, and how to
keep the violation gallery trustworthy.

## The enforcer contract

Every ACIMA reference enforcer exposes the same command line, whatever the language:

```
<enforcer> --root <dir> [--config <path>] [--format json|text] [--level L1|L2|L3]
```

- `--root` is the repository root that unit paths in the config are relative to.
- `--config` defaults to `acima.config.json`.
- `--format` is `text` (human) or `json` (machine). JSON is the format CI consumes.
- `--level` overrides the level in the config. Raising the level only adds rules; it never
  removes them.

The JSON document is stable:

```json
{
  "standard": "1.0.0",
  "level": "L3",
  "findings": [
    {
      "rule": "ACIMA-D001",
      "severity": "error",
      "message": "Module catalog imports the implementation unit orders (expected orders.contracts).",
      "path": "src/catalog/impl/pricing.ts",
      "line": 4,
      "evidence": "import { OrdersModule } from '../../orders/impl/module.ts'"
    }
  ]
}
```

`rule`, `severity`, `message`, `path` and `line` are mandatory. `evidence` is optional but
every reference implementation fills it, because a finding without the offending line is a
rumour rather than a report.

## Exit codes

| Code | Meaning | What CI should do |
| --- | --- | --- |
| `0` | No unwaived errors at the requested level. | Continue. |
| `1` | At least one unwaived `error` finding. | Fail the build, print the findings. |
| `2` | The tool could not run: missing config, unreadable waiver file, internal failure. | Fail loudly. Never treat this as an architecture result. |

The third row matters. A broken enforcer that exits `0` silently disables governance, and one
that exits `1` on a missing config teaches the team to ignore the gate. Exit `2` keeps tool
failure distinguishable from architecture debt.

## The config file

```json
{
  "standard": "1.0.0",
  "language": "typescript",
  "level": "L3",
  "root": ".",
  "units": [
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/catalog/impl"] },
    { "id": "host", "role": "host", "paths": ["src/host"] },
    { "id": "tools", "role": "tooling", "paths": ["tools"] }
  ],
  "exclude": ["node_modules", "tests", "violations"],
  "waivers": "acima/evidence/waivers.json"
}
```

Roles are fixed: `shared-kernel`, `contracts`, `implementation`, `host`, `tooling`, `test`.
A `module` is required for `contracts` and `implementation`, because the matrix is expressed
in terms of modules.

Unit membership is decided by longest matching path prefix. A file that matches no unit is a
`ACIMA-G005` finding: an unclassified file is an unowned file, and unowned code is where
architecture goes to die.

### Overriding classification

Generated code, partial classes and legacy folders do not always live where the structure
says they do. Every language profile supports a first-three-lines comment:

```
// acima-unit: orders.contracts
```

The token is either a unit id (`orders.contracts`), a module name (meaning that module's
implementation unit), or `module.contracts` shorthand. Use it for exceptions to path layout,
not to escape the rule matrix.

## Two configs per example

Every reference example ships two configurations:

| File | Purpose | Excludes |
| --- | --- | --- |
| `acima.config.json` | The production tree. Must be clean. | Violation fixtures, tests, build output |
| `acima.gallery.config.json` | The gallery of deliberate violations. Must match `violations/expected.json`. | Tests, build output |

The gallery config points `waivers` at `violations/waivers.json`, which contains deliberately
malformed entries so `ACIMA-G001` and `ACIMA-G002` have something to fire on.

## The expected-findings baseline

`violations/expected.json` is a map from rule id to the sorted list of files that must break
it:

```json
{
  "ACIMA-D001": ["violations/d001_impl_impl.ts"],
  "ACIMA-D002": ["violations/d002_contracts_impl.ts"]
}
```

The architecture test compares the enforcer's gallery output with this file. The comparison is
two-way: a new finding fails, and a finding that silently stopped firing also fails. That
second direction is what keeps the suite honest — a rule that no longer detects anything is
indistinguishable from a rule that does not exist.

When you add a fixture, regenerate the baseline deliberately and review the diff. Never
regenerate blindly: the diff is the review.

## Levels

| Level | Name | Rules evaluated |
| --- | --- | --- |
| `L1` | Structural | Dependency, layering and governance rules (`D001`–`D016`, `L001`–`L007`, `G001`, `G002`, `G005`, `G006`) |
| `L2` | Immutable | `L1` plus contract-shape rules (`C001`–`C008`, `G003`, `G004`) |
| `L3` | Autonomous | `L2` plus autonomy, lifecycle, naming and effect rules (`A001`–`A013`, `N001`–`N003`) |

`C003`, `C007`, `C008`, `L004`, `A002`, `A004`, `A010`–`A013`, `G004` and `N003` are manual. They
have no gallery fixture because there is no reliable automated decision. The enforcer reports them
`executed: false` with a reason; do not add a fixture that merely pretends to detect them.

A team adopting ACIMA starts at `L1`, fixes the dependency graph, then raises the level. The
config records the level that is actually enforced; the README records the level that is
actually passing.

## Wiring it into CI

### Python

```yaml
- run: python3 -m unittest discover -s tests -p 'test_*.py'
```

The test module shells out to `tools/acima_arch.py` and asserts the good tree is clean and the
gallery matches the baseline. Running the enforcer directly works too:

```bash
python3 tools/acima_arch.py --root . --format text --level L3
```

### TypeScript

```yaml
- run: node --test tests/*.test.mjs
- run: node tools/acima-arch.mjs --root . --format json > arch.json
```

### Go

```yaml
- run: go test ./tests/...
- run: go run ./tools/archtest --root . --format json > arch.json
```

### .NET

```yaml
- run: dotnet build tools/Acima.ArchTests -v q
- run: dotnet run --project tools/Acima.ArchTests -- --verify
```

`--verify` runs the production tree and the gallery in one process and compares the gallery with
`violations/expected.json`. The runner also reads `.csproj` files, so a forbidden `ProjectReference`
is caught structurally, before compilation.

### Java

The profile in `docs/languages/java.md` describes the same contract for ArchUnit-based enforcers.
It has no reference implementation in this repository yet; do not add it to CI pretending otherwise.

## Combining the enforcer with native tooling

The reference enforcer is not a replacement for the platform's analyzers. It is the authority
on the *dependency matrix*, which is exactly the part native tooling expresses poorly. Use it
alongside:

- Roslyn analyzers and `Microsoft.CodeAnalysis.NetAnalyzers` for immutability and API shape at
  compile time.
- ArchUnit.NET / NetArchTest for .NET type-level rules.
- ArchUnit for Java package rules.
- `eslint-plugin-boundaries` or `dependency-cruiser` for TypeScript import rules.
- `import-linter` for Python module contracts.
- `go vet` and a small `go/analysis` pass for Go.

See [analyzers-and-linters.md](analyzers-and-linters.md) for the rule-by-rule mapping.

## Failure is the product

A governance system nobody has seen fail is a governance system nobody trusts. Keep the
gallery in the repository, keep it running in CI, and keep its diff visible in code review.
The gallery is the executable definition of what ACIMA prohibits.

It is not the whole definition. A clean gallery run does not review effect ownership, duplicate
behaviour, outcome truthfulness or recovery evidence. Those are recorded in manual evidence, and
the report must name them as unevaluated until that review exists.
