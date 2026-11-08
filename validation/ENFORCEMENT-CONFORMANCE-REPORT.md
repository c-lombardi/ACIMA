# Enforcement Conformance Report

**Status:** IN PROGRESS — internal review only
**Scope:** Four reference enforcers (Python, TypeScript, Go, .NET), the service-topology
runner, the conformance harness, and the 29-rule catalog.
**Architecture source:** `docs/standard/`, not the analyzers.

## 1. Verdict

**PARTIAL — the implemented subset is credible and improving; the full enforcement claim
is not established.**

The reference enforcers execute 23 of 29 catalog rules across four languages, the galleries
are checked against exact expected paths, and the conformance runner rejects zero-source
runs and coverage drift. Eight zero-finding benchmark repositories were injection-proven.
That is materially better than a demo.

The enforcement layer still cannot support a full ACIMA conformance claim:

- six normative rules are `executed: false` at every level;
- Java has no enforcer;
- the library profile is implemented only for TypeScript and .NET;
- the service profile is exercised only against a .NET-shaped fixture;
- runtime autonomy, configuration ownership, and API baselines are not established;
- hosted CI has not been observed;
- no independent reviewer has checked the rule interpretations.

The architecture remains the source of truth. Do not change an architectural requirement
to match an analyzer limitation.

## 2. B1 — Architecture-to-enforcement traceability

**Disposition: PARTIAL.**

`validation/ARCHITECTURE-ENFORCEMENT-MATRIX.md` traces every P1–P13 obligation to a rule,
language implementation, fixture, and human-judgment flag. `validation/RULE-TRACEABILITY.md`
traces all 29 rules and all 12 ST requirements in the other direction.

Findings:

1. **No principle is completely untraced**, but several obligations have no dedicated rule:
   P1.4 (A002), P1.6, P2.1, P4.1 (L004), P4.2/P4.3, P6.3 (C003), P6.7 (C007), P7.2
   (A002), P7.4 (A004), P7.5 (G004), P7.6, P9.4/P9.5, P11.5, P12.5, P13.4.
2. **Six rules are not executed.** They are not obscure: L1 includes L004; L2 includes
   C003, C007, G004; L3 includes A002, A004. No repository can claim full execution at any
   level with the reference enforcers.
3. **Several mappings are indirect.** P1.6 is inferred from D002/L003, P4.4 from D002/L003,
   P4.5 from D006, and P2.2 from several shape rules. Indirect mapping is useful but is not
   a complete test of the obligation.
4. **No rule lacks an architectural justification.** Every catalog rule traces to at least
   one principle. G001/G002/G005 are governance rules whose justification is P8/P9, not a
   domain-coupling claim.
5. **Overlap is intentional but noisy.** D001/D008/D009 and G001/G002 overlap. They catch
   different shapes/lifecycle states, but a raw finding count is a poor coverage measure.
6. **The service profile is a separate rule set.** S001–S012 do not change L1–L3, and the
   base catalog does not express transform requirements, inter-service contract naming, or
   per-layer contracts. A single "29-rule" claim cannot describe a service-profile repo.

## 3. B2 — Enforcement correctness

**Disposition: PARTIAL.**

### What is tested

- **Positive cases:** each of the 23 executed rules has a gallery fixture with an expected
  path; `conformance/run.py` fails if a rule is missing, extra, or points at a different
  path.
- **Negative cases:** the clean example trees are checked to produce zero findings, and the
  runner rejects a gallery whose coverage drifts.
- **Boundary cases:** literal exclusions vs prefix siblings (`test_exclusions`), zero source
  files (`test_library_profile`), malformed config (`test_cli`), unsupported Java
  (`test_injected_violation`), and 65,536-byte output (`test_library_profile` large output).
- **Exceptions/governance:** exact fingerprint suppresses one finding; a fingerprint-less
  waiver suppresses nothing and produces G001 (`test_waiver_fingerprints`). Baseline
  generation emits one waiver per fingerprint.
- **Public APIs/adapters:** declared public API and intentional adapters are classified;
  undeclared edges still fire (`test_library_profile`).
- **.NET metadata:** inherited/direct/defaulted `PackageId`, `IsPackable=false`, and
  `**/` public-API matching are tested (`test_dotnet_profile`).
- **Indirect dependencies:** D008 implements graph closure; the cycle fixtures exercise
  D005; the benchmark's Spectre duplicates show precision is not solved.
