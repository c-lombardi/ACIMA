# ACIMA outcome report design

This document describes the **incumbent six-page offline HTML report**. It is a record of the
system as implemented, not a redesign brief or a target-state specification. The renderer and
stylesheet are the source of truth; if this document and the code disagree, the code wins and this
document should be corrected.

The report is the primary designed surface for a comprehensive ACIMA assessment or adoption
proposal. It is generated from an evidence-grounded JSON model, written as static files, and opened
directly from disk. There is no application server, build step, JavaScript bundle, or network
dependency in the generated output. The only script is a small inline block: it adds search and status
filtering to the module directory when a map is present, and in guided adoption it builds the answer
file on the Plan and Files pages. Both are enhancements. Without script the directory stays in
document order and both answer pages print a template instead of controls.

## Scope

This document covers:

- the six report pages and the reading path between them;
- the shared shell and page-level information hierarchy;
- the local visual system: colour, typography, spacing, and layout;
- reusable components and their behaviour;
- the guided answer console, the answers file it builds, and the history tables;
- responsive, print, and accessibility behaviour;
- the content-truth and validation rules that constrain what the design may display.

It does not cover the ACIMA CLI, the normative standard, the adoption skill's prose references, or
a future hosted dashboard. Those are separate surfaces.

## Implementation map

| File | Responsibility |
|---|---|
| `skills/acima-adoption/scripts/render_report.py` | Defines the six pages, section order, labels, default copy, status pills, tables, the module atlas and directory, and document shell. |
| `skills/acima-adoption/assets/report-template.css` | Defines all visual tokens, layout, components, responsive rules, focus treatment, and print styles. |
| `skills/acima-adoption/assets/report.schema.json` | Defines the normalized input contract for the report model, including the guided `console` block. |
| `skills/acima-adoption/assets/decisions.schema.json` | Defines the answers file a guided report page builds and the workflow ingests. |
| `conformance/adoption_workflow.py` | Owns workflow state, the console's answer state, decisions ingestion, and the refresh that keeps history current. |
| `skills/acima-adoption/references/90-html-outcome-reports.md` | Defines the information model, page questions, truth rules, and accessibility baseline. |
| `report-data.json` (generated) | Preserves the structured model used to produce the six HTML pages. |

The renderer writes `index.html`, `proposal.html`, `findings.html`, `files.html`, `plan.html`,
`evidence.html`, `assets/report.css`, and `report-data.json`. Existing report files are not replaced
unless `--overwrite` is supplied.

## Design intent

The report is a decision document disguised as an assessment dossier. It must let a reader who does
not know ACIMA understand:

1. what is being recommended and why;
2. what would change in the repository;
3. what is already working and what needs attention;
4. exactly which files are involved;
5. what happens next and who must decide;
6. what was actually checked and what remains uncertain.

The design therefore follows a **consequence-first** order. Plain-language meaning, recommendation,
and proposed action come before rule identifiers, evidence tables, and technical traceability. The
report is allowed to be dense, but it must not be vague, and it must never turn incomplete coverage
into a clean result.

Five commitments shape the visual and interaction decisions:

- **Decision before detail.** The overview starts with a recommendation, not a rule inventory.
- **Evidence before certainty.** Unknown, unverified, unsupported, and not-supplied states remain
  visible.
- **One document, six questions.** Navigation is a reading path, not a feature menu.
- **Local and offline.** No external fonts, images, scripts, analytics, or hosted assets.
- **Static files, local interaction.** Interaction is navigation, disclosure, table scrolling, the
  module directory's optional search and status filters, and, in guided adoption, an answer console
  that writes one local answers file and makes no network call.

## Readers and reading contexts

The primary readers are staff engineers and architects evaluating ACIMA in an existing repository.
They may be reading the report to understand architectural risk, review a proposed scope, or approve
a first adoption step. Engineering leaders are a secondary audience reading for the recommendation,
cost, risk, and evidence.

The report assumes:

- the reader may arrive directly on any page from a link;
- the reader may not know the rule catalog by heart;
- the reader may be comparing the proposal with a repository they did not design;
- the report may be printed, attached to a review, or read without network access;
- the reader needs enough traceability to challenge a conclusion, but not on the first pass.

## The six-page journey

`index.html` is the entry point. Every page is reachable from the left rail on desktop and the
horizontal section strip on narrow screens.

