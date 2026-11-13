# Multi-page HTML outcome reports

The HTML report is the primary reader-facing explanation for a comprehensive ACIMA assessment or adoption proposal. It is designed for product owners and engineers who may not know ACIMA or the repository's codebase. The report is generated from a normalized, evidence-grounded model; it is not a new assessment engine and must not invent facts.

## Six pages, six questions

| Page | Immediate question answered |
|---|---|
| `index.html` | Should we adopt ACIMA, and what value would it provide here? |
| `proposal.html` | What would change in the architecture, and what are the benefits and tradeoffs? |
| `findings.html` | What is already good, what did the assessment find, and why does it matter? |
| `files.html` | Exactly which files would be created, modified, removed, or only inspected? |
| `plan.html` | What happens next, in what order, and which decisions need an owner? |
| `evidence.html` | What was actually checked, what remains uncertain, and what supports the conclusions? |

All pages share responsive navigation and an offline stylesheet. `index.html` is the entry point.

The report's visual system is defined locally in `assets/report-template.css`. Do not claim that it
follows an external design skill unless that skill's source is present in the ACIMA checkout and has
actually been consulted. The report is self-contained and has no runtime dependency on an external
service. `report-data.json` preserves the structured input used to generate the pages.

## Adoption path

The proposal page opens with a four-stage path: **No ACIMA**, **Foundation**, **Implemented**, and
**Continuous**. It is a position statement, not a score. The current marker is derived only from the
report's recorded milestones; earlier stages are context, later stages are proposals, and Continuous
is a destination, not a certification. Each stage has a text label so the path does not rely on
colour. When milestones are absent, the page says the position is not recorded instead of inferring
one. Rendering the path never marks assessment, approval, implementation, or continuous operation
complete.

## Owner decision briefs

The Plan page renders each owner decision as a brief, not a rule-id questionnaire: the plain-language
question, context, recommendation, effort, consequence of leaving it open, evidence gap, other
options and what stays blocked. Module ownership, path ownership and scope approval all use the same
shape. Findings remain findings; the renderer labels required fixes as “no owner decision” rather than
asking the owner to accept a classification. The proposal page links to the Plan page instead of
duplicating the decision table.

## Input contract

Use `assets/report.schema.json` as the versioned input contract. The adoption agent prepares the model
from the current repository, standard, catalog, enforcer output, qualitative review, and proposal.
For schema 1.1, the renderer independently validates the original qualitative-review artifact
against the repository and pinned catalog before writing. It rejects incomplete requirement coverage,
fabricated evidence, stale catalog fingerprints and inconsistent report counts.

Every proposed file must have an exact repository-relative path, action (`create`, `modify`, `delete`,
`inspect`, or `no-change`), purpose, expected outcome, and approval or implementation state. Keep the
change inventory distinct from files merely inspected as evidence.

## Greenfield and brownfield

For greenfield, show proposed module ownership, contracts, dependency rules, composition boundary,
initial checks, unresolved design decisions and first deliverables. There may be no findings because
there is no existing implementation; do not call that a pass or conformance.

For brownfield, show existing architectural strengths, confirmed findings, pre-existing baseline,
proposed incremental changes, explicit non-goals, and what adoption leaves untouched. Never imply
that ACIMA requires a rewrite or that a baseline is conformance.

## Truth and coverage

Distinguish existing, proposed, implemented and verified capabilities. Expected outcomes are not
guarantees. Rule-review completeness is separate from semantic correctness. Show actual coverage,
including manual, skipped, unsupported and unresolved checks. If assessment is incomplete, make that
visible on the overview and evidence pages, even when no findings were returned.

Never fill gaps with guessed metrics, estimates, paths, owners, dates or claims. Unknown is a valid
report value. Do not include credentials, tokens, private keys, secrets, personal data, or unnecessary
source-code excerpts in the report model or generated pages. Cite paths, symbols, line ranges and
short sanitized observations instead. Preserve machine-readable evidence separately; HTML is a
navigable view, not a replacement for it.

## Module-map proposal

The report model may include `moduleMap` and `ownershipGate`. The proposal is first-class content,
not a sidebar or a substitute report: the overview names whether an authoritative map exists,
whether a proposal was generated, whether it was reviewed or approved, what decision comes next,
which qualitative reviews can continue, and which deterministic checks are blocked. The proposal
page distinguishes proposed modules, responsibilities, contracts, observed dependencies, unassigned
or ambiguous code, quality observations, recommendations and owner decisions. Every proposed module
has evidence; inference and recommendation are labelled separately from observed facts. Unassigned
production code is shown explicitly rather than silently assigned. The evidence page names the
ownership-dependent checks that remain blocked. Never render an inferred map as approved, and do not
show generic placeholders when the actual state can be explained.

## Adoption workflow status

The report model may include `adoptionWorkflow` with the selected mode, stage records, current
stage, stale warning and one next action. Show configured, generated, verified and blocked states
separately on the plan page and overview. The workflow status is a progress and decision aid, not a
conformance claim; a CI file or copied enforcer does not prove a remote run. Show the final
remediation decision separately: none/declined, selected/all, completed, partial, blocked, changed
files, deferred recommendations and the fresh verification result. Do not present an unselected,
manual or failed recommendation as resolved.

Show AI agent guidance as a first-class section: the discovered convention, primary instruction
file, generated support files, whether existing content was preserved, every rule identifier
covered, validation problems, and the limitation that structural validation does not prove every
coding agent will follow the guidance. Never describe a generated instruction file as empirically
verified agent behavior.

## Accessibility baseline

