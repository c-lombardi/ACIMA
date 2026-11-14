# Multi-page HTML outcome reports

The HTML report is the primary reader-facing explanation for a comprehensive ACIMA assessment or adoption proposal. It is designed for product owners and engineers who may not know ACIMA or the repository's codebase. The report is generated from a normalized, evidence-grounded model; it is not a new assessment engine and must not invent facts.

## Six pages, eight sections

| Page | Reader question answered |
|---|---|
| `index.html` — Overview | Should we adopt ACIMA, and what value would it provide here? |
| `proposal.html` — Architecture and map | What would change in the architecture, and what are the benefits and tradeoffs? |
| `findings.html` — Findings | What is already good, what did the assessment find, and why does it matter? |
| `files.html` — Changes and files | Exactly which files would be created, modified, removed, or only inspected? |
| `plan.html` — Plan and decisions | What happens next, in what order, and which decisions need an owner? |
| `evidence.html` — Evidence and limits | What was actually checked, what remains uncertain, and what supports the conclusions? |

Those pages carry eight primary sections in this order: **The decision**, **What would change**, **What needs attention**, **Which files change**, **What happens, in what order**, **What needs your decision**, **What the evidence shows**, and **What could not be established**. Supporting sections and disclosures stay inside the page that owns them; they do not create another primary section or another page.

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

The Plan and decisions page renders each owner decision as a brief, not a rule-id questionnaire: the plain-language
question, context, recommendation, effort, consequence of leaving it open, evidence gap, other
options and what stays blocked. Module ownership, path ownership and scope approval all use the same
shape. Findings remain findings; the renderer labels required fixes as “no owner decision” rather than
asking the owner to accept a classification. The Architecture and map page links to the Plan and decisions page instead of
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

## Owner approval for the partial-application allowlist

The proposal page may include `d016Allowlist` when the .NET partial-application check cannot run
because `partialHelpers` is absent from `acima.config.json`. This is not a silent skip: show the
current `not_executed` state, the recorded reason, any candidate helper names with evidence, the
proposed JSON (including an explicit empty list), the owner approval statement and the verification
needed afterwards. An explicit empty list records the owner's decision that no helper is used and
lets the rule execute; it does not waive the check. The Changes and files page links to the same section and may
list the configuration file as a proposed change.

## Plain-language gap briefing

Before the map, the proposal page answers the reader's practical question: what could go wrong, what
would each problem cost this product, and what would fixing it involve? This is a briefing, not a
second findings ledger and not a conformance result.

The model may include `plainLanguageGaps`, an array of objects with `title`, `risk`, `whatItCosts`
and `fixInvolves`; `paths`, `confidence`, and `basis` are optional. The assessment agent should write
these from the recorded findings and map state rather than template them. Order is high, medium, then
low risk, preserving source order within a level. Show at most six. Do not put ACIMA rule ids,
requirement ids, principle numbers, or internal defect language in the briefing; link to the
Findings page for that traceability. A path may be shown in the item's disclosure, but the title and
the cost/fix sentences must stand without it.

If `plainLanguageGaps` is absent, the renderer derives a smaller briefing from recorded findings and
unresolved map risks. An accepted map with no findings yields no gap section. Never invent a risk,
cost, fix, confidence, or path to fill the section.

## Module-map proposal

The report model may include `moduleMap` and `ownershipGate`. The proposal is first-class content,
not a sidebar or a substitute report: the overview names whether an authoritative map exists,
whether a proposal was generated, whether it was reviewed or approved, what decision comes next,
which qualitative reviews can continue, and which deterministic checks are blocked. The proposal page distinguishes proposed modules, responsibilities, contracts, observed dependencies, unassigned
or ambiguous code, quality observations, recommendations and owner decisions. Every proposed module
has evidence; inference and recommendation are labelled separately from observed facts. Unassigned
production code is shown explicitly rather than silently assigned. The evidence page names the
ownership-dependent checks that remain blocked. Never render an inferred map as approved, and do not
show generic placeholders when the actual state can be explained.

