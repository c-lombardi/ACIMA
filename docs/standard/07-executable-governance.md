# 7. Executable governance

This chapter is the contract between the standard and the tools. Implement it exactly and any
language's enforcer interoperates with any other.

## 7.1 Four artefacts

| Artefact | Location | Purpose |
|---|---|---|
| `acima.config.json` | repository root or per solution | Declares units, target level, budgets, excludes |
| `acima/evidence/waivers.json` | `acima/evidence/` | Every permitted departure, with owner and expiry |
| `acima/evidence/api-surface.json` | `acima/evidence/` | The reviewed baseline of every contracts surface |
| `acima/evidence/manual-evidence.json` | `acima/evidence/` | Review evidence for normative rules the portable enforcers cannot execute |

All four are version-controlled, reviewed in pull requests, and owned by the same people who own the
code. The first three are mandatory for an assessment; manual evidence is required only for a full
claim that includes a rule the run did not execute.

## 7.2 The finding format

A tool emits findings as JSON. This is the only shape a conformance gate accepts.

```json
{
  "rule": "ACIMA-D001",
  "severity": "error",
  "message": "Orders imports the implementation unit catalog (expected catalog.contracts).",
  "path": "src/orders/impl/place_order.py",
  "line": 4,
  "evidence": "from acima.catalog.impl.repository import ProductRepository",
  "fingerprint": "sha256:1f0c…"
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
| `fingerprint` | string | yes | `sha256:` over the finding identity (rule, normalized path and stable evidence); the key a waiver matches |

Tools may add fields; they may not omit these. Every base and profile finding carries a
fingerprint. For file-scoped profile findings the identity is the profile rule, path and
evidence; a profile finding without one cannot be waived. Profile requirements use the same object with the
`ACIMA-SNNN` namespace (chapter 11). S rules sit outside the base catalog and are produced by the
profile runner, not by a language enforcer; they do not change the L1–L3 rule set.

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
  "mode": "base",
  "language": "python",
  "level": "L2",
  "root": ".",
  "units": [
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/acima/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/acima/catalog/impl"] },
    { "id": "orders.contracts", "module": "orders", "role": "contracts", "paths": ["src/acima/orders/contracts"] },
    { "id": "orders", "module": "orders", "role": "implementation", "paths": ["src/acima/orders/impl"] },
    { "id": "payments.contracts", "module": "payments", "role": "contracts", "paths": ["src/acima/payments/contracts"] },
    { "id": "payments", "module": "payments", "role": "implementation", "paths": ["src/acima/payments/impl"] },
    { "id": "host", "role": "host", "paths": ["src/acima/host"] }
  ],
  "exclude": ["tests", "violations", "**/__pycache__/**"],
  "externals": {
    "monaco-editor": {
      "tier": "integration",
      "owner": "team-editor",
      "reason": "Browser code editor for note authoring.",
      "adapter": "editor.monaco",
      "port": "editor.port",
      "reviewedOn": "2026-11-09",
      "expires": "2027-11-09",
      "types": ["IEditor"]
    },
    "react": { "tier": "platform", "owner": "team-web", "reason": "UI runtime.",
               "reviewedOn": "2026-11-09", "expires": "2027-11-09" },
    "left-pad": { "tier": "utility", "owner": "team-platform", "reason": "Pure padding helper.",
                  "reviewedOn": "2026-11-09", "expires": "2027-11-09" }
  },
  "manifests": ["package.json"],
  "budgets": { "catalog": 0, "payments": 1, "orders": 3 },
  "rules": { "ACIMA-L004": "warning" }
}
```

Field notes:

- A **unit** is an artifact the build or repository layout can identify; a **module** is the
  ownership boundary it represents. A module may span several units, and a `contracts` or
  `implementation` unit names the module it represents. There is no required one-to-one mapping
  between modules and projects, packages, services or deployment units.
- `mode` selects the architecture mode. `base` (the default when absent) applies P1–P9, P14 and P15.
  `service-topology` applies P1–P9, P10–P15 and supersedes exactly P2.1 and P3.5 (chapter 11).
  The topology manifest cannot select a mode; a mismatch is a configuration error (exit `2`), not a
  finding.
- `units[].paths` are directory prefixes or globs. **The most specific match wins**, so
  `src/acima/catalog/contracts` beats `src/acima/catalog`.
- `role` must be one of `contracts`, `implementation`, `host`, `shared-kernel`, `test`, `tooling`.
- `host` names a declared **composition boundary**, not necessarily an executable. It may be a host
  entry point, a package initializer, a public factory, a framework integration point, a plugin
  loader or a test composition unit. A repository may declare zero, one or several `host` units; a
  library or package without one is valid.
