# Changelog

All normative changes to the ACIMA standard. The machine-readable catalog is
[`tools/acima-spec/rules.json`](tools/acima-spec/rules.json); this file explains *why* it changed and
what an adopting repository has to do about it.

## Unreleased — the guided adoption console: answers, history and events

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.40.0 to 1.41.0. No adopting repository has to
change configuration, waivers or evidence.

### Why

The report became the owner's decision document but the owner still answered it in conversation, and
the rendered report showed neither history nor what had changed since the last review. A reviewer
returning to an adoption could not see which answer was in force, and a stage whose evidence had
disappeared still looked complete.

### What changed

- Guided reports carry a schema 1.3 `console` block — report id, generation, proposal digest,
  objectives, selectable paths and which stage requires each path. The Plan and Files pages render
  native radio and checkbox controls with visible labels; the Files page offers *Select all proposed
  files* as an explicit click, starts unticked, and prefills only from answers already recorded.
- *Save answers file* writes `acima-decisions-<reportId>-<page>.json` (download; in-place save is a
  feature-detected enhancement), *Copy answers* supports paste-back, and a no-JavaScript template on
  both pages keeps the report answerable in chat. Answering is never approval: the workflow still prints the
  separate, digest-bound approval command.
- The console is hardened for its real failure paths: a cancelled save writes nothing and says so, a
  blocked clipboard selects the answers instead, unreadable answer data disables the controls with an
  explanation, and an empty Files page refuses to save an empty answer set. Reviewer names are capped
  at 120 characters and normalized. Path rows wrap at 320 px, focus rings use the two-tone token pair,
  and every answer control meets the 44 px touch target.
- Revising a recorded answer from a page sets `supersedes` to the file that held it, so re-saving one
  page replaces exactly that file. A supersede no longer waives conflicts from other files: answers
  recorded elsewhere still have to be superseded one file at a time.
- A report page cannot hash its own bytes, so `reportSha256` and `decisionSha256` are optional in the
  decisions contract. The workflow fills them from the report it has verified on disk; supplied
  values are still checked strictly. A file names its `reportId` and proposal digest, so staleness and
  supersede rules are unchanged.
- Answers saved from different pages are partial files with the same identity. The workflow merges
  answers in force, so the order in which pages are saved cannot change the resulting scope, and the
  review answer is required once per adoption rather than once per file.
- The report now shows history after the plan and the answer controls, so the page reads in workflow
  order: an append-only `progressLog`, a decision log with the answers in force
  and superseded or stale answers as read-only history, *changed since your review* measured against
  the reviewed digests, and evidence integrity that renders a missing artifact as recorded but missing.
  These ride in the refreshable progress sections, so recording an answer never changes the reviewed
  decision content or the report's generation digest.
- `acima/evidence/events.jsonl` appends `report.generated`, `report.refreshed`, `report.stale`,
  `decisions.ingested`, `approval.recorded` and `stage.changed`. It is local, append-only and excluded
  from the revision an approval binds to.
- Automated adoption gets the same report and history but no answer controls: its consolidated review
  is unchanged.

### Adopting repositories

Nothing to change. A guided owner can now answer the report directly and save the file; an owner who
prefers chat can copy the answers instead. Existing hand-written decisions files remain valid.

## Unreleased — the adoption console loop: report identities and owner answers

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.39.0 to 1.40.0. No adopting repository has to
change configuration, waivers or evidence.

### Why

The report is the owner's decision document, but it lived at a fixed path and the owner's answers had
no machine-readable form. A regenerated report silently replaced a reviewed one, and answers given
in the page had to be retyped into commands, where the workflow could not tell a current answer from
an answer to an older proposal.

### What changed

- Reports live at `acima/report/<reportId>/`, one directory per generation, with a `report.json`
  sidecar recording the report id, generation, generation digest, live digest, decision digest and
  progress status. A regeneration creates a new identity instead of overwriting a reviewed report.
- `acima adoption regenerate --reason` is the supported repair for a report that cannot be refreshed.
  It returns the review to `awaiting_review`, invalidates prior approval receipts and marks earlier
  answers stale; it is refused without a reason.
- The report model is schema 1.2: `progressSections` pins the refreshable sections to
  `adoptionWorkflow` and `milestones`, and `adoptionWorkflow.currentStage` and `asOf` are required.
  A report generated under schema 1.1 still refreshes under the same two sections, because that is
  what its refresh already replaced; a model that declares other sections, or one that predates the
  progress contract (1.0), is refused and has to be regenerated.
- The owner answers the six pages and exports `decisions.json`, validated by
  `assets/decisions.schema.json` and ingested with `acima adoption decisions --from`. Ingestion
  refuses an answer bound to a different report identity and an answer that contradicts a recorded one
  unless the file explicitly supersedes that earlier file.
- Scope answers derive a draft scope with `authorization.explicit: false`; a required path left out
  defers and names the objective that needs it instead of approving an incomplete scope. Remediation
  answers are recorded intent only. The approval command remains the only consent.
- Only `decisions.json` is meant to be committed; the pages stay local. The report remains offline
  and WCAG 2.2 AA, and reading or answering it never starts a server.

### Adopting repositories

Nothing to change. Existing reports keep refreshing under their current identity, including reports
generated under schema 1.1; the next report the
workflow generates uses schema 1.2 and the new directory. Committing `acima/report/<reportId>/` is
optional, and only its `decisions.json` is intended for version control.

## Unreleased — keep the adoption report current automatically

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.38.1 to 1.39.0. No adopting repository has to
change configuration, waivers or evidence.

### Why

The HTML report is the decision document for the adoption, but it froze at generation. Once a stage
advanced — map approval, scope approval, enforcement, CI, remediation, verification — its Overview and
Plan pages still described the earlier state, so the owner had to ask for a fresh render or read the
persisted state to know where the adoption stood.

### What changed

- The workflow refreshes a generated report after every recorded progress change. The Overview and Plan
  pages now show the current phase, current stage, milestone completion, next action, and remediation
  or agent-guidance state without a prompt.
- A refresh may replace only `adoptionWorkflow` and `milestones`. The report layer compares a decision
  digest and refuses a refresh that would change reviewed decision content, so the reviewed proposal
  cannot silently become a different document.
- The generation digest recorded at report review remains the review identity; a separate live digest
  tracks the files on disk and detects edits made outside the workflow. A refresh failure is recorded as
  stale with its reason and never blocks the workflow.
- The workflow section of the model now carries the current stage, an as-of timestamp and the
  remediation and agent-guidance summaries, and milestones are derived from recorded stages instead of
  being fixed at generation.
- The report contract, orchestration guidance and design record state that the agent keeps the report
  current and never asks the owner to regenerate it.

### Adopting repositories

Nothing to change. Resume the engagement with the updated skill and the existing report keeps itself
current. No repository configuration, evidence or assessment changes are required.

## Unreleased — omit empty gap briefing

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.38.0 to 1.38.1. No adopting repository has to
change configuration, waivers or evidence.

### Why

An approved map with no recorded findings still rendered a “What to know before the map” section
with an empty state. That made a clean map look as if a gap had gone missing, and contradicted the
documented fallback behavior.

### What changed

- The proposal omits the gap briefing entirely when there are no findings, no explicit
  `plainLanguageGaps`, and no unresolved map risks.
- Added a regression test for an approved map with no recorded gaps. It confirms the gap section and
  its empty-state copy are absent while the map still renders.

### Adopting repositories

Regenerate the HTML report from the updated skill. No repository configuration, evidence or assessment
changes are required.

## Unreleased — plain-language gap briefing

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.37.1 to 1.38.0. No adopting repository has to
change configuration, waivers or evidence.

### Why

