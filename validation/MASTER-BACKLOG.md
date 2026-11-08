# Master Backlog

**Status:** IN PROGRESS — internal review only
**Purpose:** One prioritized queue with domain ownership, evidence, dependencies and
validation. Do not collapse architecture, enforcement, adoption and product work into a
single “fix ACIMA” item.

**Priority:** P0 blocks a truthful release claim; P1 blocks real adoption; P2 improves
quality/scale. **Status:** OPEN, IN PROGRESS, BLOCKED, DONE, DEFERRED.

## P0 — release-blocking

| ID | Domain | Item | Evidence | Correct layer | Dependencies | Validation | Status |
|---|---|---|---|---|---|---|---|
| P0-01 | Architecture + adoption | Define FULL CONFORMANCE vs PARTIAL ASSESSMENT; no full claim with required `executed:false` | Preface/P8 vs coverage; skill definition | Architecture claim + skill text | AD-01/AD-11 | Doc test; run report refuses full claim | DONE — `conformance/acima_claim.py`, `acima claim`, `test_claim_model.py`; L1/L2/L3 counts and exit codes pinned |
| P0-02 | Architecture | Add explicit base/service mode and precedence for P2.1/P3.5 vs P11/P12 | C-03/C-04; no mode field | Standard/config | AD-02/AD-03 | Schema test; both modes | DONE — `mode` selector + precedence documented and tested in `test_mode_precedence.py`, `test_topology.py` |
| P0-03 | Architecture + enforcement | Resolve waiver fingerprint contradiction in §7.5/schema/catalog; require one canonical field set | C-05; docs/code mismatch | Standard + enforcement + skill | AD-05 | Schema/test; scope-only waiver fails | DONE — §7.2, `rules.json` findingSchema/G001 and §7.5 now require `fingerprint`; doc test pins it |
| P0-04 | Adoption | Fix stale brownfield/waiver guidance in `00`, `20`, `60`, glossary | 10-file threshold; `(rule,unit)` claims | Skill docs | None | Documentation regression test | DONE — corrected in skill 1.2.2; `test_documentation_contract` |
| P0-05 | Adoption | Make zero proposed units a blocker on source-bearing repos | Controlled fixture exits 0 with 0 units | Preflight + skill | None | New preflight test | DONE — `TGT-004` fail/exit 1; `test_preflight_discovery` |
| P0-06 | Adoption | Remove/report 16-unit truncation and 50k walk cap | Controlled 18-module fixture returns 16; no omitted paths | Preflight | None | New preflight test | IN PROGRESS — 16-unit cap removed and tested; 50k walk cap still unreported (R-30) |
| P0-07 | Product | Correct four-vs-six rule docs and self-certification count | `docs/rules/index`, `08` “24 of 24” | Docs | P0-01 | Documentation test | DONE — docs corrected; `test_documentation_contract` |
| P0-08 | Architecture | Decide six non-executed rules: implement, manual evidence, or remove from levels | C-01/C-02 | Architecture decision | AD-11 | Claim model + evidence test | DONE — kept normative, marked `automation: manual`, full claim requires `.acima/manual-evidence.json`; tests pin the six |
| P0-09 | Product | Stop `docs/status`/README from saying “implemented and verified” without scope | Status page; six unexecuted | Product docs | P0-01/P0-08 | Claim audit | DONE — status page states 23 automated / 6 manual and names the gap |
| P0-10 | Adoption | Add service-topology workflow or explicit `NOT SUPPORTED` stop | Skill has no topology/P10–P13 path | Skill + preflight | AD-10 | Adversarial fixture | DONE (stop only) — explicit `NOT SUPPORTED`; no workflow |
| P0-11 | Adoption | Add library-profile workflow or explicit unsupported stop for Python/Go | Hard rule only; 30 valid choices | Skill + profile | None | Fixture per language | DONE (stop only) — explicit Python/Go library stop; TS/.NET workflow unchanged |
| P0-12 | Verification | Obtain independent review of architecture, classifications, six manual rules | No independent reviewer | Process | External | Review record | BLOCKED |

## P1 — required for credible adoption

