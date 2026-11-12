# WS-04: Report model and reader experience

**Outcome:** the six-page report reads as one coherent decision document, communicates the same product journey as the skill and CLI, and never says more than its evidence proves.

**Depends on:** WS-00 product and adoption experience contract.

## Owned files

- DESIGN.md
- skills/acima-adoption/scripts/render_report.py
- skills/acima-adoption/assets/report.schema.json
- skills/acima-adoption/assets/report-template.css
- conformance/test_html_report.py

Do not edit the skill entry point/references, adoption workflow Python, CLI or language enforcers.

## Objective

Keep the six-page offline report as ACIMA's primary designed surface. Simplify information hierarchy, section copy and reader navigation without losing any current report data, validation or accessibility guarantee.

## Required reading path

- **Overview:** Should this repository adopt ACIMA, and what should the owner do next?
- **Proposal:** What would change, what value would it provide and what are the tradeoffs?
- **Findings:** What is already working, what needs attention and why?
- **Files:** Which files are only inspected and which are actually proposed to change?
- **Plan:** What happens in what order, what is the current state and who must decide?
- **Evidence:** What did the assessment check, what supports each conclusion and what remains unknown?

Every page must answer its question without requiring the reader to open another page, while clearly linking to useful detail.

## Required work

1. Inspect the current renderer, schema, CSS, tests and DESIGN.md. Treat the code as current behaviour and correct the design record if it disagrees.
2. Define one consistent content hierarchy: decision and plain-language meaning first; consequence and action next; evidence and internal traceability on demand.
3. Preserve all distinct states: observed, inferred, recommended, proposed, approved, implemented, verified, blocked, unknown, unsupported, deferred and not applicable.
4. Preserve the distinction between requirement dispositions and grouped findings. Link them only through explicit references.
5. Preserve the full 56-rule review, catalog fingerprint, evidence paths, line ranges, quotes and coverage validation for decision-ready schema 1.1 reports.
6. Preserve current, exact file-impact operations: inspect, create, modify, delete, no-change/preserve as supported. Never turn an inspected evidence file into a proposed modification.
7. Make the existing-vs-proposed module map distinction apparent. Show the actual human-readable units and their roles; do not interpret an absent discovery proposal as zero modules.
8. Make fit, recommendation, benefits, costs, risks, existing architecture, CI status, agent guidance, adoption mode, stage progress, owner decisions, preservation and verification explicit where data is supplied.
9. Use empty-state copy that says whether the data is unknown, not assessed, blocked, not applicable or genuinely unnecessary. Empty arrays are not explanations.
10. Keep the output offline and static with no runtime service or network dependency.
11. Preserve the current WCAG 2.2 AA target, semantic headings/tables, keyboard access, visible focus, contrast, reduced motion, forced colors, responsive reflow, print and offline behaviour.
12. Keep the report free of secrets, credentials, personal data and unnecessary source excerpts.

## Reader-first copy rules

- Titles state the question or outcome, not the internal subsystem.
- Use short sentences, active verbs and human-readable names.
- Never ask the user to interpret an internal rule ID to understand a finding.
- State what is known, how it was observed, why it matters, what is recommended and how confidence is limited.
- An expected outcome is not a delivered result. A configured gate is not an observed CI run. A complete report is not approval.
- Keep technical identifiers, evidence references and exact paths available in a disclosure or evidence section.

## Acceptance

- The six pages have clear distinct purposes and one consistent reading path.
- A reader can identify the recommendation, exact proposed changes, user decisions and next action without knowing the codebase.
- The report accurately separates existing, proposed, approved, implemented and verified.
- No empty findings list is styled as a conformance pass.
- Schema validation still rejects missing, stale or inconsistent evidence and counts.
- No report field is invented to fill a blank section.
- Existing accessibility tests pass and the manual browser/screen-reader checks remain visible as manual release checks.

## Handoff

Return:
- six-page information architecture and copy pattern;
- field-to-page map for the report schema;
- list of any schema compatibility changes;
- accessibility changes and manual checks;
- focused renderer test results;
- remaining content that depends on missing assessment data.