For maps with hundreds of modules, the proposal page must stay navigable rather than dumping a raw
JSON tree. Render two coordinated views:

- a **map at a glance** with one square per part, ordered by review state and linked to the matching
  directory row. The map is a macro index, not a score or a ranking; its legend and counts carry the
  same information in text.
- a **parts directory** with one row per part: name and id, review status, what it does, file and
  promise counts, connection count, and a native disclosure containing full paths, connections and
  evidence. The directory is a bounded, keyboard-scrollable region with a sticky header.

User-facing copy calls these **parts of the product**, **files**, **promises**, and **connections**.
An "ownership atlas" or "module record" may remain the internal model term, but it is not the label
the reader sees. State labels are plain: accepted, needs changes, needs an owner, set aside, already
documented, rejected.

Search and status filters are progressive enhancement. The controls are hidden until the inline
script runs; without JavaScript, every module row remains in the document and browser Find works.
The result count is announced, no-match has an explicit empty state, and a `#module-&lt;id&gt;` anchor
reveals the row and opens its record. Search covers name, id, file, what the part does and connection
text. The directory does not sort, save views, or infer health. State labels come only from recorded
review decisions or an authoritative declaration; a `pending` module is not presented as accepted.

## Adoption workflow status

The report model may include `adoptionWorkflow` with the current phase, stage records, current
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

## Automatic progress refresh

The report is a living view of the adoption, not a snapshot the owner has to ask for again. After
every recorded workflow change the adoption workflow refreshes the generated pages, so the Overview
and Plan and decisions pages show the current phase, current stage, completed milestones, next action, and
remediation or agent-guidance state without a prompt or a second command.

A refresh may replace only the progress sections: `adoptionWorkflow` and `milestones`. The reviewed
decision content — findings, module map, file impact, evidence and every other section — stays
byte-identical. The report layer compares a decision digest and refuses to write a refresh that
would change it, so an open page cannot silently become a different proposal. The generation digest
recorded at review remains the review identity; a separate live digest tracks the files on disk and
detects edits made outside the workflow.

A refresh failure never blocks the workflow. It is recorded as stale with its reason, and the
report is not presented as current until a refresh succeeds. The refreshed model is written back to
`report-data.json`, so the pages the owner reviewed remain the single report. Do not treat a
refreshed page as a new report, a new review, or new evidence.

## Accessibility baseline

The generated report targets **WCAG 2.2 AA** for the content and interaction it provides. Criteria
that do not apply to a static report, such as accessible authentication, dragging movements or
redundant entry, are recorded as not applicable rather than treated as passes.

- **Document structure.** Every page declares `lang="en"`, has one descriptive `h1` and one `main`
  landmark, and uses a document title that names the page and repository. Navigation is labelled and
  identifies the current page with `aria-current="page"`.
- **Keyboard access.** A skip link moves focus into the report. Links, disclosure controls, the
  module search and filters, and horizontally scrollable table regions are keyboard-operable in a
  logical order, with no keyboard trap. The report does not require pointer, drag, hover or timed
  interaction. The atlas is decorative and its links are duplicated by the directory and legend.
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
approved. The adoption workflow's own progress refresh is not an overwrite: it rewrites only the
progress sections of a report it already generated and keeps the reviewed decision content pinned.

When output is inside the target repository, obtain approval for the exact report directory first.
The adoption workflow writes one directory per generation at `acima/report/<reportId>/`, holding the
six pages, `assets/report.css`, `report-data.json` and a `report.json` identity sidecar. A new
generation gets a new `reportId` and a new directory, so a reviewed report is never replaced in place.

`report.json` records the report id, generation, generated-at timestamp, the generation digest
(`sha256`), the live digest of the files on disk (`liveSha256`), the decision digest and the
decision-file digest (`decisionSha256`) and the progress status. The generation digest covers only
the report's own files. `decisions.json` sits beside them, is excluded from every digest, and is the
only file in the directory meant to be committed.

