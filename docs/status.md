# Capability status

Last verified: 2026-11-08.

ACIMA is a draft standard with working reference tooling. This page separates what is
executable from what is documented, proposed, or known to be incomplete. A claim in the
README or a guide should resolve to one of these rows.

| Capability | Status | Evidence | Limits |
|---|---|---|---|
| 29-rule catalog | **Defined; 23 automated, 6 manual evidence** | [`tools/acima-spec/rules.json`](../tools/acima-spec/rules.json); [`coverage.json`](../conformance/coverage.json); `conformance/run.py` | Six rules report `executed: false` and carry `automation: "manual"`; a clean portable run is not full conformance. See below. |
| Python reference enforcer | **Implemented and verified** | `examples/python/tools/acima_arch.py`; 23/23 portable rules fire in the gallery | Source-level analysis, not type-checking. |
| TypeScript reference enforcer | **Implemented and verified** | `examples/typescript/tools/acima-arch.mjs`; 23/23 portable rules fire in the gallery | Source-text analysis, not type-checking. |
| Go reference enforcer | **Implemented and verified** | `examples/go/tools/archtest`; 23/23 portable rules fire in the gallery | Source-text and import analysis, not `go/parser`. |
| .NET reference enforcer | **Implemented and verified** | `examples/dotnet/tools/Acima.ArchTests`; 23/23 portable rules fire in the gallery | Source and MSBuild-evaluated project metadata, not assembly loading. |
| Reference implementations | **Implemented and verified** | `examples/{python,typescript,go,dotnet}`; behaviour tests are checked in | Python carries four modules (Catalog, Orders, Customers, Payments); TypeScript, Go and .NET carry three. Customers parity across languages is not implemented. Hosted CI has not been observed. |
| Java profile | **Documented, not implemented** | [`docs/languages/java.md`](languages/java.md) | No reference implementation or enforcer in this revision. A selected Java assessment fails closed; it is never reported clean. |
| Service-topology profile | **Implemented for the .NET reference fixture** | [`conformance/topology.py`](../conformance/topology.py); `conformance/test_topology.py` | 12/12 on the clean/violating fixtures; no non-.NET fixture. Checks declared evidence (names, paths, references, workflow tokens), not semantic product correctness. |
| Architecture mode selector | **Implemented and verified** | `acima.config.json` `mode`; [`conformance/topology.py`](../conformance/topology.py); `conformance/test_mode_precedence.py` | `base` is the default when absent. `service-topology` requires `acima.topology.json`, applies P1–P13, and supersedes exactly P2.1/P3.5. A mismatch is exit `2`, never a clean run. |
| Conformance claim gate | **Implemented and verified** | [`conformance/acima_claim.py`](../conformance/acima_claim.py); `acima claim`; `conformance/test_claim_model.py` | `FULL CONFORMANCE` requires every required rule executed or accepted repository-scoped manual evidence, plus zero unwaived errors. Missing evidence yields `PARTIAL ASSESSMENT`; malformed input exits `2`. |
| Manual evidence for the six rules | **Implemented and verified** | `.acima/manual-evidence.json`; [`docs/standard/08-conformance.md`](standard/08-conformance.md#89-manual-evidence-for-full-claims) | One entry per required manual rule; expired or missing evidence makes the claim partial. The reference enforcers do not execute these rules. |
| Library/framework profile | **Implemented for TypeScript and .NET** | `docs/standard/12-library-profile.md`; `conformance/test_library_profile.py`, `conformance/test_dotnet_profile.py` | Declared public API and intentional adapters are classified, not deleted; Python and Go have no profile support. |
| Violation galleries | **Implemented and verified** | `examples/*/violations/expected.json`; `conformance/run.py` | A rule counts only when a fixture fires and the expected path is checked in. |
| Unified `acima` CLI | **Implemented and verified** | [`tools/acima.py`](../tools/acima.py); `conformance/test_cli.py` | `inspect`, `analyze`, `report`, `verify`. `adopt` is not implemented; use the skill preflight. |
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
a pass. See the [product contract](product-contract.md) for the consumer guarantees, known
gaps and current release-gate disposition.
