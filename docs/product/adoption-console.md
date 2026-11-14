# The interactive adoption console (proposed)

**Status:** proposed design record, decision-complete. Nothing in this document is implemented. No
behaviour, schema, workflow or skill text has changed; this is the contract to review before that
work starts.

**Owner decisions (2026-11-13):** the repository commits only the decision, not the generated pages;
one named reviewer per adoption, with no multi-reviewer merge; the Changes and files page allows per-path scope
selection; and remediation choice (`fix now` / `defer`) is answered in the HTML report. Where a
section below described alternatives, these decisions are now the contract.

**Scope:** the six-page HTML adoption report, the adoption workflow that generates it, and the
`acima-adoption` skill that guides an owner through the lifecycle.

**Relationship to existing guarantees:** this record extends the report into a decision surface. It
does not relax the report's evidence rules, its offline requirement, its accessibility baseline, or
the workflow's consent gates. Where it disagrees with `docs/README.md`, `standard/` or `rules.json`,
those win. The report contract itself remains
[`skills/acima-adoption/references/90-html-outcome-reports.md`](../../skills/acima-adoption/references/90-html-outcome-reports.md)
and the orchestration contract remains
[`skills/acima-adoption/references/13-adoption-orchestration.md`](../../skills/acima-adoption/references/13-adoption-orchestration.md).

## Why

Today the report is a document the owner *reads* while their actual answers are collected in
conversation and re-typed by the agent into `module-map-decisions.json` and `adoption-scope.json`.
That has three costs:

1. **Discovery.** Owners do not know which questions the report is expecting them to answer, because
   the questions are not on the page as questions.
2. **Translation loss.** Re-typing an owner's intent introduces drift between what they said and what
   the workflow records; the provenance of an answer is a chat transcript, not an artifact.
3. **Interruption cost.** Every answer needs the agent to be present. The report is offline and
   reviewable at any time; the decision process is not.

ACIMA's premise is that architecture requirements become useful when intent is recorded as checkable
evidence. The place where intent is expressed should therefore be an artifact too.

## The paradigm in one paragraph

After the assessment and module-map review, ACIMA hands the owner a decision surface: the same
six-page report, now with the open questions rendered as controls. The owner answers in the page —
or in conversation, or in a hand-edited file — and the answers land in one `decisions.json` bound to
the exact report digest. The agent ingests that file at the start of the next stage, records the
answers, and continues. The skill tells the owner this is how the lifecycle works, every time, so
nobody has to discover it.

The page is a *producer* of the decision contract, not the contract itself. Chat and the file remain
first-class, because many ACIMA runs are headless or remote.

## Platform constraint

A page opened from `file://` cannot silently write into `acima/report/…`. Browsers give a local file
no ambient filesystem authority, and ACIMA must not require a server to obtain it. Therefore:

- the page **produces** `decisions.json`; it does not mutate repository artifacts;
- persisting it is an explicit user action with a visible result;
- the workflow **ingests and validates** it before anything is recorded;
- no code path treats a page's in-memory checkbox state as an answer.

This is not a limitation to work around; it is the same evidence discipline the rest of ACIMA
applies. A checked box is a claim until the artifact is validated and recorded.

## Artifact contracts

### Report location

The reviewed report moves out of the OS temporary directory into the target repository:

```
acima/report/<reportId>/          # reportId is the existing 20-hex generation identity
  index.html proposal.html findings.html files.html plan.html evidence.html  # local, not committed
  assets/report.css                                                          # local, not committed
  report-data.json                # agent-authored model; decision content is frozen; local
  decisions.json                  # owner-authored answers; the only committed file here
```

`state.json` keeps the authoritative pointer (`artifacts.proposalReport`). A human finds the report
through `acima adoption status`, which will name the directory, the generation digest, the live
digest and the freshness state.

The generated pages are local and are not committed. `.gitignore` excludes the contents of
`acima/report/<reportId>/` and force-adds `decisions.json`: the decision is the durable artifact and
the HTML is a view of it. Provenance therefore lives in the decision file (report, decision and
proposal identities plus `reportGeneratedAt`), in `acima/report/adoption-proposal.json`, and in
`state.json`. Keeping the pages out of version control does not change the digests, which cover file
content and not timestamps, but it does mean a decision file must remain interpretable without the
pages — which is why it carries its own identities and generation time.

### `decisions.json` (new)