- **Generated/test/excluded paths:** exclusion semantics are tested for two languages;
  generated-code handling is not systematically tested.
- **Failure/incomplete execution:** missing source, invalid JSON, missing execution map,
  and unexecuted rules without reasons are rejected by preflight.

### What is not established

1. **Semantic equivalence.** Four languages use different algorithms. D009 visibility,
   L001 layer detection, L002 framework detection, C004 denylist coverage, C005 ORM
   detection, and A001 SQL detection are heuristic. Passing the gallery does not prove
   general correctness.
2. **Full boundary matrix.** Tests cover representative fixtures, not every source form
   (generated code, dynamic imports, re-exports, aliases, conditional compilation,
   multi-project solutions, monorepos).
3. **All-language large output.** The 65K test runs the TypeScript enforcer only. Python,
   Go and .NET are not tested at the same scale; do not claim the truncation class is
   universally fixed.
4. **Config severity semantics.** `P8.3` forbids disabling a required rule; the config
   permits lowering severity. There is no dedicated test that raising/disabling is rejected
   or that lowered severity still respects the level's required reporting. This is a gap.
5. **Hosted CI.** The workflow file exists; hosted GitHub Actions has not been observed.
6. **Java.** No reference implementation, no fixture, no semantic support.

### Known correctness defects / open risks

| ID | Defect/risk | Evidence | Status |
|---|---|---|---|
| E-01 | Six normative rules do not execute | `coverage.json`; all four enforcers | Open |
| E-02 | No Java enforcer | Java profile only; three benchmark repos blocked | Open |
| E-03 | Library profile rejects inherited .NET `PackageId` in the benchmark | Historical `rw-...-02`; fixed in current `test_dotnet_profile` | Fixed in code; benchmark evidence remains historical |
| E-04 | tRPC multi-segment directory excludes were treated as bare segment names | Historical raw 105 G005; `test_exclusions` covers literal/glob, not every multi-segment form | Partially covered |
| E-05 | D008 duplicates inflate findings | Benchmark: 3 duplicates; Spectre D005 analyzer-cycle false positives fixed | Open |
| E-06 | 30 valid library/API choices remain unclassified | Benchmark `rw-...-02` | Open |
| E-07 | C004/C005 heuristics miss unlisted frameworks/types | Code review | Open |
| E-08 | A001 cannot prove runtime DB isolation | Rule doc admits static-only | Open |
| E-09 | No universal large-output test | `test_library_profile` uses TypeScript only | Open |
| E-10 | Profile rules use token/JSON presence, not semantic proof | `topology.py`; docs admit | Open |
| E-11 | Service profile is .NET-shaped | `test_topology` fixtures | Open |

## 4. B3 — Cross-language semantic equivalence

**Disposition: PARTIAL.**

`validation/LANGUAGE-SUPPORT-MATRIX.md` reports per-rule status. Summary:

- Same 23 executed rule IDs exist in Python, TypeScript, Go and .NET.
- The algorithms are not equivalent: project graphs, import resolution, visibility,
  framework detection and public API evidence differ by language.
- Java has zero support; it must fail closed.
- Python and Go have no library profile; public API findings can be false positives.
- The service profile is not language-neutral in practice.
- Runtime autonomy is not equivalent across languages; all four are static only.

Do not interpret "23/29 in four languages" as "the same architecture is enforced
identically." It is a catalog-level count, not a semantic equivalence proof.

## 5. B4 — Assessment integrity

**Disposition: PARTIAL.**

| Property | Status | Evidence/limit |
|---|---|---|
| Deterministic output | PARTIAL | Stable ordering in tests; no randomized/property test; dictionary ordering dependencies possible |
| Stable output contract | PARTIAL | Required fields tested; `fingerprint`, `classified`, `execution` are extra fields not in the normative schema |
| Correct exit codes | PARTIAL | 0/1/2 tested for CLI and enforcers; held-out harness errors not exhaustive |
| Valid machine-readable output | PASS (supported set) | 12/12 benchmark outputs valid JSON; malformed config exit 2 |
| Complete output/no truncation | PARTIAL | 65K TypeScript test; other languages untested |
| Accurate skipped-rule reporting | PASS | All four report six `executed:false` with reasons; runner pins coverage |
| Unsupported-rule reporting | PARTIAL | Java fails closed, but no Java report artifact |
| Configuration validation | PARTIAL | Missing units/level and malformed config tested; role/module constraints and `rules` severity not fully tested |
| Failure handling | PARTIAL | Exit 2 and no-traceback tested; partial parse failures not fully |
| Cancellation behavior | NOT TESTED | No test for SIGINT/timeout cleanup |
| Reproducibility | PARTIAL | Pinned source commits/configs; toolchains external; hosted CI unobserved |
| CI integration | PARTIAL | Workflow present; hosted run unobserved; strict fixture guard exists |

