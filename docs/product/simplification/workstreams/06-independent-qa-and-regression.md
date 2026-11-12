# WS-06: Independent QA and regression

**Outcome:** an independent reviewer proves that the simplified experience remains truthful, understandable and safe, and reports any gap without fixing it silently.

**Depends on:** WS-00 product and adoption experience contract. Read-only inspection can begin immediately. Final validation waits for WS-01 through WS-05.

## Owned files

- docs/product/simplification/qa/BASELINE.md
- docs/product/simplification/qa/ACCEPTANCE-MATRIX.md
- docs/product/simplification/qa/RESULTS.md

Do not edit production code, skills, docs owned by other workstreams or existing tests. Do not weaken or rewrite tests to get a passing result.

## Baseline

Initial committed checkpoint: 1236b37987a8523f5e5abb847372c34e07e8ecd4.

At the start of this initiative, the following six files were uncommitted and belong to WS-05:
- examples/dotnet/tools/Acima.ArchTests/Program.cs
- examples/go/tools/archtest/main.go
- examples/python/tools/acima_arch.py
- examples/typescript/tools/acima-arch.mjs
- conformance/test_waiver_fingerprints.py
- conformance/test_value_ownership.py

Preserve this baseline record and update it as the integrator changes the working tree.

## Objective

Review the intended product experience, agent instructions, workflow engine, CLI, report and enforcers independently. Distinguish deterministic correctness, content quality and untested user experience.

## Required audit questions

### Product comprehension
- Can a new user explain what ACIMA does, what it does not do and why it might help?
- Is every phase purpose, output, user decision, done condition and next action explicit?
- Are guided and automated modes clear and consistent?

### Evidence and authority
- Are all 56 requirements individually covered?
- Are evidence, reviewer provenance, catalog freshness and unresolved states preserved?
- Is module discovery always distinguished from approved ownership?
- Can assessment continue when ownership-dependent checks are blocked?
- Is report presentation and digest approval still mandatory?
- Are exact path scope and partial approval preserved?
- Can a stale report, proposal or repository state invalidate old approval?

### Workflow and data
- Does each business fact have one canonical owner?
- Are assessment, map, conformance, workflow state, approval and report projections distinct?
- Can the workflow resume without bypassing gates or duplicating authoritative evidence?
- Is the single next action correct for every status?
- Do CLI and agent outputs show the same facts without reimplementing policy?

### Report and communication
- Can a reader understand the recommendation and consequences before technical details?
- Are existing, proposed, approved, implemented and verified states distinct?
- Do files-only-inspected remain separate from proposed modifications?
- Are missing values explained instead of silently omitted?
- Are IDs translated to plain-language explanations?
- Are accessibility targets and manual release checks accurate?

### Engine and governance
- Do four enforcers follow the same fingerprint/waiver identity contract?
- Do baselines suppress only known findings?
- Are genuine violations detected by negative fixtures?
- Does unsupported or unexecuted analysis fail honestly?
- Does the report/CLI avoid full-conformance claims from partial evidence?

## Verification requirements

Run the focused tests owned by each workstream after its changes stabilize. Then run:
- module-map tests;
- adoption-workflow tests;
- CLI tests;
- HTML-report tests;
- cross-language waiver/fingerprint tests;
- value/configuration tests;
- .NET profile and false-positive fixtures;
- the executable adoption scenario matrix;
- the complete conformance runner;
- standalone skill-bundle integrity check;
- git diff whitespace/conflict checks.

Inspect failures. Do not treat an existing or unrelated test failure as a pass; record it with the evidence needed to reproduce it.

Conversation quality is a separate test category. A passing script or structured test does not prove that an LLM conversation is understandable. If a live guided and automated conversation cannot be run and scored, state that limitation.

## Acceptance

- Every product guarantee has at least one deterministic test, manual test or clearly recorded external limitation.
- Every workstream's acceptance claims are supported by test output, file inspection or an explicit manual check.
- No requirement is marked verified without evidence.
- The acceptance matrix includes guided and automated flows, partial approval, deferral, decline, stale approval, missing module map, existing authoritative map, incomplete 56-rule review, existing enforcement, no CI provider, CI decline, no remediation, selected remediation, and new scope discovery.
- The results file separates pass, fail, blocked, not run and manual review.

## Handoff

Return a concise independent review: product comprehension findings, safety/evidence regressions, failing tests, missing manual checks, scope drift and the highest-risk remaining issue. Do not modify another workstream's output to make the review pass.