A reader who asked for the gaps behind a module map got a useful result: plain language, ranked by
real risk, with a cost and a fix for each item. The generated report instead led with the map's own
vocabulary. That made the proposal harder to act on for the product owner it is written for.

### What changed

- The proposal page now opens with **What matters before the map**: at most six gaps, ordered high,
  medium, then low risk. Each says what it could cost this product and what fixing it would involve.
  Internal rule and requirement ids are omitted; the Findings page keeps the evidence.
- The report model accepts optional `plainLanguageGaps` items so the assessment agent can write the
  real consequence and remedy. When absent, the renderer ranks recorded findings and unresolved map
  risks instead of inventing content.
- Reader-facing labels now use **parts of the product**, **files**, **promises**, **connections** and
  **the map at a glance** instead of module, atlas and ownership-record language. Status labels are
  accepted, needs changes, needs an owner, set aside, already documented and rejected.
- Finding cards say **What it could cost**, **What fixing it involves**, **Required or optional**, and
  **Where this came from**. The Evidence page uses the same plain vocabulary.
- The schema, report contract, design record and skill guidance document the new briefing and labels.

### Adopting repositories

Regenerate the HTML report from the updated skill. No repository configuration, evidence or assessment
changes are required.

## Unreleased — ice-blue report palette

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.37.0 to 1.37.1. No adopting repository has to
change configuration, waivers or evidence.

### Why

The report's paper-and-red dossier palette no longer reflected the product's blue/slate identity.
The replacement needed to stay readable in long evidence tables and make module states legible at
atlas scale without turning the report into a dashboard.

### What changed

- The token palette is now anchored on `#3B82F6` primary blue, `#60A5FA` sky, `#1F2937` slate ink and
  `#F0F9FF` ice paper. The remaining values are derived slate, ice and semantic tints.
- The brand block, active navigation, decision edge, current path marker and focus system now use the
  blue family. The primary action uses the deeper blue so white text still clears 4.5:1.
- Links use `#1D4ED8`, not the lighter brand blue, to keep body-text contrast above 4.5:1.
- Status pills use tinted semantic surfaces with dark text; the module atlas uses blue for accepted,
  sky for modified, pale ice-blue for needs-owner, slate for deferred and declared, and red only for
  rejected.
- The contrast suite now locks the four base colours and checks the new text, focus, and pill pairs.

### Adopting repositories

Regenerate the HTML report from the updated skill. No repository configuration, evidence or assessment
changes are required.

## Unreleased — visualize large module maps

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.36.5 to 1.37.0. No adopting repository has to
change configuration, waivers or evidence.

### Why

A large repository can produce hundreds or thousands of proposed modules. A raw module table or JSON
dump is unreadable at that size: readers cannot see the overall review state, find a named module,
or reach one module's paths and evidence without scanning everything.

### What changed

- The proposal page now renders an ownership atlas with one tile per module, grouped by review state
  and linked to the module's directory row. A legend and metrics state the distribution in text.
- The module directory exposes name, status, responsibility, path and contract counts, dependency
  count, and a native disclosure with full paths, dependencies and evidence.
- Search covers module names, ids, paths, responsibilities and dependencies. Status buttons filter by
  review state, the result count is announced, and a no-match state is explicit.
- Search and filtering are progressive enhancement: the inline script is emitted only with a module
  map, and without JavaScript every module remains in document order for browser Find.
- The directory has a bounded scroll area with a sticky header on desktop and mobile, so a thousand
  rows do not make the page enormous. The atlas wraps to the available width and is suppressed in
  print.
- Atlas links use stable `#module-<id>` anchors; following one reveals the row and opens its record.
- The atlas is an index, not a health score or ranking. Tile order and position carry no quality claim.

### Adopting repositories

Regenerate the HTML report from the updated skill. No repository configuration, evidence or assessment
changes are required.

## Unreleased — plain-language report decisions

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.36.4 to 1.36.5. No adopting repository has to
change configuration, waivers or evidence.

### Why

Owners were asked to adjudicate ACIMA role names, path classifications and internal rule titles. A
non-expert cannot answer those questions, and presenting them as decisions made the report feel like
a terminology quiz. Findings were also mixed in with genuine owner choices.

### What changed

- Module decisions now ask whether an area is a separate part of the product with its own rules and
  data, not whether it is an “ACIMA module.”
- Path decisions are limited to unresolved production code and composition/startup areas. Routine
  test, tooling, documentation, generated and already-mapped paths are classified as agent work and
  do not become owner questions.
- Findings stay findings. Required fixes are labelled “no owner decision” and remain recommended
  work; only business ownership, exceptions, merge blocking and spending effort become questions.
- Every owner decision now shows the practical meaning, evidence gap, recommended option, effort,
  consequence of leaving it open, and what it blocks.
- The scope decision recommends a first bundle and explains the cost of CI blocking, local-only
  enforcement and proposal-only options.
- The proposal page links to the Plan page for decision briefs instead of duplicating a raw
  accept/modify/reject table.
- The unrelated notification-feature question is no longer part of the report's decision list.

### Adopting repositories

Regenerate the HTML report and proposal from the updated skill. No repository configuration or
evidence changes are required.

## Unreleased — show the adoption path in the proposal

**Skill and report change only.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.36.3 to 1.36.4. No adopting repository has to
change configuration, waivers or evidence.

### Why

The proposal page led with the module map and long technical sections. A reader who did not already
know ACIMA had to assemble the current state, the proposed change and the eventual operating model
from prose. That raised cognitive load before the decision.

### What changed

- The proposal page opens with a four-stage adoption path: No ACIMA, Foundation, Implemented and
  Continuous.
- The current marker is derived only from recorded milestones; Continuous is a destination, not a
  certification.
- The module map and ownership details now follow the plain-language current and proposed state.
- The path is labelled in text, works without colour, and is the report's single diagrammatic
  exception to the no-charts rule.

### Adopting repositories

No action. Re-render the proposal to show the path; a report rendered before this change does not
require a new assessment.

## Unreleased — turn unresolved dispositions into decision briefs

**Skill change only.** The catalog, standard version, rule ids, levels, severity and claim semantics
are unchanged; `acima-adoption` moves from 1.36.2 to 1.36.3. No adopting repository has to change
configuration, waivers or evidence.

### Why

An execution asked the repository owner whether 11 unresolved rule ids were “acceptable.” The owner
had not been taught the catalog and could not make that classification. The agent had also not
translated the unknowns into effort, risk or lost claims, so the question was unanswerable in practice.

### What changed

- Unresolved dispositions must be presented as decision briefs: practical meaning, evidence gap,
  recommended option, effort and consequence.
- Agents must resolve code-traceable unknowns themselves and group only genuine owner decisions.
- The owner decides whether to spend effort or accept a limited claim; an accepted limitation remains
  `insufficient_evidence` and never becomes conformance.
- The owner is never asked whether a catalog rule id is “acceptable.”

### Adopting repositories

No action. Re-run the installed skill's guidance if it previously presented unresolved rule ids as a
questionnaire.

## Unreleased — keep evidence placement out of owner decisions

**Skill change only.** The catalog, standard version, rule ids, levels, severity and claim semantics
are unchanged; `acima-adoption` moves from 1.36.1 to 1.36.2. No adopting repository has to change
configuration, waivers or evidence.

### Why

An execution treated a set of cross-cutting qualitative-review citations as 22 owner decisions before
the six-page proposal. The validator does not require rule evidence to be path-derived from a unit,
and rules covering the workspace, a layer, an absence or an external artefact legitimately remain
repository-scoped. Asking the owner to adjudicate that bookkeeping delays the proposal and obscures
the few choices that are genuinely architectural.

### What changed

- The module-map checkpoint is explicitly about boundaries and path classifications, not a per-rule
  unit worksheet.