```json
{
  "schemaVersion": "1.0",
  "kind": "acima-adoption-decisions",
  "reportId": "0a1aed6e6c8028559d8e",
  "reportSha256": "<generation digest the owner reviewed>",
  "decisionSha256": "<decision-content digest of that report>",
  "proposalSha256": "<proposal digest bound at generation>",
  "reportGeneratedAt": "2026-11-13T14:18:00+00:00",
  "reviewer": "Repository owner",
  "decidedOn": "2026-11-13",
  "source": "html-report",
  "package": "recommended",
  "supersedes": null,
  "answers": [
    { "kind": "report-review", "id": "all-pages", "decision": "accept" },
    { "kind": "module", "id": "orders", "decision": "accept", "note": "" },
    { "kind": "module-path", "id": "src/orders", "decision": "defer", "note": "Confirm with platform team" },
    { "kind": "recommendation", "id": "local-enforcement", "decision": "accept" },
    { "kind": "scope-objective", "id": "ci-enforcement", "decision": "defer" },
    { "kind": "scope-path", "id": "acima.config.json", "decision": "accept" },
    { "kind": "remediation", "id": "ACIMA-D001", "decision": "defer" }
  ],
  "notes": ""
}
```

Rules for the file:

- `decision` is one of `accept`, `modify`, `defer`, `reject`. `modify` requires a non-empty `note`.
- Every `id` must exist in the report model with that `kind`; unknown or duplicate ids are refused.
- The three digests bind the answers to one exact report. A mismatch is a stale file, not an approval.
- `reviewer` is self-declared, exactly like today's `approvedBy`. The report must say so; the file is
  not an identity system.
- `package` is `recommended` or `custom`, and records how the owner reached the selection. It is
  metadata, not a shortcut: `answers` still lists every included `scope-path` explicitly, because the
  approval binds to exact paths.
- The file contains no repository content beyond ids and the owner's own notes.

### Existing artifacts stay authoritative

`decisions.json` is input. It never replaces:

- `acima/evidence/module-map-decisions.json` — the map review consumed by `apply_review`;
- `acima/evidence/adoption-scope.json` — the scope document, including `authorization.explicit`;
- `acima/state.json` — the approval receipt with `reportSha256`, `liveSha256`, `approvedPaths`,
  `scopeSha256` and `approvedObjectives`;
- `acima/evidence/remediation-plan.json` — the reviewed remediation plan; its digest, its exact
  approved paths and the two distinct confirmations required for large brownfield work remain the
  only way to change source;
- `acima.config.json` — written only at implementation stage 0, after the exact scope approval; map approval stores a proposed config under `acima/evidence/`.

### Workflow state additions

- `artifacts.proposalReport.directory` — the in-repository report path.
- `decisionSources[]` — one entry per ingested file: `fileSha256`, `reportId`, `reviewer`,
  `decidedOn`, `source`, `answers`, `ingestedAt`, plus `status` (`in force`, `superseded`, `stale`).
- `progressLog[]` — append-only stage transitions `{stage, from, to, detail, at}`.
- `events` — path to the append-only event stream `acima/evidence/events.jsonl`.
- `decisionLog[]`, `sinceReview`, `evidenceIntegrity`, `consoleState` — the refreshable history the
  report renders; they are projected into `adoptionWorkflow`, so recording an answer never changes
  reviewed decision content.
- `lastReview` — the previous reviewed receipt, kept when a regeneration resets the current one.

## Ingestion

New verb, `acima adoption decisions --from <file>`:

1. Validate JSON, `kind`, `schemaVersion` and the four required identities.
2. Compare `reportId`, `reportSha256`, `decisionSha256` and `proposalSha256` with the current report
   artifact. Any mismatch stops with *"this decisions file belongs to a different report version"* and
   names both digests. It never asks the owner to confirm anyway.
3. Reject unknown `kind`/`id` pairs, duplicates, and `modify` without a note.
4. Detect conflicts with answers already in state. Without an explicit `supersedes`, conflicting
   re-answers are refused and listed, so a second file cannot silently overwrite the first.
5. Map answers to the existing artifacts:
   - `module`, `module-path`, `recommendation` → `module-map-decisions.json` (only when the map review
     is complete and every material decision is answered) → `apply_review` → `acima.config.json`;
   - `scope-objective`, `scope-path` → a **draft** `adoption-scope.json` whose `authorization.explicit`
     is still `false`, plus the derived `approvedPaths`;
   - `remediation` → answers the agent submits through `adopt remediate --choice selected` with the
     reviewed plan digest, its exact approved paths and the required confirmations; deferral answers
     submit `--choice none` and leave source untouched;
   - `report-review` → the `proposalReview` receipt, still requiring the named reviewer.
6. Record `decisionSources[]`, append an `approval.recorded` or `decisions.ingested` event, and save.