**The most important integrity rule is correct:** zero findings from zero files is not a
pass. `sourceFiles` is required positive by preflight and runner. That is a strong
safeguard.

## 6. Conformance evidence

The following evidence exists in this repository:

- `conformance/coverage.json` — explicit executed/not-executed partition;
- `conformance/run.py` — clean/gallery comparison, coverage drift, zero-source rejection;
- `examples/*/violations/expected.json` — 23 rules per language;
- `conformance/test_*.py` — targeted contracts and regressions;
- `benchmark-evidence/rw-2026-11-08-02/` — 12 supported repos, raw outputs, configs,
  adjudications, checksums, Java blocked records.

It does **not** contain:

- a full 29-rule execution proof;
- a Java artifact;
- a hosted CI run;
- an independent reviewer's sign-off;
- a real production adoption;
- runtime/operational autonomy evidence;
- a precision/recall measurement with reliable ground truth.

## 7. Enforcement scorecard

Rubric: 0 absent, 1 asserted, 2 implemented but partial, 3 implemented with strong
fixtures, 4 independently validated.

| Dimension | Score | Rationale |
|---|---:|---|
| Traceability | 2 | Matrix exists; six gaps and indirect mappings remain |
| Semantic correctness | 2 | Gallery-level correctness; heuristics and language differences |
| Positive detection | 3 | 23/23 gallery rules fire in four languages |
| Negative detection | 2 | Clean examples pass; limited adversarial negatives |
| False-positive avoidance | 2 | 1 benchmark false positive, 30 valid choices unclassified, profile limits |
| False-negative avoidance | 1 | Six rules never execute; injection only proves L001/D001 |
| Language support | 1 | Java none; library/service profiles limited |
| Assessment integrity | 2 | Strong zero-source guard; truncation/CI/cancellation gaps |
| Determinism | 2 | Stable in tests; no broad property/repeatability suite |
| CI reliability | 1 | Hosted CI unobserved; workflow only |

**Domain disposition: PARTIAL / FAIL for a full conformance release gate.** Do not average
this into a single score.

## 8. Required next actions

1. Resolve AD-01/AD-11 so no run with `executed:false` is called full conformance.
2. Add universal large-output tests, not only TypeScript.
3. Add tests for severity changes, disabled rules, malformed config permutations.
4. Add Java or explicitly remove Java from the supported matrix and all claims.
5. Add non-.NET service-profile fixtures before claiming portability.
6. Fix D008 duplicate reporting and finish the remaining library-profile classification
   cases.
7. Run the GitHub Actions workflow on a branch and record the result.
8. Obtain independent review of at least the fixture classifications and the six manual
   rules.

## 9. Local verification record (2026-11-08)

Run after the P0 documentation, discovery and waiver corrections in this iteration:

| Check | Result |
|---|---|
| `python3 conformance/run.py` | PASS — topology, python, typescript, go, dotnet, tools; exit 0 |
| `python3 -m unittest discover -s conformance -p 'test_*.py'` | PASS — 64 tests |
| `conformance/test_mode_precedence.py` | PASS — 6 tests |
| `conformance/test_topology.py` | PASS — 7 tests |
| Python gallery | PASS — clean tree, 23 rules / 33 findings |
| TypeScript gallery | PASS — clean tree, 23 rules / 33 findings |
| Go gallery | PASS — clean tree, 23 rules / 34 findings |
| .NET gallery | PASS — clean tree, 23 rules / 37 findings |
| .NET `--verify --root examples/dotnet` | PASS — 23 rules / 37 findings |
| `git diff --check` | PASS |

New regression coverage: `test_preflight_discovery.py` (zero-unit blocker, 18-module
completeness), `test_mode_precedence.py` (mode selector, precedence, fail-closed config) and
`test_documentation_contract.py` (rule counts, brownfield threshold, fingerprint waivers,
partial-assessment template).

This record does not change the verdict. It is local evidence only: hosted CI, independent
review, Java, non-.NET service topology, runtime autonomy and a real application pilot are
still absent. The six non-executed rules still prevent a full conformance claim.
