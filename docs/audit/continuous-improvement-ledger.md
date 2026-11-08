# Continuous improvement ledger

Last updated: 2026-11-08

Repository: `c-lombardi/ACIMA`

Base commit before remediation: `541775b`
Current workspace HEAD: `25ed9f8c672c4e8031af7b50cc6b60b8635a0a2b` (dirty; changes uncommitted)

Verification environment: Linux, Python 3.12.3, Node 26.13.0, Go 1.26.0, .NET SDK 10.0.403 targeting net8.0

This ledger records the release-readiness audit that began from the earlier read-only
assessment. “Verified” means the acceptance criteria were exercised on the current workspace;
it does not mean every possible violation is detected. Hosted GitHub Actions and independent
review are external checks that could not be executed in this environment.

## Status summary

| Status | Count |
|---|---:|
| Verified | 17 |
| Awaiting external verification | 1 |
| Deferred with justification | 2 |
| Deferred with disclosure | 1 |
| Rejected | 0 |
| Unresolved Critical / High | 0 / 0 |

## Finding records

### ACIMA-001 — Conformance could report green without evidence

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** The previous runner skipped missing toolchains, accepted zero source files, and
  did not require every portable gallery rule.
- **Remediation:** `conformance/run.py` now fails on missing toolchains, requires
  `sourceFiles > 0`, requires an execution entry for all 29 catalog rules, requires a reason for
  every non-executed rule, and requires `expected.json` and measured gallery rules to equal the
  canonical 23-rule contract in `conformance/coverage.json`.
- **Acceptance:** Missing toolchains, zero sources, missing fixtures, or coverage drift produce
  exit 1; a valid profile prints the measured source-file and rule counts.
- **Tests/evidence:** `python3 conformance/run.py`; `conformance/coverage.json`.
- **Verified:** 2026-11-08. All six default profiles passed. Java explicitly fails closed because
  no implementation exists.

### ACIMA-002 — Python parser false negatives

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** The Python enforcer missed dynamic imports, string annotations, quoted SQL,
  `__init__` mutation, mutable class state, and role-overridden units.
- **Remediation:** Reworked `examples/python/tools/acima_arch.py` to cover the full catalog,
  dynamic imports, annotations, quoted SQL, mutation, role overrides, excluded declared units,
  `sourceFiles`, execution evidence, and invalid-level exit 2.
- **Acceptance:** Each probe fires its rule; the clean example remains at zero findings; gallery
  covers 23 rules.
- **Tests/evidence:** `examples/python/tools/acima_arch.py`; Python behaviour suite; conformance
  profile `python` (33 findings, 23 rules).
- **Verified:** 2026-11-08.

### ACIMA-003 — TypeScript parser false negatives

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** `.tsx`, `require`, imported static names, type aliases, and path/module waiver
  scopes were not all analysed; the gallery did not cover four portable rules.
- **Remediation:** Reworked `examples/typescript/tools/acima-arch.mjs`, added the missing
  fixtures and expected paths, and added execution/source evidence.
- **Acceptance:** `.tsx` and `require` probes fire D001/D008; mutable aliases fire C001/C002/G003;
  clean tree is zero;  gallery is 23 rules.
- **Tests/evidence:** TypeScript behaviour suite (4 tests); conformance profile `typescript`
  (33 findings, 23 rules).
- **Verified:** 2026-11-08.

### ACIMA-004 — Go parser and waiver false negatives

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** Go missed `[]T` C002, private/internal D009, discarded waiver findings, and had no
  execution evidence. The gallery covered only 20 rules.
- **Remediation:** Added full execution evidence, fail-closed levels, slice detection, private
  import detection, preserved waiver findings, role-override/excluded-unit checks, path waivers,
  and finding fingerprints. The reference contract was corrected to private slices with copying
  constructors and accessors.
- **Acceptance:** Clean tree zero findings; gallery 23 rules; D009/G001/G002 fire; `go test ./...`
  passes.
- **Tests/evidence:** `go test ./...`; conformance profile `go` (34 findings, 23 rules).
- **Verified:** 2026-11-08.

### ACIMA-005 — .NET proof gaps

- **Severity:** High
- **Status:** Verified
- **Evidence:** The .NET enforcer did not cover the full catalog/execution contract, did not
  detect array collections or package-reference edges, and had no source/execution evidence.