Approval remains its own step. The page's *"Approve this scope"* control pre-fills everything the
existing approval command needs — reviewer, digest, objectives, exact paths — and the agent runs that
command, so the persisted receipt and its digest bindings are created by the workflow, not by a
browser.

## Consent invariants

These are non-negotiable for this feature:

1. A rendered control, a checked box, a downloaded file or an open page is never consent.
2. Consent exists only as the existing workflow receipt: named reviewer, date, generation digest,
   proposal digest, explicit scope, exact paths, unchanged repository revision.
3. Ingestion may create drafts and reviews; it may not set `authorization.explicit` or
   `implementationApproval`.
4. A decisions file bound to any other report identity is refused, never reconciled.
5. Conflicting answers are surfaced, never resolved by picking one.
6. An owner's answer in chat and in the page are the same class of input; neither outranks the other
   except by an explicit, recorded `supersedes`.
7. The page must state, next to the controls, that answering is not authorization.
8. Remediation answers never bypass the plan digest, the exact approved paths or the two distinct
   confirmations required for large brownfield work. `fix now` means *include this recommendation in
   the plan*, not *apply it now*.

## Browser write strategy

Progressive, offline-first, no server by default.

| Mechanism | Behaviour | Availability | Role |
|---|---|---|---|
| Download | *Save answers file* writes `acima-decisions-<reportId>.json` to the browser's download directory; the owner moves it into the report directory or tells the agent where it landed | every browser | default |
| In-place write | `showSaveFilePicker` with a one-time user grant writes `decisions.json` directly | Chromium-family, secure context, feature-detected | enhancement |
| Paste back | A compact JSON block the owner pastes into the conversation; the agent writes the same file | every surface, including headless agents | fallback |

Not chosen as the default: a local HTTP server. It would break the report's no-runtime-dependency
contract, and a browser request that writes repository artifacts needs same-origin checks, a token and
digest binding — a security surface this feature does not need. If a server is ever offered, it is an
explicit opt-in for power users, not part of "open the report".

Every mechanism shows the same confirmation: file name, report identity, number of answers, and the
sentence that answering is not approval.

## What each page becomes

| Page | Controls | Decision ids | Notes |
|---|---|---|---|
| Overview | *I have reviewed all six pages* checkbox, reviewer name, link to the Plan and decisions page | `report-review` | No recommendation is accepted here |
| Architecture and map | Accept / modify / defer / reject per proposed part and per path disposition, and per recommendation | `module`, `module-path`, `recommendation` | Unassigned and unresolved paths are shown but not silently assigned |
| Findings | Per remediation recommendation: *fix now* or *defer*, with the plan digest and the reason for the recommendation shown | `remediation` | Never lets a finding be marked conforming; the two confirmations still apply. These controls appear only on the refreshed report after enforcement is verified, because the remediation plan does not exist at first generation |
| Changes and files | Per exact path: include it in the approved scope, or leave it out; required paths are labelled *Needed for* the stage that needs them, and *Select all proposed files* is an explicit option that fills every box visibly | `scope-path` | No globs, no directories; boxes are unticked at generation and prefilled only from answers already recorded; excluding a required path defers the stage that needs it instead of producing an invalid scope |
| Plan and decisions | Per scope objective: accept / defer / reject; approval block with reviewer, digest confirmation and explicit path list | `scope-objective`, `report-review` | The only page that can start an approval, and only through the command |
| Evidence and limits | Read-only | — | Shows freshness, integrity and what remains unknown |

Persistent indicators on every page: *answered N of M* (answers in force only), *this report is current
as of …*, and a link to the decision log. Percentages are not a score; they count answers, not quality.

### Per-path scope selection

The Changes and files page is the one place where an owner can narrow the approved scope, so its semantics are
exact:

- every row is a repository-relative file path from the proposal; there are no directories, globs or
  free-text additions, and no path outside the proposal can be selected;
- paths are labelled **required** or **optional** for the currently selected objectives, using the same
  derivation the workflow already applies (`_implementation_paths`);
- deselecting an optional path simply removes it from `approvedPaths`;
- deselecting a required path does not create an invalid scope. The console marks the objective that
  needs it as **deferred** and says which path caused that, so the owner chooses between keeping the
  path or deferring the stage;
- the workflow's existing completeness check remains the final guard: an approval whose `approvedPaths`
  omits a required path is still refused, whatever the page displayed.

