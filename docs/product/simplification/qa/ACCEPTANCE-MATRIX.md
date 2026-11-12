# Acceptance matrix

Each row maps a requirement to its owner, implementation location, verification and expected result. `Automated` means a command or test asserts it; `Manual review` means a person must inspect the integrated result.

| Requirement | Workstream | Implementation | Verification | Expected result | Type |
|---|---|---|---|---|---|
| One canonical journey: Start, Phase 1 — Assess, Phase 2 — Explain and propose, Phase 3 — Review and authorize, Phase 4 — Implement, Phase 5 — Verify and hand off | WS-01, WS-02, WS-03, WS-04 | Product docs, skill, engine, CLI, report | `test_adoption_workflow`, `test_html_report`, `test_consent_workflow`; cross-document search | Identical identifiers and labels everywhere | Automated |
| Guided adoption uses distinct review checkpoints | WS-01, WS-02 | `README.md`, `SKILL.md`, `22-workflow.md` | Manual review against workflow stages | Map, report, CI, optional work and implementation each have a checkpoint | Manual review |
| Automated adoption prepares the complete package, then one consolidated review | WS-01, WS-02, WS-03 | `README.md`, `PRODUCT.md`, `SKILL.md`, `adoption_workflow.start` | `test_adoption_workflow.test_cli_exposes_the_workflow` | Automated mode still waits for explicit scope approval | Automated |
| Both modes use the same evidence and approval authority | WS-02, WS-03 | Skill guidance and workflow gates | Guided/automated scenario runs; review of `_require_approved_scope` | No mode bypasses the 56-requirement review or approval provenance | Automated + manual |
| A generated proposal is never implementation permission | WS-01, WS-02, WS-03 | Docs, skill, workflow state/next action | Workflow tests; manual review of report and scope gates | Report review and scope approval remain separate | Automated |
| All 56 requirements assessed individually | WS-02, WS-03 | Review validation and workflow preflight | Existing full conformance suite; report tests | 56/56 dispositions required before decision-ready output | Automated |
| Evidence, limitations and unknowns remain visible | WS-01, WS-04 | Report schema/model/renderer | `test_html_report`; manual report inspection | Incomplete assessment cannot be styled or described as verified | Automated |
| Module-map ownership is reviewed, not inferred as confirmed | WS-02, WS-03 | Skill and workflow module-map gate | Existing workflow tests | An inferred map requires owner review before enforcement | Automated |
| Approval provenance and scope-specific authorization | WS-03 | `_require_approved_scope` | Existing workflow tests | Exact report digest, paths and approver must agree | Automated |
| Publication, release or merge needs separate approval | WS-01, WS-02 | Docs and skill | Manual review | Implementation approval is not release approval | Manual review |
| Optional artifacts are not created from general approval | WS-02 | `SKILL.md`, `15-consent-and-scope.md` | `test_consent_workflow` | Explicit artifact request remains required | Automated |
| Engine is the sole phase owner | WS-03, WS-04 | `conformance/adoption_workflow.py` | `test_adoption_workflow`; `adoption_reports._canonical_phase` test | Report and CLI project engine state; no second calculation | Automated |
| Every workflow stage maps to exactly one canonical phase | WS-03 | `STAGE_PHASE`, `PHASE_ORDER` | `test_adoption_workflow.test_every_stage_has_a_canonical_phase` | No missing or unknown mapping | Automated |
| Empty workflow state is Start | WS-03 | `_current_phase` | `test_adoption_workflow.test_empty_workflow_starts_at_start` | `start` | Automated |
| In-progress assessment is Phase 1 | WS-03 | `_current_phase` | `test_adoption_workflow.test_awaiting_review_stays_in_assess` | `assess` | Automated |
| Pending report review is Phase 3 | WS-03 | `STAGE_PHASE`, `_current_phase` | `test_html_report_review_maps_to_review_and_authorize` | `review_and_authorize` | Automated |
| Blocked stages hold the workflow | WS-03 | `_current_phase` | Blocked-stage workflow test | No phase advance | Automated |
| Deferred stages do not silently advance | WS-03 | `_current_phase` | Deferred-stage workflow tests | Deferred work remains visible; completed later work does not rewind | Automated |
| Implementation in progress is Phase 4 | WS-03 | `_current_phase` | `test_active_later_stage_is_not_pulled_back_by_missing_earlier_records` | `implement` | Automated |
| Completed workflow is Phase 5 | WS-03 | `_current_phase` | Completed/deferred workflow test | `verify_and_hand_off` | Automated |
| Missing earlier records are not inferred complete | WS-03 | `_current_phase` | Completed-later-stage test | Earliest missing phase is reported | Automated |
| CLI human output shows authoritative phase | WS-03 | `tools/acima.py` adoption summary | `test_cli_exposes_the_workflow` text assertion | `Phase 1 — Assess` from engine | Automated |
| CLI JSON preserves structured phase information | WS-03 | `tools/acima.py` | `test_cli_exposes_the_workflow` JSON assertions | `phase`, `phaseLabel`, `phaseOrder` retained | Automated |
| Report exposes `phase`, `phaseLabel`, `phaseOrder` | WS-04 | `adoption_reports.build_report_model`, schema | `test_html_report` schema and projection tests | Fields present and schema-required | Automated |
| Report renders the canonical phase | WS-04 | `render_report.py` | `test_plan_page_states_the_canonical_phase` | Canonical label appears on the plan page | Automated |
| Missing phase information is not invented | WS-04 | `render_report.py` fallback | `test_plan_page_does_not_invent_a_missing_phase` | Shows “not recorded”, not a phase | Automated |
| Blocked/incomplete workflow remains truthful in report | WS-04 | report model + renderer | Workflow/report tests and manual inspection | No verification claim from report generation alone | Automated + manual |
| Full 64-hex waiver fingerprints are stable | WS-05 | Four enforcers and fingerprint tests | Language suites and conformance tests | Fingerprints are full SHA-256 hex and match test derivation | Automated |
| Value ownership semantics are preserved | WS-05 | Value-ownership analyzer/tests | `test_value_ownership` and language suites | No weakening of A005/A006 behavior | Automated |
| .NET infrastructure-path matching is case-insensitive | WS-05 | .NET enforcer | `test_dotnet_false_positives` | No L001 false positive for `Infrastructure` casing | Automated |
| .NET internal types with the same simple name are distinct | WS-05 | .NET enforcer | `test_dotnet_false_positives` | No D009 finding for an unrelated same-name type | Automated |
| Repository namespaces are not third-party | WS-05 | .NET enforcer | `test_dotnet_false_positives` | No D004 finding for a declared repository namespace | Automated |
| Skill references and manifest agree | WS-02 | `SKILL.md`, references, `manifest.json` | Bundle check and `conformance/run.py tools` | Version and references consistent | Automated |
| Standalone skill bundle is regenerated and verified | WS-02, WS-07 | `tools/bundle_skill.py`, vendor tree | `bundle_skill.py --check` | No drift; no unexplained deleted resources | Automated |
| Skill's own Python code has an explicit unit map and passes the Python enforcer | WS-05, WS-07 | `skills/acima-adoption/acima.config.json`, `conformance/test_skill_architecture.py` | `test_skill_architecture`; self-preflight | Four tooling units, vendor excluded, zero findings, authoritative map | Automated |
| CI blocks a missing skill unit or stale vendor snapshot | WS-07 | `.github/workflows/acima.yml`, `conformance/run.py` | Workflow step; `conformance/run.py tools` | Both skill tests run before full conformance and fail the job | Automated |
| .NET execution resolves from `PATH` or `DOTNET_ROOT` and stops when absent | WS-05, WS-07 | `conformance/executables.py`, `conformance/adoption_workflow.py`, skill scripts | `test_toolchain_lookup`; missing-toolchain scenario | No fixed installation path; no enforcer copy or enforcement write without a resolved executable | Automated |
| QA baseline, matrix and results exist and use actual evidence | WS-06 | `docs/product/simplification/qa/` | Manual review | Commands, exit codes and limitations recorded honestly | Manual review |
| No commits, pushes, branch changes, deployments or releases | WS-07 | Working tree | Final `git status`, `git log`, branch check | HEAD and branch unchanged; changes remain uncommitted | Automated + manual |
