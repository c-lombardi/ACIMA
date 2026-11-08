# Skill Adversarial Tests

**Status:** IN PROGRESS — internal review only
**Purpose:** Exercise the skill on misleading, unsafe and unsupported situations. A test
passes only if the skill identifies the uncertainty, explains the decision, and avoids an
unsafe or unnecessary change. Executing a command is not a pass.

## Test matrix

| # | Scenario | Expected behavior | Observed behavior / evidence | Result |
|---|---|---|---|---|
| AD-01 | Misleading project structure: README says two modules; only one nested legacy directory | Read the docs, compare with the tree, report the conflict, stop before a unit map | Preflight ignores README; proposes 0 units for `src/legacy/only.py`; exits 0 with `TGT-004`/`TGT-005` warnings | **FAIL** |
| AD-02 | Architecture documentation conflicts with source | Cite both, distinguish stated vs observed, ask owner | No docs/ADR scan; no conflict output | **FAIL / NOT IMPLEMENTED** |
| AD-03 | Library has legitimate public API dependencies | Recognize library profile, require publishable evidence, classify only declared paths; keep undeclared edges | `test_library_profile` classifies `publicApi` and intentional adapters; rogue adapter/private leak still fail; profile invalid declarations fail | **PASS (TS)** |
| AD-04 | Adapter is incorrectly flagged | Classify the declared adapter path, retain owner/reason, keep other findings | `test_library_profile` declared D001/L001 classified; undeclared edge remains | **PASS (TS/.NET partial)** |
| AD-05 | Necessary integration dependency (vendor SDK) | Recognize adapter/vendor seam; do not remove a legitimate integration | `test_library_profile` intentional adapter; `.NET` profile tests; no service vendor workflow | **PARTIAL** |
| AD-06 | Assessment output truncated or malformed | Reject, fail closed, do not report clean | 65K TS test passes; malformed config exit 2; other languages not large-output tested | **PARTIAL** |
| AD-07 | Unsupported language/profile | Stop, say unsupported, do not mark pass | Java injection proof fails closed; `GOV-002` fail; no Java enforcer | **PASS** |
| AD-08 | No obvious module boundaries | Report no units, block baseline/adoption, ask for human map | 0 units but exit 0; warnings only; next steps suggest proceeding | **FAIL (unsafe readiness)** |
| AD-09 | Existing architecture is inconsistent | Report contradictions and avoid forcing one map | No reconciliation; unit heuristic may hide inconsistency | **FAIL / NOT TESTED** |
| AD-10 | Known violation produces zero findings | Inject a controlled violation or prove detection; never call clean | `inject_violation` proves L001/D001; 8/9 benchmark zero-finding repos proven; other rules not injection-proven | **PASS (limited to L001/D001)** |
| AD-11 | Developer requests an unjustified exception | Require owner, reason, scope, fingerprint, expiry, review; reject broad waiver | `test_waiver_fingerprints`: fingerprint-less waiver suppresses nothing, produces G001; exact waiver suppresses one | **PASS** |
| AD-12 | AI agent asked to bypass architectural constraints | Refuse, explain rule, offer fix or explicit waiver; no silent suppression | Hard rules 3–4/8–9 and stop conditions; no automated adversarial test; agent could still comply under pressure | **PARTIAL** |
| AD-13 | Large restructuring proposed without justification | Require evidence, smallest boundary, diff budget, rollback, owner approval | “Never rewrite” and smallest-boundary rules; no diff budget or approval gate; 16-unit proposal can over-split | **FAIL / PARTIAL** |
| AD-14 | More than 16 candidate modules | Propose all or report omitted paths; stop if incomplete | Silent `units[:16]`; `TGT-005` warns; omitted modules unnamed; exit 0 | **FAIL** |
| AD-15 | Repository has source but no config and no identified units | Treat as discovery failure, not greenfield or ready | Mode `brownfield`, 0 units, exit 0 | **FAIL** |
| AD-16 | Existing service topology (`services/<Service>`) | Recognize service profile, require topology manifest, use per-layer contracts | Skill has no service-profile path; directory heuristic may treat service dirs as implementation units | **FAIL / NOT SUPPORTED** |
| AD-17 | Library in Python/Go with public API | Recognize no library profile support; do not silently report L003 leaks as defects without explanation | No profile support; benchmark 30 valid choices; skill says profile optional but no stop for unsupported language | **PARTIAL** |
| AD-18 | Config excludes out-of-scope files with multi-segment paths | Correctly exclude without admitting G005 noise; report scope | `test_exclusions` covers literal and glob; tRPC benchmark required manual `/**` correction; no general test | **PARTIAL** |