*Select all proposed files* is one click, but it is an option the owner chooses, not a default the
page assumes. Activating it fills the per-path boxes visibly, records `package: "recommended"`, and
leaves every removal visible; changing any box records `package: "custom"`. Nothing is preselected,
so no path enters `approvedPaths` without the owner selecting it.

## What the console shows back

- **History.** An append-only `progressLog` (stage, from → to, at, actor, reason) rendered as a short
  timeline, plus *what changed since your last review* measured against the previously reviewed
  digest.
- **Decision log.** The answers in force, with reviewer, date and the digests that bind them, plus
  each superseded answer as read-only history under the row it replaced. The log states which answer
  currently governs, so a returning owner sees what is settled and how it got there.
- **Evidence integrity.** Every artifact a stage claims is checked for existence — and hash, where one
  is recorded — on each refresh. A stage whose evidence is missing renders as *recorded but missing*,
  never as complete.
- **Conflicts.** Answers that disagree with decisions already recorded, including an earlier decisions
file from the same reviewer. There is one reviewer per adoption, so no cross-reviewer merge exists.
Superseded answers appear as history only: they are never controls, never counted, and never shown as
current.
- **Freshness.** Progress refresh keeps its current contract: only progress sections change; a
  decision digest refuses any change to reviewed content; a failed refresh is recorded as stale.

## Events

The workflow already implies the events; this feature names them so the console, the status command
and any future notification channel read one stream instead of scraping state.

`report.generated`, `report.refreshed`, `report.stale`, `decisions.ingested`, `approval.recorded`,
`stage.changed`, `stage.blocked`, `owner_input_required`, `verification.recorded`.

Append-only JSON Lines under `acima/evidence/events.jsonl`, local only, no network, no personal data
beyond the reviewer name the owner already records.

## Failure, staleness and regeneration

- **Report missing or stale** (temp cleanup is no longer possible once the report is in-repo, but OS,
  user or branch operations can still remove it): a deliberate `regenerate` rebuilds from the
  persisted review, module map and proposal, invalidates previous review receipts with a recorded
  reason, re-pins the digests, and marks every prior `decisions.json` stale by identity.
- **Decisions file stale:** refused by digest with both identities named.
- **Decisions file partially answered:** accepted as a draft, never as an approval; the report shows
  what is still open.
- **Refresh failure:** recorded as stale with its reason; the workflow continues and the console says
  so on every page.

## Accessibility baseline additions

The existing WCAG 2.2 AA target still applies, with these additions for the controls:

- each decision is a `fieldset` with a `legend` naming the question; native `input type=checkbox` and
  `radio`, never custom widgets;
- visible labels, no placeholder-only labelling, no timed interaction, no drag;
- an error summary at the top of the page after a failed save, linked to the offending field;
- keyboard order follows document order; focus is preserved after saving;
- reflow at 320 CSS pixels with the controls intact;
- **no-JavaScript path:** every page remains fully readable, and a copyable decisions template lets an
  owner answer in chat instead. The controls are progressive enhancement, exactly like the module
  directory's search;
- a screen-reader spot check and a real-browser zoom check remain manual release checks, as today.

## Security and privacy

- `decisions.json` is untrusted input: validated, never executed, never used to construct paths.
- No credentials, tokens or personal data; the reviewer name is the one the owner already provides.
- No network access from the report; no analytics; no external fonts or assets.
- The report directory contains only what the report already discloses plus the owner's own notes.

## Non-goals

- No hosted dashboard, account system or shared link service.
- No multi-user live collaboration, presence or multi-reviewer merge: one named reviewer decides each
  adoption, and a second file from that reviewer must explicitly supersede the first.
- No free-form exploration, sorting, filtering beyond today's module directory, saved views or scores.
- No replacement for the conversation; the page removes re-typing, not the agent's judgement.
- No relaxation of the assessment, evidence or conformance rules.

These restrictions keep the feature consistent with `DESIGN.md`, which explicitly excludes a hosted
dashboard, accounts, charts and free-form data exploration.

## Staged plan

Each stage is independently reviewable, and later stages are blocked on earlier acceptance gates.

