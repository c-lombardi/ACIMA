# Reporting an adoption


For a reader-facing, navigable multi-page HTML report, use [90-html-outcome-reports](90-html-outcome-reports.md).
The HTML outcome pack is the product-facing explanation; this document remains the source for
status semantics, traceability and evidence presentation.

Two audiences read an adoption: the people who own the repository, and the people who audit the
run. Give them two different documents, and make the first one the product.

## Communication contract

**All user-facing communication MUST express the actual meaning of an architectural requirement,
finding, recommendation or decision in plain, human-comprehensible language. An internal identifier
MUST NOT be the explanation or the primary description.** This applies to every phase: the initial
assessment, findings, recommendations, implementation plans, approval requests, progress updates,
final reports, warnings and spoken output.

A reader who has never seen ACIMA must be able to understand what is wrong, why it matters and what
should happen next without learning a rule, requirement, principle or evaluator identifier.

### Resolve the authoritative meaning

Translate at the point of use from the source that owns the definition:

| Identifier kind | Authoritative source | What to express |
|---|---|---|
| Enforcement rule (`ACIMA-D001`, `A006`, `L001`, …) | `tools/acima-spec/rules.json` | the catalog `title`, `summary`, `fix` and coverage limits |
| Principle or requirement (`P…`, `R…`) | the heading and normative text in `docs/standard/` | the obligation in ordinary architectural language |
| Evaluation criterion (`D8.4`, …) | the active benchmark rubric | the criterion statement and the evidence it requires |
| Repository-local identifier | the repository document that defines it | the local meaning, without claiming it is an ACIMA rule |

Do not infer meaning from a prefix or number, and do not keep a second hand-written dictionary of
labels. Identifiers can be overloaded: an examples index may use `R3` for dependency isolation while
the lifecycle chapter uses `R3` for separating behaviour from mutable state. Resolve the source in
context and name it when there is ambiguity. If no authoritative definition resolves the identifier,
state that the check is unresolved, call it an internal reporting defect, preserve the raw evidence
and do not invent a meaning or a remedy.

### Explain the finding, not the code

Use this shape in proportion to the finding's importance:

| Part | What it answers |
|---|---|
| **What we found** | the actual implementation behaviour, in plain language |
| **What it could cost** | the practical consequence, risk or maintenance cost |
| **What fixing it involves** | the intended software change, including its ownership |
| **Where this came from** | the file, symbol or location and the observation that supports it |
| **How sure we are** | confirmed, probable, uncertain, or requiring human review, and what is still unknown |

Do not repeat a shared architectural explanation for every occurrence. Group findings that share a
cause and state the count and affected modules once. Match the depth to the reader: a precise module
and interface explanation for an engineer; the same consequence and decision in domain terms for a
manager. Precision is not jargon, and accessibility is not vagueness.

### Brief the gaps before the map

When presenting a module map, lead with a short plain-language briefing of the gaps it exposes. Rank
by real risk to this product, not by rule order or identifier. For each item, say what it could cost
the product and what fixing it would involve. Use at most six items in the spoken or top-of-report
briefing and point to the full findings for evidence.

Do not use ACIMA terminology, rule ids, requirement ids, or internal defect language in this
briefing. "A consumer reaches into another part's private code" is useful; "ACIMA-D001 is
nonconforming" is not. If the map is accepted and no gaps remain, say so rather than padding the
briefing with generic risks.

### Preserve traceability without exposing it

Structured evidence may retain the internal requirement ID, rule ID, finding classification, source
evidence, enforcement mechanism and authoritative reference. The presentation layer must put the
meaning first. If traceability is useful, add it after the explanation and make it optional, for
example: “Operational values are embedded instead of owned by named immutable declarations.
(Internal reference: A006)” Do not use “A006: operational literal” as a finding title.
Normally omit identifiers unless the user asks for advanced traceability.

### Approval, progress and voice

- An approval request names the files, components, responsibilities and behaviour being authorized.
  Never ask for approval to “resolve A006” or “apply R3”.
- Progress updates describe activities and outcomes, not evaluator phases, rule codes or benchmark
  classifications.
- Spoken output never reads an identifier as though it were an explanation. Say the meaning first;
  offer the internal reference only if the listener asks.

| Level | Audience | Question it answers | Artefact |
|---|---|---|---|
| **Adoption summary** | developer, lead, architect | what was found, why it matters, what to do next, what is proven | `acima/handoff/adoption-summary.md` |
| **Technical evidence** | reviewer, auditor, future agent | exactly which rule, path, line, fingerprint and execution state supports the summary | the enforcer JSON, `acima/evidence/baseline.json`, `acima/evidence/waivers.json`, `acima/evidence/triage.json`, `acima.py report` |

The summary is generated, not improvised:

```bash
python3 skills/acima-adoption/scripts/summarize.py --root <target> --report <run>.json \
  --triage <target>/acima/evidence/triage.json \
  --out <target>/acima/handoff/adoption-summary.md
```

Optional flags: `--initial-report` (reconciles the first measurement with the frozen baseline),
`--claim` (the JSON from `acima.py claim --format json`; the only route to `Verified`),
`--architecture`, `--ci-observed`, `--manual-evidence`, `--catalog`, `--format json`.
Exit `2` means the report, catalog or triage file cannot be used; it never invents a result.

## Summary structure

1. Header: repository, date, architecture family (with its evidence), plain-language status.
2. **Overall result** — one paragraph: what ran, how many findings, what the baseline means.
3. **What this means** — two or three paragraphs of consequence in the team's vocabulary.
4. **Key findings** — at most eight groups, each with impact, affected modules and one remedy.
5. **What should happen next** — one action in full (why, where, done, verification, judgement),
   then no more than four more in order.
6. **What has already been completed** — only what an artefact proves.
7. **What has not been verified** — unexecuted rules, unobserved CI, absent manual evidence,
   detector artefacts, expiring waivers, count reconciliation.
8. **Supporting technical details** — links to the run, baseline, waivers, triage, plan, status.

Do not paste the JSON into the summary. Do not add a health score. A clean gate is a statement
about new findings at one level, not about architectural quality.

## Status vocabulary

Pick exactly one, from the evidence, with the least flattering accurate reading:

| Status | Evidence that supports it |
|---|---|
| Not assessed | no usable run artefact |
| Assessment incomplete | the run has no source files or no execution map; or zero findings but a required rule did not execute |
| Significant issues found | `newFindings > 0` |
| Partially aligned | at least one real defect is present and not waived |
| Baseline established | no new findings and no unwaived defects; findings may remain waived or triaged as detector artefacts |
| Verified | zero findings, every required rule executed or evidenced, and a supplied claim is **FULL CONFORMANCE** with `current: true` |

Precedence follows that order, with one exception: `Verified` is never inferred. Without a claim
artefact the strongest honest result is `Assessment incomplete` when coverage is incomplete, or
`Baseline established` when it is not. “The gate is green” is not `Verified`. A rule-complete claim
that is historical, stale or missing provenance never yields `Verified`; report its `claimState` and
name freshness, not an architecture defect, as the limitation.

## Grouping and traceability

Group internally by `(rule, classification, cluster, severity)`. The technical record keeps the rule
id, count, affected modules, every path and every fingerprint, so a reader can trace the summary to
the run without reading it. The human-facing heading and explanation use the catalog meaning, never
the identifier. Never merge a defect with a detector artefact, and never merge two clusters that need
different remedies: give the triage entry a `cluster` and a `label` when one rule has unrelated
causes.

For a qualitative review, enumerate the validator's `gapRegister` instead of grouping from memory.
Every `gap` and `insufficient_evidence` entry stays attached to its catalog rule, and every
human-readable finding must name at least one current catalog rule. A theme count that does not
reconcile with the distinct rule ids beneath it is a reporting defect; correct the summary before
presenting it.

A group's remedy is the catalog `fix`, quoted rather than paraphrased. If the catalog has no fix,
say so and link the rule page; do not invent one.

### Priority

| Priority | Meaning |
|---|---|
| High | removes or protects an essential boundary; also any new finding |
| Medium | weakens a boundary or creates maintainability risk |
| Low | warnings and cleanup |
| Review | manual rules, unclassified matches, detector artefacts, tooling limits |

Priority is a recommendation about order. It never changes a rule's severity, level or normative
meaning, and it is not a substitute for explaining the consequence.

Among High defects with no `new` finding, take the **smallest** group first: the cheapest change
that proves the remedy is a better first slice than the largest one.

## Defects, detector artefacts, review items

Triage is a recorded decision, not a suppression. It lives in `acima/evidence/triage.json`; the finding
stays in the report and in the gate.

```json
{
  "triage": [
    {"rule": "ACIMA-D009", "classification": "detector-artifact", "owner": "name",
     "reason": "the detector matches a bare identifier, so a module's own Extensions class is read as another module's",
     "evidence": "fixture or issue link", "note": "fix the detector; do not rename the class"}
  ],
  "findings": [
    {"fingerprint": "sha256:...", "classification": "review", "reason": "owner must confirm"}
  ]
}
```

Classifications: `defect` (default), `review`, `detector-artifact`, `tooling-limitation`.
A non-defect entry requires a reason; `cluster` and `label` are optional and exist to split one
rule into unrelated causes.

Language to use, and not use:

- Detector artefact: “the detector matched this pattern; the code is not crossing that boundary”.
  Never “violation”, never code debt, never a reason to rename working code.
