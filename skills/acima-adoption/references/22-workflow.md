# 22 Workflow


## Canonical workflow

One order, everywhere. Preflight establishes that this skill matches the catalog on disk and
classifies the target; the assessment establishes fit. Neither writes to the target.

| Phase | Purpose | Command | Ends when |
|---|---|---|---|
| 1. Assess | preflight, all 55 qualitative dispositions, then read-only fit and deterministic checks where possible | `preflight.py --project <target>`, `validate-review`, then `acima.py assess --root <target> --review <review.json>` | 55/55 valid dispositions, unresolved states explicit, and deterministic limits recorded |
| 2. Propose | the decision document | fill `../assets/adoption-proposal.md` | a recommendation, exact paths, one question |
| 3. Authorize | explicit, scope-specific approval | none | an unambiguous yes to that proposal |
| 4. Implement | only the approved scope | the approved commands | the named files exist and measure |
| 5. Verify | prove what changed and what did not | the enforcer and `acima.py claim` | artefacts support every claim, limits named |

Do not run the same expensive analysis twice for two phases: reuse the assessment's run for the
proposal, and the implementation's run for the handoff. `status` reports which phase is evidenced.

**Phase 1 — Assessment.** Preflight runs first, always: it compares `rules.json` with the pinned SHA-256
and rule ids (`SKL-002`/`SKL-003`), classifies `greenfield`, `brownfield` or `adopting`, and lists
blockers. Exit `1` blocks adoption and implementation until its causes are resolved, but it does
not automatically block independent qualitative review. Stop only for skill-integrity, invalid-target,
ambiguous-classification or unsupported-mode blockers. If the only blockers are missing candidate
units, uncovered source files or unavailable deterministic tooling, continue the complete 55-rule
read-only qualitative review and keep affected deterministic claims blocked. Then assess six dimensions
independently: technical
compatibility, architectural substance, existing enforcement, incremental value, adoption cost and
practical applicability. Choose one outcome: `RECOMMENDED`, `RECOMMENDED_WITH_LIMITATIONS`,
`NOT_RECOMMENDED`, `INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`. A clean report is not a
recommendation: a utility with no meaningful boundaries, or a system whose existing checks already
cover the guarantee, is a `NOT_RECOMMENDED` only after the 55-rule review establishes that ACIMA adds no meaningful value.
Until then, the outcome is `INSUFFICIENT_EVIDENCE`, even when preliminary discovery suggests a
small utility or existing enforcement. Explain the target software, discovered boundaries, existing
enforcement, what ACIMA requires and does not require, cost, confidence and
unresolved questions. Record one compatibility outcome — compatible, compatible with adaptation,
incompatible or insufficient evidence — against the applicable requirements. Distinguish an
implementation difference from a genuine conflict, and never treat missing evidence as
incompatibility. Name any requirement that is stricter than the team's current practice and why it
exists. No config, waivers, baselines, CI, docs or source changes. `NEEDS_UNIT_MAP` blocks deterministic
conformance measurement only; it does not block qualitative architectural discovery or assessment.
Never stop at a missing map. Automatic discovery now goes further: it produces an evidence-backed
module-map proposal with candidate responsibilities, contracts, observed dependencies, unassigned
source, quality observations, recommendations and owner decisions. Continue with that provisional,
explicitly unapproved hypothesis; inspect the actual source and all relevant architecture evidence;
mark unresolved ownership as uncertain. A partial map preserves existing units and proposes only
missing ownership. `NEEDS_UNIT_MAP` means deterministic checks did not run, never that independent
qualitative review stopped or that the architecture is clean. After the owner accepts or modifies the
proposed boundaries and decisions, write the approved unit map only within the approved scope; then
run the previously blocked ownership-dependent checks. If approval is deferred, preserve completed
independent reviews and name the outstanding decisions.

