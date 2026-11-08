# Capability status

Last verified: 2026-11-08.

ACIMA is a draft standard with working reference tooling. This page separates what is
executable from what is documented, proposed, or known to be incomplete. A claim in the
README or a guide should resolve to one of these rows.

| Capability | Status | Evidence | Limits |
|---|---|---|---|
| 29-rule catalog | **Implemented and verified** | [`tools/acima-spec/rules.json`](../tools/acima-spec/rules.json); `conformance/run.py` | Some rules require native analyzers or human judgement; see below. |
| Python reference enforcer | **Implemented and verified** | `examples/python/tools/acima_arch.py`; 23/23 portable rules fire in the gallery | Source-level analysis, not type-checking. |
| TypeScript reference enforcer | **Implemented and verified** | `examples/typescript/tools/acima-arch.mjs`; 23/23 portable rules fire in the gallery | Source-text analysis, not type-checking. |
| Go reference enforcer | **Implemented and verified** | `examples/go/tools/archtest`; 23/23 portable rules fire in the gallery | Source-text and import analysis, not `go/parser`. |
| .NET reference enforcer | **Implemented and verified** | `examples/dotnet/tools/Acima.ArchTests`; 23/23 portable rules fire in the gallery | Source and project-file analysis, not assembly loading. |
| Reference implementations | **Implemented and verified** | `examples/{python,typescript,go,dotnet}`; behaviour tests run in CI | Python carries four modules (Catalog, Orders, Customers, Payments); TypeScript, Go and .NET carry three. Customers parity across languages is not implemented. |
| Java profile | **Documented, not implemented** | [`docs/languages/java.md`](languages/java.md) | No reference implementation or enforcer in this revision. The conformance runner skips it. |
| Service-topology profile | **Implemented and verified** | [`conformance/topology.py`](../conformance/topology.py); `conformance/test_topology.py` | Checks declared evidence (names, paths, references, workflow tokens), not semantic product correctness. |
| Violation galleries | **Implemented and verified** | `examples/*/violations/expected.json`; `conformance/run.py` | A rule counts only when a fixture fires and the expected path is checked in. |
| Unified `acima` CLI | **Implemented and verified** | [`tools/acima.py`](../tools/acima.py); `conformance/test_cli.py` | `inspect`, `analyze`, `report`, `verify`. `adopt` is not implemented; use the skill preflight. |
| Executable violation-to-fix walkthrough | **Implemented and verified** | [`tools/acima_walkthrough.py`](../tools/acima_walkthrough.py); `conformance/test_walkthrough.py` | One D001 path through the Python example. The gallery covers the rest. |
| Architecture evidence report | **Implemented and verified** | `acima report --root <repo> --format markdown` | Reports executed rules and explicitly lists unevaluated rules. It does not compute a health score. |
| Brownfield preflight and draft units | **Implemented and verified** | [`skills/acima-adoption/scripts/preflight.py`](../skills/acima-adoption/scripts/preflight.py) | Heuristic draft; a human must review module names and ownership. |
| Waiver baseline generation | **Implemented and verified** | `preflight.py --write-waivers` | Writes `owner: unassigned`; a human must replace every owner before merging the gate. |
| GitHub Actions conformance workflow | **Implemented, not yet observed in hosted CI** | [`.github/workflows/acima.yml`](../.github/workflows/acima.yml) | The workflow file is present in this checkout, but this environment cannot execute GitHub Actions. Run it once on a branch before relying on it. |
| Overall architecture health score | **Proposed** | — | No objective, calibrated scoring model exists. Do not infer one from the evidence report. |
| Historical trend reporting | **Proposed** | — | Requires a report store and retention policy; not implemented. |
| `acima adopt` command | **Proposed** | — | The adoption workflow currently lives in the agent skill and preflight. |
| Additional language enforcers | **Proposed** | — | Java is the next candidate; see [`docs/languages/adding-a-language.md`](languages/adding-a-language.md). |

## Rules that are not decided by the portable enforcers

These six rules are normative but require a native analyzer, package metadata, or human
architectural judgement. The CLI report lists them as **not evaluated**; a clean run is not
evidence that they pass.

| Rule | Why the portable runner cannot decide it |
|---|---|
| `ACIMA-C003` | Behaviour versus validation is a semantic judgement. |
| `ACIMA-C007` | Whether a constructor makes the required state obvious needs symbol and API analysis. |
| `ACIMA-L004` | Service-locator calls are framework-specific. |
| `ACIMA-A002` | Configuration APIs differ per ecosystem. |
| `ACIMA-A004` | Version-lock coupling is visible only across published packages. |
| `ACIMA-G004` | An API baseline needs a per-language surface format. |

The TypeScript and Go enforcers have additional documented gaps in the table above. Their
profiles name the native analyzer or review practice that covers each gap.

## What “verified” means here

“Implemented and verified” means the capability has a checked-in executable path and the
conformance suite exercises it on the current commit. It does **not** mean every possible
violation is detected, or that the tool proves runtime autonomy. Compile-time isolation,
runtime ownership, and operational independence are related but distinct claims.

The conformance runner is the source of truth:

```bash
python3 conformance/run.py
```

A report is evidence, not a score. The absence of a finding for an unevaluated rule is not
a pass.
