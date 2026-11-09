# Adoption reporting: before and after

Scenario: the eShop repository, L1, run `docs/acima/gate-L1-latest.json` (499 source files),
frozen baseline 220 fingerprints, 98 waivers, 221 findings in the first measurement. The summary
was generated with:

```bash
python3 skills/acima-adoption/scripts/summarize.py \
  --root ../eShop \
  --report ../eShop/docs/acima/gate-L1-latest.json \
  --initial-report ../eShop/docs/acima/gate-L1-baseline.json \
  --triage audit/product-readiness/eshop-triage.json \
  --out audit/product-readiness/eshop-adoption-summary.md
```

Full outputs: [`eshop-adoption-summary.md`](eshop-adoption-summary.md) and
[`eshop-adoption-summary.json`](eshop-adoption-summary.json).

## Before — the existing status report (excerpt)

```markdown
## 1. Where you are

... The number that matters: **0 new findings** against the frozen baseline, from **499 source
files**. The measured tree has **220 findings at L1**: 98 are real defects, waived individually ...
122 are **enforcer detector artefacts** ...

## 2. What is wrong, and the correction

| # | Rule | File | Why it is wrong | Correction | Owner | Blocks |
|---|---|---|---|---|---|---|
| 1 | `ACIMA-D001` (22) | `src/Basket.API/Basket.API.csproj:17` ... | Each service references another module's **implementation** ... | Replace each `ProjectReference` ... | c-lombardi | First slice / L2 |
| 4 | `ACIMA-D009` (48) — **detector artefact** | `src/Basket.API/Extensions/Extensions.cs:6` ... | The detector matches a bare identifier ... | Fix the detector upstream ... | c-lombardi | Conformance only |
```

The table is readable only after the reader accepts that the first column is an internal code,
learns what `D001` and `D009` mean, and trusts a hand-written “detector artefact” note. The raw
`acima.py report` for the same run has 220 individual bullets and no grouping or next action.

## After — the generated adoption summary (excerpt)

Header and overall result:

```markdown
# ACIMA Repository Assessment

**Repository:** eshop
**Assessment date:** 2026-11-09
**Architecture:** microservices — one deployable per service, Aspire as the composition ...
**Assessment status:** **Baseline established** — The measured findings are recorded against a
frozen baseline and the gate reports no new findings. A passing baseline is not architectural
conformance.

## 1. Overall result

122 findings in the current run, none new, 122 produced by the detector rather than by the code.

The frozen baseline contains **220** fingerprints measured over 498 source files. 98 findings
carry owned waivers. This run contains **122** findings, of which 122 are detector artefacts.
```

Key findings — problem first, identifier second:

```markdown
## 3. Key findings

| Finding | Impact | Affected areas | Recommended action |
|---|---|---|---|
| Shared kernel violation (`ACIMA-D007`, 3 occurrences, baseline, waived) | Modules can reach across a boundary ... | 1 module: messaging.contracts | Move the type ... keep only dependency-free values in the kernel. |
| Implementation references another implementation (`ACIMA-D001`, 22 occurrences, baseline, waived) | ... | 10 modules: basket, catalog, hybridapp, identity +6 more | Import the provider's contracts port ... |
| Implementation type published outside the module (`ACIMA-L003`, 73 occurrences, baseline, waived) | ... | 10 modules ... | Make the type internal ... |
| Access to another module's internals (`ACIMA-D009`, 48 occurrences, detector artifact) | The detector matched this pattern, but the match does not describe a defect ... | 13 modules ... | Report the detector problem ... do not rename working code. |
| Domain references infrastructure (`ACIMA-L001`, 74 occurrences, detector artifact) | ... | 5 modules ... | Report the detector problem ... |
```

The next action, and the limits:

```markdown
## 4. What should happen next?

**Shared kernel violation.** Move the type to the owning module or to the contract project that
needs it, and keep only dependency-free values in the kernel.

- **Why:** Modules can reach across a boundary that was meant to contain them ...
- **Where:** messaging.contracts
- **Done when:** `ACIMA-D007` no longer appears in the enforcer report.
- **Verified by:** Run the enforcer again and confirm this rule is gone and the gate reports no new findings.
- **Needs human judgement:** no

## 6. What has not been verified?

- 6 rules did not run: `ACIMA-A002` (Cross-module configuration key), ... (`ACIMA-L004`).
- At the declared level, `ACIMA-G004`, `ACIMA-L004` still need executed evidence or a recorded manual review.
- 98 waivers are in force; the earliest expiry is 2027-02-07.
- The CI gate has not been observed running; a workflow file proves configuration, not enforcement.
- No full-conformance claim was supplied ...
- 122 findings are detector artefacts, not architectural defects ...
- The current run has 122 findings; the baseline records 220 ...
- Source scope changed: the baseline was measured over 498 files, this run over 499.
- The first measurement reported **221** findings; the frozen baseline contains **220** ...
  `ACIMA-G001` ×1 (Undocumented exception) ...
```

## The nine required clarifications

1. **The 98 architectural defects are explained as problems.** They appear as three groups with
   titles, counts, affected modules and the catalog remedy: shared kernel (3), implementation →
   implementation (22), implementation type published outside the module (73). They are marked
   `baseline, waived`, which is why they no longer appear in the run.
2. **The 122 suspected artefacts are separate.** `D009` (48) and `L001` (74) are labelled
   `detector artifact`, grouped by cause in the triage file, and given a detector remedy.
3. **Artefacts are not defects.** The impact column says the match does not describe a defect; §6
   says they are not evidence the code is wrong; the next action is to fix the detector, not code.
4. **The highest-value next action is ordinary language.** “Shared kernel violation” plus the
   concrete move, why it matters, where it belongs, done-state and verification.
5. **The full mapping to identifiers is preserved.** Every group names its rule in parentheses;
   §7 links the run; the JSON output keeps every fingerprint and path. §6 names each unexecuted
   rule with its title.
6. **221 vs 220 is reconciled, not chosen.** The summary states both counts, identifies the one
   finding in the first run that is not in the baseline (`ACIMA-G001`, the missing-waiver finding),
   and explains which artefact is authoritative.
7. **A passing baseline is not compliance.** The status is `Baseline established`, immediately
   qualified: “A passing baseline is not architectural conformance.” §1 repeats it; §6 says the
   run has 122 findings while the baseline has 220.
8. **Configured and observed CI are distinct.** §5 says the workflow exists; §6 says it has not
   been observed, and the next-actions list asks for a throwaway failing run.
9. **Manual evidence and conformance limits survive.** Six unexecuted rules, the two required at
   L1 (`G004`, `L004`), the absence of a claim, and the waiver expiry are all in §6.

## Measured differences

| Metric | Before (`STATUS.md`, hand-written) | After (generated summary) |
|---|---|---|
| Length | 78 lines / 7,762 bytes | 87 lines / 9,580 bytes |
| Finding presentation | 5 hand-written rows, rule id first | 5 groups, human title first, id in parentheses |
| Defects visible after waiver | named in prose | 3 groups, 98 occurrences, modules and remedies |
| Artefact separation | hand-written note in two rows | classification + reason + tooling remedy + §6 |
| Status claim | “0 new findings” and a `baselined` phase | six-term status, qualified in the same sentence |
| Next action | written by hand, one command | selected from evidence, with why/where/done/verify |
| Count reconciliation | prose | explicit 221/220 with the differing rule |
| Rule ids | primary labels | secondary labels; full detail in the linked run |

Identifier mentions rise from 6 to 15 because the summary names every unexecuted rule and keeps
each group traceable. They are no longer required to understand a sentence: every one appears
after a human title, and §6 pairs each with its title.

## Traceability example

The `ACIMA-D009` group (48 occurrences, 13 modules) is one row. The JSON output for the same group
contains 48 fingerprints and 48 paths; each one is also in `gate-L1-latest.json` with its line and
message. Nothing is aggregated away, and the triage entry records why the group is an artefact.
The same is true for the three baseline groups: their 98 fingerprints are in
`.acima/waivers.json` and in the first-run report.

## Note on values

The numbers above are eShop test data used to validate the reporting model. None of them is
hardcoded in the skill; the renderer derives counts, groups, status and reconciliation from the
supplied artefacts.