- `module` is required for `contracts` and `implementation`, forbidden for `shared-kernel` and `host`.
- `exclude` is applied before classification. Fixtures and tests are never part of the product graph.
- `budgets` is optional; a breach is reported as `ACIMA-G005`-adjacent informational finding, not a
  catalog rule, because the threshold is local policy.
- `externals` declares the third-party tiers (chapter 4 §4.10). It is **configuration, never
  inference**: an undeclared package is `G006`, not a guess.
  - `tier` is `platform`, `integration` or `utility`; it is required, with `owner`, `reason`,
    `reviewedOn` and `expires`.
  - `adapter` and `port` are **required for `integration`** and name declared unit ids. An adapter
    unit that no entry names is `L006`.
  - `specifiers` (optional) lists the import names a package is known by when they differ from the
    manifest name — a PyPI distribution and its module, for example.
  - `types` (optional) lists the vendor type names `L007` should look for. When absent, tokens are
    derived from the package name.
  - An entry whose `expires` date has passed is `G006`; an entry missing a required field, naming an
    unknown unit or an unknown tier is `G001`.
- `manifests` lists the files `G006` reads. When absent, `package.json`, `pyproject.toml` and
  `requirements.txt` are read if present. `devDependencies` are not checked: they do not ship.
- When `externals` is absent the five tier rules (`L005`–`L007`, `D010`, `G006`) report
  `executed: false` with that reason. A repository with a manifest should declare it —
  `acima.py externals --write-draft` produces the first version:

```bash
python3 tools/acima.py externals --root . --write-draft   # one entry per manifest package
```

The draft sets every package to `utility` with an `UNASSIGNED` owner: it is a starting point for
review, not a decision. `--write-draft` never overwrites an existing entry, so re-running it after a
new dependency appears adds only the new one.
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
      "fingerprint": "sha256:1f0c…",
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

1. A waiver matches a finding only when `rule`, `scope` and `fingerprint` all match. Scope is
   `unit:<id>`, `path:<glob>` or `module:<name>`. The fingerprint is the hash of the finding's
   identity (rule, path, evidence); scope alone MUST NOT suppress a finding, because it would hide
   every future finding in that scope.
2. A waiver is valid only if `fingerprint`, `owner`, `reason`, `expires` and `reviewedOn` are present
   and non-empty (`G001`).
3. Past `expires`, the waiver no longer matches and the finding returns (`G002`).
4. A waiver for an unknown rule id is itself a finding (`G001`) — a typo must never silently excuse
   nothing.
5. Waiving is per finding, never global. There is no "skip" switch in `acima.config.json`.

P9.5 is **advisory in Draft 1**. A C001–C006 waiver should not outlive one minor version and
must be reviewed at every contract release, but the waiver schema has no standard-version or
contract-version field, so no tool can compute the limit. `G004` still handles breaking API
changes. Do not describe P9.5 as machine-enforced.

The report must summarise: total waivers, waivers expiring within 30 days, and expired waivers. That
summary is the only mechanism that reliably gets debt paid.

## 7.6 API baseline

`acima/evidence/api-surface.json` is a sorted record of every public type in every contracts unit:

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
| Add an automated rule | minor | it must ship with a violation fixture and at least one language implementation |
| Add a manual rule | minor | it must name a principle, a decision procedure and an evidence method; it has no fixture because it cannot be executed |
| Lower a rule's severity | minor | documented in the changelog with the reason |
| Raise severity to `error` | major | migrating existing findings first, or a waiver with an expiry |
| Retire a rule | major | id is retired permanently, never reused |

A rule that cannot produce the four answers in §4.8 — who, what, why, where — is not ready to be
enforced. **Do not ship rules that only say "this is wrong".** They train people to ignore the report.

A manual rule is a deliberate exception to the fixture requirement. It ships with a stable id, a
principle, an applicability condition, a review method and a manual-evidence requirement. It MUST be
reported as `executed: false` with a reason in every enforcer; a waiver cannot substitute for the
evidence, because a waiver records an accepted departure, not a completed review. The five P15/P1.7
rules (`A010`–`A013`, `C008`) follow this path: their subject matter — ownership, duplicate semantics,
outcome truthfulness and recovery evidence — is not reliably decidable from source text, and a
heuristic that guessed would be worse than an honest manual rule.

Manual rules may later acquire an automated rule when a native analyzer can decide a narrowly defined
part of them. That new rule gets its own id and fixture; the manual obligation is not silently
downgraded, and the two rules must state their relationship.

## 7.9 What the tools must not do

- Refuse to run because one unit is misconfigured; report configuration findings and continue.
- Fail with a stack trace instead of a finding.
- Guess a unit's role from a name when the config is silent. Silence is `G005`.
- Treat an unparseable file as compliant. A file it cannot parse is an `info` finding and the run is
  marked incomplete, because "we could not check" and "we checked and it is clean" are different
  results and must never be conflated.