- **Remediation:** Added the full catalog and execution map, invalid-level handling, array C002,
  PackageReference edge mapping, C002 reference correction, and source-file evidence.
- **Acceptance:** Clean host build and `--verify` pass; gallery 23 rules; invalid level exits 2.
- **Tests/evidence:**  `dotnet build host/Host/Host.csproj`; `dotnet run ... --verify` (clean,
  23 rules / 37 findings); conformance profile `dotnet`.
- **Verified:** 2026-11-08.

### ACIMA-006 — Unit waivers could hide future findings

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** A waiver scoped to `unit:<id>` suppressed every finding of that rule in the unit,
  including findings introduced after the baseline.
- **Remediation:** Every finding now carries a stable `sha256:` fingerprint over rule, path and
  evidence. Active waivers without a fingerprint are rejected with G001. The preflight emits one
  fingerprinted waiver per measured finding, not one per rule/unit. Python, TypeScript, Go and .NET
  apply exact fingerprints; path, module and unit remain selectors only.
- **Acceptance:** A fingerprinted waiver suppresses exactly one finding; a fingerprint-less
  waiver suppresses none and produces G001; a second finding in the same unit remains.
- **Tests/evidence:** `conformance/test_waiver_fingerprints.py` (3 tests across all four
  enforcers plus preflight); `conformance/test_cli.py`.
- **Verified:** 2026-11-08.

### ACIMA-007 — Small brownfield repositories were called greenfield

- **Severity:** High
- **Status:** Verified
- **Evidence:** The preflight used `total < 10` source files as the greenfield test, so a legacy
  repository with nine files received the wrong playbook.
- **Remediation:** Greenfield now means no configuration and no source files; any existing source
  tree is brownfield. Discovery also includes `app`, `apps`, `services`, `lib` and `modules`.
- **Acceptance:** A one-file repository is classified brownfield.
- **Tests/evidence:** `conformance/test_waiver_fingerprints.py::AdoptionPreflightTests`.
- **Verified:** 2026-11-08.

### ACIMA-008 — Invalid levels/configs could traceback or silently downgrade

- **Severity:** High
- **Status:** Verified
- **Evidence:** Invalid levels could fall back to L1, and malformed CLI config could raise an
  unhandled JSON traceback.
- **Remediation:** All enforcers reject unknown levels; the CLI raises a typed `ConfigError` and
  exits 2 with a message. Go’s program exits 2, although `go run` reports the wrapper as exit 1.
- **Acceptance:** No traceback; non-zero exit; no silent level downgrade.
- **Tests/evidence:** `conformance/test_cli.py::test_malformed_config...`; manual invalid-level
  probes (Python 2, TypeScript 2, .NET 2, Go program 2 / `go run` wrapper 1).
- **Verified:** 2026-11-08.

### ACIMA-009 — Stale/misleading capability documentation

- **Severity:** High
- **Status:** Verified
- **Evidence:** Status and language pages claimed 19/23 and 20/23 coverage, documented gaps that
  no longer existed, claimed `go/parser`/`go/ast`, used a different Go module path, and implied
  every language profile had a reference implementation.
- **Remediation:** Updated status, language index, Go and rule-index documentation; removed stale
  gap tables; made Java’s profile-only status explicit; corrected the Go scanner description and
  module path.
- **Acceptance:** No stale coverage/gap claims remain; `rg` scan is clean.
- **Tests/evidence:** Documentation scan; `preflight --deep` calibration.
- **Verified:** 2026-11-08.

### ACIMA-010 — Full catalog/execution coverage evidence

- **Severity:** High
- **Status:** Verified
- **Evidence:** Profiles had different catalogs and no machine-readable proof that every rule was
  executed or deliberately not executed.
- **Remediation:** `conformance/coverage.json` is canonical: 29 rules, 23 executed/gallery rules
  and 6 explicit non-executed rules per implemented profile.
- **Acceptance:** Runner rejects any partition or gallery mismatch.
- **Tests/evidence:** `conformance/run.py`.
- **Verified:** 2026-11-08.

### ACIMA-011 — Brownfield baseline workflow

- **Severity:** Medium
- **Status:** Verified
- **Evidence:** The adoption skill could draft units and measure a baseline, but did not produce
  finding-scoped waivers or cover common source layouts.
