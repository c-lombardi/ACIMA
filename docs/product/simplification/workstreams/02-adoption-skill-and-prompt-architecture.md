# WS-02: Adoption skill and prompt architecture

**Outcome:** an agent can start, assess, guide or automate adoption through a small, clear set of instructions and phase-specific references without losing any current safety or evidence requirement.

**Depends on:** WS-00 product and adoption experience contract.

## Owned files

- skills/acima-adoption/SKILL.md
- skills/acima-adoption/manifest.json
- all Markdown under skills/acima-adoption/references/

Do not edit skills/acima-adoption/scripts, assets, vendor copies, conformance Python, tools/acima.py, PRODUCT.md, README.md or report design files.

## Objective

Simplify the agent's instructions, not the product's guarantees. The skill is the agent's entry point and workflow controller. It must state intent, the phase sequence, authority boundaries and routing clearly. Procedural detail belongs in one authoritative reference that is loaded only when relevant.

## Required work

1. Read the full current skill, every existing reference, the manifest and the current workflow/report implementation.
2. Identify duplicate instructions, contradictions, ambiguous terms, overlong sections, missing transitions and details that are difficult for an agent to apply.
3. Keep the entry skill focused on:
   - what ACIMA does and who it serves;
   - first-use and resume behaviour;
   - the two adoption modes;
   - the canonical phase sequence;
   - non-negotiable safety/evidence guarantees;
   - routing to the correct detailed reference.
4. Give each reference one clear responsibility. Consolidate repeated material only when the authoritative owner is obvious. Avoid a new general-purpose reference that becomes another encyclopedia.
5. Use a consistent procedural pattern in phase references: purpose, prerequisites, actions, user-visible output, owner decision, completion evidence, next action, stop conditions.
6. Use consistent terms, active voice, explicit actors and concise instructions. Explain what an internal field or identifier means rather than showing its code as the explanation.
7. Make guided and automated workflows visibly different in checkpoint cadence while identical in assessment quality, evidence and approval authority.
8. Preserve the complete 56-rule review as the first assessment gate. The skill must not recommend adoption or create a decision-ready report until every rule has a valid evidence-backed disposition.
9. Preserve the behavior for missing/incomplete module maps: generate evidence-backed candidates, continue independent qualitative review, require explicit ownership approval, and block only genuinely dependent checks.
10. Preserve the mandatory six-page HTML report and presentation checkpoint, exact digest review, approval provenance, target freshness and exact path/scope authorization.
11. Preserve distinct decisions for CI integration, adoption notifications, agent guidance, remediation, branch changes and optional artefacts wherever required by the current skill.
12. Preserve no-write-before-consent, no automatic inferred ownership, no silent scope expansion, no blanket full-automation consent and separate commit/push/merge/release approval.
13. Preserve accurate handoff and conformance claims, human evidence, unsupported language handling, baseline/waiver integrity, no synthetic health score and technical-preview limits.
14. Add a small routing index: when the agent should load each reference and what question it answers.
15. Update the manifest/version consistently with the repository's versioning practice. Do not change the normative standard or catalog as part of this work.

## Prompt-engineering rules

- Instructions should be imperative and testable, not aspirational.
- Each instruction should have one primary action.
- State actor, trigger, input, output and stop condition where relevant.
- Separate user-facing wording from machine-facing commands and field names.
- Do not ask an LLM to "remember" a safety requirement buried in an unrelated section; state critical gates at the workflow decision where they apply and link to the detailed source.
- Avoid repeating full rule text. Reuse the canonical reference and link to it.
- Do not invent generic agents, tools, hooks, skills or commands that are not present in the repository.

## Acceptance

- The first-use path can be followed without the user knowing ACIMA commands or internal IDs.
- The agent can determine the next step from the current evidence/state, not from an assumed universal checklist.
- Guided and automated routes cannot bypass the same evidence, map, report, consent or verification gates.
- Every existing normative requirement in the current skill and references is either preserved in one authoritative location or explicitly identified for product-owner resolution.
- No duplicated or contradictory instruction remains for the same decision.
- The top-level skill is materially easier to scan; detailed instructions are discoverable through progressive disclosure.
- The skill bundle can be regenerated from canonical sources and passes its integrity check.

## Handoff

Return:
- final skill/reference map showing one responsibility per file;
- a traceability matrix from pre-existing requirements to their new authoritative locations;
- duplicate and contradiction resolutions;
- version changes and bundle commands;
- exact tests and results;
- any requirements that could not be preserved without a product decision.
