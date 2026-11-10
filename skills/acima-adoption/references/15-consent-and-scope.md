# Consent, scope and artifact selection

**Analysis is not authorization to adopt.** An assessment may inspect, measure, explain and
recommend. It may not leave a configuration, baseline, waiver, plan, workflow, dependency, source
change or documentation change in the target repository. Adoption begins only when the owner has
approved a specific proposal.

This reference is the long form of the phase gate in `SKILL.md`. It does not relax any conformance
requirement: it decides *whether* and *how much* to implement, never whether the implemented part is
described accurately.

## The five phases

| Phase | Purpose | May write to the target? | Ends with |
|---|---|---|---|
| 1. Assessment | understand fit, findings and limits | no | a recommendation and named gaps |
| 2. Proposal | make the adoption decision reviewable | no | exact paths, statuses, decisions and risks |
| 3. Explicit authorization | the owner accepts a named scope | no | one direct approval answer |
| 4. Approved implementation | implement only the approved scope | approved paths only | the approved artifacts and slices |
| 5. Verification and handoff | prove what exists and state what does not | no new scope | a handoff with capabilities and limits |

Read-only analysis may use operating-system temporary directories outside the target. Delete them
or leave them outside; never commit them. If an analysis genuinely cannot run without a persistent
target change, stop and explain the requirement before making the change.

### Phase 1: assessment (default)

Use `acima.py assess` and `preflight.py` without `--write-*`. Inspect manifests, project references,
entry points, deployments, tests and documentation. Run only read-only checks. Report:

- languages, source counts, projects and architecture family;
- confirmed findings, potential findings and detector artifacts;
- rules that did not execute and environmental limitations;
- discovered boundaries, confidence and unresolved questions;
- whether ACIMA is recommended, recommended with limitations, not recommended, or has insufficient
  evidence.

`NEEDS_UNIT_MAP` means the architecture was not assessed. It is not a clean result.

### Phase 2: proposal

Present the proposal from `assets/adoption-proposal.md` before creating anything. It must name every
path, what the file contains, why it exists, its status, the dependencies, the maintenance burden,
the decisions only a human can make, and the risks. Keep it readable without the rule catalog.

Classify each artifact honestly: required, conditional or optional. An adoption plan, a communication
plan, a status dashboard and a summary are optional unless the owner asks for them or coordination
genuinely requires them. Do not mark an artifact required because a template exists for it.

### Phase 3: explicit authorization

The approval question is explicit:

> Would you like me to proceed with this adoption plan and create the listed files and changes?

Do not substitute “Should I proceed with ACIMA?” or “Want me to set it up?”. A general expression
of interest, continued conversation, silence, or approval of the assessment is not consent. Wait for
the answer before the first write.

Approval covers only what was shown. Partial approval is supported and is the normal case: implement
the approved paths and level, then state the capability and the gap of what was not approved.

### Phase 4: approved implementation

Implement the approved paths and level. Routine choices inside that scope are allowed. Do not create
optional artifacts that were not in the approved list. Stop and ask before adding a path, changing
target source or build configuration, adding CI, raising the level, or introducing a boundary
that was not in the proposal. If implementation reveals that the proposal was wrong, say what
changed, why the approved scope cannot deliver the stated result, and what new approval is needed.

### Phase 5: verification and handoff

Verify the generated configuration, run the available enforcement, validate waiver and baseline
integrity, exercise controlled violations where supported, and inspect CI configuration without
claiming it has run. State exactly what was and was not observed. Handoff includes the approved
scope, the evidence, the remaining work and the limitations.

## Recording the approved scope

Approval is explicit and machine-readable. Record it at `.acima/adoption-scope.json` (preferred)
or `docs/acima/adoption-scope.json`; an `adoption` object in `acima.config.json` is also accepted
but changes the configuration hash, so prefer an external file. The record is written only after
the owner answers the approval question, and it is read-only to `status`:

```json
{
  "version": 1,
  "approvedBy": "repository-owner",
  "approvedOn": "2026-11-10",
  "proposal": "docs/acima/adoption-proposal.md",
  "objectives": [
    {"id": "assessment", "disposition": "required"},
    {"id": "local-enforcement", "disposition": "approved"},
    {"id": "ci-enforcement", "disposition": "deferred", "reason": "next quarter"},
    {"id": "communication-governance", "disposition": "declined"}
  ]
}
```

The canonical objectives are `assessment`, `local-enforcement`, `baseline-waivers`,
`ci-enforcement`, `full-conformance`, `developer-handoff` and `communication-governance`.
`required` and `approved` are completion obligations; `declined`, `deferred`, `optional` and
`not-applicable` never block. Do not use `NOT_APPLICABLE` for a declined objective: a declined
choice, a deferred choice, an optional document and a genuinely irrelevant objective are four
different answers. Missing approval metadata, unknown ids, duplicate ids, invalid dates and an
approved objective whose prerequisite was declined make the scope invalid rather than guessed.