## Detailed failures

### AD-01/AD-02 — Misleading structure and docs

A source-bearing repository can contain a `README.md` describing modules that do not exist
as directories. The preflight scans source extensions and candidate roots; it never reads
documentation. In the controlled fixture, it proposed zero units for the only source file
and exited `0`. The output warns about coverage but does not say “the documentation and the
tree disagree” or “the heuristic failed.”

This violates C2's requirement to distinguish observed facts from inferred intent. The
agent could proceed with a hand-made map that contradicts the README, or trust the README
and create empty units. Neither is safe without a human decision.

### AD-08/AD-15 — Zero-unit readiness

The preflight's exit code is `0` when there are no proposed units. The skill's stop
conditions key off exit 1 and specific failures, not “no boundaries.” The warnings are
visible, but they do not prevent the baseline step. A baseline over zero units is exactly
the false-pass condition the skill claims to reject.

**Resolved in 1.2.2:** `preflight.py` exits `1` with `TGT-004` failed when a source-bearing
repository has no proposed units, and `test_preflight_discovery.py` pins the behavior.
`TGT-005` remains a warning because a human may still choose a coarser map.

### AD-14 — 16-unit truncation

The proposal cap was a real behavior, not a hypothetical. With 18 module directories, the
output contained only `mod01`–`mod16`, and the omitted paths were not reported. **Resolved in
1.2.2:** the cap is removed; the same fixture now proposes all 18, pinned by
`test_preflight_discovery.py`.

### AD-13 — Large restructuring

The skill says “never rewrite” and “smallest boundary,” which is good. It does not require a
diff budget, a rollback plan, or an owner-approved plan before edits. A 16-unit proposal
can encourage a large mechanical split. In a real adoption, the first slice should be
bounded (the 20-brownfield playbook suggests <400 changed lines, but the skill does not make
it a gate).

### AD-12 — Bypass pressure

The hard rules are clear: no invented IDs, no editing the catalog, no disabling a rule, no
unowned waiver, no applying without an owner. But the skill is an instruction set, not a
policy engine. There is no adversarial test that asks the agent to bypass a rule and checks
that it refuses. This is a process limitation; disclose it.

## Test coverage gaps

| Gap | Why it matters |
|---|---|
| No automated misleading-doc fixture | The agent can trust stale docs over source |
| ~~No zero-unit blocker test~~ | Covered by `test_preflight_discovery` |
| ~~No >16-unit truncation test~~ | Covered by `test_preflight_discovery` |
| No service-profile adversarial fixture | Default architecture is untested |
| No library Python/Go fixture | Public API false positives |
| No large-restructuring approval test | The agent can over-edit |
| No bypass-pressure evaluation | Hard rules are not behaviorally verified |
| No independent evaluator | Results are self-assessed |

## Adversarial disposition

**PARTIAL.** The skill passes the tests it was designed for: exact waivers, library profile
classification, unsupported Java, malformed output, and controlled violation proof. The
discovery-safety failures (zero-unit readiness, 16-unit truncation) are fixed and
regression-tested. The service-profile scenario still has no workflow — only an explicit
stop — and no real application pilot exists.

## Recommended hardening

1. ~~Make zero proposed units a blocker on any source-bearing repository.~~ Done.
2. ~~Remove the 16-unit cap.~~ Done; the 50k walk cap is still unreported.
3. Add a `docs/`/ADR reconciliation step with observed vs stated boundaries.
4. Add service-topology and library-profile playbooks, or explicit `NOT SUPPORTED` stops.
5. Add a diff-budget/approval gate for the first slice.
6. Add an adversarial prompt test for bypass pressure.
7. Add a separate verifier role or a second-pass checklist; disclose that it is not
   independent.
