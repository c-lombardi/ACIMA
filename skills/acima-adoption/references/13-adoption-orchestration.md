# Adoption orchestration: guided and automated workflows

## Product contract

ACIMA has exactly two user-facing adoption workflows. They share the same assessment and evidence
quality; they differ in when the user reviews the work.

- **Guided adoption** is collaborative. The user reviews the module map, adoption proposal, CI
  proposal, and implementation stages at separate checkpoints.
- **Automated adoption** minimizes interruptions. ACIMA completes assessment and prepares the
  complete adoption package before one consolidated review. The user selects implementation
  stages; ACIMA then executes those stages automatically.

Do not describe old CLI labels as the user experience. The legacy CLI mode named full is the
automated workflow's preparation mode; it must not mean permission to apply every recommendation.
The conversational agent must explain the selected workflow and current checkpoint.

## First interaction and mode persistence

When no mode has been selected in the current engagement, ask:

> ACIMA can help you adopt its architecture standard in two ways:
>
> **Guided adoption:** We review the architecture, recommendations, enforcement, and CI together
> at meaningful checkpoints. You decide what happens at each stage.
>
> **Automated adoption:** I inspect the application, complete the assessment, prepare the
There is one adoption flow. Start the read-only assessment without asking the owner to choose a
mode. Assessment and preparation are read-only; map approval and scope approval are separate
checkpoints; implementation begins only after one owner decision record and approval receipt bind
the exact report, objectives and paths. Legacy `full` state can be resumed but cannot be newly
started, and it grants no implementation privilege.

## Shared foundation: mandatory assessment and discovery

Generated artifacts share one visible workspace. `acima/state.json` resumes the engagement;
`acima/evidence/` holds assessment, review, approval, enforcement, verification, waiver and
remediation records; `acima/report/` holds proposal inputs; `acima/handoff/` holds handoff and
generated agent guidance; and copied enforcers live under `acima/tooling/`. The root
`acima.config.json` remains the human-authored unit contract. Optional documents belong under
`acima/optional/` and are created only when explicitly requested. Existing `.acima/` and
`docs/acima/` evidence is read for migration but never written.

The adoption flow must complete the same foundation.

1. Discover the repository, production languages, architecture, existing module declarations,
   contracts, dependencies, composition, data/configuration ownership, entry points, tests,
   tooling, generated content and existing architecture enforcement.
2. Complete one genuine qualitative review record for each of the 56 current catalog requirements.
   Each record needs a disposition, repository-specific rationale and evidence. The 14
   judgment-dependent requirements need actual contextual reasoning, not copied descriptions.
3. Validate the complete review against the pinned catalog, evidence paths, line ranges and exact
   quotes. insufficient_evidence is explicit coverage but unresolved; it is not conformance.
4. Generate a proposed module map automatically. Pair contracts and implementation paths when they
   share one ownership boundary. Classify non-module paths and keep uncertain production paths
   unresolved. Projects, packages, folders and manifests are signals, not ownership decisions.
5. Inspect existing architecture rules, tests, analyzers, linters and CI. Explain what should be
   preserved, reused, extended or deferred.

Before starting either adoption workflow, the agent must create a repository-specific review
document at acima/evidence/qualitative-review.json. Validate it with:

    python tools/acima.py validate-review --root . --file acima/evidence/qualitative-review.json --format json

The validator must report decisionComplete=true, reviewed=56, required=56 and unresolved=0.
Structural validation proves coverage and evidence provenance, not the semantic correctness of the
agent's reasoning; the agent must independently inspect the evidence and author each disposition.
Start adoption only after validation succeeds:

    python tools/acima.py adoption start --root . --review acima/evidence/qualitative-review.json
A decision-ready adoption proposal requires all 56 valid dispositions and a complete, reviewed
ownership map. Discovery and independent qualitative work may continue while a map is unresolved.
Never claim an assessment complete merely because the catalog expects 56 records.

Do not turn unresolved dispositions into a per-rule owner questionnaire. Resolve code-traceable
unknowns yourself. If owner input is genuinely required, group related rules into a decision brief
with plain meaning, the missing evidence, a recommended option, effort and consequence, as described
in [35-user-transparency](35-user-transparency.md). The owner decides effort or whether to accept a
limited claim; an accepted limitation remains unresolved and never becomes conformance.

## Guided adoption sequence

### G1. Assessment and module-map review