The engine promotes a prerequisite of an approved objective to `required`. A stage is not advanced
while its prerequisite is blocked or unverified, and the status names one next action with its
completion condition and the effect of approval. Assessment-only and local-only scopes can
complete without CI, baseline, waivers or optional documents. Full conformance still requires the
whole claim: no approved objective weakens a normative rule, currentness check or manual-evidence
requirement.

## Approval boundary

| Action | Approval |
|---|---|
| Inspect repository files, manifests and history | not required |
| Read ACIMA docs, rules and examples | not required |
| Run `assess`, `inspect`, `analyze`, `report`, `claim`, `status` | not required |
| Run calibration (`preflight.py` without `--write-*`) and `inject_violation.py` | not required; they do not modify the target |
| Generate a report outside the target, or prepare a proposal in the conversation | not required |
| Create or modify `acima.config.json` | required |
| Create `.acima/` (baseline, waivers, manual evidence, triage) | required |
| Create or copy adoption, communication or status documents into the target | required |
| Add or copy enforcement tooling, scripts or dependencies | required |
| Add or modify CI workflows | required |
| Modify build, test or packaging configuration | required |
| Modify target source or existing repository documentation | required |
| Declare, split or merge architectural units or change their roles | required |
| Merge, publish, release or push | separate explicit approval |

`preflight --write-draft` and `--write-waivers` are writes even when the path looks incidental.
Passing them is an adoption act, not part of assessment.

### Reading the request

| Request | Authorizes |
|---|---|
| “Assess this repository with ACIMA.” | assessment only |
| “What would adopting ACIMA require?” | assessment and a proposal |
| “Show me the files you would create.” | the artifact plan, not creating it |
| “Adopt ACIMA.” | assessment and a proposal; approval still follows |
| “Create the configuration and baseline we discussed.” | only those named artifacts, at the discussed paths |
| “Do the whole thing.” | assessment and proposal; it does not pre-approve unseen files |

Scope words such as “whole thing” cannot replace the specific list. Approval covers only what was
shown. If the user says “yes” after the proposal, restate the approved paths and level in the first
status update so a mistaken scope is caught early.

## Artifact classification

Classify against the selected objective, not against the template inventory. Never mark an artifact
required because a template exists for it.

| Artifact | Purpose | Status | Depends on | What it proves |
|---|---|---|---|---|
| `acima.config.json` | declares units, roles, paths, language, level and mode | **Required** for any unit-aware assessment, enforcement or baseline | a reviewed unit map | that boundaries are declared, not that code follows them |
| `.acima/waivers.json` | records owned, scoped, fingerprinted, expiring exceptions | **Conditional**: required when findings remain or a gate is used; an empty file is needed for an adopted gate | config and a measured run | that exceptions are governed, not that findings are absent |
| `.acima/baseline.json` | records the measured fingerprints at adoption | **Conditional**: typical for brownfield gating and ratcheting; optional for a clean greenfield | a valid run and config | what was known at that commit, not conformance |
| `.acima/adoption-scope.json` | records the approved objective dispositions and approval metadata | **Required** to make completion and the next action scope-aware; not needed for a read-only assessment | the owner's answer to the proposal | what was approved, not that any objective was implemented |
| `docs/acima/assessment.json` | records the read-only assessment verdict | **Required** for an assessment-only completion claim | an assessment run for this repository | what was assessed, not conformance |
| Enforcement tooling | runs the rules locally or in CI | **Required** for automated enforcement; not required for a read-only assessment | config and a supported enforcer | that checks can run, not that they passed |
| CI workflow | runs the gate on integration | **Conditional**: only if the owner wants automated blocking | tooling, config, policy for baseline/waivers | that CI is configured, not that it executed |
| `.acima/manual-evidence.json` | records human/native evidence for non-portable rules | **Conditional**: required for a full claim at a level containing such rules | an actual review and artifact | that a named person reviewed a named method, not that a rule is automated |
| Adoption plan | records boundaries, sequence, owners and metrics | **Optional** | approved scope and named people | coordination intent, not implementation |
| Communication plan | records audiences, messages and responsibilities | **Optional** | approved adoption and stakeholders | coordination intent |
| Status dashboard | records phase, findings and next action | **Conditional**: useful once an adopted repository has state to resume | approved adoption and a run | the recorded programme state |
| Adoption summary | reader-facing interpretation of a run | **Optional**: may live outside the target; inside only with approval | a run or a manual assessment | an interpretation of evidence, not new evidence |
| Triage file | classifies matches as defects, review items or detector artifacts | **Optional** | a run and reporting | reviewed classification, never suppression |
| Source or build changes | correct a boundary or wire the gate | **Conditional and separately approved** | an approved first slice | the change itself; the gate must still be run |

**No artifact is evidence of conformance.** A config can describe a false architecture, a baseline
can freeze a bad measurement, a waiver can hide a new finding if the fingerprint is missing, and a
workflow file can be committed without ever running.

### Smallest useful sets