The generated report targets **WCAG 2.2 AA** for the content and interaction it provides. Criteria
that do not apply to a static report, such as accessible authentication, dragging movements or
redundant entry, are recorded as not applicable rather than treated as passes.

- **Document structure.** Every page declares `lang="en"`, has one descriptive `h1` and one `main`
  landmark, and uses a document title that names the page and repository. Navigation is labelled and
  identifies the current page with `aria-current="page"`.
- **Keyboard access.** A skip link moves focus into the report. Links, disclosure controls and
  horizontally scrollable table regions are keyboard-operable in a logical order, with no keyboard
  trap. The report does not require pointer, drag, hover or timed interaction.
- **Visible focus.** Every focusable element has a two-tone focus indicator that remains visible on
  light, dark and accent surfaces. Focus is never removed without an equally visible replacement.
- **Semantics and status.** Tables have a programmatically associated caption, column headers with
  `scope="col"`, and row headers with `scope="row"` when the first cell names the row. Status is
  conveyed by text as well as colour; colour is never the only carrier of meaning.
- **Contrast.** Body and secondary text meet at least 4.5:1 against its surface; large text and the
  focus indicator meet at least 3:1. The stylesheet's core text and status pairs are checked by the
  conformance suite.
- **Reflow and zoom.** Content remains usable at 320 CSS pixels wide and at 200% zoom without
  page-level horizontal scrolling. Wide tables scroll inside a labelled, focusable region rather
  than forcing the whole page sideways.
- **Motion and preferences.** The report does not depend on animation; reduced-motion preferences
  disable transitions, animation and smooth scrolling. Forced-colours mode keeps a system focus
  indicator and system colours.
- **Offline and print.** The report has no network dependency. Reading order follows the semantic
  document order, so the same content remains available without the stylesheet. Printing is a
  convenience, not a claim that every interactive disclosure is expanded on paper.

The automated accessibility checks cover document structure, table semantics, focus styling,
contrast tokens, reduced-motion and forced-colours support, and the responsive rules. A screen-reader
spot check and real-browser zoom/reflow check remain manual release checks; a passing static test is
not evidence that every assistive-technology combination has been exercised.

## Generate

From the installed skill root:

```bash
python scripts/render_report.py --input <report-model.json> --out-dir <output-directory>
```

The command writes six HTML pages, `assets/report.css`, and `report-data.json`. It has no third-party
runtime dependencies; generated reports need no network or build step. Existing report files are not
overwritten unless `--overwrite` is explicitly supplied. Only use that flag when replacement has been
approved.

When output is inside the target repository, obtain approval for the exact report directory first.
Prefer `acima/report/<assessment-id>/` so generated pages remain separate from product source.

## Decision-ready model, schema 1.1

Schema 1.1 adds explicit sections for preservation, fileImpact, roadmap, conformance, and section-specific explanation fields (outcomesStatus, decisionsStatus, fileImpactStatus, roadmapStatus, preservationStatus). Empty sections must explain whether information is unknown, not yet assessed, blocked, not applicable, or genuinely unnecessary. Empty arrays alone are not an explanation.

Outcomes distinguish the basis for the claim:
- standard-guarantee: the normative standard guarantees the architectural capability when implemented and verified.
- implementation-dependent: the capability depends on successful repository changes and verification.
- potential-benefit: a possible downstream benefit, never a promise.
- not-established: the evidence or owner decision is not yet available.

Every outcome also states why it matters, the practical engineering change, applicable requirement references, implementation prerequisites, required/optional classification, verification, and limitations.

Findings separate conformance disposition from action classification. Dispositions retain unresolved states such as unverified, not assessed, unsupported and blocked. Recommendation classifications are required, recommended, optional, or owner-decision. Do not translate optional preferences into normative requirements.

Every schema 1.1 finding MUST name at least one current catalog rule in `rule` or `requirementRefs`, and every named rule must exist in the pinned catalog. The renderer rejects an unlinked or unknown finding, so a human-readable item cannot enter a decision-ready report without a requirement identity. The finding details show that internal reference after the plain-language explanation. Findings and requirement results remain separate ledgers and are not expected to match one-to-one; the requirement reference makes the link traceable without turning the finding into a conformance result. Schema 1.0 remains accepted for legacy reports, where a finding without a reference is still only a grouped problem.

fileImpact groups inspect, create, modify and preserve actions. A file examined as evidence is not automatically a proposed change. The renderer treats these as proposals only; no report action authorizes editing.

The roadmap uses phases with prerequisites, activities, deliverables, affected areas, verification, approvals and completion criteria. A proposed phase is not a completed phase. Preservation is a distinct inventory and must not be inferred from the out-of-scope list.

Schema 1.0 remains accepted for legacy, non-decision-ready reports. New decision-ready reports use 1.1 and must embed the complete current catalog review, exact catalog fingerprint, one human-readable disposition per current requirement, evidence references and matching coverage counts. The renderer derives the required count from the pinned catalog, revalidates every source path, line range and exact quote, and rejects an incomplete or stale review, missing evidence, duplicate rule, mismatched disposition or inconsistent count. A review with valid dispositions but one or more `insufficient_evidence` outcomes may render only with an `INSUFFICIENT_EVIDENCE` recommendation and an incomplete assessment status. A render is only report-generation completion; it cannot mark assessment, adoption proposal, implementation or conformance complete.

For adoption, report generation is followed by a mandatory presentation checkpoint. Open and show the HTML report, provide direct links to all pages, and record the owner's review of the exact report digest. A file path in workflow state is not proof that the user saw the report. Report review does not authorize implementation.