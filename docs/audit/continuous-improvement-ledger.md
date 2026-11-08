# Continuous improvement ledger

Last updated: 2026-11-08

Repository: `c-lombardi/ACIMA`

Base commit before remediation: `541775b`

Verification environment: Linux, Python 3.12, Node 22, Go 1.23.4, .NET SDK 8.0.427

This ledger records the release-readiness audit that began from the earlier read-only
assessment. “Verified” means the acceptance criteria were exercised on the current workspace;
it does not mean every possible violation is detected. Hosted GitHub Actions is the one
mandatory external check that could not be executed in this environment.

## Status summary

| Status | Count |
|---|---:|
| Verified | 13 |
| Awaiting external verification | 1 |
| Deferred with justification | 3 |
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
  clean tree is zero; gallery is 23 rules.
- **Tests/evidence:** TypeScript behaviour suite (4 tests); conformance profile `typescript`
  (32 findings, 23 rules).
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
- **Tests/evidence:** `dotnet build host/Host/Host.csproj`; `dotnet run ... --verify` (clean,
  23 rules / 38 findings); conformance profile `dotnet`.
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

## Verification evidence

Commands executed on 2026-11-08, in this workspace:

| Check | Result |
|---|---|
| `python3 conformance/run.py` | PASS — topology, python, typescript, go, dotnet, tools |
| `python3 conformance/test_waiver_fingerprints.py` | PASS — 3 tests |
| `python3 conformance/test_cli.py` | PASS — 7 tests |
| Python behaviour suite | PASS — 10 tests |
| TypeScript behaviour suite | PASS — 4 tests |
| `go test ./...` | PASS |
| .NET host build | PASS |
| .NET `--verify` | PASS — clean tree, 23 rules / 38 gallery findings |
| `preflight --deep` | PASS — 4 enforcers clean, Java skipped, no blockers |
| `python3 conformance/run.py java` | FAIL-CLOSED — exit 1, no false green |
| YAML parse of workflow | PASS |
| `git diff --check` | PASS |

Per-profile measured galleries:

| Profile | Clean findings | Gallery findings | Gallery rules | Source files |
|---|---:|---:|---:|---:|
| Python | 0 | 33 | 23 | 27 |
| TypeScript | 0 | 32 | 23 | 12 |
| Go | 0 | 34 | 23 | 12 |
| .NET | 0 | 38 | 23 | 11 |

## Remaining limitations

1. Hosted GitHub Actions has not run; the workflow and upload-artifact step are unobserved.
2. Java is profile-only; no enforcer or gallery exists.
3. Six semantic/non-portable rules are explicitly unevaluated, not passed.
4. Python/TypeScript/Go/.NET enforcers are source-text analysis, not full type/symbol analysis.
5. No historical trend store or calibrated architecture health score exists.
6. The final adversarial pass was not performed by a separate agent.
7. The remediation is uncommitted in the workspace at base commit `541775b`.

## Release disposition

No unresolved Critical or High finding remains in the implemented scope. The accepted Medium
items are either resolved, explicitly deferred with a future acceptance criterion, or awaiting
the external hosted-CI run. The evidence supports a **small-team pilot** recommendation, not
enterprise-wide adoption.