| File | Rail label | Page `h1` | Subtitle | Immediate question |
|---|---|---|---|---|
| `index.html` | Overview | Overview | The decision at a glance | Should we adopt ACIMA, and what value would it provide here? |
| `proposal.html` | Proposal | What would change | The proposed architecture and what it would deliver | What would change, and what are the benefits and tradeoffs? |
| `findings.html` | Findings | What we found | What is working and what needs attention | What is already good, what did the assessment find, and why does it matter? |
| `files.html` | Files | Files and impact | Exactly what is proposed to change | Which files would be created, modified, removed, or only inspected, and which may be approved? |
| `plan.html` | Plan | Plan and decisions | What happens, in what order, and who decides | What happens next, which decisions need an owner, and where do I record my answers? |
| `evidence.html` | Evidence | Evidence and limits | What was checked and what the results prove | What supports the conclusions, and what remains uncertain? |

The rail labels are shorter than the page titles. This is intentional: the rail is a compact reading
path, while the page head carries the fuller framing. The current page is marked with
`aria-current="page"` and a blue rule in the rail (a blue underline on narrow screens).

## Shared shell

Every page is generated through the same `shell()` function and has this order:

1. **Skip link** — “Skip to report content,” visible on keyboard focus, targets `#main`.
2. **Header** — dark slate bar with the ACIMA wordmark, a blue square containing an `A`, the
   repository name, and a readable generation date. The header is not sticky.
3. **Layout grid** — a 240px navigation rail plus a flexible main column, capped at 1600px.
4. **Navigation rail** — a “REPORT SECTIONS” label, six links, and a short note explaining that the
   report covers what ACIMA found, proposes, and would deliver. The note is hidden below 900px.
5. **Main region** — `id="main"`, `tabindex="-1"`, and `aria-labelledby="page-title"`. It contains
   a page head, the page body, and a footer.
6. **Page head** — a small breadcrumb-like line (`repository / page label`), the `h1`, and a
   one-sentence subtitle. A two-pixel ink rule closes the head.
7. **Footer** — “ACIMA · Architecture that enforces itself.” plus a note that the pages were
   generated from the accompanying evidence model.

The shell is deliberately stable across pages. The reader should be able to move between the
recommendation, the proposal, the findings, the file inventory, the plan, and the evidence without
relearning the frame.

## Page hierarchy

### Overview (`index.html`)

The overview is the decision page. Its sections appear in this order:

1. **Recommendation panel.** A “RECOMMENDATION” kicker, the recommendation status as an `h2`, the
   recommendation summary, and an assessment-status pill. The panel has a blue top edge and a raised
   paper surface.
2. **“THE SHORT VERSION” / “What this means for your product.”** A larger lead paragraph carrying
   the plain-language explanation immediately after the decision.
3. **Compact evidence row.** Two tiles only: problems found and checks reviewed. The check-review
   tile shows `reviewed of required` and an unresolved note that explicitly says coverage is not a
   score. A small context line below carries repository type and structure without adding two more
   tiles.
4. **“What has been completed?”** A five-row milestone table: assessment, report generation, change
   proposal, implementation, and final verification. A note below states that writing the report
   does not complete assessment, approval, implementation, or verification.
5. **“WHAT GETS BETTER” / “What this work would make possible.”** Two-column benefit cards, each
   with a sequence number, title, description, and an availability or “proposed benefit” line.
6. **“THE DECISION” / “Why this recommendation?”** Two columns: “Why it fits this repository” and
   “Tradeoffs and caveats.”
7. **Next-step band.** A dark panel with a “NEXT STEP” kicker, the next action as an `h2`, its
   rationale, and a blue link to the proposal page: “See what would change →”.

The intended reading order is recommendation → short explanation → evidence at a glance →
completion boundary → value → tradeoffs → next action. Tables and metrics support that order rather
than replacing it.

### Proposal (`proposal.html`)

The proposal page explains the architectural change and its value:

1. **Adoption path.** A four-stage rail from **No ACIMA** through **Foundation** and **Implemented**
   to **Continuous**. It states the current position from recorded milestones, labels earlier stages
   as context, and marks the last stage as a destination rather than a certification. The rail is the
   report's positional diagram; it carries no invented score or trend.
2. **“TODAY” / “How the repository works today.”** A lead paragraph followed by two columns:
   “Already working” and “What would be added.”
3. **“WHAT TO KEEP” / “What already works and should stay.”** Existing architecture and
   enforcement assets are listed before proposed changes so the reader can see what remains intact.
4. **“WHAT WOULD CHANGE” / “What would change.”** A paragraph describing the proposed state,
   followed by a three-column capability table: capability, what changes, and what it makes possible.
