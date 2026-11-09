# Adoption reporting review

Status: implemented; see `adoption-reporting-before-after.md` and
`adoption-reporting-validation.md`.

## Scope and method

I read the complete adoption skill (`skills/acima-adoption/SKILL.md` and its references),
the templates in `skills/acima-adoption/assets/`, every script that renders adoption output
(`preflight.py`, `inject_violation.py`, `tools/acima.py`, `conformance/acima_claim.py`) and the
eShop adoption artefacts (`.acima/`, `docs/acima/STATUS.md`, `docs/acima/adoption-plan.md`, the
two gate reports). I then rendered the eShop run through the new summary and evaluated it against
the criteria in the request.

No rule catalog entry, severity, level, enforcer, baseline or waiver was changed. The work is
presentation, aggregation and instruction only.

## 1. Existing reporting behaviour

| Surface | Where it comes from | What the reader currently gets | Audience |
|---|---|---|---|
| Preflight | `scripts/preflight.py` `print_text` | `SKL-00x`/`GOV-002` check ids, status symbols, a `BLOCKED`/`READY` verdict, proposed units, numbered next steps | agent, operator |
| Read-only assessment | `acima.py assess` (text/markdown) | verdict codes (`ASSESSED`, `NEEDS_UNIT_MAP`, …), per-rule counts (`ACIMA-D001 22`), the first 12 findings with paths and ids | operator |
| Evidence report | `acima.py report` | every finding as a bullet with rule id, severity, message and path, grouped under a category letter | reviewer |
| Conformance claim | `acima.py claim` | claim class, missing rules, blocking findings — identifiers only | reviewer |
| Detection proof | `inject_violation.py` | `PROVEN`/`NOT PROVEN` per rule id, exit code and paths | operator |
| Persistent status | `assets/status-dashboard.md` → `docs/acima/STATUS.md` | a rule-first table, then the next step, phases and blockers | team |
| Agent close-out | `SKILL.md` Step 6 | four bullets about status, findings, next command and route | team |

The eShop run is representative: 220 frozen findings, 98 waived, 122 detector artefacts, six
unexecuted rules, a configured but unobserved CI gate, and a 221-vs-220 first-run difference.

## 2. Usability problems

1. **Identifier-first.** Preflight, assessment, report and status all lead with `ACIMA-D001`,
   `GOV-002`, `SKL-005`. The catalog has human titles, but no renderer uses them. A reader must
   open `rules.json` or a rule page to know what the sentence is about.
2. **Every finding is a row.** `report_markdown` emits one bullet per finding — 220 in eShop — and
   `assess_text` prints the first twelve with no grouping. The shape of the problem disappears in
   the repetition, and the reader cannot see that 73 matches are one issue.
3. **No defect/artefact distinction in the output.** The gate counts all 122 detector matches as
   error findings. Only the hand-written `STATUS.md` explains that `D009` and `L001` are detector
   artefacts; the machine report, assessment and claim cannot express it. A reader reasonably
   concludes the code has 122 defects.
4. **Baseline and conformance blur.** `0 new findings` and `0 unwaived errors` read like a clean
   bill of health. Nothing in the CLI output states that a passing baseline is not conformance, or
   that six rules did not run.
5. **No next action in the report.** `status` prints one command, the report does not, and the
   assessment's next steps are generic. The most valuable sentence — what to do first and why — is
   written by hand in `STATUS.md`, if at all.
6. **Category letters are not consequences.** Grouping by `D`/`L`/`C`/`A`/`G` explains the catalog,
   not the repository. It does not say what breaks for a consumer.
7. **The first measurement is not reconciled.** eShop's 221 initial findings and 220 frozen
   fingerprints are explained only in prose. A reader cannot tell which finding was dropped or
   whether the baseline is trustworthy.
8. **Terminology is assumed.** “Unit”, “contract”, “baseline”, “waiver”, “conformance” and
   “enforcer” appear without a first-use explanation. The glossary exists but is not in the path of
   the output.
