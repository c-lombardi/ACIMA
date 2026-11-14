# Principles and rules

Two different things live one level up, and confusing them is the most common reading error in this repository:

- A **principle** states an obligation and its rationale: *"Every module owns its implementation."* Principles are prose, in [`../standard/01-principles.md`](../standard/01-principles.md).
- A **rule** is the smallest independently checkable consequence of a principle: *`ACIMA-D001` — an implementation references another implementation.* A rule has an id, a severity, a conformance level and an automation status.

One principle maps to several rules; one rule always traces back to exactly one requirement.

## Where a rule is defined

| Artifact | Role | Authority |
|---|---|---|
| [`../../tools/acima-spec/rules.json`](../../tools/acima-spec/rules.json) | id, severity, level, `automation`, manual evidence hint | **authoritative** |
| [`index.md`](index.md) | the same 56 rules as tables, plus severity policy | generated-equivalent; a test fails if it drifts |
| [`dependency.md`](dependency.md) | `D` and `L` rules with violation/fix examples per language | explanatory |
| [`contracts.md`](contracts.md) | `C` rules | explanatory |
| [`autonomy.md`](autonomy.md) | `A` and `G` rules | explanatory |
| [`naming.md`](naming.md) | `N` rules | explanatory |

There is exactly one catalog. Do not create a second one in a report, spreadsheet or directory README: that is how the previous `validation/` matrix drifted from the code.

## Automated versus human judgement

42 of 56 catalog rules are marked automated. The actual executed set is language-dependent: Python executes 42, TypeScript 41, .NET 42, and Go 27. Fourteen rules require human judgement in every profile; additional language-specific rules are reported as `executed: false` when that language cannot enforce them. D017 is executed only where the language supports native named call arguments (Python and C#); TypeScript/JavaScript and Go report it as not executed rather than inventing wrapper conventions. The language-specific unsupported set is recorded in `conformance/coverage.json`. Human-judgement requirements include:

| Rule | Who decides |
|---|---|
| `C003` behaviour in contracts | human review |
| `C007` one-step construction | human review |
| `C008` business behaviour visibility | contract and implementation review |
| `A010` effect boundary ownership | effect-owner review |
| `A011` effect semantics | contract, retry and consistency review |
| `A012` truthful effect outcome | failure-path review |
| `A013` critical-effect evidence | test, reconciliation or operational evidence review |
| `A014` telemetry and business behaviour | observability, business-event and audit review |
| `A015` consistency boundary ownership | design review of the owner, guarantee and recovery path |
| `L004` service locator | human review or framework analyzer |
| `A002` cross-module configuration key | human review |
| `A004` version-lock coupling | package metadata review |
| `N003` semantic naming clarity | human semantic review |
| `G004` unreviewed contract change | API baseline comparison |

A clean portable run is therefore **not** full conformance. A full claim needs a repository-scoped entry for each of these in `acima/evidence/manual-evidence.json`; see [`../standard/08-conformance.md`](../standard/08-conformance.md#89-manual-evidence-for-full-claims).

## Where each rule is implemented

| Layer | Location |
|---|---|
| mapping rule → profile | [`../../conformance/coverage.json`](../../conformance/coverage.json) |
| implementations | `../../examples/{python,typescript,go,dotnet}/tools/` |
| third-party tiers | `docs/standard/04-dependency-model.md` §4.10 and the `externals` map in chapter 7 |
| proof a rule can fire | `../../examples/<lang>/violations/` + `expected.json` |
| runner | [`../../conformance/run.py`](../../conformance/run.py) |

Java is a documented profile with no enforcer: a Java selection fails closed.

## Changing a rule without breaking the languages

1. Edit `rules.json` (never renumber an id; retire it instead).
2. Update the chapter and the page in this directory.
3. Implement or explicitly not-execute it in **every** enforcer; add a fixture and `expected.json` entry.
4. Update `coverage.json` so the executed/not-executed partition still sums to the catalog.
5. Re-pin `../../skills/acima-adoption/manifest.json` (hash + version).
6. Run `python3 conformance/run.py` and `python3 conformance/test_documentation_integrity.py`.

Step 5 is not optional bookkeeping: the preflight refuses to advise on a catalog it was not calibrated against.
