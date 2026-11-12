# WS-00: Product and adoption experience contract

**Role:** product experience architect and editor.

**Purpose:** establish the shared product-level truth that all implementation workstreams use. This is the first gate. It is not permission to rewrite the standard or alter adoption safety rules.

## Product outcome

Make ACIMA easy to understand and safe to adopt in an existing codebase. The owner should understand the recommendation, the evidence, the exact proposed changes, the next decision and the consequences of approval without learning internal ACIMA identifiers.

Use this plain-language product explanation as the starting point:

> ACIMA helps a team make its software module boundaries explicit and enforceable. It assesses the existing code without changing it, explains what it found, proposes the smallest useful improvements, and waits for the owner to approve the exact work before making changes. It then verifies the result and reports what remains unproven.

## Audience and decisions

Primary human evaluator: staff engineer or architect who understands the product and owns or evaluates the repository.

Secondary decision-maker: engineering leader considering value, cost, operational risk and maintenance.

The user makes these decisions:
- whether the product is a fit;
- which proposed ownership boundaries are real;
- whether the proposed changes and level are appropriate;
- which exact paths and stages are approved;
- whether separate CI, adoption notification or optional guidance work is approved;
- whether no, selected or all recommended source corrections should be applied.

ACIMA performs repository investigation, requirement evaluation, evidence reconciliation, proposal preparation, deterministic execution and approved implementation.

## Shared phase contract

Use the same phase names and the same explanation structure in the skill, CLI, documentation and report.

For every phase, define:
1. **Purpose**
2. **ACIMA does**
3. **You see**
4. **You decide**
5. **Done when**
6. **Next**

### Start

- Identify the actual target repository from the active workspace or ask for one path/link. Do not ask again when the path is already known.
- When the user has not selected a mode in this engagement, ask one plain question: **"Would you prefer guided adoption, with review checkpoints as we go, or automated adoption, where I prepare the complete proposal first and then carry out the stages you approve?"**
- Preserve an explicit existing choice when resuming.
- Do not ask the user to choose a level or learn ACIMA terminology before assessment.

### Phase 1: Assess

- Read-only repository discovery and compatibility assessment.
- Review all 56 current requirements individually and record evidence-backed dispositions.
- Inspect current architecture, existing enforcement, module ownership and dependencies.
- Run only supported deterministic checks with their real prerequisites.
- If an authoritative map is absent or incomplete, generate an evidence-backed candidate proposal while continuing all independent qualitative review.
- Do not present an adoption recommendation or decision-ready report when review coverage is incomplete.
- Do not call empty findings a pass. Do not call the qualitative review proof of semantic correctness.

**Done when:** every current requirement has a valid recorded disposition and the assessment truthfully describes unresolved, unsupported and ownership-blocked work.

### Phase 2: Explain and propose

- Explain fit and recommendation in terms of practical consequences.
- Explain the level before its internal name.
- Identify current strengths and missing capabilities.
- Explain benefits as available today, achievable through adoption, requiring additional work or not applicable.
- Prepare candidate ownership map if necessary, exact proposed paths, exclusions, prerequisites, risks, CI options and the required report.
- Generate and validate all six report pages.
- Explain what ACIMA will preserve and what it does not prove.

**Done when:** every proposal statement traces to the assessment or is explicitly marked as a recommendation, assumption or unknown; report validation succeeds.

### Phase 3: Review and authorize

- Present the exact six-page report and make its pages accessible.
- Ask the owner to inspect the recommendation, map, findings, file impact, plan and evidence.
- Capture per-boundary ownership decisions and any required map modifications.
- Capture the reviewer and exact report/proposal/repository identity.
- Capture exact paths, stages and level the owner approves. Partial approval is valid.
- Keep CI integration, adoption notifications and remediation separate where the active skill requires separate decisions.
- A report view or acknowledgement is not implementation permission.

**Done when:** the user has explicitly approved the exact scope, and the approval receipt matches the current report, proposal and repository state.

### Phase 4: Implement

- Execute only approved work.
- Preserve existing architecture and user-authored instructions.
- Validate each logical stage before moving to the next.
- Stop when the implementation requires a new path, dependency, boundary or decision.
- Do not commit, push, merge, deploy or release without its own explicit authorization.

**Done when:** every approved stage either completed and passed its stated checks or has a precise blocked/failed/deferred status.

### Phase 5: Verify and hand off

- Run fresh checks against the current repository state.
- Verify the configured local enforcer, known-good fixture, controlled violation and applicable CI evidence separately.
- Reconcile current repository, commit, catalog, configuration, source inventory and evidence.
- Calculate conformance claims using the claim engine. Never infer full conformance from a completed workflow.
- Explain what changed, what passed, what did not run, what remains unresolved and how to continue.

**Done when:** the handoff matches actual evidence and makes remaining uncertainty visible.

## Guided versus automated contract

The two modes share all phase outcomes and product guarantees. They differ only in when and how review is grouped.

| Concern | Guided | Automated |
|---|---|---|
| Assessment | Same complete, read-only assessment. | Same complete, read-only assessment. |
| Ownership | Individual review checkpoint before ownership-dependent checks. | Candidate ownership is included in the consolidated package; user still accepts/modifies/rejects each ownership decision needed for implementation. |
| Proposal | Review after assessment and map decisions. | Complete proposal prepared before one consolidated review. |
| Scope | User authorizes selected paths/stages at the relevant checkpoints. | User selects the exact stages and paths from the consolidated proposal. |
| Implementation | ACIMA executes one approved stage at a time with visible checkpoints. | ACIMA automatically executes the selected approved stages and validates them as it goes. |
| Authority | Human approval remains mandatory. | Human approval remains mandatory. |

Automated preparation never approves an inferred boundary, authorizes an unseen file, or permits scope expansion.

## Communication rules

- Use the term **module** for the architectural ownership concept; explain the configuration representation when it matters.
- Use **module map** in user-facing prose. Keep JSON property names and rule IDs for technical detail only.
- Describe findings as what the code does and why it matters, not as a bare rule ID.
- One user-facing status view exposes complete, in progress, blocked, deferred, declined, not applicable and failed states distinctly.
- Give the user one clear next action with its prerequisite and reason.
- Do not use a checklist as a replacement for the explanation.
- Never claim the agent will follow generated instructions or that report presence proves a user saw it.

## Authoritative evidence and constraints

The contract is derived from PRODUCT.md, the current skills/acima-adoption/SKILL.md, its references, DESIGN.md, the current 56-rule catalog and existing conformance tests. When a detail differs, preserve the normative standard and existing safety guarantee; record a discrepancy rather than silently changing it.

## Acceptance

- A new reader can describe ACIMA and the adoption flow without knowing rule IDs.
- The five phases have clear purpose, visible output, user decisions, completion condition and next action.
- Guided and automated mode descriptions differ only in review cadence/grouping, not in evidence quality or authorization.
- All non-negotiable requirements in the parent simplification plan remain present.
- No new product feature, service, score, organizational artifact or automatic rewrite is invented.
