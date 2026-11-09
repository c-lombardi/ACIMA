# Reporting an adoption

Two audiences read an adoption: the people who own the repository, and the people who audit the
run. Give them two different documents, and make the first one the product.

| Level | Audience | Question it answers | Artefact |
|---|---|---|---|
| **Adoption summary** | developer, lead, architect | what was found, why it matters, what to do next, what is proven | `docs/acima/adoption-summary.md` |
| **Technical evidence** | reviewer, auditor, future agent | exactly which rule, path, line, fingerprint and execution state supports the summary | the enforcer JSON, `.acima/baseline.json`, `.acima/waivers.json`, `.acima/triage.json`, `acima.py report` |

The summary is generated, not improvised:

```bash
python3 skills/acima-adoption/scripts/summarize.py --root <target> --report <run>.json \
  --triage <target>/.acima/triage.json \
  --out <target>/docs/acima/adoption-summary.md
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
| Verified | zero findings, every required rule executed or evidenced, and a supplied claim is **FULL CONFORMANCE** |

Precedence follows that order, with one exception: `Verified` is never inferred. Without a claim
artefact the strongest honest result is `Assessment incomplete` when coverage is incomplete, or
`Baseline established` when it is not. “The gate is green” is not `Verified`.

## Grouping and traceability

Group by `(rule, classification, cluster, severity)`. The group keeps its rule id, count, affected
modules, every path and every fingerprint, so a reader can trace the summary to the run without
reading it. Never merge a defect with a detector artefact, and never merge two clusters that need
different remedies: give the triage entry a `cluster` and a `label` when one rule has unrelated
causes.

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
meaning, and it is not a substitute for the rule id.

Among High defects with no `new` finding, take the **smallest** group first: the cheapest change
that proves the remedy is a better first slice than the largest one.

## Defects, detector artefacts, review items

Triage is a recorded decision, not a suppression. It lives in `.acima/triage.json`; the finding
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
- Confirmed defect: the consequence first, then the rule id.

## Progress etiquette

Narrate six milestones at most: structure inspected, boundaries identified, checks run, findings
triaged, baseline reviewed, report written. One or two sentences each. Do not announce each
command, restate the plan, or explain the implementation of the skill. A blocker gets a message
only when it changes the outcome or needs a decision. The final message is the summary; the work
log belongs in the evidence, not in the conversation.

## Compatibility

- The enforcer report schema is unchanged: no new required field, no renamed field.
- Baseline, waivers and manual evidence are read as before; a missing triage file means every
  finding is a defect, which is the conservative default.
- `summarize.py` writes only when `--out` is passed; otherwise it prints.
- Older artefacts still render: a report without per-finding `status` falls back to
  `newFindings` for priority, and a missing `execution` map yields `Assessment incomplete`.

## What each phase sounds like

Short examples of the interaction contract. Adapt the facts; keep the shape.

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

**Proposal.** Recommendation first, then discovery, what ACIMA adds, evidence-grounded benefits,
scope in plain English, the exact path table with required/conditional/optional status, tradeoffs,
sequence, and one question: "Would you like me to proceed with the listed files and scope?"

**Implementation progress.**

> **Where you are:** phase 4, implementing the approved unit map and local check.
> **Done:** `acima.config.json` now declares five units; the local check reports 14 findings, all
> pre-existing.
> **Not done:** no CI gate and no waivers — both were outside the approved list.
> **Next:** review the unit map. If it is right, the next decision is whether to gate pull requests.

**Blocker.**

> I stopped before writing the baseline: the Go toolchain is not installed, so that run would be
> incomplete. Nothing was changed. Either install Go and I continue, or I record the Python and
> TypeScript results only and mark the rest unverified.

**Handoff.**

> **What changed:** five units declared, a local check wired, a baseline kept at
> `docs/acima/baseline-2026-11-09.json`.
> **Verified:** the check runs, finds 14 pre-existing errors, and rejects a new cross-module import.
> **Not verified:** CI is configured but has not been observed on a pull request; the manual rules
> have no evidence, so the claim is a partial assessment.
> **How to use it:** run the check before opening a pull request; a failure names the rule and its
> remedy. **Next:** approve the CI gate, or watch the check on the next pull request.