Complete the shared foundation and present the map in plain language: module responsibilities,
implementation and contract paths, dependency direction, composition, non-module paths, uncertainty
and the evidence behind proposed boundaries.

Ask the user to accept, modify, reject or defer individual boundaries and path classifications.
Do not make inferred ownership authoritative before approval. Revalidate the map after edits.
Unresolved ownership blocks only work that depends on that ownership; independent review continues.

Do not present a per-rule worksheet or ask the owner to assign every catalog rule to a unit. The
review validator does not require path-derived rule evidence, and a rule covering the workspace, a
layer, an absence or an external artefact may legitimately remain repository-scoped. The agent fixes
mechanical citations itself. Ask only where the answer changes a boundary or ownership decision, and
give a recommended default with its consequence.

### G2. Adoption proposal review

After the assessment and map are decision-ready, generate an actionable proposal. Explain what
ACIMA adds, what already exists, what should be preserved, required and optional changes, exact
affected files/modules, risks, dependencies, expected value and intentionally excluded work.

Present the proposal before generating or modifying active enforcement, agent instructions or CI
files in the target. Let the user accept, modify, defer or decline individual recommendations.

### G2a. Mandatory HTML proposal presentation and review

After the complete assessment and required module-map review, generate and validate the six-page HTML report: Overview, Proposal, Findings, Files, Plan and Evidence. The report is a mandatory user-facing decision document in both workflows, not an optional export.

Do not block the report on converting cross-cutting rule evidence into unit-scoped evidence. When
`validate-review` reports `decisionComplete=true` and the map review is decision-ready, proceed;
disclose genuinely workspace-level evidence as a limitation rather than inventing a unit for it.

Open the report in the user's available browser or viewer. Show a direct link to the index page and each supporting page. Do not merely print a path, say it was generated, or proceed to the next approval question without presenting it. If the environment cannot open or show the report, mark the workflow blocked at this checkpoint and explain the limitation. Do not accept approval of a Markdown summary as a substitute.

Ask the owner to inspect all six pages. Record the reviewer's identity, report SHA-256 and proposal SHA-256. Approval must match those exact digests and the assessed repository state, including branch and working-tree content. If any of those change, invalidate the review and generate a fresh report. Reviewing the report is acknowledgement of the proposal, not implementation permission. A separate file-scoped implementation approval is still required.

### G3. Enforcement and agent-guidance preparation

Use the accepted map and proposal to select only the necessary architecture tests, analyzers,
linters, dependency checks, contract checks and manual-evidence procedures. Prefer reuse or extension
of sound existing tooling over a duplicate gate.

Select the instruction convention from repository evidence: preserve and update a case-insensitive
AGENTS.md when established; use CLAUDE.md when that is the established primary convention;
otherwise use the active supported convention. If none exists, default to AGENTS.md. Preserve
user-authored content outside clearly marked generated sections. Root instructions stay concise and
link to supporting guidance.

The instructions must accurately state module ownership, explicit and zero-dependency contracts,
acyclic dependencies, no direct or transitive implementation leakage, dependency direction, data
and configuration ownership, controlled composition and host authority, explicit inputs, lifecycle,
state and effect ownership, and manual judgment obligations. Translate internal catalog identifiers
into human-readable explanations.

Agent-guidance and adoption notifications are separate decisions. Updating AGENTS.md/CLAUDE.md
changes future AI-agent behavior; user-facing ACIMA adoption notifications change how milestones,
decisions, blockers and verification are communicated. Do not combine these options or imply that
approval of one approves the other.

Ask separately whether the owner wants ACIMA adoption notifications included. If yes, inspect the
existing interaction surfaces and notification mechanisms, then prepare a distinct proposal that
identifies event triggers, audience, delivery surface, exact paths, user controls, privacy, retries,
deduplication and tests. Do not assume email, push, webhook, Slack or another external provider. Do
not modify product code or provider configuration until the user reviews that proposal and approves
its exact paths. If declined or deferred, record that separately and continue with the approved core
adoption.

Verification must separate:
- A known-compliant positive fixture: expected successful exit (normally 0), non-zero source
  coverage and zero relevant findings.
- A controlled negative fixture: the intended violation is detected.
- The actual repository scan: its own exit code, source count and findings, never relabelled as the
  positive fixture.