- Mechanical citation fixes are the agent's work; workspace-level evidence is recorded at repository
  scope with its limitation rather than assigned to a synthetic unit.
- An owner is asked only about a genuine boundary or ownership choice, with a recommended default
  and consequence.
- The six-page report is not blocked on path-derived evidence when `validate-review` reports
  decision-complete coverage and the map review is decision-ready.

### Adopting repositories

No action. Re-run the installed skill's guidance if it previously stopped to ask for per-rule unit
assignments before the proposal.

## Unreleased — traceable qualitative gaps

**Skill change only.** The catalog, standard version, rule ids, levels, severity and claim semantics
are unchanged; `acima-adoption` moves from 1.36.0 to 1.36.1. No adopting repository has to change
configuration, waivers or evidence.

### Why

A qualitative review could report a gap count by theme without every item remaining tied to a
catalog rule. Schema 1.1 findings could also cite no rule, or a rule that is not in the pinned
catalog, while the renderer treated the item as a grouped problem. That made it possible to present
an unlinked finding or an unreconciled count as if it belonged to the assessment.

### What changed

- The review validator now returns `gapRegister` (every valid `gap` and `insufficient_evidence`
  disposition with its rule, level, title, rationale and evidence references) and
  `unresolvedRules`.
- Schema 1.1 report findings must name at least one current catalog rule, and unknown rule ids are
  rejected by the renderer. Schema 1.0 remains accepted for legacy reports.
- Rendered finding details show the internal requirement reference after the plain-language
  explanation.
- The skill requires gap summaries to enumerate the register and to reconcile every theme count
  with the distinct rule ids beneath it.

### Adopting repositories

No action. A report that previously rendered with an unlinked schema 1.1 finding will now be
rejected; attach that finding to its catalog rule, or remove it if it is not a requirement finding.

## Unreleased — one enforceable waiver contract

**Enforcement and skill change.** The catalog, standard version, rule ids, levels, severity and claim
semantics are unchanged; `acima-adoption` moves from 1.35.0 to 1.36.0. Preflight, status and all four
enforcers now apply the same waiver governance and path-glob rules.

### Why

Preflight and the gates disagreed about what a valid waiver was. An `unassigned` owner or a malformed
fingerprint could pass a gate that preflight rejected; strict and loose date parsers disagreed about
expiry; Python let `*` cross `/`, Go had no recursive wildcard, and TypeScript and .NET interpreted
`**` differently. The same exception could therefore suppress different findings depending on the
language.

### What changed

- `owner: unassigned` and fingerprints that are not exactly `sha256:<64 lowercase hex>` are rejected
  by every enforcer as `G001`.
- `expires` and `reviewedOn` are strict `YYYY-MM-DD` dates. `reviewedOn` cannot be in the future or
  after `expires`; expiry is inclusive through the expiry date and evaluated on the UTC date.
- `path:` globs use one grammar everywhere: `*` matches within one segment, `?` matches one
  non-separator character, and `**` is a whole segment matching zero or more segments. Malformed
  patterns are `G001`.
- A shared conformance fixture drives the same governance and glob cases through preflight, status
  and the Python, TypeScript, Go and .NET enforcers.

### Adopting repositories

Run preflight and the gate after upgrading. Replace every `unassigned` owner, make accepted
fingerprints canonical, and rewrite date fields rejected as non-ISO. Review `path:` waivers that
relied on the old Python `*` crossing directories or on language-specific `**` behaviour: use `**`
explicitly for recursive matches, otherwise the finding is expected to return.

## Unreleased — optional parameters are prohibited inputs

**Catalog change.** `D011` and `D012` are now `error` rules. Their `severityRatchet` entries are
removed: there is no 2.0.0 migration window, and an optional or defaulted parameter on a
module-owned constructor, method or function is prohibited. Rule ids, levels, summaries and the
56-rule catalog are otherwise unchanged.

### Why

ACIMA already said required inputs must be explicit, but a warning allowed a repository to claim
adoption while retaining the second construction or invocation path the rule exists to prevent. A
owner decision that the input is required cannot be optional at the gate. The prohibition applies to
module-owned behavior units; required nullable parameters without defaults, contract members,
framework entry points, generated code and test/tooling units remain governed by their documented
scope. A genuine compatibility exception remains a named, scoped, owned and expiring waiver under
`G001`/`G002`.

### Adopting repositories

Run the Python or TypeScript enforcer and fix every `D011`/`D012` finding: require the parameter and
move the value to its owner, split the operation, use an explicit options or policy object, or record
the narrow waiver. Go and .NET still report both rules `executed: false` in this revision, so their
full claims require manual evidence.

## Unreleased — human-comprehensible adoption communication

**Skill change only.** The catalog, standard version, rule ids, levels, severity and claim semantics
are unchanged; `acima-adoption` moves from 1.20.0 to 1.21.0. No adopting repository has to change
configuration, waivers or evidence.

### Why

The skill could explain architecture well, but its templates and examples still let internal rule,
requirement and evaluation identifiers stand in for the explanation. A reader who did not know the
catalog had to decode codes before deciding whether a finding mattered.

### What changed

- The skill now requires every user-facing interaction to explain the meaning, observed behaviour,
  consequence, recommended action and confidence before any internal reference. This covers
  assessments, findings, recommendations, plans, approvals, progress, reports and spoken output.
- Rule meanings are resolved from the catalog, principles and requirements from the standard, and
  evaluation criteria from the active rubric. Unknown identifiers are reported as an internal
  reporting defect; the agent must not invent a meaning.
- The generated adoption summary now presents semantic finding titles, explanations, impact,
  evidence, remedies and confidence. Rule IDs and fingerprints remain in machine-readable evidence
  and the technical appendix.
- Report, proposal, status and communication templates no longer use rule IDs as primary labels.
  Worked examples cover value ownership, module boundaries, scoped requirement identifiers,
  semantic value review, approval requests, unresolved checks and spoken output.

### Adopting repositories

No migration is required. Existing reports remain readable; newly generated summaries explain the
same evidence in more accessible language. Technical traceability is unchanged.

## Unreleased — meaningful value ownership

**Normative and enforcement change.** `ACIMA-A006` is repurposed without adding a rule or changing its
identity: severity stays `warning` at L3, ratcheting to `error` at 2.0.0. Existing fingerprints,
waivers and baselines remain valid.

### Why

A006 detected named operational literals but could not distinguish a mutable declaration from an
immutable one, an incidental literal from meaningful policy, or equal values with different owners.
It also had no review model for semantic consolidation or constant-versus-configuration choices.

### What changed

- Chapter 14 now requires one identifiable immutable declaration at the highest appropriate ownership
  boundary when a value's meaning is shared. It defines immutable bindings versus immutable values,
  receiving-identifier data flow, semantic identity, consolidation, explicit propagation, and the
  boundary between code-owned constants, deployment configuration, runtime configuration and secrets.
- A006 now scans implementation, adapter and host roles in Python and TypeScript for meaningful inline
  literals, mutable declarations, same-module duplicate declaration candidates, and configuration or
  secret candidates. Every A006 finding is classified as a `candidate`.
- Semantic equivalence, the highest common owner and the configuration category remain review
  decisions. The enforcers do not refactor source and do not merge across module boundaries.
- Go, .NET and Java continue to report A006 `executed: false` and require source-cited manual
  evidence. The expanded workflow and its distinction table are in the adoption skill.

### Adopting repositories

Review existing A006 waivers and baselines: the rule meaning is broader even though the identifier,
fingerprint algorithm and severity are unchanged. Treat new findings as review candidates. Do not
consolidate equal literals or matching names automatically.

## 1.18.0 — guided adoption experience