9. **The agent narrates its investigation.** The skill's workflow encourages step-by-step
   commentary (“now I'll inspect…”, “let me read…”), and Step 6 asks for four bullets. The user
   experience becomes a transcript with a status table at the end.
10. **No stable reader-facing artefact.** `STATUS.md` is a dashboard, the gate JSON is evidence and
    the report is a dump; no document is written for the developer who was not in the session.

## 3. Proposed reporting model

Two levels, one generator, no new judgement:

| Level | Artefact | Content |
|---|---|---|
| Adoption summary | `docs/acima/adoption-summary.md` | plain-language result, meaning, grouped key findings, one next action, completed work, unverified limits, links |
| Technical evidence | gate JSON, baseline, waivers, triage, `acima.py report` | rule ids, paths, lines, fingerprints, execution map, raw messages |

The summary is produced by `skills/acima-adoption/scripts/summarize.py`. It reads the run, baseline,
waivers and an optional triage file, and never modifies the target unless `--out` is given.

### Status vocabulary

`Not assessed`, `Assessment incomplete`, `Significant issues found`, `Partially aligned`,
`Baseline established`, `Verified`. `Verified` requires a supplied claim whose class is FULL; the
renderer cannot infer it. `Baseline established` always carries “a passing baseline is not
conformance” in the same sentence.

### Grouping and traceability

Findings are grouped by rule, classification, triage cluster and severity. A group keeps its rule
id, count, modules, every path and every fingerprint. Baseline-only waived findings are their own
groups, so the 98 real defects remain visible after they leave the current run. No finding is
removed; triage only changes how a match is described.

### Defect, detector artefact, review

`.acima/triage.json` records `defect`, `review`, `detector-artifact` or `tooling-limitation`, with a
reason and optional evidence. A non-defect entry requires a reason. Detector artefacts remain in
the gate and in the report; they are reported as tooling problems and never as code debt.

### Priority

High / Medium / Low / Review, derived from rule impact, newness, severity and automation. Among High
defects the smallest group is recommended first — the cheapest change that proves the remedy.

### Progress

Six milestones at most (structure, boundaries, checks, triage, baseline, report); no command
narration; the final message is the summary, not the work log.

### Terminology

First use is explained in line: “module (a unit in ACIMA's vocabulary)”, “baseline (the frozen
snapshot of existing findings)”, “waiver (an owned, expiring exception)”. Formal terms stay where
precision needs them.

## 4. Files and templates changed

| File | Change |
|---|---|
| `skills/acima-adoption/scripts/summarize.py` | new renderer (markdown + JSON), grouping, status, next actions, reconciliation |
| `skills/acima-adoption/assets/adoption-summary.md` | manual fallback with the same seven sections |
| `skills/acima-adoption/assets/triage.template.json` | recorded defect/artefact/review decisions |
| `skills/acima-adoption/references/80-reporting.md` | agent-facing reporting contract, vocabulary and triage schema |
| `skills/acima-adoption/SKILL.md` | reporting section, progress etiquette, command/context/reference entries, summary step |
| `skills/acima-adoption/assets/status-dashboard.md` | problem-first table; rule id moved to its own column; summary link |
| `docs/commands.md` | `summarize.py` usage and the summary/evidence split |
| `docs/guides/ai-agents.md` | agent reporting contract |
| `skills/acima-adoption/manifest.json`, `docs/product-contract.md` | version 1.7.0, new reference/asset |
| `conformance/test_reporting.py` | four regression tests |

## 5. Compatibility

- The enforcer JSON schema is unchanged: no required field added, none renamed.
- Baseline, waiver and manual-evidence formats are read as before.
- A missing triage file means every finding is a defect — the conservative default.
- A report without per-finding `status` falls back to `newFindings`; a report without `execution`
  yields `Assessment incomplete`.
- Old adoption artefacts keep rendering; the summary is additive.
- `summarize.py` exits `0` when it writes a report and `2` for unusable input. It is never a gate.

## 6. Invariants this work preserves

- No rule was added, removed, renumbered, re-levelled or re-severitied.
- No enforcer, baseline matcher or waiver rule changed.
- No finding is suppressed: every current finding appears in a group and its fingerprints remain
  in the evidence; baseline-only findings are added, not hidden.
- A green gate never becomes a conformance claim; only `--claim` with a FULL class can produce
  `Verified`.
- Manual evidence, unexecuted rules, unobserved CI and count differences are reported, not
  resolved in prose.

## 7. Remaining usability risks

- The architecture description is copied from the adoption plan and can be long; a one-sentence
  family statement would read better, but truncating it risks dropping the qualification.
- Priority is heuristic; it orders work, it does not replace an owner's judgement, and the summary
  says so by keeping rule ids and evidence visible.
- The renderer cannot detect a detector artefact by itself; it depends on a recorded triage
  decision with a reason, which is deliberate — automating that would hide a judgement.
- Grouping by rule can still merge unrelated causes within one rule unless triage assigns a
  cluster; the schema supports that split, but a first-time run will not have it.