- Review item: “needs a person to decide”; list what evidence would settle it.
- Tooling limitation: “the check could not run here”; name the environment and who can run it.
- Confirmed defect: the consequence first; the internal reference belongs only in technical
traceability or an explicit request for it.

## Progress etiquette

Narrate six milestones at most: structure inspected, boundaries identified, checks run, findings
triaged, baseline reviewed, report written. One or two sentences each. Describe the meaningful
activity and result; never narrate evaluator stages, rule codes or benchmark classifications. Do not
announce each command, restate the plan, or explain the implementation of the skill. A blocker gets a
message only when it changes the outcome or needs a decision. The final message is the summary; the
work log belongs in the evidence, not in the conversation.

## Compatibility

- The enforcer report schema is unchanged: no new required field, no renamed field.
- Baseline, waivers and manual evidence are read as before; a missing triage file means every
  finding is a defect, which is the conservative default.
- `summarize.py` writes only when `--out` is passed; otherwise it prints.
- Older artefacts still render: a report without per-finding `status` falls back to
  `newFindings` for priority, and a missing `execution` map yields `Assessment incomplete`.

## What each phase sounds like

Short examples of the interaction contract. Adapt the facts; keep the shape.

**Initial explanation (first-time user).**

> **Where you are:** this is a read-only look; nothing has been changed.
> **What ACIMA is:** a standard with its own portable architectural requirements: module ownership,
> explicit contracts, dependency isolation, data and configuration ownership, and controlled
> composition. Existing approaches can often satisfy them, but compatibility is assessed against the
> requirements, not assumed; some are deliberately stricter. It does not prescribe Clean
> Architecture, DDD, microservices or a rewrite, and it does not replace your overall architecture.
> **What it is not:** a promise that every architecture is compatible, a code-quality score, a
> migration project or a claim that your current design is wrong. Existing good boundaries are
> recognised, not replaced.
> **Limits:** a static check cannot prove runtime behaviour or business correctness.
> **Next:** I will inspect the repository and tell you where ACIMA would help, where it would not,
> and what the smallest useful adoption would cost. No files will be written.

**Assessment (read-only).**

> **Where you are:** nothing has been changed. I inspected the repository and ran the read-only
> analysis.
> **What I found:** three deployable services share one `Common` project, and `Orders` reads
> `Billing`'s internal models directly. That is why a Billing refactor keeps breaking Orders.
> **What it means:** ACIMA can make that dependency explicit and fail a pull request that adds a new
> one. It cannot fix the shared project for you, and it does not require splitting the services.
> **Limits:** the Go enforcer did not run here, so those rules are unproven.
> **Next:** if this is useful, I will propose the smallest adoption — a unit map and a local check.
> No files will be created without your approval.

**Proposal.** Recommendation first, then discovery, what ACIMA requires here, evidence-grounded benefits,
scope in plain English, the exact path table with required/conditional/optional status, tradeoffs,
sequence, and one question: "Would you like me to proceed with the listed files and scope?"

**Recommendation and approval request.**

> **Recommendation:** recommended with limitations. The module boundaries are clear, but Orders and
> Billing still share implementation types, so a change in one can break the other. ACIMA would
> make that edge fail a pull request with a named remedy; it would not remove the shared types or
> split the services.
> **Smallest useful scope:** declare the existing units, keep a measured baseline, and add one local
> check. CI and waivers can wait for a second decision.
> **What stays unchanged:** deployment topology, framework and public APIs.
> **Decision:** may I create the unit map, baseline and local check in the listed paths? A partial
> yes is fine; anything outside that list stays untouched.

**Implementation progress.**

> **Where you are:** I am implementing the approved unit map and local check.
> **Done:** `acima.config.json` now declares five modules; the local check reports 14 existing
> findings, all recorded at adoption.
> **Not done:** no CI gate and no waivers — both were outside the approved list.
> **Next:** review the module map. If it is right, the next decision is whether to gate pull requests.

**Blocker.**

> I stopped before writing the baseline: the Go toolchain is not installed, so that run would be
> incomplete. Nothing was changed. Either install Go and I continue, or I record the Python and
> TypeScript results only and mark the rest unverified.

**Handoff.**

> **What changed:** five units declared, a local check wired, a baseline kept at
> `acima/evidence/baseline-2026-11-09.json`.
> **Verified:** the check runs, finds 14 pre-existing errors, and rejects a new cross-module import.
> **Not verified:** CI is configured but has not been observed on a pull request; the manual rules
> have no evidence, so the claim is a partial assessment.
> **How to use it:** run the check before opening a pull request; a failure names the practical
> problem and the correction. **Next:** approve the CI gate, or watch the check on the next pull
> request.

## Worked translations

These examples demonstrate wording, not alternative definitions. The catalog, standard and rubric
remain authoritative.