5. **“WHAT COULD GO WRONG” / “What matters before the map.”** A plain-language gap briefing before
   the map itself. At most six items are ranked by real risk; each states what it could cost this
   product and what fixing it would involve. Internal rule and requirement identifiers are omitted,
   with a link to the Findings page for evidence. The assessment agent may supply these directly in
   `plainLanguageGaps`; otherwise the renderer ranks recorded findings and unresolved map risks.
6. **The map of the product and its details.** Proposed boundaries, contracts, dependencies, quality
   observations, recommendations, and owner decisions. This technical detail follows the plain-language
   current, proposed and gap sections rather than leading the page. The map is synthesized for scale: a
   **map at a glance** gives one square per part and a status legend gives the macro distribution; a
   searchable **parts directory** gives the micro view, with status, what it does, file and promise
   counts, connections, and a native disclosure for full paths, links and evidence. Map squares link
   to their directory rows. Search and status filters are progressive enhancement; without JavaScript
   the controls are hidden and every part remains in the document.
7. **“WHAT GETS BETTER” / “What should become easier or safer.”** A stacked set of outcome rows.
   Each row includes title, description, what it could cost, practical change, classification, basis,
   verification, limitations, and a status pill.
8. **“TRADEOFFS” / “Costs, risks, and limits.”** Two columns for cost/effort and risks/mitigations,
   followed by “What this work will not do.”

The page deliberately separates current state, proposed state, expected outcome, and limitation. A
proposed benefit is never presented as a delivered capability. The adoption path is a position
statement: its current marker uses recorded milestones, and Continuous is never inferred from a
rendered report.

### Findings (`findings.html`)

The findings page has two sections:

1. **“WHAT IS ALREADY WORKING” / “What is already in good shape.”** A bullet list. If none are
   recorded, the empty state says that this does not mean none exist.
2. **“PROBLEMS FOUND” / “What needs attention.”** A lead paragraph explaining that problems are
   grouped by underlying cause, followed by a reconciliation block and finding cards. The block
   states that problems and checks are counted separately, counts problems with an explicit matching
   result, and keeps unmatched problems visible. Contextual links point to file changes, the plan,
   and checks needing attention.

Each problem card contains:

- title and a disposition/status pill in a shared row;
- what happens;
- what it could cost;
- what fixing it involves;
- whether it is required or optional;
- a closed disclosure labelled “Where this came from.”

The disclosure contains what the check means, source paths and evidence references, what good looks
like, how to know it worked, confidence, and what is still unknown. Technical traceability is
available on demand; it is not the first thing the reader sees.

If no problems are recorded, the page does not declare a pass. The empty state directs the reader to
the evidence page to confirm that the review was complete before interpreting the absence as a
clean result.

### Files (`files.html`)

The files page is the proposed-change inventory:

1. **“Proposed file changes.”** A lead paragraph clarifying that inspection is not a proposed edit and
   that create/modify actions remain proposals until approved. A six-column table lists the file or
   area, action, why it is involved, what it should achieve, required/optional status, and confidence.
2. **“What should stay the same.”** A bullet list covering preservation.
3. **Four count tiles** for create, modify, inspect, and preserve.

The table comes before the counts. The reader sees the named paths and their purpose before seeing
aggregate totals. The page does not turn inspection into an implied edit.

In guided adoption the page ends with **“YOUR SCOPE” / “Choose the files this adoption may change.”**
A fieldset lists every proposed path as a native checkbox, with a *Needed for <stage>* note where a
stage requires that file. No box is ticked at generation; recorded answers are prefilled when the
report is reopened. *Select all proposed files* is a secondary button the reader chooses, never a
default. A reviewer name is required, and the controls build
`acima-decisions-<reportId>-files.json`. The report review answer lives on the Plan page; the workflow
merges the two page files by identity. With script off, the page prints a template for its path
answers instead of controls.

### Plan (`plan.html`)

The plan page is the execution, authority, and answering page. It opens with **“Where the adoption
stands”**: mode, current phase, current stage, a stage table (stage, status, what this proves or
blocks, next action), the next action, and a note that the section refreshes after a recorded workflow
change. That progress is rewritten in place; the reviewed decision content is not. After the status
section, and the agent-guidance and remediation sections where those apply, the page reads in
workflow order — what will happen, what needs a decision, how to answer, what approval would mean —
and ends with the record:

1. **“Plan.”** A stack of phase cards. Each card has a phase name and status pill, purpose,
   what comes before it, what it produces, how to verify it, when it is done, who approves it, and a
   closed “Work and affected areas” disclosure.