| Stage | Work | Acceptance gate |
|---|---|---|
| **A** | Report written to `acima/report/<reportId>/`; `status` names the directory, digests and freshness; `regenerate` with receipt invalidation; report schema 1.2 pins the progress sections and digests | A report survives restart; a deleted report is recoverable; `bundle_skill --check` and report tests pass |
| **B** | `decisions.json` schema asset; `acima adoption decisions --from`; draft scope derivation; conflict and staleness refusal; skill text describing the loop | A decisions file produced by hand drives map review and a draft scope end to end; a stale or conflicting file is refused with both identities |
| **C** | Controls on all six pages, including per-path scope selection and remediation answers; download, in-place write and paste-back; error summary; no-JS fallback; accessibility tests | Keyboard-only completion at 320px; no-JS read-only path; a downloaded file ingests unchanged; excluding a required path defers its objective instead of failing approval later |
| **D** | `progressLog`, since-last-review digest, decision log with superseded history, evidence integrity, `events.jsonl` | History and integrity are visible on the pages; a missing evidence file never renders as complete; a superseded answer is readable but never presented as current |
| **E** | `references/13`, `references/35`, `references/90`, `SKILL.md`, `CHANGELOG.md`, version bump, re-bundle to `~/.agents/skills` | The skill states the paradigm at the point it matters; installed copy matches the repository |

Stage B before Stage C is deliberate: a page with checkboxes and no ingestion contract is a demo,
while ingestion alone already changes how every adoption is conducted.

**Status:** Stages A–E are implemented — in-repository report identity and regeneration, the decisions
contract, guided answer controls on the Plan and decisions and Changes and files pages with download, paste-back and a no-script
template, history (progress log, decision log with superseded history, since-review digests, evidence
integrity) and the `events.jsonl` stream. Automated adoption keeps its consolidated review and shows
history without answer controls.

Implemented deviations from this record, deliberate and documented: the report is schema 1.3 and its
`console` block carries the report id but not a digest of its own bytes, so `reportSha256` and
`decisionSha256` are optional in a decisions file and the workflow completes them after verifying the
report on disk; each answered page writes a partial file that the workflow merges by identity, so save
order cannot change the scope; and in-place save is a feature-detected enhancement because the File
System Access API is unavailable on `file://`.

The workflow excludes `acima/report/` and `acima/evidence/events.jsonl` from the revision an approval
binds to, so the console never makes its own approval stale. Committing policy stays the owner's: only
decisions files are meant to be committed, and the workflow does not edit the target's `.gitignore` to
enforce that.

## Decisions taken

Recorded 2026-11-13; they replace the open questions this record previously carried.

1. **Only the decision is committed.** The generated pages stay local; `decisions.json` is the
   committed artifact. Consequence: the decision file carries its own report identities and
   `reportGeneratedAt`, and regeneration creates a new report identity so older decisions become
   visibly stale rather than silently wrong.
2. **One reviewer per adoption.** No `decisions/<reviewer>.json`, no merge step. A second file from the
   same reviewer must set `supersedes` explicitly, and conflicting answers are otherwise refused.
3. **The Changes and files page allows per-path scope selection.** Guarded by the required/optional distinction:
   excluding a required path defers the objective that needs it, and the workflow's path-completeness
   check stays the final authority.
4. **Remediation choice lives in the HTML.** `fix now` / `defer` answers are recorded per
   recommendation and submitted through the existing remediation plan digest, exact paths and
   confirmations. The controls appear on the refreshed report, after enforcement is verified.
5. **The recommended package is one explicit click, never a preselected default.** The Plan and Files
   pages offer *Select all proposed files* as a first-class option that names its exact paths and
   fills the per-path boxes visibly; the boxes themselves start unchecked. A disclosure was rejected:
   collapsing the common path adds a step for the majority, hides the only actionable control from
   readers who do not explore, and buys nothing — a collapsed section is not a read one. Certainty
   comes from explicitness, the digest confirmation and the named reviewer, not from a second ritual.
   ACIMA must not let an owner approve files they never saw, and must not punish the owner who read
   the whole report.
6. **The decision log shows the answer in force first and superseded answers as history.** Superseded
   entries are read-only disclosures under the row they replaced, with their date, reviewer, digest,
   note and the `supersedes` reference that replaced them. Nothing is deleted. The gate binds to the
   latest recorded answer, so history must not look current; the audit trail needs the earlier answer,
   so history must not be erased either. `answered N of M` counts only answers in force, and a
   superseded answer is never rendered as a control.

## Definition of done for the whole feature

- The owner can open a report from `acima/report/` and answer every open question there, offline,
  including which exact paths to include and whether to fix each remediation recommendation now.
- Those answers reach `state.json` through one validated ingestion path with recorded provenance.
- No checkbox, download or open page can produce an approval.
- Narrowing the scope never silently drops a required path; it defers the objective that needs it.
- An owner can always tell which answer is in force, and what previously applied, without guessing.
- A stale, conflicting or partially answered file is refused or downgraded with a plain explanation.
- Chat-only and page-based engagement produce the same recorded outcome.
- The skill tells the owner, at the right moment, how answers are collected and what happens next.