**Skill change only.** The catalog, standard version, rule ids, levels, severity and claim semantics
are unchanged; `acima-adoption` moves from 1.17.0 to 1.18.0. No adopting repository has to change
configuration, waivers or evidence.

### Why

The adoption skill was accurate but not guided. The routing table started with `acima.py assess`
while Step 0 said preflight always ran first; `status` inferred progress from file existence (an
adoption plan blocked nothing technically, yet was recommended before measurement; a workflow that
mentioned ACIMA counted as a gate; a manual-evidence file counted as a claim); and `SKILL.md` had
grown to 620 lines of per-rule detail. A first-time user had to understand ACIMA, their own
architecture and the command set before getting value.

### What changed

- **One workflow.** Assessment (preflight first, then the read-only fit analysis), proposal,
explicit authorization, approved implementation, verification. `docs/commands.md` and §9.9 use the
same order.
- **Evidence-based status.** Seven states rendered in plain English. Calibration compares the
manifest pin with the catalog; a baseline must parse with `sourceFiles > 0`, an execution map and a
findings list; a workflow is read for a real gate invocation and distinguished from an observed run;
the claim is computed with `acima.py claim`; a slice requires a falling measured count. Optional
documents never block and never appear in the next action.
- **Actionable next step.** Status prints one action with why, done-condition, command and whether
approval is required; write actions are proposed, never performed.
- **A decision document.** The proposal has nine sections: recommendation, application discovered,
what ACIMA adds, evidence-grounded benefits, recommended scope, exact changes, tradeoffs, next steps
and one approval question supporting partial approval.
- **Progressive documentation.** Assessment brief → proposal → implementation guide → verified
handoff; persistent documents only when approved or requested.
- **Execution contexts.** Checkout, copied/installed skill using `vendor/`, and a separate target
repository are distinguished, with the correct command form for each.
- **Compact controller.** `SKILL.md` is 303 lines (from 620). Per-rule correction detail, effect
review and lifecycle guidance live in `references/70-corrections.md`; phase-response examples live in
`references/80-reporting.md`.
- **Tests.** `conformance/test_adoption_experience.py` covers 14 scenarios: read-only default,
optional artifacts, mention-only and configured and observed gates, rejected zero-source baselines,
manual evidence that is not a claim, expired evidence, fix-as-plan, untouched assessment, returning
user, unsupported language, copied-skill availability, and contract/compactness.

## 1.9.0-draft.1 — conformance integrity, consent, and application-wide execution ownership

**Version change:** MINOR. `1.8.0-draft.1` → `1.9.0-draft.1`. Two manual rules added; no rule
removed, renumbered or weakened. The catalog total goes from 53 to 55. Automated rules stay at 41;
manual rules go from 12 to 14. There is no new automated rule, profile or conformance level.

### Why

Three gaps remained after 1.8. First, P8.1 required every rule at the declared level to *execute in
CI*, while the conformance model accepted manual evidence for rules that cannot be executed. The two
statements described different standards. Second, the claim layer trusted an execution map that
reported a catalog-manual rule as `executed: true`, so an unsupported check could pass without
evidence. Third, P15 owned externally visible effects but not the state mutation, consistency boundary
and telemetry decisions that surround them, and the adoption skill described artifacts as mandatory
without a single, explicit authorization phase.

### Normative changes

- **P8.1 is rewritten** to require every required rule to be *accounted for*: automated rules execute
  through their designated enforcement mechanism, manual rules require accepted, current,
  repository-scoped evidence, and a manual rule is never counted as executed. Missing or expired
  evidence, an unsupported check reported as passing, or an incomplete execution map cannot produce
  full conformance. Chapter 8 §8.4, §8.6 and §8.9 state the same rule.
- **`ACIMA-A014` — Telemetry conceals or alters business behaviour.** L3, `error`, manual. Logging,
  metrics and telemetry observe behaviour; they do not make a business decision, swallow a failure,
  compute the value they report or replace a required audit record. Operational diagnostics, business
  events and audit records are distinguishable by owner and purpose (chapter 6 §6.10).
- **`ACIMA-A015` — Unowned consistency boundary.** L3, `error`, manual. A multi-step state change or
  transaction has one identifiable owner and a declared guarantee on return. Atomic, recoverable,
  compensating and reconciled are all valid; an unowned gap described as atomic is not (chapter 6
  §6.5.3).
- **P15 is extended** with state-mutation ownership (`P15.5`), consistency-boundary ownership
  (`P15.6`) and observability (`P15.7`). P15.5 distinguishes architectural state ownership from
  ordinary local mutation and reuses `A001`/`A009` rather than duplicating them.

### Deliberately unchanged

No new automated rule, detector or gallery fixture was added. Whether telemetry replaces a business
decision and who owns a consistency guarantee are semantic and design questions; a heuristic that
guessed would be worse than an honest manual rule. Retries, idempotency, transactions, cancellation
and all-or-nothing atomicity remain conditional on the design. Naming is not expanded: no new naming
rule, analyzer or subjective violation was introduced. The P4/P7 dependency, value and lifecycle
obligations were reviewed and extended in prose where the existing rules already covered the
concern; no duplicate rule IDs were created.

### Claim-layer hardening

The claim model now treats a catalog-manual rule reported as `executed: true` as unsupported: the
rule is listed in `unsupportedExecution`, still requires repository-scoped evidence, and keeps the
result `PARTIAL ASSESSMENT` until that evidence is accepted. A catalog rule with an unknown
`automation` value is an invalid assessment. This is what makes “a clean automated run cannot establish
full conformance by itself” executable rather than aspirational.

### Adoption consent

The adoption skill is **1.17.0** and now implements five phases: assessment, proposal, explicit
authorization, approved implementation, and verification and handoff. Authorization is its own phase;
approval is scope-specific and partial approval is supported. Adoption plans, communication plans,
status dashboards and summaries are optional unless the approved scope includes them or the owner asks
for them. The skill, its consent reference and chapter 9 §9.9 agree, and `test_consent_workflow.py`
asserts the phase structure, the optional-artifact rule and the read-only default.

### Verification

Executed in this change: `python conformance/test_claim_model.py`, `test_rule_catalog.py`,
`test_consent_workflow.py`, `test_documentation_contract.py`, and the full `conformance/run.py`
routine, whose results are reported in the change record. The gallery expectations are unchanged
because no automated rule was added; the Python, TypeScript, Go and .NET execution maps carry both
new IDs as `executed: false` with a reason, and `coverage.json` records 14 manual rules for Python and
TypeScript and 32 not-executed rules for Go and .NET.

## 1.8.0-draft.1 — owned effects, retries, transactions and truthful outcomes

**Version change:** MINOR. `1.7.0-draft.1` → `1.8.0-draft.1`. Five manual rules added; no rule removed,
renumbered or weakened. The catalog total goes from 48 to 53. Automated rules stay at 41; manual
rules go from 7 to 12. There is no new automated rule, profile or conformance level.

### Why

ACIMA could describe who owned data, configuration, contracts and dependencies, but not who owned a
side effect. A host could open a transaction across two modules, a read-shaped method could write an
audit record, a retry could duplicate a charge, and a timeout could be reported as a clean failure —
and every structural rule could still pass. Adding nine universal rules would have made the standard
more prescriptive without making it more correct. This release instead adds a thin principle, one
extension to P1, five manual rules and a conditional applicability model.

### Added normative requirements

| Requirement | Rule | Level | Automation |
|---|---|---|---|
| Business behaviour must be visible at a boundary operation | `ACIMA-C008` | L2 | manual |
| Every externally visible effect has an owner and execution boundary | `ACIMA-A010` | L3 | manual |
| The effect owner must state retry, duplicate, consistency, partial-completion and cancellation semantics where they apply | `ACIMA-A011` | L3 | manual |
| The effect owner must report success, failure, unknown and partial outcomes truthfully | `ACIMA-A012` | L3 | manual |
| A critical effect must have evidence proportionate to its failure impact | `ACIMA-A013` | L3, warning | manual |

