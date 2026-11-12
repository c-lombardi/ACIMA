# Results

Actual results from the integrated working tree. No result below is inferred from a plan or a code review alone.

## Environment

- Branch: `main`
- HEAD: `1236b37` (`Make adoption reports reconcile assessment evidence`)
- Python: `py -3` → 3.15.2
- .NET: 11.0.100-rc.3.26522.148
- Node: v26.13.0
- Go: go1.27.3 windows/amd64
- Working tree intentionally uncommitted; no commit, push, branch operation, deployment or release was performed.

## Commands and results

| Command | Result | Exit code |
|---|---|---|
| `py -3 -m unittest discover -s conformance -p 'test_*.py'` | 432 tests run, 0 failures, 0 errors | `0` |
| `py -3 conformance/run.py` | All selected profiles conform: topology; Python 42 rules / 57 gallery findings; TypeScript 41 / 54; Go 23 / 34; .NET 24 / 39; tools | `0` |
| `py -3 conformance/run.py tools` | Re-ran the tools profile after registering the new .NET, toolchain-lookup, skill-architecture and skill-bundle checks; CLI, consent, scenario, report and executable-walkthrough checks pass | `0` |
| `py -3 conformance/test_consent_workflow.py` | 6 consent-workflow tests passed | `0` |
| `py -3 -m unittest conformance.test_documentation_contract conformance.test_documentation_integrity conformance.test_adoption_experience` | 61 documentation and experience tests passed on the final documentation | `0` |
| `py -3 -m unittest conformance.test_dotnet_false_positives -v` | 3 controlled .NET false-positive tests passed | `0` |
| `py -3 -m unittest conformance.test_skill_architecture -v` | 3 skill self-architecture checks passed | `0` |
| `py -3 conformance/test_toolchain_lookup.py -v` | 10 lookup, blocked-toolchain and script-invocation checks passed | `0` |
| `py -3 conformance/test_skill_bundle.py -v` | 3 vendored-skill bundle-drift checks passed | `0` |
| `py -3 -m unittest discover -s benchmarks/ai-adoption/harness/tests -p 'test_*.py'` | 113 tests run, 2 skipped, 0 failures | `0` |
| `py -3 tools/bundle_skill.py` | Wrote 50 files and `MANIFEST.json` | `0` |
| `py -3 tools/bundle_skill.py --check` | 50 files match their sources | `0` |
| `git diff --check` | No whitespace errors | `0` |

The full `unittest` discovery includes the workflow, report, skill-bundle, standalone-skill, documentation, enforcement and .NET profile tests. The `conformance/run.py` tools profile invokes the pytest-style consent and scenario tests directly.

## Workflow coverage

- Canonical identifiers and labels are asserted in `conformance/test_adoption_workflow.py` and `conformance/test_consent_workflow.py`.
- Empty, assessment-in-progress, report-review, blocked, deferred, implementation-in-progress, completed and partially populated states are covered by `CanonicalPhaseTests`.
- The report receives its phase from `adoption_reports._canonical_phase`, which delegates to the workflow module; `test_report_model_projects_the_engine_phase_without_recalculating_it` checks the projection.
- `test_cli_exposes_the_workflow` checks JSON `phase` / `phaseLabel` and human output `phase   Phase 1 — Assess`.
- `test_report_renders_workflow_state` generates the six-page HTML pack and asserts `Current phase: <b>Phase 1 — Assess</b>`.
- A separate generated report inspection produced `Current phase: Phase 1 — Assess. Current stage: Module map.` and the six expected pages (`index`, `proposal`, `findings`, `files`, `plan`, `evidence`).
- Guided and automated mode behavior is exercised by `test_guided_start_generates_deliverables_but_no_implementation`, `test_full_requires_explicit_authorization`, `test_full_generates_enforcement_ci_state_and_verification`, and the adoption-scenario suite.
- `.github/workflows/acima.yml` runs the skill self-architecture and bundle-drift tests explicitly before the full conformance suite; `conformance/run.py tools` includes both tests as well.

## Enforcement results

| Language | Clean profile | Gallery | Result |
|---|---|---|---|
| Python | 42 executed rules | 57 findings | Pass |
| TypeScript | 41 executed rules | 54 findings | Pass |
| Go | 23 executed rules | 34 findings | Pass |
| .NET | 24 executed rules | 39 findings | Pass |

The existing WS-05 changes were preserved:

- Finding fingerprints are full SHA-256 hex values in all four reference enforcers and both fingerprint tests.
- Value-ownership and waiver-fingerprint tests pass.
- The three controlled .NET fixtures confirm case-insensitive `Infrastructure` path handling, distinct same-name internal types, and same-repository namespaces not being treated as third-party.
- Positive gallery behavior remains covered by `conformance/run.py`; the rules were not weakened to make the fixtures pass.

## Bundle integrity

- Regeneration wrote 50 files plus `MANIFEST.json`.
- `--check` compared every vendored file with its authoritative source and found no drift.
- `git status` contains no deleted vendor files; the bundle sources were not reduced.
- `SKILL.md` and `skills/acima-adoption/manifest.json` both declare skill version `1.35.0`.

## Outstanding limitations and unverified checks

- No isolated subagent workspaces were available. Work was serialized in this tree; no claim of parallel writing is made.
- Owner approvals in tests are simulated fixture records. No live human owner completed a guided or automated adoption during this run.
- No external CI provider was contacted, no remote workflow was executed, and no deployment, release or publication occurred. The suite verifies local CI artifact generation only.
- The generated HTML was inspected as rendered text and markup, not in a graphical browser or with a screen reader. Automated contrast, structure and accessibility-baseline tests passed; manual assistive-technology release checks remain outstanding.
- .NET verification used the installed prerelease SDK `11.0.100-rc.3.26522.148`, not every supported .NET runtime.
- The benchmark harness passed with 2 skipped tests; skipped tests were not counted as passes.
- The working tree remains uncommitted by design.