A comprehensive assessment is mandatory before any adoption recommendation or decision-ready
report. A user may request a narrower read-only review, but label it as limited scope and do not
present it as an adoption assessment or recommendation. Read
[25-comprehensive-assessment](25-comprehensive-assessment.md). For adoption, assess all 55 current
catalog requirements across L1, L2 and L3, independently of the level recommended for adoption.
Keep the selected adoption/conformance level separate from the comprehensive architectural review.
The CLI's `comprehensiveRuleReview` is a checklist, not evidence that those rules were reviewed.
Do not issue a recommendation before the 55-rule review has passed `validate-review`. A missing
module map or preflight candidate-unit failure blocks only dependent deterministic checks and owner
decisions, not the independent qualitative review. Inspect the repository and record evidence/status
for each requirement. A deterministic check that
cannot run must not be silently replaced by a pass; a qualitative review is also not a conformance
claim or accepted manual evidence unless the formal evidence requirements are met.
Produce a structured qualitative-review JSON artefact with exactly one evidence-backed disposition
for every current catalog rule. Validate it with the vendored `acima.py validate-review` command.
The artefact must pin the current catalog SHA-256 and include reviewer/date metadata, a rationale,
and repository-relative evidence for every rule. File evidence must cite valid line ranges and an
exact quote from those lines. Missing, duplicate, unknown, stale-catalog, fabricated-quote,
invalid-path, out-of-range evidence, duplicate rationale or copy-pasted evidence prevents coverage
completion. `insufficient_evidence` is a valid explicit disposition for coverage, but remains
unresolved and blocks an adoption recommendation. The overall assessment is complete only when all
55 rules validate with no unresolved dispositions, the ACIMA unit map is declared, and deterministic
assessment succeeds. Completion is not conformance; gaps remain gaps.
Attach the validated artefact using `assess --review <review-json>` and report its validator result.

**Phase 2 — Proposal.** Present [the proposal](../assets/adoption-proposal.md) as a decision document:
recommendation first, then the compatibility outcome and evidence, requirements already satisfied,
the smallest useful scope, exact paths with required/conditional/optional status, stricter
constraints and tradeoffs, and the one approval question. Do not write files "so the user can see
them".

**Phase 3 — Explicit authorization.** Approval covers the listed scope only — the named paths,
level and changes. Partial approval
is supported: implement exactly what was approved and name the capability that stays unavailable.
Wait for an unambiguous yes to that proposal before touching a path. Interest, silence, "looks good"
about the diagnosis, or a request to see files is not approval.
Approval to change files never authorizes merge, release, publication or external systems.

**Phase 4 — Approved implementation.** Only approved changes. A new path, level, dependency or enforcement
mechanism outside the approved list stops work for a new decision.

**Phase 5 — Verification and handoff.** Verify with a run artefact, not intent, and report what is
proven separately from what is not.

| Action | Approval |
|---|---|
| Inspect, read, run read-only analysis, prepare a proposal | not needed |
| Create config, baseline, waivers, tooling, docs or CI | required, named paths |
| Modify source, build configuration or existing docs | required, named paths |
| Merge, publish or release, or change an external system | separate, explicit |

Full boundary and artifact matrix: [15-consent-and-scope](15-consent-and-scope.md).



## Guided and full automation

Before Phase 3, explicitly ask for **guided adoption** or **full automation**. Guided keeps the
five approval gates and waits for a scoped map/scope decision. Full automation uses the persisted
`.acima/adoption-workflow.json` authorization to implement the generated enforcement, run positive
and controlled-negative checks, integrate an existing CI provider and verify the result. It still
cannot deploy, release, commit, push, modify another repository or expose secrets. Unsupported or
ambiguous ownership pauses only that decision; completed independent work and artifacts remain.
Every stage must produce its artifact and next action, and a changed repository revision makes the
relevant artifacts stale. See [13-adoption-orchestration](13-adoption-orchestration.md).

## Load only the detail needed for this phase

- Repository inventory and architecture evidence: [45-discovery](45-discovery.md).
- User communication and approval wording: [42-communication-and-interaction](42-communication-and-interaction.md) and [35-user-transparency](35-user-transparency.md).
- Status, evidence and completion decisions: [55-status-and-evidence](55-status-and-evidence.md).
- Proposal and HTML report generation: [75-proposals-and-deliverables](75-proposals-and-deliverables.md) and [90-html-outcome-reports](90-html-outcome-reports.md).
- Commands: [65-commands-and-context](65-commands-and-context.md), only after confirming the active checkout paths.

Do not load every reference at startup. Load the phase-specific reference immediately before performing that phase; retain the core consent and honesty rules throughout.