A target scan with exit 1 or findings is not a positive pass. Unsupported or unrun checks remain
explicitly unsupported or unrun.

### G4. CI evaluation and review

Inspect actual providers and workflow files, triggers, build/test stages and architecture checks.
For existing CI, propose the smallest coherent enhancement. If no provider exists, present reasonable
supported choices and ask the user which one they prefer. Identify exact workflow paths, commands,
triggers, prerequisites and expected behavior.

Ask whether to enhance existing CI, create the proposed setup, modify it, defer it or decline it.
Do not write CI until the user approves that specific change. Local configuration is not evidence of
a remote CI run.

### G5. Select implementation stages

Present the overall adoption plan and ask whether the user wants changes applied in one complete
implementation or in multiple logical stages. Keep local enforcement, CI, agent guidance, ACIMA
adoption notifications and application-source remediation as distinct selectable decisions. For brownfield systems, recommend incremental stages
when that reduces risk.

Derive stages from real dependencies and risks, not arbitrary file counts. For each stage identify
purpose, expected result, affected files/modules, prerequisites, risk, tests, whether application
source changes, and what remains if deferred. The user can approve one, several, all, selected
recommendations or none. Do not infer consent for unselected work.

### G6. Execute approved stages and hand off

Implement only the approved scope, in dependency order. Validate after each stage, preserve the
baseline and user changes, refresh affected evidence, and request new approval before materially
expanding scope. Retain the two-confirmation safeguard for high-risk brownfield work. If the user
declines implementation, stop without unapproved changes and retain the assessment/proposal.

## Automated adoption sequence

### A1-A4. Assess and prepare the complete package

Complete the same 56-rule assessment, module discovery, enforcement-landscape review and map
quality validation as guided mode. Then prepare the adoption proposal, appropriate enforcement and
agent-guidance proposal, CI evaluation/proposal, and dependency-ordered implementation stages.

Do not ask routine questions that repository evidence can resolve. Do not auto-approve module
ownership from manifest presence, folder structure, confidence labels derived from layout, or
placeholder responsibilities. Defer unsupported ownership decisions and explain them in the
consolidated review. If CI provider preference is genuinely necessary, ask that narrow question
without abandoning independent preparation.

Preparation artifacts must be clearly marked proposed or generated-but-not-applied. Do not make
consequential target changes while preparing the package. In particular, do not silently apply
module ownership, enforcement, agent instruction edits, CI changes or source remediation.

### A5. Consolidated review

Generate, open and present the complete six-page HTML report before asking the user to approve scope. Present the complete package in that report and review conversation:
1. Assessment summary and all 56 human-readable dispositions.
2. Proposed module map, contract/implementation relationships and unresolved decisions.
3. Adoption proposal and existing architecture to preserve.
4. Enforcement design, fixtures and actual validation evidence.
5. Agent-instruction convention and proposed content, as a separate decision.
6. CI discovery and proposed integration or setup choices, as a separate decision.
7. ACIMA adoption-notifications decision and, when requested, a separate notification proposal.
8. Ordered implementation stages, affected paths, dependencies and risks.
9. Limitations, deferred work and decisions requiring human judgment.

Clearly distinguish existing/verified, proposed, generated and validated outside the target,
approved, implemented, verified, deferred and declined. A generated proposal is not an approval.

### A6. Select scope; A7. Execute automatically

Ask the user to approve all stages, select one or more stages/recommendations, request modifications,
defer work or decline implementation. The first consequential target change must occur only after
the user approves the actual scope. A request to run automated assessment is not blanket
implementation consent.

After scope approval, execute selected stages automatically without unnecessary per-file prompts.
Stop for renewed approval if scope materially expands, an undisclosed risk appears, or a consequential
architectural decision remains unresolved. Validate each stage and produce a fresh final assessment
and honest handoff.

## Persisted state, approvals and resumption

Use one authoritative workflow state. At minimum record mode, repository identity and baseline
revision; assessment and map artifacts; proposal revision; approval provenance; enforcement and
fixture results; agent-guidance proposal/application/validation; CI discovery/decision/application;
selected implementation stages; remediation; fresh verification; and handoff.

Stage states must distinguish not_started, in_progress, awaiting_review, approved, declined,
deferred, blocked, complete and failed. An omitted decision is not acceptance. A deferment is not
approval. A stale approval cannot authorize a changed proposal. Map approval, HTML-report review,
CI approval, AI-agent-guidance approval, adoption-notifications approval, remediation approval and
implementation-scope approval are separate decisions. Record the exact report/proposal digests and
repository revision, branch and working-tree identity with the approval.