- **Remediation:** `--write-waivers` now emits fingerprinted, owner-placeholder waivers for exact
  findings; unit discovery covers app/service/lib layouts; preflight rejects active broad waivers.
- **Acceptance:** Generated baseline waivers are unique and fingerprinted.
- **Tests/evidence:** `AdoptionPreflightTests.test_baseline_waivers...`.
- **Verified:** 2026-11-08.

### ACIMA-012 — Hosted CI unobserved

- **Severity:** Medium
- **Status:** Awaiting external verification
- **Evidence:** `.github/workflows/acima.yml` exists and parses as YAML, but this sandbox cannot run
  GitHub Actions. The `.github/` directory is untracked in the current worktree.
- **Remediation:** Workflow runs all four behaviour suites, the conformance runner and the evidence
  report, and uploads `acima-report.md` plus per-profile clean/gallery artifacts.
- **Acceptance:** One green hosted run on a branch, including artifact upload.
- **Tests/evidence:** YAML parse only; no hosted run.
- **Verified:** Not verified externally. This remains an adoption limitation, not a code claim.

### ACIMA-013 — Java profile has no reference enforcer

- **Severity:** Medium
- **Status:** Deferred
- **Evidence:** `examples/java` does not exist; `conformance/run.py java` fails closed.
- **Remediation:** Profile is explicitly documented as profile-only; the skill stops and tells the
  user to use ArchUnit. No Java point is counted.
- **Acceptance for a future milestone:** Java fixture, gallery, enforcer, execution evidence and
  expected.json matching the canonical contract.
- **Tests/evidence:** `python3 conformance/run.py java` exits 1 by design.
- **Verified:** Disposition verified; implementation not claimed.

### ACIMA-014 — Semantic/non-portable rules

- **Severity:** Medium
- **Status:** Deferred
- **Evidence:** C003, C007, L004, A002, A004 and G004 require semantic, framework, package or API
  baseline analysis that the portable source enforcers do not perform.
- **Remediation:** Every profile reports them as `executed:false` with a reason; reports list them
  as not evaluated. They are never counted as passes.
- **Acceptance for a future milestone:** Native analyzers or profile-specific evidence formats.
- **Tests/evidence:** Execution evidence in every profile; `acima report` not-evaluated section.
- **Verified:** Disposition verified; no false claim of detection.

### ACIMA-015 — Independent-agent separation

- **Severity:** Medium
- **Status:** Deferred with disclosure
- **Evidence:** No separate independent agent was available in this environment.
- **Remediation:** A distinct adversarial verification pass was performed after implementation:
  new fixtures, exact-fingerprint tests, invalid-level probes, zero/Java fail-closed checks, docs
  scan, and a full rerun. It was executed by the same assistant, not a separate agent.
- **Acceptance for a future milestone:** A separate reviewer reruns the ledger commands and signs
  the release recommendation.
- **Verified:** Disclosed limitation; not claimed as independent-agent verification.

### ACIMA-016 — Go invalid-level wrapper exit status

- **Severity:** Low
- **Status:** Verified with documented limitation
- **Evidence:** The Go program calls `os.Exit(2)`, but `go run` returns 1 and prints
  `exit status 2`.
- **Remediation:** The program’s own exit is 2; CI and CLI should build a binary if the exact
  wrapper status matters. No silent downgrade occurs.
- **Tests/evidence:** Manual probe.
- **Verified:** 2026-11-08.

### ACIMA-017 — Brownfield discovery collapsed a namespace into one unit

- **Severity:** Medium
- **Status:** Verified
- **Evidence:** A `src/acima/{catalog,orders,...}` layout was proposed as one unit, so D001
  findings were silently absorbed by the draft map.
- **Remediation:** `propose_directory_units` descends through a single namespace directory when
  the source root has no direct source files, then proposes the module children.
- **Acceptance:** The brownfield trial proposes `catalog`, `customers`, `orders`, `payments` and
  `host` units; D001 is measured; `--write-waivers` emits one fingerprint per finding.
- **Tests/evidence:** Brownfield trial on a temporary copy: 9 units, 14 findings, 14 waivers, all
  fingerprinted; `conformance/test_waiver_fingerprints.py` still passes.
- **Verified:** 2026-11-08.

### ACIMA-018 — Literal exclusions admitted out-of-scope sibling prefixes

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** Python and TypeScript literal exclusions were compared as substrings or exact
  paths. A declared `tooling` exclusion could therefore admit `tooling-extra`, and multi-segment
  path handling differed from Go/.NET.
