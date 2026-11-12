# WS-01: Product language and documentation

**Outcome:** a reader understands what ACIMA does, why it matters, what will happen next and what decisions are theirs without knowing the internal implementation.

**Depends on:** WS-00 product and adoption experience contract.

## Owned files

- PRODUCT.md
- README.md
- docs/commands.md
- docs/start/quickstart.md
- existing top-level product/terminology Markdown identified during discovery
- new terminology cross-reference only if necessary

Do not edit skills/acima-adoption, conformance Python, tools/acima.py, examples language enforcers, DESIGN.md or report assets.

## Objective

Rewrite and organize the product-facing English so that it communicates ACIMA from the product promise down to the user's next action. It must remain consistent with the normative standard, technical-preview limitations and the shared experience contract.

## Required work

1. Inspect the owned files and trace every statement to actual product capability or current behaviour.
2. Establish one clear explanation of ACIMA, its primary user, its value and its limits.
3. Use a consistent product vocabulary for module, module map, contract, assessment, finding, requirement disposition, approval, baseline, waiver, conformance and adoption.
4. Explain the five adoption phases using the shared phase contract: purpose, ACIMA does, you see, you decide, done when, next.
5. Explain guided and automated adoption with the same evidence, ownership and authorization guarantees. Do not imply the automated mode can approve boundaries or authorize unseen changes.
6. Explain L1, L2 and L3 through practical outcomes before naming the levels. The user must not be asked to select a level before assessment.
7. Explain what happens on first use, resumption, missing map, incomplete evidence, unsupported language, declined work and partial approval.
8. Make CLI command documentation task-oriented. For each command, explain when to use it, what it reads or writes, what it guarantees, what it does not prove and the expected next action.
9. Keep optional artefacts optional. Do not add marketing claims, user testimonials, pricing, hosted capabilities, scores or guarantees unsupported by PRODUCT.md.
10. Keep detailed technical command arguments available, but do not make them the first explanation presented to a reader.

## Writing rules

- Prefer plain, direct English and short active sentences.
- Lead with intent and consequence, then explain the mechanism.
- Use one name for one concept. Do not alternate between synonyms for variety.
- Explain an internal term before relying on it.
- Keep rule IDs and JSON property names in technical reference sections, not as user-facing explanations.
- Use MUST/MUST NOT only for binding requirements, SHOULD for recommendations and MAY for optional choices.
- Avoid generic filler, repeated disclaimers, abstract slogans and vague phrases such as "ensure proper architecture".
- Never remove an inconvenient limitation to make the prose sound cleaner.

## Acceptance

- A new staff engineer can explain ACIMA's purpose in one paragraph after reading README.md.
- A new user can identify the first step and understand the phases without reading the adoption skill.
- The language for guided and automated mode matches WS-00 and preserves explicit approval.
- Product capability claims match the current code and evidence.
- The quickstart and command reference do not imply that any command grants write authority.
- The links and reading order are coherent.
- No behavior, standard requirement or safety guarantee was weakened.

## Handoff

Return:
- changed file list and why each needed change;
- a brief vocabulary table showing old ambiguity → selected term → intended meaning;
- any contradiction found between product docs and current behavior;
- links to relevant tests or documentation checks actually run;
- unresolved content decisions for the integrator.
