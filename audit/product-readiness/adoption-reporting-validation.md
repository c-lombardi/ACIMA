# Adoption reporting validation

## Method

1. Rendered the eShop run through `skills/acima-adoption/scripts/summarize.py` with the current
   gate report, first measurement, baseline, waivers, triage and adoption plan.
2. Ran `conformance/test_reporting.py` (four tests: grouping, status, no-inference of `Verified`,
   and 221/220 reconciliation).
3. Ran a fresh-reader checklist over the generated summary: ten assertions covering the five
   comprehension questions and the nine eShop clarifications.
4. Attempted an independent evaluator that would see only the summary.

The eShop artefacts were copied to `.scratch/eshop` because the shell and Python mounts differ;
the summary's evidence paths were normalised to `../eShop/...` afterwards. The copy was removed
after validation.

## Criteria

| Criterion | Result | Evidence |
|---|---|---|
| First-time comprehension | **Partial** | all five questions are answerable from the summary by inspection; no independent semantic evaluator ran (see below) |
| Clarity | Pass (structural) | every group has a human title, impact, modules and one remedy; identifiers are parenthetical |
| Actionability | Pass | §4 names the shared-kernel change with why, where, done-state, verification and judgement |
| Prioritization | Pass | 3 defect groups (High) precede 2 artefact groups (Review); D007 chosen as the smallest high-impact slice |
| Conciseness | Pass | 87 lines / 9,580 bytes; 5 groups instead of 220 per-finding rows |
| Traceability | Pass | each group retains rule id, count, modules, all paths and fingerprints; JSON keeps 48 D009 fingerprints and 74 L001 fingerprints |
| Accuracy | Pass | counts match the gate and JSON (122 current, 220 baseline, 98 waived, 221 first run); status is `Baseline established`, never `Verified` |
| Separation | Pass | §3 and §6 distinguish 3 defect groups from 2 detector-artefact groups; artefacts get a tooling remedy |
| Evidence | Pass | §7 links the run, first measurement, baseline, waivers, triage, plan and status |
| Consistency | Pass | the renderer is language-neutral; rule titles and fixes come from the catalog, not from .NET-specific prose |

## Fresh-reader checklist

```
ok   status qualified
ok   3 defects grouped
ok   122 artefacts separated
ok   next action complete
ok   completed evidence
ok   221 vs 220
ok   6 rules named
ok   CI not observed
ok   no claim
ok   scope difference
failed: none
```

The checklist proves the required information is present and correctly labelled. It does not prove
that a person unfamiliar with ACIMA can paraphrase it, which is the remaining gap.

## Independent evaluator

**Not completed.** Three routes were attempted:

- `gpt-5-agent`, `opus-agent`, `basher` and `code-reviewer-multi-prompt` are not available to
  spawn in this environment.
- `claude -p` returned `Not logged in · Please run /login`.
- `codex exec` returned `401 Unauthorized` while refreshing its token.

No evaluator answers are reported, because reporting an invented or self-authored evaluation as
independent would misrepresent the check. The structural checklist above and the manual review in
`adoption-reporting-before-after.md` are the available evidence.

To close the gap, give the summary alone to a developer who has not read the skill or the catalog
and record their answers to the five questions; or authenticate one of the local CLIs and rerun
the same prompt. If they cannot say what is wrong, why it matters, what to do next, what is done
and what is unverified, revise §1/§3/§4/§6 rather than adding detail.

## Scenario limits

- The enforcer was not re-executed: the host has .NET SDK `11.0.100-rc.3`, while eShop pins
  `10.0.302` in `global.json`. The summary is a rendering of the latest recorded run
  (`docs/acima/gate-L1-latest.json`), not a new measurement.
- CI is configured (`acima.yml`) but has not been observed failing a throwaway change; the summary
  says so in §6 and §4.
- Six rules did not execute; two of them (`G004`, `L004`) are required at L1. No conformance claim
  is made.
- The baseline was measured over 498 files and the current run over 499; the summary reports the
  difference instead of reconciling it silently.
- Detector artefacts are recorded by triage, not detected automatically. The decision and its
  reason live in `eshop-triage.json`; if the triage file were wrong, the summary would describe a
  defect as tooling.

## Invariants confirmed

- No rule catalog entry, severity, level, automation value or enforcer was modified.
- No finding was suppressed: current findings are grouped, baseline-only findings are added, and
  every fingerprint remains in the evidence.
- `Verified` is reachable only with a supplied FULL claim; the four tests cover that boundary and
  the zero-findings case.
- No adoption artefact format was broken; triage and summary are additive, and old reports still
  render.