## Answering the report

The owner answers pages locally and each answered page writes one decisions file, validated by
`assets/decisions.schema.json`. It carries the identity of the report it answers (`reportId`,
`proposalSha256`), one named reviewer, the decision date, and an `answers` array whose entries name a
`kind`, an `id` and a `decision` of `accept`, `modify`, `defer` or `reject`. A checked box is never
consent: approving implementation remains a separate command bound to the report digest.

The Plan and decisions and Changes and files pages carry the controls: objectives and remediation on Plan and decisions,
per-path scope on Files, with visible labels, a *Needed for* note on paths a stage needs, and
every proposed file selected only by an explicit click. *Save answers file* downloads
`acima-decisions-<reportId>-<page>.json`; in-place save is offered only where the File System Access
API exists on a secure context. *Copy answers* supports paste-back in chat, and a no-JavaScript
template shows the answers current at generation so the report stays answerable without script; the
Changes and files page prints the same template for its path answers.

A page cannot hash its own bytes, so `reportSha256` and `decisionSha256` are optional: the workflow
completes them from the report it has verified on disk, after checking `reportId` and the live
generation. Supplied digests are still checked strictly. Because pages answer separately, files with
the same identity are partial; the workflow merges answers in force, so save order cannot change the
resulting scope, and the review answer is required once per adoption rather than once per file.

Ingest it with `acima adoption decisions --from <path>`. A file from a different report identity is
refused as stale. An answer that contradicts a recorded answer is refused unless the file names the
earlier file in `supersedes`; a page sets that reference itself when it revises an answer, and only
the named file is replaced — answers recorded by other files still conflict and are superseded one
file at a time. Map answers are accepted only while the map is awaiting review. Scope
answers derive a draft scope that records `authorization.explicit: false`; the approval command still
has to run. If a required path is left out, the objective that needs it is deferred and named rather
than approved incompletely. Remediation answers are recorded intent, not a remediation decision.

A report that cannot be refreshed — files deleted, edited, or left inconsistent by an interrupted
operation — is rebuilt with `acima adoption regenerate --reason "<why>"`. Regeneration is a repair:
it creates a new report identity, returns the review to `awaiting_review`, invalidates prior
approvals and marks earlier answers stale.

## Console history, decision log and events

The plan page renders history from the refreshable progress payload, never from reviewed decision
content: the decision log shows the answers in force and lists superseded or stale answers as
read-only history; *changed since your review* compares the current report identity and generation
digests against the last reviewed receipt; evidence integrity lists each artifact the workflow
recorded and marks one that has disappeared as recorded but missing rather than complete. A stage
history lists transitions with their time and detail. Recording an answer therefore never changes
the reviewed pages or the generation digest.

`acima/evidence/events.jsonl` is an append-only local event stream: `report.generated`,
`report.refreshed`, `report.stale`, `decisions.ingested`, `approval.recorded` and `stage.changed`. It
is not a conformance claim and is excluded from the revision an approval binds to.

## Progress contract, schema 1.2

Schema 1.2 pins the progress contract in the model itself. It declares
`progressSections: ["adoptionWorkflow", "milestones"]` — exactly the sections a refresh may replace —
and requires `adoptionWorkflow.currentStage` and `adoptionWorkflow.asOf`. The renderer rejects a 1.2
model that omits either, or that claims different progress sections, so a refresh cannot quietly
widen its own write surface. A report generated under schema 1.1 still refreshes under the same two
sections, because that release already refreshed exactly those; a model that declares other sections,
or one that predates the progress contract entirely (1.0), is refused and must be regenerated rather
than refreshed. Schema 1.1 and 1.0 remain readable for reports generated earlier. Schema 1.3 keeps that progress contract and adds a
`console` block: report id, generation, proposal digest, objectives with the paths they require, and
the selectable paths with the stages that require them. Automated reports carry the block with
`mode: full` and still render no answer controls.

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