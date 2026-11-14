# ACIMA adoption redesign — implementation plan

**Status:** approved implementation plan. This document records the agreed redesign and the order in
which it is being implemented. It does not change the normative ACIMA standard.

**Scope:** one adoption flow, four product phases, read-only preparation, one owner decision record,
CI before remediation, a shrink-only CI baseline, and a repeatable remediation loop.

## Guardrails

- Preserve existing uncommitted work in the repository; touch only adoption-related files.
- Do not commit or push without a separate request.
- Keep every existing assessment, evidence, approval and verification requirement.
- Report environment failures honestly; never weaken a test to obtain a pass.
- Finish each increment with its focused tests before starting the next.

## Target model

`conformance/adoption_workflow.py` remains the authoritative engine. State schema 2 derives the
product phase from recorded stages. `conformance/adoption_decisions.py` owns owner decisions. A new
`conformance/adoption_ci.py` owns the CI socket and baseline ratchet. `remediate` becomes a
post-adoption loop. `render_report.py` projects the engine into six pages with plain language.

## Phases

1. **Assess.** Read-only preflight, discovery, evidence-backed review and the proposed ownership map.
2. **Review and authorize.** The proposal and six-page report; one owner decision record; one approval
   receipt bound to the exact report, objectives and paths.
3. **Implement.** Write the approved configuration at stage 0, install local enforcement, configure
   CI, and perform any authorized remediation.
4. **Verify and hand off.** Fresh checks, evidence, limitations and the handoff.

`Start` is an entry point, not a phase.

## Increments

### 0. Baseline and characterization

Record the focused suite and the existing environment-only failures. Add regression coverage for
read-only assessment, receipt binding, path closure and report identity.

Acceptance: baseline recorded; no production behaviour changed.

### 1. State, phases and statuses

Reduce `PHASE_ORDER` to the four phases. Map stages into them. Add a first-class `failed` status and
state schema 2 with tolerant migration. Derive phases; never persist a guessed phase.

Acceptance: phase derivation and legacy-state reads are tested.

### 2. Read-only preparation

Stop writing `acima.config.json` when the module map is approved. Build and store the proposed
configuration as evidence. Write the authoritative config only at implementation stage 0, after the
scope approval passes every existing guard. Preserve an existing config.

Acceptance: map approval and report generation leave the root config absent; implementation writes
exactly the approved config; stale proposals fail closed.

### 3. One decision record and one approval

Extend the decisions contract to carry map answers, scope objectives, exact paths, notifications and
remediation intent. `approve --decisions` is the single owner command. Keep separate ingestion for
intent-only use. A failed approval writes no target source. Legacy flags remain importers.

Acceptance: one artifact produces one receipt; incomplete or stale decisions are refused.

### 4. One flow

Remove new automated-mode starts, the mode question, `--authorize-full`, and combined map-plus-scope
approval. Legacy `full` state resums through the same checkpoints without retaining any privilege.

Acceptance: no code path starts an automated adoption; legacy state resumes safely.

### 5. CI socket

Add `adoption ci` with a plan, provider-aware idempotent integration, digest-bound approval, decline and
revisit decisions, and explicit `configured` versus `observed` states. CI is proposed before
remediation.

Acceptance: existing workflows are preserved; without approval no workflow is written; no remote run
is claimed.

### 6. CI baseline ratchet

Add a stable-fingerprint baseline. Existing findings are warnings on the first run; new findings are
errors; resolved entries are pruned; growth requires a reviewed update. Wrap enforcer JSON output so
all four language enforcers share the contract without changing each enforcer.

Acceptance: first snapshot warns; a new finding fails; a fixed finding shrinks the baseline;
malformed output fails closed.

### 7. Repeatable remediation

Allow direct remediation when state, config, enforcer, CI configuration and baseline exist. Each round
has its own plan digest, exact paths and confirmations. `none` defers a round, not the loop. New debt
is never baselined. Handoff may be complete while remediation remains available.

Acceptance: repeated none/selected/all rounds; missing prerequisites refused; no terminal dead end.

### 8. Re-entry for CI

Returning for CI refreshes the assessment, map, config proposal and report before proposing CI again.
Refresh performs no source writes.

Acceptance: changed and unchanged repositories; stale approvals invalidated; no jump directly to CI.

### 9. Report, console and plain language

Six pages and eight sections. Plain language: part of the product, temporary exception, baseline.
CI appears before remediation. The report states authorization and limitations without overclaiming.

Acceptance: report-schema and renderer tests pass; one desktop and one phone-width visual check.

### 10. Documentation and regression

Update the skill, references, product docs and changelog. Run the focused suites, the end-to-end
guided flow and the skill bundle check. Inspect the final diff; unrelated work stays untouched.

## Execution status (2026-11-14)

Implemented: the four-phase model and schema-2 migration; read-only proposed configuration; one
`approve --decisions` command; removal of new automated starts; CI planning, decline, digest approval
and shrink-only baseline; CI-before-remediation; per-round remediation records; CI re-entry refresh;
and the reader-facing report page names. The skill, references, quickstart, brownfield guide,
product notes and changelog were updated to the one-flow model.

Verified: `conformance.test_adoption_ci` (8 tests), `test_consent_workflow` (6 tests), the
report/guidance suites, and the focused adoption suite (208 tests). The only focused-suite failures
are the four known environment cases: `git`, `dotnet` and `go` are not installed on the runner.

Not claimed: the report was not visually inspected in a browser, and the skill bundle check still
reports pre-existing `.NET` `obj/` drift outside the adoption files. No commit or push was made.

## Compatibility

| Area | Rule |
|---|---|
| State | Schema 1 migrates to 2; legacy `full` resumes gated |
| Config | Existing config preserved; new flow writes only after implementation approval |
| Report | Schema 1.3 remains readable; new schema carries phase and console identity |
| CLI | `--mode guided` is a no-op; new `full` starts are refused |
| CI | Existing provider integration reused; no duplicate step |
| Baseline | Created only when CI is approved |

## Definition of done

- One flow; no automated branch remains.
- The assessment can complete with named unresolved evidence; no false conformance.
- No config before implementation authorization.
- One decision record produces one approval receipt.
- CI records a shrink-only baseline; configured is not observed.
- Remediation repeats none/selected/all with per-round approval.
- Re-entry refreshes before proposing CI.
- The report and handoff never claim more than the evidence proves.
