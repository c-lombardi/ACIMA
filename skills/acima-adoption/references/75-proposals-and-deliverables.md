# 75 Proposals And Deliverables


## Proposal: a decision document

Nine sections, in this order: **Recommendation** (`RECOMMENDED`, `RECOMMENDED_WITH_LIMITATIONS`,
`NOT_RECOMMENDED`, `INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`, and why); **Software
discovered**; **What ACIMA adds**; **Expected benefits** grounded in evidence and classified as
available today, achievable through adoption, requiring additional work, or not applicable;
**Recommended scope** (smallest useful, level in plain English, what is excluded and why);
**Proposed changes** (exact paths, purpose, required/conditional/optional, modified files,
dependencies, CI); **Tradeoffs and risks** (maintenance, tooling limits, migration, compatibility,
what ACIMA does not prove); **Next steps** (sequence, what the user sees, decisions); **Approval**
(one question, scope-limited, partial approval allowed).

Recommend; do not turn the proposal into a questionnaire. State the level's practical consequence
before naming L1/L2/L3. Unresolved dispositions follow the same rule: give a decision brief with
plain meaning, evidence gap, recommended option, effort and consequence
([35-user-transparency](35-user-transparency.md)); never ask the owner to classify a rule id.

## Orchestrated deliverables

During the one adoption flow, generate the module-map proposal, adoption proposal,
`acima/evidence/adoption-scope.json`, enforcement record, architecture-test record, CI decision and final
handoff as stage artifacts. The flow presents the map and scope for separate approval; CI and
remediation remain separately approved decisions. Every artifact records its status and every
recommendation has an implementation path or an explicit deferral. A proposal is not an approved
map, a written CI file is not a remote run, and a copied enforcer is not a conformance claim.

The generated adoption report is a stage artifact with an identity of its own: `acima/report/<reportId>/`
holds the six pages, `report.json` and, once the owner answers, `decisions.json`. A regeneration
creates a new report id and directory rather than overwriting a reviewed report. Only `decisions.json`
is meant to be committed, and ingesting it (`acima adoption decisions --from <path>`) records answers
and derives a draft scope; it never substitutes for the approval command.

The final remediation decision produces `acima/evidence/remediation-plan.json` and
`acima/evidence/remediation-result.json`. The plan discloses maturity, affected files, prerequisites,
risk, all recommendations and their readiness; the result records none/selected/all, changed files,
manual or failed items, deferred items, before/after verification and the post-remediation review.
Only deterministic changes are applied; manual recommendations remain explicit work.

Agent guidance is another first-class deliverable: a concise root instruction update or creation plus
`acima/handoff/agent-guidance/agent-architecture-guidance.md`, `enforcement.md`, `judgment-guidance.md`
and `architectural-workflow.md`. Existing user-authored instruction content is preserved. The
proposal and validation record live in `acima/report/agent-guidance-proposal.md` and
`acima/evidence/agent-guidance.json`; the guidance is refreshed after remediation and never claims agent
behavior was empirically guaranteed.

## Module-map proposal and scoped approval

When no sufficient authoritative map exists, the assessment includes an automatic module-map
proposal. Present proposed human-readable module names and responsibilities, observed evidence,
inferred ownership, candidate contracts, observed dependencies, unassigned or ambiguous production
code, quality observations, recommendations with rationale and tradeoffs, and the decisions that
require owner input. Distinguish observed facts, evidence-supported inference, recommendations and
unverified assumptions. Never present a folder, project, package or runtime unit as an approved
module.

The owner may accept the map, accept or modify individual boundaries, accept or reject individual
recommendations, defer decisions, reject the proposal and supply an alternative, or request more
discovery. Explain which decisions are essential before ownership-dependent checks and which are
optional refinements. Approval is explicit and scoped; record proposal identity, reviewer, date and
approval status. Only a complete approved map may be written as the unit contract and used for
ownership-dependent deterministic checks. A partial approval leaves unapproved ownership and its
checks unresolved. Independent qualitative review continues while approval is pending or deferred.



## HTML outcome reports

For comprehensive assessments and adoption proposals, prepare the normalized model in
`assets/report.schema.json` and render the six-page, offline HTML outcome pack with
`scripts/render_report.py`. Include the ACIMA value, recommendation, greenfield/brownfield context,
findings, exact file impact, expected outcomes, phases, owner decisions, coverage and limitations.
Never invent missing facts. Obtain approval for report files written inside the target. See
[90-html-outcome-reports](90-html-outcome-reports.md) for the complete contract.



## Document lifecycle

Build documents only as the work earns them.

| Stage | Deliverable | Written where |
|---|---|---|
| A. Assessment brief | what the app is, what was found, fit, limits, recommendation | conversation, or outside the target |
| B. Proposal | the decision document above | conversation / temporary file |
| C. Implementation guide | steps, commands, files, verification, failure handling | in the approved scope only |
| D. Handoff and developer guide | what changed, what was verified, what remains, how to run and read the gate | approved docs, or the final message |If a document is not approved, deliver its content in the response — that is not a lesser outcome.