2. **“Decisions only you can make.”** Decision rows with the question, context, recommendation,
   what the decision blocks, what is needed before implementation, and a closed disclosure for other
   options, impact, and why an owner is needed. If no decisions are recorded, the empty state
   explicitly distinguishes “no decision needed” from incomplete discovery.
3. **“Answer this report” (guided adoption only).** The console pairs each stage with three native
   options — *Implement*, *Defer*, *Decline* — and a “Needed for …” or “No file changes” note. A
   reviewer name and a confirmation that all six pages were reviewed are required before the page
   builds one `acima-decisions-<reportId>-plan.json` answers file; answering is never approval.
   *Save answers file* downloads the file (with an in-place save where the browser supports it),
   *Copy answers* copies it, and both fill the read-only paste-back area. Validation failures appear
   in an alert that receives focus; a cancelled save writes nothing. When a page would change an
   answer already recorded, it names that answer's file in `supersedes`, so re-saving one page
   replaces exactly that file. With script off, the page prints a JSON template instead of controls.
4. **“What approval would mean.”** A short statement that reading the report does not authorize
   implementation and that approval must identify a specific proposed scope.
5. **“What is settled, and how it got there.”** Read-only history under one kicker: **Current
   answers** (kind, answer, decision, reviewer, date), **Earlier answers** behind a native disclosure
   with *Replaced* and *Out of date* states and the stored reason, and **Stage changes** (when, stage,
   from, to, what changed). A closing note either confirms that every recorded evidence file exists
   or names the ones that no longer do. Answer names use the same labels as the controls.

The adoption plan describes proposed phases; a phase is not complete because it appears in the plan.
History follows the plan and the answer controls so outcomes never precede the work they describe;
automated reports carry the same history and no controls.

### Evidence (`evidence.html`)

The evidence page is the audit trail and the limits page:

1. **Evidence summary / “What the evidence shows.”** A short lead sentence and three inline facts:
   checks reviewed, still unresolved, and checks needing attention. A note states that coverage is
   not a passing score.
2. **Checks needing attention / “What needs attention.”** Only non-conforming or unresolved check
   results, with the check, result, explanation, and evidence. If no results were supplied, the page
   says so rather than claiming there are no problems.
3. **Limits / “What could not be established.”** A visible bullet list. If empty, the fallback asks
   the reader to confirm that coverage and tooling limits were explicitly considered.
4. **Evidence details.** Four native disclosures: review coverage, all check results, supporting
   evidence, and how the report was made. The full coverage table and 56-result table remain
   available here, but are closed by default.

The page is complete but progressive: summary and exceptions first, full audit trail on demand. It
shows its work without making the reader scan every row before understanding the result.

## Visual language

The report reads as a printed assessment dossier rendered in ice-blue: pale blue paper, slate
structure, narrow industrial headings, a single blue structural rule, and restrained sky, amber,
green, and red for meaning. It is closer to an editorial report than to a SaaS dashboard. The
palette is anchored on `#3B82F6` (primary blue), `#60A5FA` (sky), `#1F2937` (slate ink), and
`#F0F9FF` (ice paper); the remaining values are derived tints and semantic states.

### Colour tokens

| Token | Value | Role |
|---|---|---|
| `--board` | `#1F2937` | Header, next-step band, darkest structure. |
| `--bay` | `#111827` | Navigation rail. |
| `--paper` | `#F0F9FF` | Page background. |
| `--lit` | `#FFFFFF` | Raised cards, decision panel, table surfaces. |
| `--shade` | `#DBEAFE` | Table headers, notes, neutral pills, inset states. |
| `--ink` | `#1F2937` | Primary text and strong rules. |
| `--mid` | `#334155` | Secondary body copy. |
| `--muted` | `#475569` | Metadata, captions, footer, muted labels. |
| `--rule` | `#CBD5E1` | Table row rules and light dividers. |
| `--strong` | `#94A3B8` | Section dividers, card seams, pill borders. |
| `--accent` | `#3B82F6` | Brand mark, active navigation, decision edge, current path marker. |
| `--accent-deep` | `#2563EB` | Primary-action surface. |
| `--sky` | `#60A5FA` | Secondary accent, modified modules, logo subtitle. |
| `--blue` | `#1D4ED8` | Links, current path label, focus ring. |
| `--ochre` | `#92400E` | Findings, notes, empty-state edges, caution. |
| `--green` | `#047857` | Positive status text. |

Blue is structural and brand-led, not an error colour. `--accent` supplies the bright blue edge,
while `--accent-deep` backs the primary action because white text on it clears 4.5:1. Links use
`--blue`, not the lighter accent, for the same reason. Findings use amber; risk uses red; success
uses green. Status pills use tinted semantic surfaces (`--success-*`, `--warn-*`, `--danger-*`)
with dark text. The module atlas uses blue for accepted, sky for modified, pale ice-blue for
needs-owner, slate for deferred and declared, and red only for rejected. The page has
a light colour scheme only; there is no dark-mode variant.