Resume from persisted state without repeating completed work or bypassing a prerequisite. If the
repository revision changes materially, mark affected evidence and approvals stale and reassess
before proceeding.

The generated HTML report is part of that persisted state. It lives at
`acima/report/<reportId>/index.html`, with `report.json` recording its identity (report id,
generation, generated-at, generation/live/decision digests, progress status) and `decisions.json`
holding the owner's answers once they exist. A regeneration gets a new directory and a new report id,
so a reviewed report is never overwritten in place.

The report stays current automatically. Every
recorded progress change refreshes its progress sections, so do not ask the user to regenerate or
update it, and do not describe a previous version as the current state. A refresh may change only
the progress sections (current phase, stage table, completed milestones, next action, remediation
and agent-guidance status); the reviewed decision content and the generation digest stay fixed, and
a refresh that would change decision content is refused. If a refresh fails, report the report as
stale with its reason, and the workflow's recorded state remains authoritative until a refresh
succeeds. Rebuild a report that cannot be refreshed at all (`acima adoption regenerate --reason`):
that is the only supported repair, and it is not a routine step. Regeneration increments the report
generation, writes a new report id, returns the review to `awaiting_review`, invalidates any
implementation receipt and marks answers written against the previous report as stale.

## The answer loop

The owner answers the report, not the agent's paraphrase of it. In guided adoption the Plan and Files
pages carry the controls; each answered page saves a partial decisions file, and the workflow merges
them by report identity, so save order does not matter. Ingest with
`acima adoption decisions --root . --from <path>` for each saved file; do not retype answers into
commands. Only decisions files are meant to be committed — the pages stay local unless the owner asks
otherwise. Automated adoption has no console controls; its consolidated review is unchanged.

Ingestion enforces four things. It refuses a file whose `reportId`, `reportSha256`, `decisionSha256`
or `proposalSha256` differs from the current report, because those answers describe a document that
is no longer current. It refuses an answer that contradicts an earlier recorded answer unless the
file names that earlier file in `supersedes`, so history is replaced explicitly rather than
accumulated by accident. It applies map answers only while the module map is awaiting review, and
never after approval. And it refuses a file that does not record the report review itself.

What ingestion is not: consent. Scope answers derive a draft scope whose `authorization.explicit` is
`false` and whose `basis` says the approval command is still required. A path the owner leaves out
defers the objective that requires it, named with the missing paths, instead of producing an
incomplete approved scope. Remediation answers are stored as recorded intent; `adopt remediate` still
requires its plan digest, exact paths and confirmations. Guided mode keeps its map gate, so no report
exists at map time and map decisions stay in conversation.

## Target preservation and honest claims

Never overwrite user-authored instructions outside generated markers. Preserve existing architecture
checks and CI behavior unless the user approves a change. Do not create duplicate infrastructure just
to satisfy a template. Never create, switch or recover a branch automatically. A branch name or
recovery selection is not approval to change target files; branch operations themselves require
explicit approval. Any branch/commit movement invalidates stale evidence and scope approval. Never
commit, push, release or deploy without separate authorization.

A verification result is verified only when required positive and negative fixture evidence passes
and is tied to the approved map and correct language-specific enforcer. The real repository scan is
reported separately. No full-conformance claim follows merely from a generated config, passing
fixture, CI file or agent guidance.

## Required report and handoff

Produce the progressively disclosed HTML adoption report for both workflows. Include executive
overview, 56-rule assessment, module-map visualization and ownership, existing architecture to
preserve, findings, affected files, enforcement, agent guidance, CI, implementation stages and
decisions, evidence and limitations. Use /impeccable only if available in the ACIMA development
environment; do not invent its capabilities.

The handoff states what was implemented, what was verified, what was not verified, remaining gaps
and insufficient evidence, deferred/declined stages, next actions and the actual local commands.

## Canonical user experience

**Guided:** Assess → Review Map → Review Proposal → Review CI → Select Stages → Implement.

**Automated:** Assess → Prepare Everything → Review Complete Proposal → Select Stages → Automatically
Implement.

Both end with fresh, evidence-backed verification and an honest handoff. The user controls decisions;
ACIMA performs the reasoning and approved work.