- **Remediation:** Literal exclusions now match a file or directory subtree only; sibling prefixes
  do not match. Glob patterns remain globs and bare segments retain legacy any-directory matching.
- **Acceptance:** A file under the declared subtree is excluded; a sibling prefix is not; a glob
  exclusion still matches; the clean examples remain clean.
- **Tests/evidence:** `conformance/test_exclusions.py`; `conformance/run.py` tools profile.
- **Verified:** 2026-11-08.

### ACIMA-019 — `G005` catalog title contradicted its documented meaning

- **Severity:** High
- **Status:** Verified
- **Evidence:** `tools/acima-spec/rules.json` called `G005` “Module without architecture tests”
  while the standard and every enforcer used it for unclassified source.
- **Remediation:** Corrected the catalog title/summary to “Unclassified source”; added a contract
  test so docs and catalog cannot drift silently again.
- **Acceptance:** The catalog title/summary matches the documented meaning and all enforcers.
- **Tests/evidence:** `conformance/test_rule_catalog.py`; preflight `SKL-002` after re-pinning;
  catalog SHA-256 `ec2a77d7a2ed4d8c68fd71c32ad47ac486022b2eb541b959a23f1d2b7ea9221b`.
- **Verified:** 2026-11-08.

### ACIMA-020 — .NET library profiles rejected inherited PackageId

- **Severity:** Critical
- **Status:** Verified
- **Evidence:** FluentValidation’s `PackageId` is inherited/defaulted by MSBuild, not written as
  literal `<PackageId>` XML. The enforcer concatenated project/props text, so it emitted `G001`
  and disabled the profile, leaving five public-API findings unclassified.
- **Remediation:** Profile validation now evaluates `PackageId` and `IsPackable` with
  `dotnet msbuild -getProperty` (evaluation only, no target build). Evaluation failures produce a
  `G001` instead of silently rejecting or accepting the profile.
- **Acceptance:** Direct, inherited, and SDK-defaulted package IDs are accepted; `IsPackable=false`
  is rejected; the FluentValidation repro has no `G001`.
- **Tests/evidence:** `conformance/test_dotnet_profile.py` (5 tests); targeted FluentValidation
  run: 144 source files, 6 classified, 1 remaining D001.
- **Verified:** 2026-11-08.

### ACIMA-021 — .NET publicApi glob missed root-level package files

- **Severity:** High
- **Status:** Verified
- **Evidence:** `src/FluentValidation/**/*.cs` classified nested files but not root-level public
  types, so five legitimate public-API findings remained unclassified after ACIMA-020.
- **Remediation:** .NET path globs now convert `**/` to zero-or-more directories; `*` does not
  cross separators and `?` matches one non-separator character.
- **Acceptance:** The same pattern classifies both `src/Widget/Widget.cs` and
  `src/Widget/Internal/Nested.cs`; undeclared paths still fail.
- **Tests/evidence:** `conformance/test_dotnet_profile.py::test_public_api_glob_matches_root_and_nested_files`;
  FluentValidation targeted run classified all five L003 findings.
- **Verified:** 2026-11-08.

## Verification evidence

Commands executed on 2026-11-08, in this workspace:

| Check | Result |
|---|---|
| `python3 conformance/run.py` | PASS — topology, python, typescript, go, dotnet, tools |
| `python3 -m unittest discover -s conformance -p 'test_*.py'` | PASS — 64 tests |
| `conformance/test_exclusions.py` | PASS — 1 test |
| `conformance/test_rule_catalog.py` | PASS — 1 test |
| `conformance/test_dotnet_profile.py` | PASS — 5 tests |
| `conformance/test_waiver_fingerprints.py` | PASS — 3 tests |
| `conformance/test_preflight_discovery.py` | PASS — 2 tests |
| `conformance/test_documentation_contract.py` | PASS — 8 tests |
| `conformance/test_mode_precedence.py` | PASS — 6 tests |
| `conformance/test_topology.py` | PASS — 7 tests |
| `conformance/test_cli.py` | PASS — 7 tests |
| Python behaviour suite | PASS — 10 tests |
| TypeScript behaviour suite | PASS — 4 tests |
| `go test ./...` | PASS |
| .NET host build | PASS |
| .NET `--verify` | PASS — clean tree, 23 rules / 37 gallery findings |
| `preflight --deep` with all toolchains on PATH | PASS — 4 enforcers clean, Java explicitly skipped, no blockers |
| `python3 conformance/run.py java` | FAIL-CLOSED — exit 1, no false green |
| YAML parse of workflow | PASS |
| `git diff --check` | PASS |