### Typography

| Role | Family | Size and treatment |
|---|---|---|
| Body | `"Segoe UI", Arial, sans-serif` | 16px / 1.58, ink on paper. |
| Display headings | `"Arial Narrow", "Segoe UI", sans-serif` | Tight 1.12 line-height; `h1` clamps from 34px to 56px. |
| Section headings | Same as display | `h2` clamps from 23px to 32px; `h3` is 20px. |
| Lead paragraph | Same as body | 19px / 1.55, maximum 78 characters wide. |
| Metadata, labels, pills, tables | `"Cascadia Code", Consolas, monospace` | Small uppercase labels with modest tracking. |
| Table body | Body family | 13px / 1.5. |

Small metadata is normalized to 12px in the final stylesheet. Section kickers are 12px uppercase
monospace with `0.06em` tracking. Heading letter-spacing is slightly negative, which gives the
display type its compact, industrial character.

### Spacing and surfaces

- The shell is capped at 1600px, with a 240px rail and a main column capped at 1280px.
- Main padding uses `clamp(24px, 4vw, 58px)`.
- Sections use approximately 34px top and 42px bottom margins.
- Cards use 18–26px internal padding and thin border tops rather than heavy shadows.
- The decision panel and next-step band are the only strongly elevated or inverted surfaces.
- Rules and borders do the structural work; the palette stays quiet.
- The console column is capped at 78ch, the report's reading measure; answer rows use 44px targets and
  one statement per row.

## Layout behaviour

| Viewport | Behaviour |
|---|---|
| Above 900px | Two-column shell: 240px rail and flexible main. Metrics are four across; benefits and paired sections are two across. |
| 601–900px | Shell becomes one column. The rail becomes a horizontal, scrollable section strip. Metrics become two across. |
| 600px and below | Paired columns become one column. Decision and next-step panels stack. Pills may wrap. Footer switches to a grid. |
| Print | Header, rail, skip link, and next-step CTA are hidden. Main becomes full width. Sections, cards, benefits, and metrics avoid page breaks. Disclosure expansion remains browser-dependent. |

The report targets 320 CSS pixels and 200% zoom without page-level horizontal scrolling. Wide
tables scroll inside a labelled, focusable `.table-wrap` region rather than forcing the entire page
sideways.

## Components

| Component | Class or element | Behaviour and hierarchy |
|---|---|---|
| Skip link | `.skip` | Fixed, visually hidden until focused; jumps to `#main`. |
| Brand | `.brand` | Blue `A` block, ACIMA name, “ARCHITECTURE OUTCOME REPORT” subtitle; links to the overview. |
| Header metadata | `.meta` | Repository name and generation timestamp, right-aligned; wraps rather than overflowing. |
| Rail navigation | `aside`, `nav` | Six links; current page has `aria-current="page"` and an active rule. Horizontally scrollable below 900px. |
| Page head | `.page-head` | Small location line, one `h1`, one subtitle, closed by a 2px rule. |
| Decision panel | `.decision` | Recommendation status, summary, assessment pill; blue top edge and raised paper surface. |
| Adoption path | `.adoption-path` | Four-stage rail with a milestone-derived current marker; earlier, current, next, and destination states are labelled in text and remain legible without colour. |
| Metric tile | `.metric` | Monospace label, strong value, optional note. The overview uses a compact two-tile row; the files page keeps four, dropping to two below 900px. |
| Benefit card | `.benefits article` | Number, title, description, availability/proposed-benefit line; blue top edge. |
| Finding card | `.finding` | Title and pill, what/why/response/action type, closed evidence disclosure; ochre top edge. |
| Reconciliation block | `.reconciliation` | Explains that problems and checks are counted separately and reports linked versus unlinked problems. |
| Cross-page links | `.cross-links` | Contextual “Related” links between findings, files, plan, and evidence; plain links, no global link bar. |
| Outcome row | `.stack > .row` | Title, description, why, practical change, classification, basis, verification, limitation, status pill. |
| Phase card | `.phase` | Name and status, purpose, prerequisites, deliverable, verification, completion, approval, activities disclosure. |
| Decision row | `.decision-row` | Plain-language question, context, recommendation, effort, consequence, blocked work, prerequisite, evidence gap/alternatives disclosure. |
| Console identity strip | `.console-strip` | Reports with a console block: report id, answer version, answers in force, a decision-log link, and — in guided mode — the *Answer this report* link; automated reports replace that link with a sentence saying answers are recorded in one consolidated review. |
| Answer console | `.answers` | A 78ch column of fieldsets: report review, stage choices, source fixes, scope paths. Native controls only. |
| Answer row | `.answer-row` / `.choices` | Label and note on the left, aligned radio columns or a path checkbox on the right; stacks below 600px. |
| Console button | `.button` | Primary save and secondary copy/select-all; 44px minimum height, two-tone focus ring, disabled state for unreadable data. |
| Console message | `.answers-error` / `#answers-status` | Error in a focusable `role="alert"` region; save, copy and cancellation results in a polite live region. |
| No-script template | `.template` | Read-only JSON or path template shown when script is off, so both answer pages stay answerable in chat. |
| Table region | `.table-wrap` | Horizontal overflow container with `role="region"`, a caption reference, and `tabindex="0"`. |
| Status pill | `.pill` | Uppercase monospace label; neutral, good, risk, or review treatment. |
| Empty state | `.empty` | Shaded panel with an ochre left edge; explains absence rather than hiding it. |
| Note | `.note` | Shaded inset with an ochre left edge; carries qualifications and scope limits. |
| Disclosure | `details` / `summary` | Native open/close control for technical traceability or long supporting detail. |
| Next-step band | `.next` | Dark inverted panel with next action, rationale, and blue proposal link. |
| Footer | `footer` | Provenance reminder and report-generation statement. |

