# Enforcement Regression Register

**Status:** IN PROGRESS — internal review only
**Purpose:** Record every known enforcement defect/fix, the test that pins it, and the
residual risk. A fixed item is not a claim that the whole rule is semantically complete.

## Regression entries

| ID | Defect / risk | Reproduction or evidence | Regression coverage | Status | Residual risk |
|---|---|---|---|---|---|
| R-01 | TypeScript assessment truncated at 65,536 bytes | `rw-...-01` tRPC output; `rw-...-02` valid | `test_library_profile.LargeOutputTests` (500 files, >64K) | **Fixed/covered** | Other enforcers untested at same scale |
| R-02 | Literal exclusion matched sibling prefix (`packages/tests` excluded `tests-extra`) | Python/TS bug; `test_exclusions` | `conformance/test_exclusions.py` | **Fixed/covered** | Only Python/TS; Go/.NET not in this test |
| R-03 | G005 titled/summarized as something other than unclassified source | `test_rule_catalog` | `conformance/test_rule_catalog.py` | **Fixed/covered** | Human docs may still drift |
| R-04 | .NET library profile rejected inherited `PackageId` | FluentValidation benchmark; `rw-...-02` | `test_dotnet_profile` inherited/direct/default/`IsPackable=false` | **Fixed/covered** | Equivalent metadata forms (props/conditions) not exhaustive |
| R-05 | .NET `**/` public-API glob did not match root and nested files | `test_dotnet_profile` | `test_dotnet_profile.public_api_glob` | **Fixed/covered** | Glob semantics not uniform across languages |
| R-06 | Fingerprint-less waiver suppressed every finding in scope | `test_waiver_fingerprints` | Exact vs broad waiver across four enforcers | **Fixed/covered** | Fingerprint algorithm stability not specified |
| R-07 | Brownfield classification used a 10-file threshold; docs still do | `test_waiver_fingerprints.one_existing_source_file_is_brownfield`; skill `00-preflight` | Preflight unit test | **Code fixed; docs open** | Glossary/00/20 still stale |
| R-08 | Zero-source run could look clean | `test_library_profile.ZeroSourceTests`; `test_adoption_safety` | Zero-source tests | **Covered** | No check across all four enforcers |
| R-09 | Unsupported Java could be treated as skipped/pass | `test_injected_violation.unsupported_language` | Java fail-closed test | **Covered** | No Java enforcer; three benchmark repos blocked |
| R-10 | Zero-finding repos not proven to detect anything | `test_injected_violation`; benchmark 8/9 proven | L001/D001 injection proofs | **Covered for L001/D001** | Other 21 rules are not injection-proven |
| R-11 | Library profile could hide undeclared edges | `test_library_profile` rogue adapter/private leak | Positive/negative profile tests | **Covered (TS)** | .NET equivalent tested separately; Python/Go none |
| R-12 | Multi-segment directory excludes treated as bare names | tRPC raw 105 G005; corrected config | `test_exclusions` literal/glob | **Partially covered** | No test for every multi-segment/wildcard form; benchmark config was hand-fixed |
| R-13 | `D008` reports duplicate transitive paths | Benchmark: 3 duplicates (Spectre etc.) | Gallery checks paths, not dedup | **Open** | Finding counts noisy; no dedup test |
| R-14 | D005 analyzer-cycle false positives on Spectre | Prior benchmark | Historical evidence only | **Fixed in code/benchmark** | No dedicated regression fixture in this repo |
| R-15 | Valid .NET public APIs remain unclassified | 30 valid choices in `rw-...-02` | `test_dotnet_profile` only covers fluent fixture | **Open** | Adoption noise; profile completeness |
| R-16 | `rules` severity lowering / disabling not tested | Code review; no test | None | **Open** | P8.3 guarantee not established |
| R-17 | Large-output completeness only tested in TypeScript | `test_library_profile` | None for Python/Go/.NET | **Open** | Silent truncation class may remain |
| R-18 | Hosted CI never observed | No run evidence | Workflow file only | **Open/blocked** | Gate reliability unknown |
| R-19 | No independent review | Process | N/A | **Open/blocked** | Author adjudication risk |
| R-20 | Service profile .NET-shaped | `test_topology` | .NET clean/bad fixtures | **Open** | Non-.NET applicability unproven |
| R-21 | ST-11 checks tokens, not workflow semantics | `topology.py` / test | Positive/negative token fixture | **Open by design** | A UI can mention tokens and still differ |
| R-22 | A001 static-only persistence ownership | Rule doc | Gallery SQL detection | **Open by design** | Runtime grants can differ |
| R-23 | C004/C005/C006 denylists can miss aliases/custom frameworks | Rule docs | Gallery examples | **Open** | Semantic gaps |
| R-24 | L001 only four layering edges | Rule doc | Gallery | **Open by design** | Clean/Hexagonal completeness not claimed |
| R-25 | Six catalog rules not executed | `coverage.json` | Runner pins the gap (does not close it) | **Open/architecture** | No full conformance claim |
| R-26 | `fingerprint` absent from normative finding schema | `07` §7.2 vs P9.1 | `test_documentation_contract` covers §7.5 matching only | **Open/docs** | Waiver matching now requires it; the finding object still omits it |
| R-27 | P9.5 unenforceable | P9.5 | None | **Open/architecture** | Immutability waivers can outlive limit |
| R-28 | Python/Go library public API false positives | Benchmark 30 valid choices | None | **Open** | No profile support |
| R-29 | Uncovered proposed units cap at 16; large repos may be truncated | `preflight.py` `units[:16]` | `test_preflight_discovery.py` 18-module fixture | **Fixed/covered** | Cap removed; all candidates proposed |
| R-30 | `walk_files` caps at 50,000 without reporting | `preflight.py` | No test | **Open** | Large repo completeness unknown |