Per-profile measured galleries:

| Profile | Clean findings | Gallery findings | Gallery rules | Source files |
|---|---:|---:|---:|---:|
| Python | 0 | 33 | 23 | 27 |
| TypeScript | 0 | 33 | 23 | 12 |
| Go | 0 | 34 | 23 | 12 |
| .NET | 0 | 37 | 23 | 11 |

## Validation remediation iteration (2026-11-08)

Applied the audit's P0 documentation, discovery and claim corrections, then re-ran the gate:

- `docs/rules/index.md` names all six non-executed rules and the correct 23 executed rules.
- `docs/standard/08-conformance.md` removes the fixed “24 of 24”, distinguishes full
  conformance from `PARTIAL ASSESSMENT`, and corrects the warning example.
- `docs/standard/07-executable-governance.md` §7.5 now requires `rule` + `scope` +
  `fingerprint` to match, resolving C-05; the finding schema still omits `fingerprint` (C-14).
- `preflight.py` adds `fingerprint` to `WAIVER_FIELDS`, removes the 16-unit cap, and fails
  `TGT-004` when a source-bearing repository yields no units; the 50,000-file walk cap is
  still unreported (R-30).
- The skill is 1.2.3: partial-assessment rule, mode selector and explicit service-topology
  stop, Python/Go library stops, corrected brownfield/waiver/glossary guidance.
- New tests: `test_preflight_discovery.py` (2), `test_documentation_contract.py` (8),
  `test_mode_precedence.py` (6), plus five new topology mode tests.

Verified after the changes: conformance exit 0; 64 unittest tests OK; repo preflight exit 0
with 5 units and no blockers/warnings; `--deep` exit 0; .NET `--verify` exit 0; `git diff
--check` clean. Hosted CI and independent review remain unobserved.

## Mode selector iteration (2026-11-08)

Resolved AD-02/AD-03 (C-03/C-04) with a single machine-readable selector:

- `acima.config.json.mode` is authoritative: `base` (default when absent) or
  `service-topology`.
- `service-topology` applies P1–P9 plus P10–P13 and supersedes exactly P2.1 and P3.5;
  all other base obligations remain in force.
- `conformance/topology.py` rejects a missing/mismatched mode or manifest profile with exit 2.
- `preflight.py` reports `TGT-006` and blocks service mode as `NOT SUPPORTED` by this skill.
- All example, gallery and fixture configs now declare `mode`; the preflight draft does too.
- Tests: `test_mode_precedence.py` (6), five new topology mode tests; full gate 64 tests,
  conformance exit 0, repo preflight base mode, `--deep` and .NET verify clean.

## Remaining limitations

1. Hosted GitHub Actions has not run; the workflow and upload-artifact step are unobserved.
2. Java is profile-only; no enforcer or gallery exists.
3. Six semantic/non-portable rules are explicitly unevaluated, not passed.
4. Python/TypeScript/Go/.NET enforcers are source-text analysis, not full type/symbol analysis.
5. No historical trend store or calibrated architecture health score exists.
6. The final adversarial pass was not performed by a separate agent.
7. The remediation is uncommitted in the workspace at base commit `25ed9f8`.
8. The published `rw-2026-11-08-02` benchmark predates ACIMA-018–021; a new immutable rerun is
   required before portfolio-level claims move.
9. Path-glob semantics are not yet uniform: .NET now treats `**/` as zero-or-more directories;
   Python, TypeScript and Go retain library-specific behavior. The product contract discloses this.
10. The benchmark record correctly says skill 1.2.0 / the old catalog hash; it must not be edited
    retroactively.

## Release disposition

No unresolved Critical or High finding remains in the locally verified implementation scope. The
remaining Medium items are explicitly deferred, awaiting hosted CI, or awaiting independent
review. The evidence supports a **technical-preview / advisory pilot** recommendation only; beta
and GA remain blocked by the product contract’s gate criteria. This is not an independent
certification and not a claim of organizational adoption.