### Status pills

The renderer maps known status values to reader-facing labels, then classifies the underlying value
by keyword:

| Class | Matched terms | Visual treatment |
|---|---|---|
| `review` | incomplete, not assessed, partial, pending, unknown, insufficient, review, unverified, not supported | Amber |
| `risk` | gap, fail, blocked, not recommended, significant, does not conform | Red |
| `good` | verified, pass, complete, approved, conforms, confirmed | Green |
| neutral | Anything else, including “Not recorded” | Grey |

Examples of the presentation mapping include `RECOMMENDED_WITH_LIMITATIONS` → “Recommended, with
limitations,” `DOES-NOT-CONFORM` → “Does not meet the check,” and `unverified` → “Needs more
evidence.” CSS uppercases the human label in the pill; it does not expose the raw enum. The
classification is still substring-based and is an implementation detail, not a semantic guarantee.
New status vocabulary must be checked against this map and against the report's truth rules.

## Interaction model

- **Navigation:** ordinary links between the six static pages.
- **Disclosure:** native `<details>` and `<summary>` elements; no script is required for disclosure.
- **Table overflow:** horizontal scrolling inside a focusable, labelled region. The module directory also bounds its vertical height so a thousand rows do not make the page unpaginated; its header stays sticky within that region.
- **Keyboard:** skip link, visible two-tone focus ring, logical document order, no keyboard trap.
- **Pointer:** no drag, timed, or gesture-dependent interaction. The atlas hover outline is decorative; the directory carries the same links and text.
- **Answering (guided):** native radios and checkboxes record closed-set choices. *Save answers file* downloads one `acima-decisions-<reportId>-<page>.json` (in-place save only where the File System Access API exists on a secure context); *Copy answers* copies the same document. The page requires a reviewer name, the Plan page also requires the review confirmation, and the read-only paste-back area is filled only by these actions. Answers live in the file and in the form, never in browser storage. Reopening a page prefills answers recorded in the report snapshot, and a changed answer names the file it replaces in `supersedes`. The console cannot approve anything; approval remains a separate workflow command.
- **State:** the browser's open/closed state for disclosures is the only other persistent state. A module query and selected status filter are ephemeral and reset on reload; a `#module-...` anchor reveals its row and opens the record.
- **Module atlas:** the atlas is presentational and hidden from assistive technology. Each tile is a link to the matching directory row; the legend and directory carry the same status in text, so colour is never the only carrier.
- **Search and filtering:** one labelled search field and a row of status filter buttons narrow the module directory. A polite live region reports the result count, and an explicit empty state appears when nothing matches. The controls are hidden until the inline script runs; without JavaScript, the full directory is still present and browser Find remains usable.
- **Cross-page links:** contextual “Related” links connect findings, file impact, plan, and evidence. Anchors identify the destination section, such as `#file-changes`, `#adoption-plan`, and `#exceptions`.
- **Reconciliation:** problems and check results are presented separately. A problem can carry an optional `rule` or `requirementRefs`; the report states how many problems have an explicit matching check result and how many remain unlinked.
- **Print:** hides the shell and next-step CTA and keeps report components intact where possible.

