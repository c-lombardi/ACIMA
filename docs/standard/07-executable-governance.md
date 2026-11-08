# 7. Executable governance

This chapter is the contract between the standard and the tools. Implement it exactly and any
language's enforcer interoperates with any other.

## 7.1 Three artefacts

| Artefact | Location | Purpose |
|---|---|---|
| `acima.config.json` | repository root or per solution | Declares units, target level, budgets, excludes |
| `.acima/waivers.json` | repository root | Every permitted departure, with owner and expiry |
| `.acima/api-surface.json` | repository root | The reviewed baseline of every contracts surface |

All three are version-controlled, reviewed in pull requests, and owned by the same people who own the
code.

## 7.2 The finding format

A tool emits findings as JSON. This is the only shape a conformance gate accepts.

```json
{
  "rule": "ACIMA-D001",
  "severity": "error",
  "message": "Orders imports the implementation unit catalog (expected catalog.contracts).",
  "path": "src/orders/impl/place_order.py",
  "line": 4,
  "evidence": "from acima.catalog.impl.repository import ProductRepository"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `rule` | string | yes | `ACIMA-<category><3 digits>` |
| `severity` | `error` \| `warning` \| `info` | yes | must match the catalog unless a waiver lowers it |
| `message` | string | yes | one sentence; must name the fix, not only the problem |
| `path` | string | yes | relative to the analysis root, `/` separators |
| `line` | integer | yes | 1-based; `0` for unit- or file-scoped findings |
| `evidence` | string | no | smallest source excerpt that proves it |

Tools may add fields; they may not omit these.

## 7.3 The tool interface

Every language enforcer implements the same command line:

```
<enforcer> --root <dir> [--config <path>] [--format json|text] [--level L1|L2|L3]
```

- `--format json` prints exactly one object: `{ "standard": "1.0.0", "level": "L2", "findings": [ ... ] }`.
- Exit code `0` when no `error`-severity finding is unwaived; `1` when at least one is; `2` on tool
  failure (unreadable config, parse error). Conflating `2` with `1` hides broken tooling as
  architecture debt, so the distinction is mandatory.
- `--format text` is human output; it is never parsed.

This is what allows `conformance/run.py` in this repository to execute five different languages'
suites and compare them against the same expected findings.

## 7.4 `acima.config.json`

```json
{
  "$schema": "../tools/acima-spec/config.schema.json",
  "standard": "1.0.0",
  "language": "python",
  "level": "L2",
  "root": ".",
  "units": [
    { "id": "shared-kernel", "role": "shared-kernel", "paths": ["src/acima/shared_kernel"] },
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/acima/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/acima/catalog/impl"] },
    { "id": "orders.contracts", "module": "orders", "role": "contracts", "paths": ["src/acima/orders/contracts"] },
    { "id": "orders", "module": "orders", "role": "implementation", "paths": ["src/acima/orders/impl"] },
    { "id": "payments.contracts", "module": "payments", "role": "contracts", "paths": ["src/acima/payments/contracts"] },
    { "id": "payments", "module": "payments", "role": "implementation", "paths": ["src/acima/payments/impl"] },
    { "id": "host", "role": "host", "paths": ["src/acima/host"] }
  ],
  "sharedKernel": "shared-kernel",
  "exclude": ["tests", "violations", "**/__pycache__/**"],
  "budgets": { "catalog": 0, "payments": 1, "orders": 3 },
  "rules": { "ACIMA-L004": "warning" }
}
```

Field notes:

- `units[].paths` are directory prefixes or globs. **The most specific match wins**, so
  `src/acima/catalog/contracts` beats `src/acima/catalog`.
- `role` must be one of `contracts`, `implementation`, `host`, `shared-kernel`, `test`, `tooling`.
- `module` is required for `contracts` and `implementation`, forbidden for `shared-kernel` and `host`.
- `exclude` is applied before classification. Fixtures and tests are never part of the product graph.
- `budgets` is optional; a breach is reported as `ACIMA-G005`-adjacent informational finding, not a
  catalog rule, because the threshold is local policy.
- `rules` may only **lower** severity, never raise it above the catalog, and never disable a rule at
  the declared level.

## 7.5 Waivers

```json
{
  "standard": "1.0.0",
  "waivers": [
    {
      "rule": "ACIMA-D009",
      "scope": "unit:reports",
      "owner": "team-reporting",
      "reason": "Reporting reads the Orders read-model view until the analytics migration lands.",
      "expires": "2027-03-31",
      "reviewedOn": "2026-11-01",
      "ticket": "ARCH-412"
    }
  ]
}
```

Semantics, all mandatory:

1. A waiver matches a finding only when `rule` and `scope` both match. Scope is `unit:<id>`,
   `path:<glob>` or `module:<name>`.
2. A waiver is valid only if `owner`, `reason`, `expires` and `reviewedOn` are present and non-empty
   (`G001`).
3. Past `expires`, the waiver no longer matches and the finding returns (`G002`).
4. A waiver for an unknown rule id is itself a finding (`G001`) — a typo must never silently excuse
   nothing.
5. Waiving is per finding, never global. There is no "skip" switch in `acima.config.json`.

The report must summarise: total waivers, waivers expiring within 30 days, and expired waivers. That
summary is the only mechanism that reliably gets debt paid.

## 7.6 API baseline

`.acima/api-surface.json` is a sorted record of every public type in every contracts unit:

```json
{
  "standard": "1.0.0",
  "units": {
    "catalog.contracts": {
      "ProductView": ["id:str", "name:str", "price:Money", "tags:tuple[str,...]"],
      "CatalogReader": ["get(product_id:ProductId)->ProductView|None"]
    }
  }
}
```

`G004` compares the working tree to the baseline:

- identical → pass;
- additive only (new types, new members with defaults) → pass with an `info` finding telling the
  author to regenerate the baseline;
- breaking → `error` until the baseline is regenerated **in the same commit**, which forces the change
  to be visible in review.

Regenerating is a deliberate command (`--update-baseline`), never automatic in CI.

## 7.7 CI integration

```yaml
- name: ACIMA
  run: |
    dotnet run --project tests/Acima.ArchTests -- --root . --format json > acima.json
    python3 tools/acima-report.py acima.json
```

Requirements for a gate:

- runs on every pull request, not nightly;
- fails on `error` findings (exit code `1`);
- uploads the JSON as a build artefact, so a failure can be inspected without re-running;
- prints the waiver summary, so expired debt is never invisible;
- never runs with `--format text | grep` in a way that loses the exit code (`pipefail`, or capture the
  status explicitly).

## 7.8 Rule lifecycle

Rules are added, deprecated and retired with the standard's version:

| Action | Version change | Requirement |
|---|---|---|
| Add a rule | minor | it must ship with a violation fixture and at least one language implementation |
| Lower a rule's severity | minor | documented in the changelog with the reason |
| Raise severity to `error` | major | migrating existing findings first, or a waiver with an expiry |
| Retire a rule | major | id is retired permanently, never reused |

A rule that cannot produce the four answers in §4.8 — who, what, why, where — is not ready to be
enforced. **Do not ship rules that only say "this is wrong".** They train people to ignore the report.

## 7.9 What the tools must not do

- Refuse to run because one unit is misconfigured; report configuration findings and continue.
- Fail with a stack trace instead of a finding.
- Guess a unit's role from a name when the config is silent. Silence is `G005`.
- Treat an unparseable file as compliant. A file it cannot parse is an `info` finding and the run is
  marked incomplete, because "we could not check" and "we checked and it is clean" are different
  results and must never be conflated.