## Test inventory (current checkout)

| Test file | What it covers |
|---|---|
| `conformance/run.py` + `examples/*/violations/expected.json` | 23 executed rules per language; clean/gallery drift |
| `conformance/test_cli.py` | inspect/analyze/report; malformed config; no health score |
| `conformance/test_walkthrough.py` | violation→fix→verify path |
| `conformance/test_exclusions.py` | literal subtree vs sibling prefix; globs (Python/TS) |
| `conformance/test_rule_catalog.py` | G005 title/summary contract |
| `conformance/test_waiver_fingerprints.py` | exact-finding waivers; brownfield classification; baseline uniqueness |
| `conformance/test_adoption_safety.py` | fail-closed assessment validation; zero source; missing execution map |
| `conformance/test_library_profile.py` | public API/adapter classification; invalid declarations; zero source; 65K output |
| `conformance/test_dotnet_profile.py` | inherited/direct/default PackageId; IsPackable; public API glob |
| `conformance/test_injected_violation.py` | L001/D001 injection; fail-closed Java/no units/no detection |
| `conformance/test_topology.py` | ST-1–ST-12 clean and violating fixtures |
| `conformance/test_preflight_discovery.py` | Zero-unit blocker on source-bearing repos; 18-module completeness |
| `conformance/test_documentation_contract.py` | Rule counts, brownfield threshold, fingerprint waivers, partial-assessment template |

## Regression policy gaps

1. **No test asserts that a rule's severity cannot be raised above the catalog or disabled
   at a required level.** That is a P8.3 obligation, not a convenience.
2. **No test asserts that `fingerprint` is in the normative finding schema.** Waiver matching
   now requires it (§7.5), but the finding object in §7.2 still omits it.
3. **Documentation/preflight drift was proven by R-07 and is now partly pinned.**
   `test_documentation_contract.py` covers the corrected rule counts, brownfield threshold,
   fingerprint waiver guidance and partial-assessment template; other claims remain manual.
4. **No test checks that a full conformance claim is rejected when a required rule is
   `executed:false`.** The runner accepts the six as a pinned gap. It should accept the gap
   only as a partial assessment.
5. **No test for Java other than fail-closed injection.** That is correct for unsupported,
   but it does not create support.

## Release-blocking regressions

The following must be closed or explicitly accepted as a **partial assessment** limitation
before a release gate can pass:

- R-01/R-17 (output completeness across languages);
- R-06/R-26 (fingerprint normative contract);
- R-12/R-13 (exclude and duplicate precision);
- R-25/R-27 (non-executed rules and P9.5);
- R-29/R-30 (discovery truncation);
- R-18/R-19 (hosted CI and independent review);
- Java support decision.