The only data entry is the guided console's closed-set answers and reviewer name; there are no
free-form fields, charts, scores, theme switchers, or asynchronous updates. The adoption path is a
static position diagram, and the module atlas is a navigational index, not an interactive chart or
score.

## Responsive and reflow rules

- The shell and main column set `min-width: 0` so flex and grid children can shrink.
- The rail becomes a single scrollable row below 900px; the rail note is hidden.
- Long headings, pills, findings, decision rows, and table cells use `overflow-wrap: anywhere`.
- Tables keep their column structure and scroll horizontally rather than collapsing into cards.
- The module atlas wraps to the available width. The module directory keeps a bounded vertical area on desktop and mobile, with its header sticky inside that area.
- The compact overview row stays two columns; full metric strips, such as the file counts, reduce from four to two below 900px.
- The console keeps its 78ch measure; below 600px the stage choices sit in two columns under their label, and long paths wrap inside the row.
- The report does not rely on hover to reveal meaning.
- The layout is checked at 320 CSS pixels and 200% zoom; tables are the expected local scroll
  exception, not the page itself.

## Accessibility baseline

The report targets **WCAG 2.2 AA** for the content and interaction it provides.

- Each page declares `lang="en"`, has one `h1`, and has one `main` landmark labelled by the page
  title.
- Navigation and the complementary rail are labelled; the current page uses `aria-current="page"`.
- Tables have captions, column headers with `scope="col"`, and row headers with `scope="row"` where
  the first cell names the row.
- The skip link and main focus target provide a keyboard path into the content.
- Focus uses a two-tone ring that remains visible on light, dark, and accent surfaces.
- The module atlas is decorative and removed from the accessibility tree; its legend and directory
  carry the same links and state in text.
- The module directory search has a persistent label, status filters expose `aria-pressed`, and the
  result count is announced politely. Every row remains in the document without JavaScript.
- Console fieldsets use legends, every radio, checkbox and the name field has a visible label, and the reviewer field is capped at 120 characters.
- Validation failures render in a `role="alert"` region that receives focus; save, copy and cancellation results are announced through a polite live region.
- The console identity strip and its *Answer this report* link give a keyboard path to the controls; without script, the template stays readable and selectable.
- Status is conveyed by text as well as colour.
- Core text and status pairs meet contrast targets enforced by the conformance suite.
- Reduced-motion preferences disable transitions, animation, and smooth scrolling.
- Forced-colours mode preserves a system focus indicator and system colours.
- Reading order follows semantic document order and remains meaningful without the stylesheet.
- Screen-reader spot checks and real-browser zoom/reflow remain manual release checks. A passing
  static test is not evidence that every assistive-technology combination works.

## Content truth rules

These rules are part of the design, not editorial polish:

- **Never invent a value.** Missing fields render as “Not recorded,” “Not established,” or an
  explicit status explanation.
- **No health score.** The report does not aggregate conformance into a single number, grade, or
  trend. Requirement-review coverage is not a conformance score.
- **The atlas is an index, not a judgement.** A tile encodes only the module's recorded review state;
  tile order, position, and count do not rank modules or imply architectural quality.
- **The path is a position, not a score.** Its current marker comes from recorded milestones; later
  stages are proposals, and Continuous is a destination the report cannot certify.
- **Coverage is not correctness.** A complete evidence record can still contain unresolved
  interpretation. Automated checks, qualitative review, and conformance claims remain distinct.
- **Empty findings are not a pass.** The findings page directs the reader to confirm coverage before
  interpreting no findings as a clean result.
- **Proposed is not implemented.** Benefits, outcomes, phases, and file changes are proposals until
  explicitly approved and verified.
- **Inspection is not an edit.** `inspect` entries in the file inventory are evidence work, not
  proposed modifications.
- **Preservation is explicit.** “What should stay the same” is a separate inventory, not an
  inference from out-of-scope items.
- **Unknown states remain visible.** Unverified, not assessed, unsupported, blocked, and skipped
  work must not be hidden behind a summary that implies completion.
- **No fabricated provenance.** Repository path, commit, dates, versions, and catalog fingerprints
  come from the model and its validation.
- **No sensitive material.** Credentials, tokens, private keys, secrets, personal data, and
  unnecessary source excerpts do not belong in the report model or generated pages.
- **An answer is not approval.** The console records intent in a local file; only the digest-bound
  approval command authorizes implementation. A checked box never stands in for consent.
- **Prefill is not consent.** A page shows recorded answers so the reader can revise them; seeing an
  answer back is not a new decision, and saving re-states it without turning it into approval.
