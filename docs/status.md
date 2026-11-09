# Capability status

Last verified: 2026-11-09.

ACIMA is a draft standard with working reference tooling. This page separates what is
executable from what is documented, proposed, or known to be incomplete. A claim in the
README or a guide should resolve to one of these rows.

| Capability | Status | Evidence | Limits |
|---|---|---|---|
| 55-rule catalog | **Defined; 41 automated, 14 manual evidence** | [`tools/acima-spec/rules.json`](../tools/acima-spec/rules.json); [`coverage.json`](../conformance/coverage.json); `conformance/run.py` | Fourteen rules report `executed: false` and carry `automation: "manual"`; a clean portable run is not full conformance. See below. |
| Python reference enforcer | **Implemented and verified** | `examples/python/tools/acima_arch.py`; 41/41 automated rules fire in the gallery | Source-level analysis, not type-checking. |
| TypeScript reference enforcer | **Implemented and verified** | `examples/typescript/tools/acima-arch.mjs`; 41/41 automated rules fire in the gallery | Source-text analysis, not type-checking. |
| Go reference enforcer | **Implemented and verified; 23/23 gallery rules** | `examples/go/tools/archtest`; `conformance/run.py go`; the eighteen automated gaps (`L005`–`L007`, `D010`, `G006`, `D011`, `D012`, `A005`, `A006`, `D013`, `D014`, `D015`, `D016`, `A007`–`A009`, `N001`–`N002`) and the fourteen manual rules (including `N003`) report `executed: false` | Source-text and import analysis, not `go/parser`. |
| .NET reference enforcer | **Implemented and verified; 23/23 gallery rules** | `examples/dotnet/tools/Acima.ArchTests`; `conformance/run.py dotnet`; the eighteen automated gaps (`L005`–`L007`, `D010`, `G006`, `D011`, `D012`, `A005`, `A006`, `D013`, `D014`, `D015`, `D016`, `A007`–`A009`, `N001`–`N002`) and the fourteen manual rules (including `N003`) report `executed: false` | Source and MSBuild-evaluated project metadata, not assembly loading. |
| Reference implementations | **Implemented and verified** | `examples/{python,typescript,go,dotnet}`; behaviour tests are checked in | Python carries four modules (Catalog, Orders, Customers, Payments); TypeScript, Go and .NET carry three. Customers parity across languages is not implemented. Hosted CI has not been observed. |
| Java profile | **Documented, not implemented** | [`docs/languages/java.md`](languages/java.md) | No reference implementation or enforcer in this revision. A selected Java assessment fails closed; it is never reported clean. |
| Service-topology profile | **Implemented for the .NET reference fixture** | [`conformance/topology.py`](../conformance/topology.py); `conformance/test_topology.py` | 12/12 on the clean/violating fixtures; no non-.NET fixture. Checks declared evidence (names, paths, references, workflow tokens), not semantic product correctness. |
| Architecture mode selector | **Implemented and verified** | `acima.config.json` `mode`; [`conformance/topology.py`](../conformance/topology.py); `conformance/test_mode_precedence.py` | `base` is the default when absent. `service-topology` requires `acima.topology.json`, applies P1–P15, and supersedes exactly P2.1/P3.5. A mismatch is exit `2`, never a clean run. |
| Conformance claim gate | **Implemented and verified** | [`conformance/acima_claim.py`](../conformance/acima_claim.py); `acima claim`; `conformance/test_claim_model.py` | `FULL CONFORMANCE` requires every required rule executed or accepted repository-scoped manual evidence, plus zero unwaived errors. Missing evidence yields `PARTIAL ASSESSMENT`; malformed input exits `2`. |
| Manual evidence for the fourteen rules | **Implemented and verified** | `.acima/manual-evidence.json`; [`docs/standard/08-conformance.md`](standard/08-conformance.md#89-manual-evidence-for-full-claims) | One entry per required manual rule; expired or missing evidence makes the claim partial, and a manual rule reported as executed does not count. The reference enforcers do not execute these rules. |
| Owned effects, consistency and observability | **Defined; manual evidence required** | P1.7, P15; [`A010`–`A015`](rules/autonomy.md), [`C008`](rules/contracts.md); [guide](guides/effects-and-atomicity.md) | No portable detector. The obligations cover ownership, duplicate/retry semantics, truthful outcomes, recovery evidence, state-mutation ownership, consistency boundaries, telemetry and boundary visibility; a clean scan is not evidence. |
| Intent-revealing naming | **Defined; 2 automated candidates and 1 manual review** | [`N001`–`N003`](rules/naming.md); `conformance/test_naming.py`; [`NAMING_VALIDATION.md`](../conformance/NAMING_VALIDATION.md) | Type casing and generic responsibility names only. Side effects, units, boolean clarity, domain consistency and contextual naming remain manual evidence; Go, .NET and Java report `executed: false`. |
| Lifecycle and state ownership | **Defined; 3 automated candidates** | [`A007`–`A009`](rules/autonomy.md); `conformance/test_lifecycle_ownership.py`; [`LIFECYCLE_OWNERSHIP_VALIDATION.md`](../conformance/LIFECYCLE_OWNERSHIP_VALIDATION.md) | Explicit host registrations only. Thread safety, tenant isolation, resource cleanup, factory/closure retention and the runtime container graph remain manual evidence; Go, .NET and Java report `executed: false`. |
| Library/framework profile | **Implemented for TypeScript and .NET** | `docs/standard/12-library-profile.md`; `conformance/test_library_profile.py`, `conformance/test_dotnet_profile.py` | Declared public API and intentional adapters are classified, not deleted; Python and Go have no profile support. |
| Violation galleries | **Implemented and verified** | `examples/*/violations/expected.json`; `conformance/run.py` | A rule counts only when a fixture fires and the expected path is checked in. |
| Unified `acima` CLI | **Implemented and verified** | [`tools/acima.py`](../tools/acima.py); `conformance/test_cli.py` | `assess` (read-only), `inspect`, `analyze`, `report`, `claim`, `verify`. `adopt` is not implemented; use the skill preflight. |
| Executable violation-to-fix walkthrough | **Implemented and verified** | [`tools/acima_walkthrough.py`](../tools/acima_walkthrough.py); `conformance/test_walkthrough.py` | One D001 path through the Python example. The gallery covers the rest. |
| Architecture evidence report | **Implemented and verified** | `acima report --root <repo> --format markdown` | Reports executed rules and explicitly lists unevaluated rules. It does not compute a health score. |
| Brownfield preflight and draft units | **Implemented and verified for base mode** | [`skills/acima-adoption/scripts/preflight.py`](../skills/acima-adoption/scripts/preflight.py) | Heuristic draft; a human must review module names and ownership. No service-profile workflow. |
| Waiver baseline generation | **Implemented and verified** | `preflight.py --write-waivers` | Writes `owner: unassigned`; a human must replace every owner before merging the gate. |
| GitHub Actions conformance workflow | **Implemented, not yet observed in hosted CI** | [`.github/workflows/acima.yml`](../.github/workflows/acima.yml) | The workflow file is present in this checkout, but this environment cannot execute GitHub Actions. Run it once on a branch before relying on it. |
| Overall architecture health score | **Proposed** | — | No objective, calibrated scoring model exists. Do not infer one from the evidence report. |
| Historical trend reporting | **Proposed** | — | Requires a report store and retention policy; not implemented. |
| `acima adopt` command | **Proposed** | — | The adoption workflow currently lives in the agent skill and preflight. |
| Additional language enforcers | **Proposed** | — | Java is the next candidate; see [`docs/languages/adding-a-language.md`](languages/adding-a-language.md). |

## Rules that are not decided by the portable enforcers

These fourteen rules are normative but require a native analyzer, package metadata, or human
architectural judgement. The CLI report lists them as **not evaluated**; a clean run is not
evidence that they pass.

| Rule | Why the portable runner cannot decide it |
|---|---|
| `ACIMA-C003` | Behaviour versus validation is a semantic judgement. |
| `ACIMA-C007` | Whether a constructor makes the required state obvious needs symbol and API analysis. |
| `ACIMA-C008` | Whether a boundary operation makes its business behaviour visible is a semantic judgement. |
| `ACIMA-L004` | Service-locator calls are framework-specific. |
| `ACIMA-A002` | Configuration APIs differ per ecosystem. |
| `ACIMA-A004` | Version-lock coupling is visible only across published packages. |
| `ACIMA-A010` | Effect ownership and transaction boundaries require design intent, not syntax. |
| `ACIMA-A011` | Retry, duplicate, consistency and cancellation semantics are not statically decidable. |
| `ACIMA-A012` | Truthful success, failure, unknown and partial outcomes require failure-path reasoning. |
| `ACIMA-A013` | Evidence proportionality depends on the effect's business criticality. |
| `ACIMA-A014` | Whether telemetry observes or replaces a business decision is a semantic judgement. |
| `ACIMA-A015` | Consistency ownership, guarantees and recovery intent are design decisions, not syntax. |
| `ACIMA-G004` | An API baseline needs a per-language surface format. |
| `ACIMA-N003` | Responsibility, side effects, units and domain consistency are semantic judgements. |

The language enforcers have additional documented gaps in the table above, including the Go and
.NET value, explicit-input, composition, functional-capture, lifecycle and naming rules. Their
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
a pass. See the [product contract](product-contract.md) for the consumer guarantees, known
gaps and current release-gate disposition.