| ID | Domain | Item | Evidence | Correct layer | Dependencies | Validation | Status |
|---|---|---|---|---|---|---|---|
| P1-01 | Architecture | Resolve P9.5 (version metadata + rule, or downgrade) | C-06 | Standard | AD-06 | Review/evidence | DONE — explicitly advisory in Draft 1; no false enforcement claim |
| P1-02 | Architecture | Define runtime evidence for L3 autonomy (DB grants, config, release) | A001 static only; P7.6 no rule | Standard + enforcement | AD-08/AD-09 | Runtime fixture/evidence | OPEN |
| P1-03 | Enforcement | Java enforcer, or formally remove Java from supported claims | 3 benchmark repos blocked | Enforcement | Language profile | Java gallery/CI | OPEN |
| P1-04 | Enforcement | Non-.NET service-topology fixture + language adapter | `test_topology` .NET-only | Enforcement | AD-10 | TS/Go/Python fixture | OPEN |
| P1-05 | Enforcement | Universal large-output tests for Python/Go/.NET | TS-only 65K test | Enforcement | None | Tests >64K each | OPEN |
| P1-06 | Enforcement | Test severity raise/disable/config permutations (P8.3) | No test | Enforcement | None | Config tests | OPEN |
| P1-07 | Enforcement | Fix D008 duplicate reporting; classify remaining public API | Benchmark 3 duplicates, 30 unclassified | Enforcement/profile | None | Bench rerun | OPEN |
| P1-08 | Adoption | Add docs/ADR reconciliation and observed-vs-inferred report | No docs scan | Skill/preflight | None | Adversarial fixture | OPEN |
| P1-09 | Adoption | Add manual-evidence template for six rules, runtime grants, release independence | Plan template lacks them | Skill | P0-01/P0-08 | Plan fixture | OPEN |
| P1-10 | Adoption | Require target build/test, diff budget, rollback, clean copy before edits | C5 gaps | Skill | None | Pilot checklist | OPEN |
| P1-11 | Adoption | Separate assessment from implementation verification (or disclose same-agent) | No independent verifier | Process | External | Review record | BLOCKED |
| P1-12 | Product | Align README/quickstart/status/product contract with two modes and partial claims | Product docs | Docs | P0-01/P0-02 | Doc test | OPEN |
| P1-13 | Product | Make installation/support boundaries explicit (toolchains, Java, profiles, OS) | Partial docs | Product | P1-03 | Self-service test | OPEN |
| P1-14 | Verification | Run hosted CI and record a real workflow receipt | Unobserved | CI | None | CI run log | BLOCKED |
| P1-15 | Verification | Run a real base-mode application pilot | No application adoption | Adoption | P0/P1 fixes | Pilot evidence | BLOCKED |

## P2 — quality, scale, and evidence

| ID | Domain | Item | Rationale | Status |
|---|---|---|---|---|
| P2-01 | Architecture | Add a tenancy profile or declare multi-tenant out of scope | Applicability gap | OPEN |
| P2-02 | Architecture | Add a full-stack/UI profile or narrow P13.1 | UI semantics not checked | OPEN |
| P2-03 | Architecture | Define shared-platform profile / shared operational concerns | Platform gap | OPEN |
| P2-04 | Enforcement | Deduplicate D008; improve C004/C005/C006 precision | Benchmark noise | OPEN |
| P2-05 | Enforcement | Add non-.NET library profiles or declare unsupported | Python/Go false positives | OPEN |
| P2-06 | Enforcement | Add cancellation/timeout/reproducibility tests | B4 gaps | OPEN |
| P2-07 | Adoption | Add service/library onboarding playbooks | No workflow | OPEN |
| P2-08 | Adoption | Measure time-to-assessment/baseline/gate in pilot | C7 unmeasured | OPEN |
| P2-09 | Product | Replace “architecture health score” absence with clear evidence vocabulary | No score is correct; claim classes missing | OPEN |
| P2-10 | Product | Add a migration guide for base→service mode | Mode ambiguity | OPEN |
| P2-11 | Verification | Re-run benchmark after fixes; preserve old evidence | Historical integrity | DONE (mechanical) — `rw-2026-11-08-03`; 12 assessed, 3 Java blocked; not re-adjudicated |
| P2-12 | Verification | Add independent classification sample | Author bias | BLOCKED |

## Sequencing

1. **P0-01/P0-08 (done):** the claim model and six manual rules are settled and executable.
2. **P0-02/P0-03 (done):** mode precedence and waiver identity are settled and tested.
3. **P0-04–P0-07:** fix the unambiguous documentation/claim errors and add tests.
4. **P0-05/P0-06/P0-10/P0-11:** harden discovery and state unsupported profiles.
5. **P1:** Java/service portability, runtime evidence, real pilot, independent review.
6. **P2:** breadth and quality; do not start these before P0.

## Explicitly not on the backlog

- Optimizing benchmark scores.
- Adding more rules before the six existing rules are resolved.
- Making the skill more autonomous before its safety blockers are fixed.
- Rewriting the architecture to match analyzer behavior.
- Publishing or pushing without authorization.

## Done criteria

An item is DONE only when:

1. the change is in the correct layer;
2. a regression test or evidence artifact exists;
3. the relevant domain report is updated;
4. downstream traceability is checked;
5. the limitation is disclosed;
6. independent review is recorded, or the lack of it is explicit.

Creating a document does not close an item.