P1.7 covers business-behaviour visibility. P15 Owned Effects covers the effect obligations, extending
P1, P7 and P8 without replacing them. Chapter 6 adds §6.2.1 retry ownership, §6.3.1 idempotency and
duplicate execution, §6.5.1 transaction ownership, §6.5.2 atomicity and recovery, and §6.9
cancellation and partial completion. Chapter 5 adds effect and outcome semantics to contract review.

### Deliberately conditional

This release does **not** require universal retries, idempotency keys, transactions, atomicity,
cancellation parameters or recovery evidence. Each obligation is triggered by the design:

- retry rules apply when retry behaviour exists or is part of the operation's execution contract;
- duplicate handling applies when duplicate execution is possible and could affect correctness;
- transaction and atomicity rules apply when the consistency contract needs them;
- cancellation applies where the environment supports it and the operation is long-running or
  externally cancellable;
- evidence applies in proportion to the effect's criticality.

"Not applicable" is a reviewable outcome; it is not a violation, and it is not silently treated as
a pass. ACIMA still does not mandate pure functional programming, universal immutability, a
particular application-service pattern, a logging or transaction framework, distributed locks or
global transactions.

### Enforcement classification

All five rules are `automation: "manual"` in every profile. The portable enforcers report them
`executed: false` with a reason and emit no fabricated findings. There are no gallery fixtures,
because a fixture would only prove that a heuristic fires, not that ownership or outcome
correctness was established. A full claim needs a repository-scoped entry in
`.acima/manual-evidence.json`; a waiver cannot substitute for the evidence.

The Python and TypeScript execution maps now contain all 53 rules, with 12 `executed: false`. The
Go and .NET maps carry the same catalog entries and coverage adds the five IDs to their 30
not-executed rules. Java remains profile-only, with no enforcer.

### Documentation and adoption

The normative chapters, vocabulary, conformance checklist, catalog pages, language index, status and
product contract are updated. A new guide, `docs/guides/effects-and-atomicity.md`, explains the
ownership question, the conditional matrix, retry/duplicate behaviour, transaction and recovery
choices, truthful outcomes, cancellation and evidence. The adoption skill is **1.16.0**, pins the new
catalog hash and teaches the reviewer to separate confirmed defects, suspected defects and
insufficient evidence. Its manual-evidence template now names all twelve rules.

### Verification

Executed in this change:

- `python examples/python/tools/acima_arch.py --root examples/python --config acima.config.json
  --format json` — exit `0`, zero findings, 53 execution entries, 12 `executed: false`, 27 source files.
- `node examples/typescript/tools/acima-arch.mjs --root examples/typescript --config
  acima.config.json --format json` — exit `0`, zero findings, 53 execution entries, 12
  `executed: false`, 12 source files.
- `py -3 conformance/run.py` — topology, Python, TypeScript, Go, .NET and the tools tests all
  pass. Gallery results: Python 41 rules / 54 findings, TypeScript 41 / 53, Go 23 / 34,
  .NET 23 / 37. Each clean example reports 53 execution entries with 30 `executed: false`
  (18 automated gaps plus 12 manual rules).
- Go and .NET were executed against this host's installed toolchains (`go1.27.3`, .NET SDK
  11.0.100-rc.3). The Go gallery exposed a Windows-only path-separator defect: `byDir` used
  `filepath.Dir` (backslashes) while import resolution produced slash paths, hiding every
  cross-unit edge. The key is now normalized with `filepath.ToSlash`; the gallery matches all
  23 expected rules.
- The Windows runner also exposed a test bug in `test_package_matching.py`: it asserted that
  no finding could mention `Grpc.Tools`, although the expected `D004` finding names that
  package. The assertion is now scoped to the package-derived `D002`/`D008` edges it was
  meant to protect.
- All 26 directly executable conformance test files pass; the catalog, claim, documentation,
  skill bundle, composition, explicit inputs, functional capture, lifecycle, naming, values
  and adoption-safety tests were exercised individually.
- `py -3 tools/bundle_skill.py --check` — 43 vendored files match their sources.
- `py -3 skills/acima-adoption/scripts/preflight.py --project . --deep --format text` —
  `READY`; all four language examples are clean, the catalog hash and counts match the skill
  pin, and the manual IDs are checked against the catalog.

Java remains profile-only, with no reference enforcer. The twelve manual rules are not executed
by any reference enforcer; they require repository-scoped evidence. Source-level analysis still
does not prove runtime isolation, framework behavior or semantic correctness. These limitations
are reported in `docs/status.md` and the final implementation report.

## 1.7.0-draft.1 — intent-revealing naming and semantic clarity

**Version change:** MINOR. `1.6.0-draft.1` → `1.7.0-draft.1`. Three rules added; no rule removed,
renumbered or weakened. The catalog total goes from 45 to 48 and the portable set from 39 to 41.

### Why

A dependency graph and contract surface can be correct while the names on it conceal the design.
`OrderHelper`, `ProcessOrderData` and `timeout` satisfy casing rules and still force a reader into
the implementation to learn what owns a responsibility, what a method changes, and what a number
measures. Formatting consistency is not semantic clarity.

This release makes naming intent a first-class architectural obligation. It does **not** define a
universal casing guide, and it does **not** claim that static analysis can prove a name is good.
Names must communicate responsibility, operation and outcome, meaningful values and units,
side effects, domain terms and architectural ownership in the conventions of the target language.

### Added rules

- **`ACIMA-N001` — Non-idiomatic type identifier.** L3, `warning`. Python class names use
  `PascalCase`; TypeScript `class`, `interface`, `type` and `enum` names use `PascalCase`. The finding
  is a convention candidate, not proof that the name communicates intent.
- **`ACIMA-N002` — Generic responsibility name.** L3, `warning`. A type declaration whose name is an
  exact placeholder (`Helper`, `Manager`, `Processor`, `Utility`, `Common`, `Base`, `Default`,
  `Generic`, `Handler`, `Service`, `Provider`, `Factory`) or carries a generic suffix is a candidate
  for review. A precise name inside a narrow abstraction is not automatically a defect.
- **`ACIMA-N003` — Semantic naming clarity review.** L3, `warning`, **manual**. Responsibility,
  side-effect transparency, boolean polarity, units, unexplained abbreviations, domain terminology,
  contextual clarity and lifecycle/version names that encode incidental history.

All three are `warning`; there is no severity ratchet. A rename is not a mechanical fix, and a
subjective preference must never be reported as a proven violation.

### Decision model and scope

Chapter 18 separates naming **syntax** from naming **quality**. Construct-specific expectations cover
types, interfaces, operations, booleans, constants, variables, parameters, collections, enums,
events, commands, queries and exceptions. The chapter also defines responsibility and side-effect
transparency, positive boolean naming, units, abbreviations, domain consistency, contextual
redundancy, boundary names, generated/legacy exceptions, implementation identity versus lifecycle
history, and the language-specific profiles.

Existing requirements are reused rather than duplicated: `A006` remains the explicit values and
configuration rule, `C002` the collection shape rule, `D009` visibility, and `A007`–`A009` lifecycle
and state ownership. Naming must not add a second, conflicting owner for those concerns.

### Scope and enforcement

- **Python** checks class declarations for `PascalCase` and generic class names.
- **TypeScript** checks `class`, `interface`, `type` and `enum` declarations for `PascalCase` and
  generic type names.
- Both are syntax-level **candidates**. They do not evaluate method behavior, variable meaning,
  domain terminology, units, boolean polarity or side effects.