| Objective | Recommended artifacts | Explicitly not needed |
|---|---|---|
| Understand fit | none in the target; report in the conversation or outside | config, baseline, waivers, CI, plans |
| Local enforcement | config, reviewed unit map, enforcer invocation, waivers if findings remain | CI, plans, status dashboard |
| Brownfield gate | config, run artifact, baseline and/or waivers, CI workflow | adoption narrative unless coordination needs it |
| Multi-team programme | the gate set plus adoption and communication plans | nothing extra solely for ACIMA |
| Full level claim | gate set plus manual evidence for unexecuted required rules | a claim without the evidence |

If the user asks for “adoption” but only wants a local check, propose the local set. If the user asks
for CI but has no config, explain that CI has nothing to run until the configuration exists.

## Dependencies and partial approval

The normal dependency chain is:

```text
reviewed unit map (acima.config.json)
        ↓
measured run
        ↓                 ↓
baseline (optional)   waivers (if findings remain)
        ↓                 ↓
        └──── gate policy ────┘
                  ↓
             CI workflow
                  ↓
      manual evidence for a full level claim
```

A user may approve any prefix or subset:

- config only: enables inspection and a first measurement, but no gate and no conformance claim;
- config + local enforcement: useful locally; nothing prevents merges;
- config + baseline, no CI: a frozen measurement, not a ratchet;
- config + CI, no baseline: the gate can block, but every existing finding is new unless handled;
- everything except plans: a working technical adoption without programme documents;
- one module: a pilot, not repository-wide coverage.

When approving a partial scope, state its capability and its gap in one sentence each. For example:
“This creates the map and local check, so developers can measure before merging. It does not block
integration, and no level is claimed.” Do not call a partial implementation “adopted” without that
qualification.

If the user declines, stop. Keep the assessment and proposal as the result. Do not create a
“harmless” config, empty `.acima/`, or report file to make the next session easier.

## Module mapping must stay reviewable

Discovery is heuristic. It is not an authoritative architecture.

| Class | Meaning | Typical evidence | May enter confirmed config? |
|---|---|---|---|
| Discovered project | a build unit found on disk | project file, package manifest, source root | only as a candidate |
| Proposed module | a candidate ACIMA unit with a role | directory shape, references, entry points | as a labelled proposal |
| Confirmed module | an owner has accepted the boundary and role | explicit owner decision | yes |
| Supporting library | code shared without being a domain module | package metadata, no entry point, many consumers | only with an owner decision |
| Shared kernel | a deliberately shared model depended on by many modules | ubiquitous types, high fan-in | only as a declared exception or redesign decision |
| Composition boundary (`host`) | wires implementations; not a module | entry point, DI registration, public factory or consumer code | optional; declare each, after review |
| Test project | verifies other units | test framework, naming, build metadata | normally excluded, not a domain unit |
| Tooling project | builds, deploys or analyzes | scripts, generators, analyzers | normally excluded or declared separately |
| Uncertain | evidence conflicts or is missing | duplicate names, generated code, ambiguous manifests | no; ask first |

Present a mapping table with: discovered path, proposed unit/role, evidence, confidence (high,
medium, low), and the decision still needed. Confidence is about the classification, not about
whether the owner likes it.

Do not turn a directory-name guess into configuration. Do not declare a shared kernel merely to make
an inconvenient dependency legal. If two plausible maps exist, describe both and their consequences;
the owner chooses. An ambiguous map stops the creation of authoritative configuration, not the
assessment.

## Implementation discipline

1. Work from the approved list; do not opportunistically add improvements.
2. Keep changes reviewable and attributable to one artifact or one boundary slice.
3. Re-run the relevant check after each material change.
4. Report a material discovery before acting on it if it changes scope, architecture or risk.
5. Stop before source, build, CI or documentation changes that were not approved.
6. Do not merge, publish or release without a separate instruction.
7. If interrupted, leave a truthful state note: what exists, what is incomplete, what was verified.

Routine decisions inside the approved scope — formatting a JSON file, choosing the documented output
path when the proposal named it, ordering independent steps — do not need another approval. Changes
to commitments do.

## Conversation behavior

- Default to assessment. Do not upgrade because findings look serious.
- Explain in the reader's language: “prevents new cross-module database access”, not “enforces D001”.
- Present the proposal once, completely; do not dump every template into the chat.
- Ask one direct approval question and stop. Do not treat a follow-up question as a yes.
- During implementation, report milestones (map, baseline, gate, verification), not every command.
- When done, lead with the outcome and the limits; keep technical evidence available by path.
- Never claim a CI run, a merge or a conformance level that was not observed.

## Stop conditions

Stop and ask when:

- the target has no named human owner for exceptions;
- a unit's role is materially ambiguous;
- the approved scope cannot produce the stated capability without an unapproved change;
- configuration would have to be edited to hide a finding;
- a new rule, level or enforcement mechanism appears that was not in the proposal;
- the owner asks to skip baseline/waivers but still wants a no-new-findings claim;
- the request would merge, publish or release without separate consent.

A limited adoption is legitimate. Calling it complete is not.