### An embedded operational value (`A006`)

**Say:**

> Three operational values are written directly into the implementation: a request timeout, a retry
> limit and a batch size. Each one controls behaviour but has no named owner. A later change can
> update one copy and leave another inconsistent, and a reader cannot tell which value is the policy.
> Name each value once in the scope that owns it, make the declaration immutable where the language
> supports it, and supply environment-dependent values through the composition boundary rather than
> a source constant. This is a candidate for review: equal numbers do not prove two values mean the
> same thing.

### A module-boundary dependency (`L001`)

**Say:**

> The domain logic imports the database adapter directly. That makes the business rules depend on a
> storage choice: changing the database or testing the domain now requires the infrastructure code
> to be present. Define the operation the domain needs as a port, implement that port in the adapter,
> and inject it from the composition boundary so dependencies point inward and the domain stays
> independent of storage.

### A repository requirement labelled `R3`

`R3` is scoped, not globally self-describing. If a repository's requirement register defines it as
dependency isolation, say:

> The module depends directly on another module's private implementation instead of its published
> contract. That bypasses the ownership boundary, so an internal change can break this consumer and
> the two modules become harder to change independently. Depend on the published contract; if it
> lacks an operation, request an additive contract change from its owner.

If the lifecycle chapter is the source, `R3` instead means “separate behaviour from mutable state”:

> A shared service keeps request-specific data in its own fields. The service now lives longer than
> the state it holds, so one request can observe another request's data. Move the state to an
> explicitly owned request or operation boundary, or pass it through the operation instead of
> retaining it in the service.

Name which source applies rather than silently choosing.

### Equal values with different meanings (`D8.4`)

**Say:**

> These two values are both 30, but one is a request timeout and the other is a cache lifetime. They
> belong to different behaviours and different owners; numeric equality does not make them the same
> value. Combining them would make an unrelated change alter both. Keep them separate and name each
> one for its purpose. We need a person to confirm the units, domain meaning and owner before
> treating them as the same value. This is a review criterion, not a finding that the code is wrong.

### An approval request

Source metadata may contain internal scope identifiers. The user hears the actual change:

> I propose creating `acima.config.json` with the five discovered modules and their roles, and
> `acima/evidence/baseline.json` with the current findings frozen as the starting point. This lets the local
> check distinguish existing problems from new ones. It does not add CI, change source code or
> suppress any finding. May I create those two files at those paths?

### An unresolved identifier

**Say:**

> One result refers to a check that is not defined in the installed catalog. I cannot explain what it
> means or recommend a code change without guessing, so I am treating it as a reporting defect. The
> raw evidence is preserved; restore the matching catalog or tool version and re-run before acting
> on that result.

### Spoken output

Do not say “A006, three occurrences.” Say:

> Three operational values are embedded in the code instead of being owned by named declarations.
> That makes policy changes easy to apply inconsistently. I recommend naming each value once and
> keeping the environment-specific ones in configuration.

### Two readers, same finding

For an engineer:

> `Orders` imports `CatalogRepository` from `catalog/impl`. Depend on `Catalog.Contracts` and call
> the published operation; if the operation is missing, request it from the Catalog owner.

For a non-specialist:

> The Orders team is using Catalog's private code instead of the interface Catalog publishes for
> other teams. A change inside Catalog can therefore break Orders without warning. Orders should use
> the published interface, and Catalog should add anything genuinely missing to that interface.

## Decision-ready report contract

Use schema 1.2 for new HTML outcome reports (1.1 remains accepted for reports already generated): it declares the refreshable `progressSections` and pins `adoptionWorkflow.currentStage` and `adoptionWorkflow.asOf`. Answering a report is intent, not approval: answers are ingested with `acima adoption decisions --from`, a draft scope keeps `authorization.explicit: false`, and the approval command still has to run. Keep normative conformance dispositions separate from adoption recommendations:
- Conformance answers whether evidence establishes that an applicable requirement is satisfied. Retain unverified, not assessed, unsupported and blocked as distinct states.
- Recommendation classification answers what kind of action is proposed: required, recommended, optional, or owner decision.

An outcome must explain the capability, why it matters, the practical engineering change, its supporting requirements, prerequisites, classification, verification and limitations. Identify whether it is guaranteed by the standard when implemented and verified, dependent on implementation, merely a potential downstream benefit, or not yet established.

Every empty report section must carry an explicit explanation. Unknown, not assessed, blocked, not applicable and genuinely unnecessary are not interchangeable. Do not infer a clean assessment from an empty findings list.

Keep inspect, create, modify and preserve file inventories separate. A file read as evidence is not a proposed edit. A generated plan or report is not authorization. Preserve the distinction between assessment completion, report generation, proposal completion, implementation completion and verified conformance.