- **Go, .NET and Java** carry the catalog entries and report the naming rules `executed: false`;
  Java has no reference enforcer. Those profiles require recorded manual evidence.
- `N003` is manual everywhere. A clean run does not establish semantic naming quality.

### Documentation and fixtures

Chapter 18 and P14 define the normative principle and requirements. `docs/rules/naming.md` defines
the three rules; chapters 1, 8, 9 and all five language profiles were updated. Controlled violations
live in `examples/{python,typescript}/violations/naming_conventions.*`; positive fixtures live in
`conformance/fixtures/naming/` and cover idiomatic types, a focused responsibility, a positive
boolean and unit-bearing names. `conformance/test_naming.py` exercises both galleries and both
fixtures. The skill is **1.15.0** with the new hash and 48/41 counts.

### Verification

`conformance/run.py python typescript topology tools` and `conformance/test_naming.py` pass; the
Python and TypeScript galleries fire all 41 portable rules. Go and .NET remain unverified because
their toolchains are absent. No static evidence establishes semantic naming quality, side-effect
clarity or domain consistency; those remain manual-review obligations.

## 1.6.0-draft.1 — lifecycle and state ownership

**Version change:** MINOR. `1.5.0-draft.1` → `1.6.0-draft.1`. Three rules added; no rule removed,
renumbered or weakened. The catalog total goes from 42 to 45 and the portable set from 36 to 39.

### Why

A repository could satisfy import, contract, configuration and even composition rules while leaving
instance lifetime implicit. A stateless service was rebuilt for every request because transient was
the container default; a singleton kept the first request's context; a shared cache had no owner,
key space or eviction policy. The dependency graph looked correct while the runtime graph was not.

This release makes lifetime and state ownership architectural obligations. It does **not** require
singleton registration. The governing rule is the longest appropriate lifecycle that preserves
correctness, isolation, concurrency safety and resource ownership. Transient remains valid for
independent identity, isolated mutable state, short-lived resources and operation scope.

### Added rules

- **`ACIMA-A007` — Unnecessary transient lifetime.** L3, `warning`, ratcheting to `error` at
  `2.0.0`. A stateless application service registered transient should be shared at the longest
  appropriate lifetime. Domain objects, value objects and unregistered classes are not evaluated.
- **`ACIMA-A008` — Captive scoped dependency.** L3, `warning`, ratcheting to `error` at `2.0.0`. A
  shared/singleton component must not directly capture a scoped dependency. The correction is a
  shorter consumer lifetime, an operation parameter or an explicit factory — not a service locator.
- **`ACIMA-A009` — Shared mutable state without ownership.** L3, `warning`, ratcheting to `error` at
  `2.0.0`. A shared component must not own a mutable container without an explicit owner, isolation
  boundary, concurrency policy and disposal or expiration rule.

### Decision model and scope

Chapter 17 defines a framework-independent model: stateless and thread-safe → shared; request- or
transaction-bound → scoped; tenant-bound → explicit tenant-owned lifecycle; independent identity →
transient; resource-owning → lifecycle appropriate to the resource; shared mutable state → explicit
ownership. R1–R7 cover sharing, justification, behaviour/state separation, ownership, cross-scope
leakage, lifetime compatibility and resource ownership.

A singleton is process-local. The release does not introduce distributed locking, cluster-wide
coordination or a central state store, and does not treat in-memory sharing as globally consistent.

### Scope and enforcement

- **Python** reads explicit host registrations (`register(... lifetime=...)`,
  `add_singleton`/`add_scoped`/`add_transient`). `A007` detects a transient class with no instance
  state; `A008` detects a shared class whose constructor annotation names a scoped registration;
  `A009` detects a shared class initialising a list/dict/set or container field.
- **TypeScript** reads `register(Class, { lifetime })` and `addSingleton`/`addScoped`/`addTransient`,
  using the same class-body and constructor-dependency checks.
- Both are syntax-level **candidates**. They do not resolve a container, decorators, module-level
  singletons, factory closures, framework proxies or runtime graphs, and they do **not** prove thread
  safety, tenant isolation or resource cleanup.
- **Go and .NET** carry the catalog entries and report `executed: false`; **Java** has no reference
  enforcer. Those profiles require recorded manual evidence.
- Legitimate transient domain objects, immutable objects, framework-required lifetimes, correctly
  scoped services, synchronised shared state and properly managed resources remain permitted.

### Documentation and fixtures

Chapter 17 defines the model, the captive-dependency and tenant-isolation analysis, resource
ownership, distributed limits, language profiles, exceptions and enforcement limits. P4.13–P4.15
were added; chapters 3, 6, 8, 9, all five language profiles and the rule pages were updated.

Controlled violations live in `examples/{python,typescript}/violations/lifecycle_registration.*`;
positive fixtures live in `conformance/fixtures/lifecycle/` and cover a shared stateless service, a
legitimate transient value, correctly scoped context and an explicitly owned cache. The gallery and
positive fixtures are exercised by `conformance/test_lifecycle_ownership.py`. The skill is
**1.14.0** with the new hash and 45/39 counts.

### Verification

`conformance/run.py python typescript topology tools` and the lifecycle test pass; the Python and
TypeScript galleries fire all 39 portable rules. Go and .NET remain unverified because their
toolchains are absent. No static evidence establishes thread safety, tenant isolation, resource
cleanup or the runtime container graph; those remain manual-review obligations.

## 1.5.0-draft.1 — functional composition and dependency visibility

**Version change:** MINOR. `1.4.0-draft.1` → `1.5.0-draft.1`. Two rules added; no rule removed,
renumbered or weakened. The catalog total goes from 40 to 42 and the portable set from 34 to 36.

### Why

A function could satisfy constructor injection and still capture a repository from module scope, or
return a handler with a dependency pre-bound inside the component. The signature looked complete;
the dependency graph was not. This release extends Total Visibility through closures, callbacks,
currying, partial application and higher-order functions without banning functional programming.

### Added rules

- **`ACIMA-D015` — Closed-over application dependency.** L1, `warning`, ratcheting to `error` at
  `2.0.0`. A closure, lambda or returned function must not capture an application dependency from a
  module binding or enclosing local. An enclosing parameter is the explicit curried form and is
  allowed; pure closures are untouched.
- **`ACIMA-D016` — Partial application of an application dependency.** L1, `warning`, ratcheting to
  `error` at `2.0.0`. Pre-binding a collaborator with `partial`/`bind` inside a component is
  forbidden; the binding belongs at the composition boundary. Pure partial application is allowed.

### Scope and enforcement

- **Python** uses AST scope comparison: direct loads versus parameters/locals, then enclosing scopes.
  Module bindings and enclosing locals are `D015`; `functools.partial` in an implementation/adapter
  is `D016` when an argument names a dependency.
- **TypeScript** builds a lightweight function-scope model over arrows and function declarations;
  module/enclosing-local captures are `D015`; `partial(...)`/`.bind(...)` in an implementation or
  adapter with a dependency argument is `D016`.
- Both are candidates, not a type checker or runtime graph proof. Dynamic dispatch, generated
  closures, framework callbacks and unsupported profiles remain manual evidence.
- **Go and .NET** carry the catalog entries and report `executed: false`; **Java** has no enforcer.
- Currying with every dependency as a parameter is compliant. A framework-managed callback may close
  over a dependency only when the registration site is the composition boundary and the dependency
  is named there.

### Documentation and fixtures

Chapter 16 defines the lifecycle, closure/callback rules, legal currying, partial application at the
host, pure HOFs, language profiles, exceptions and limits. P4.11/P4.12 were added; chapters 3, 6, 8,
9 and all five language profiles were updated. Positive fixtures cover explicit currying and pure
HOFs; controlled violations cover closure capture and component-internal binding. The skill is
**1.13.0** with the new hash and 42/36 counts.