- **History is a record, not a control.** Current, replaced and out-of-date answers are read-only;
  they do not count toward the scope until the workflow ingests a file.

Schema 1.1 enforces the decision-ready contract: 56 requirement dispositions, exact catalog
fingerprint, evidence references, matching coverage counts, and a validated qualitative review. A
review with unresolved requirements can render only with an `INSUFFICIENT_EVIDENCE` recommendation
and an incomplete assessment status. Schema 1.2 pins the refreshable progress sections so a workflow
refresh cannot alter reviewed decision content; schema 1.3 adds the guided console block described
below. Rendering the report is report-generation completion; it does not mark assessment, proposal,
implementation, or conformance complete.

## Data and rendering contract

The report is a view over a normalized JSON model, not an assessment engine. The model includes
repository identity, recommendation, overview, value, architecture, coverage, strengths, findings,
proposed changes, outcomes, phases, decisions, evidence, limitations, conformance, milestones,
preservation, file impact, and provenance fields.

Schema 1.0 remains accepted for legacy, non-decision-ready reports. New reports are generated at
schema 1.3. The renderer:

1. validates required fields and supported enum values;
2. revalidates the embedded qualitative review against the target repository and pinned catalog;
3. checks coverage counts and one-to-one requirement results;
4. rejects incomplete, stale, duplicated, or inconsistent decision-ready models;
5. writes six HTML pages, the stylesheet, and `report-data.json`;
6. refuses to overwrite an existing report without explicit approval, while the adoption workflow
   refreshes the progress sections of a report it already generated after every recorded change;
   a refresh that would alter reviewed decision content is refused and recorded as stale.

Schema 1.3 adds the guided `console` block to the model: report id, answer generation, proposal
digest, objectives with the paths each needs, the selectable paths, and the recorded answers used for
prefill. Automated reports keep mode `full` and carry no controls.

The generated report has no third-party runtime dependencies. It can be opened directly from the
output directory and does not require a web server.

Guided reports are answerable but not approving. The console writes one
`acima-decisions-<reportId>-<page>.json` per page under decisions schema 1.0: report identity and
proposal digest, reviewer, decision date, page name, closed-set answers, and an optional `supersedes`
naming the earlier answers file it replaces. Answers from different pages merge by identity, so save
order cannot change the resulting scope, and the review answer is required once per adoption. The
workflow ingests the file with `acima adoption decisions --from <path>` and records the outcome in
`acima/evidence/events.jsonl`; approval remains a separate, digest-bound command. The product
rationale for this surface is in
[`docs/product/adoption-console.md`](docs/product/adoption-console.md).

## Boundaries and non-goals

The incumbent system deliberately does **not** include:

- a hosted dashboard, account system, or shared link service;
- a health score, grade, trend line, or benchmark comparison;
- data charts, graphs, sparklines, or decorative imagery; the evidence-grounded four-stage adoption
  path is a positional diagram and the module atlas is a navigational index, neither a trend nor a score;
- client-side search or filtering outside the module directory, or any sorting, saved views, or
  free-form data exploration;
- dark mode, theme switching, or user-selectable density;
- remote fonts, icon libraries, tracking, or third-party scripts;
- automatic adoption, editing, or approval from the report;
- a claim that a rendered report proves conformance;
- a claim that the report follows an external design system when that source is not present and
  consulted.

The current tables are intentionally native and horizontally scrollable on narrow screens. The
current status pills are text-first: known values are mapped to reader language, then classified for
colour. The current print treatment favors legibility and page-break avoidance over forcing every
disclosure open. The guided console is a closed-set answer sheet, not free-form data entry, and it
cannot approve anything. These are implementation choices of the incumbent system, not promises
about a hosted product.

## Maintenance rules

When changing the report:

1. Update `render_report.py` for structure and labels, `report-template.css` for visual change, and
   `decisions.schema.json` with the workflow when an answer or history field changes;
2. keep `references/90-html-outcome-reports.md`, both schemas, and this document aligned;
3. preserve the six-page reading path and the one-`h1`-per-page structure;
4. preserve the truth rules above, especially the distinction between coverage and conformance;
5. run the HTML report conformance tests and the documentation contract tests;
6. check the changed pages at desktop width, 320 CSS pixels, keyboard-only, print, and the console's
   empty, error, cancelled-save and no-script states;
7. treat screen-reader and real-browser zoom checks as manual release checks.

The report's visual identity is local to this repository. Do not replace it with a generic component
library or claim an external design lineage without adding that source to the checkout and actually
consulting it.