### Verification

`conformance/run.py python typescript topology tools` passes; Python and TypeScript galleries fire
all 36 portable rules. Go and .NET remain unverified because their toolchains are absent.

## 1.4.0-draft.1 — explicit composition and injection

**Version change:** MINOR. `1.3.0-draft.1` → `1.4.0-draft.1`. Two rules added; no rule removed,
renumbered or weakened. The catalog total goes from 38 to 40 and the portable set from 32 to 34.

### Why

A repository could satisfy every import, contract and configuration rule and still leave its object
graph to assembly scanning, convention registration or property injection. The code looked modular,
but no one could inspect the composition boundary and answer which components existed, which
implementation was selected, or what each component received. This release makes construction part
of the architecture standard.

### Added rules

- **`ACIMA-D013` — Implicit component registration.** L1, `warning`, ratcheting to `error` at
  `2.0.0`. An application-owned component must be registered and constructed explicitly at the
  composition boundary. Assembly scans, convention registration and dynamic discovery must not hide
  the graph.
- **`ACIMA-D014` — Property or field injection.** L1, `warning`, ratcheting to `error` at `2.0.0`.
  Dependencies must arrive through the constructor or composition function, not through property or
  field injection or post-construction assignment.

`L004` remains the rule for service-locator/global-provider resolution. The new rules do not replace
it or duplicate its findings: `D013` is about who chooses the components, `D014` is about how a chosen
component receives its dependencies, and `L004` is about resolving a peer from a locator at all.

### Scope and enforcement

- **Python** detects host scans (`pkgutil.walk_packages`, `pkgutil.iter_modules`,
  `importlib.import_module`, `__import__`, explicit autodiscovery calls) as `D013`, and class-field
  `Provide[...]`/`Inject[...]`/`Autowired[...]` annotations as `D014`.
- **TypeScript** detects `import.meta.glob`, `require.context` and explicit discovery calls as
  `D013`, and field decorators such as `@Inject` as `D014`. Constructor parameter decorators are not
  findings; the dependency is still declared at construction.
- Both detectors are candidates, not proof of the runtime graph. Missing registrations, a framework's
  activation contract, generated components and container behaviour remain manual-review items.
- **Go and .NET** carry both catalog entries and report `executed: false` with reasons. **Java** has no
  enforcer; both rules are manual-review requirements.
- Framework-managed controllers and handlers are explicitly legitimate. ACIMA requires their
  application-owned dependencies to be declared in the constructor and their implementations to be
  registered; it does not require manual instantiation of framework objects.

### Documentation and fixtures

Chapter 15 defines the composition boundary, explicit registration, explicit construction, entry
points, forbidden acquisition paths, language profiles, generality, exceptions and enforcement
limits. P4.9/P4.10 were added, chapter 3, 6 and 8 were updated, and all five language profiles now
describe their composition convention. `docs/rules/dependency.md` has the rule pages. Positive
fixtures and controlled violations cover both languages, and the skill is updated to **1.12.0** with
the new catalog hash and 40-rule/34-portable counts.

### Migration

Start at the host: replace scans and conventions that select application components with explicit
registrations. Then move application dependencies from properties/fields to constructors. Keep
framework infrastructure registration as it is. If discovery is genuinely required, record an owned,
scoped, expiring exception and a reproducible discovered set; do not call a container a composition
boundary merely because it starts successfully.

### Verification

`python3 conformance/run.py python typescript topology tools` passes; the galleries fire both rules
at the checked-in paths, and the positive fixtures are clean. Go and .NET remain unverified here
because their toolchains are unavailable.

## 1.3.0-draft.1 — values, constants and configuration ownership

**Version change:** MINOR. `1.2.0-draft.1` → `1.3.0-draft.1`. Two rules added; no rule removed,
renumbered or weakened. The catalog total goes from 36 to 38 and the portable set from 30 to 32.

### Why

ACIMA already said a module owns its configuration namespace (`A002`, `P7.2`) and that a module must
receive its dependencies rather than discover them (`P4.1`, `L004`). It did not say where a meaningful
value comes from. A timeout could be `30` inside a method, a retry count could be three different
literals in three modules, and an implementation could read `os.environ` directly while still passing
the dependency and contract rules. The architecture was explicit at the boundary and silent inside
the operation.

1.3 makes the value itself reviewable: who owns it, what it means, whether it is fixed, configurable,
per-deployment or secret, and whether a change needs a deployment. It does not require every literal
to become a constant, and it does not require every value to become runtime-adjustable.

### Added

| Rule | Title | Severity now | Severity at 2.0.0 | Level |
|---|---|---|---|---|
| `A005` | Configuration read outside the composition boundary | `warning` | `error` | L3 |
| `A006` | Operational value without a declared owner | `warning` | `error` | L3 |

Both ship as `warning` with `severityRatchet: { "to": "error", "at": "2.0.0" }`, following the same
release pattern as the 1.1 tier rules and the 1.2 explicit-input rules.

### Scope, deliberately

- **Meaningful, not every literal.** `A006` reports numeric and string literals bound to operational
  names — timeouts, retries, limits, rates, batches, retention, endpoints and similar. Loop indices,
  trivial operands and obvious structural values remain local.
- **Named constants are allowed.** An uppercase module constant is an owner, not a finding. The rule
  asks for a name and a classification; it does not demand configuration injection for fixed policy.
- **The host is the composition boundary.** `A005` scans `implementation` and `adapter` units. A host
  may read the environment, validate it and pass typed settings in; a module may not.
- **Text is not meaning.** Two identical literals with different policies remain two values. Static
  analysis cannot infer semantic equivalence, so `A006` reports candidates and requires review.
- **Contracts are data.** Optional contract members remain governed by `C007` and the additive
  evolution rules. A public library may retain a documented optional parameter for compatibility;
  application-owned required inputs remain governed by `D011`/`D012`.
- **Runtime configurability is not free.** When a value is runtime-adjustable, chapter 14 §14.5
  requires validation, audit, propagation, refresh, rollback and failure behaviour. A global file
  edit does not change a running process by itself.

### Language support

- **Python** detects `os.environ`/`os.getenv` in components (`A005`) and operational literal
  assignments, keyword arguments and comparisons (`A006`) with the AST.
- **TypeScript** scans `process.env`/`import.meta.env` and operational assignments/properties
  (`A005`, `A006`). Defaults remain `D012`'s concern; destructuring defaults and string contents are
  review items.
- **Go and .NET** carry the catalog entries and report both rules `executed: false` with a reason;
  they require manual evidence. Their toolchains were not available in this environment.
- **Java** is a documented profile with no enforcer; the rules are manual-review requirements.

### Added elsewhere

- Chapter 14 (values, constants and configuration) and P4.7/P4.8.
- Rule pages for `A005` and `A006`, vocabulary for configuration category and operational value.
- Python/TypeScript positive and violation fixtures, a conformance contract test, and gallery
  coverage for both rules.
- Adoption-skill guidance that reports candidates instead of externalizing every literal.

## 1.2.0-draft.1 — explicit required inputs

**Version change:** MINOR. `1.1.0-draft.1` → `1.2.0-draft.1`. Two rules added; no rule removed,
renumbered or weakened. The catalog total goes from 34 to 36 and the portable set from 28 to 30.

### Why

ACIMA already said a module must declare its dependencies (`P4.1`, `L004`) and that contracts must be
constructible with obvious state (`C007`). It did not say that the declaration has to be complete. A
constructor could take `payments = null`, build a fallback inside the class, and pass every rule:
the dependency existed, the object worked, and no call site showed which of two objects the system
was running. The same hole existed on the invocation side: `sendOrderEmail(request, true)` and
`sendOrderEmail(request)` are different operations with the same name.

Defaults are not the problem; ownership is. A literal in a signature is a decision nobody owns, and
an omitted argument is a decision nobody made. 1.2 makes both visible.

### Added

| Rule | Title | Severity now | Severity at 2.0.0 | Level |
|---|---|---|---|---|
| `D011` | Optional construction dependency | `warning` | `error` | L1 |
| `D012` | Optional argument hides an operational decision | `warning` | `error` | L1 |

Both ship as `warning` with `severityRatchet: { "to": "error", "at": "2.0.0" }`, for the same reason
as the 1.1 tier rules: existing repositories need a release to make the inputs required before the
gate blocks. The obligations themselves are normative now (chapter 13, `P4.6`).

### Scope, deliberately

- **Constructors** (`D011`): every application-owned constructor requires its dependencies, and the
  composition root supplies them. A nullable dependency **without** a default is required and legal;
  the caller must choose `null` explicitly. That distinction is the centre of the chapter.
- **Invocation** (`D012`): methods and functions must not hide a caller decision behind a default.
  Require the argument, split the operation, take an explicit options value, or take a policy.
- **Contracts are out of scope.** An optional contract member is additive evolution under §5.7 and
  is already governed by `C007`; treating it as a hidden dependency would punish compatible change.
  Test, tooling and end-to-end units are excluded because a fixture's convenience is not production
  behaviour. Both exclusions are documented in §13.7 and in the rules' detection notes.

### Migration

1. **Read the findings.** `D011`/`D012` name the parameter and the file. They are `warning`s at 1.x,
   so the gate does not block yet.
2. **Decide per parameter.** Required → make it required and pass it from the composition root. Genuinely
   optional → model it (policy, documented no-op port implementation) or record an owned waiver.
3. **Update the tests.** The test graph must construct the same objects production does; a test that
   relied on the fallback was testing the wrong object.
4. **Keep the composition root explicit.** A default that moved into the host as a literal is not fixed;
   give it a named owner (configuration, constant or policy).

### Language scope

`D011` and `D012` are implemented by the **Python** (AST) and **TypeScript** (signature scan)
reference enforcers, with gallery fixtures in `examples/*/violations/` and positive fixtures under
`conformance/fixtures/explicit-inputs/`. The **Go** and **.NET** enforcers name both rules and report
them `executed: false`; a full claim needs manual evidence for them. As with 1.1, this is scoped
honesty, not universal enforcement.

### Artefacts updated in this change

`tools/acima-spec/rules.json` (two rules, version), chapter 13 (new), chapter 5 §5.4 and chapter 8
§8.3, `docs/rules/{index,dependency,README}.md`, `docs/standard/{01,02}.md`, the Python and TypeScript
enforcers and their galleries, `conformance/{coverage.json,test_explicit_inputs.py}`, the new positive
fixtures, `tools/acima.py` (`LANGUAGE_GAPS`), `docs/status.md`, `docs/product-contract.md`, and the
regenerated adoption skill bundle.

## 1.1.0-draft.1 — third-party library governance

**Version change:** MINOR. `1.0.0-draft.1` → `1.1.0-draft.1`. Five rules added; no rule removed,
renumbered or weakened. The catalog total goes from 29 to 34 and the portable set from 23 to 28.

### Why

The only third-party protection in 1.0 was a prohibition *inside* contracts (`D004`, `L002`, `D007`)
plus a hardcoded database-client list in `L001`. §11.7 described the right shape — a vendor contract
project plus an adapter — but only under service topology, which the adoption skill marks
`NOT SUPPORTED`. The result was that a UI integration such as Monaco could be imported anywhere and
the gate stayed silent. 1.1 closes that gap in the base profile.

### Added

| Rule | Title | Severity now | Severity at 2.0.0 | Level |
|---|---|---|---|---|
| `L005` | Integration library used outside its declared adapter | `warning` | `error` | L1 |
| `L006` | Adapter without a port | `error` | `error` | L1 |
| `L007` | Vendor type outside the adapter | `warning` | `error` | L1 |
| `D010` | Port exposes a vendor shape | `error` | `error` | L1 |
| `G006` | Undeclared external dependency | `warning` | `error` | L1 |

Three declared tiers (`platform`, `integration`, `utility`) and two roles (`adapter`, `port`), all
configured in `externals` in `acima.config.json` — declared per package, never inferred. See chapter
4 §4.10, chapter 5 §5.12, chapter 7 §7.4 and chapter 8 §8.10.

### The severity ratchet

The design target for all five rules is `error` at L1. The three that change how existing code is
*organized* rather than whether it compiles ship as `warning` for one minor release, because a
repository with a working build should be able to declare its tiers before the gate starts failing
it. `L006` and `D010` ship as `error` immediately: an adapter with no port produces no governance at
all, and a port carrying a vendor shape is the same defect family as `D002`/`D004`, which are already
errors.

`rules.json` records the ratchet as `severityRatchet: { "to": "error", "at": "2.0.0" }` on `L005`,
`L007` and `G006`. A run at 1.x reports them; a 2.0 catalog reports them as errors and the gate
blocks. Nothing else about the rules changes.

### Not changed

- `D004`, `L001`, `L002` and `D007` are unchanged. Contracts and the shared kernel remain
  third-party-free; `D004` still fires on any package in a contracts unit.
- `L001` keeps its database semantics. An `externals` entry with `tier: integration` supersedes the
  `L001` token list **for that package only**, because `L005`/`L007` are the sharper rules for a
  package with a declared seam.
- The library profile (chapter 12) is unchanged. It governs a repository that *publishes* a library;
  the new rules govern an application reaching a vendor.

### Migration

1. **Declare the tiers.** `python3 tools/acima.py externals --root . --write-draft` generates one
   entry per manifest package. Every entry starts as `tier: utility`, `owner: UNASSIGNED`. Re-running
   it never overwrites an existing entry.
2. **Review each entry.** Set `owner`, `reason`, `reviewedOn` and `expires`. Classify honestly:
   `platform` for runtime/framework surfaces, `integration` for anything with IO, state, a wire
   format or a third-party UI surface, `utility` for pure helpers.
3. **Build the seams.** For each `integration` package, add the port unit and the adapter unit and
   complete `adapter`/`port` in the entry. `L006` fails until both exist; the adapter is the only
   place allowed to import the vendor (`L005`).
4. **Move the imports.** Application, domain, contracts and host code call the port. Map vendor
   types inside the adapter (`L007`); keep the port free of vendor names (`D010`).
5. **Run the swap drill** on a fixture or a small module (chapter 8 §8.10). Keep the output as
   evidence next to the run artefact.
6. **Expect warnings, not failures**, for `L005`, `L007` and `G006` until 2.0.0. They are reported
   and countable; they do not block merges at 1.x.

### Language scope

`L005`, `L006`, `L007`, `D010` and `G006` are implemented by the **Python** and **TypeScript**
reference enforcers, with gallery fixtures and a positive fixture
(`conformance/fixtures/third-party/python`). The **Go** and **.NET** enforcers report the five rules
`executed: false` with that reason; a Go or .NET repository needs manual evidence for them or the
scoped statement in §8.10. The swap drill is implemented for Python fixtures in this revision.

### Artefacts updated in this change

`tools/acima-spec/rules.json` (catalog + `thirdPartyTiers`), `docs/rules/{index,dependency,autonomy,README}.md`,
chapters 2, 4, 5, 7, 8 and 11, `conformance/coverage.json`, the Python and TypeScript enforcers and
their galleries, `conformance/swap_drill.py` and `conformance/test_third_party_governance.py`,
`tools/acima.py` (`externals`), `docs/commands.md`, `skills/acima-adoption/manifest.json`,
`skills/acima-adoption/SKILL.md` and the regenerated skill bundle.
