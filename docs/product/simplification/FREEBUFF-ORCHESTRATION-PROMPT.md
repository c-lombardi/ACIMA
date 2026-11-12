# Freebuff orchestration prompt: ACIMA product and adoption simplification

**Target repository:** G:\Code Repository\ACIMA

**Preferred model:** DeepSeek V4.1 Flash Fast, high reasoning.

**Status:** prepared prompt. Do not submit repository content to the model until the operator explicitly accepts the Freebuff model's displayed data-use notice.

## Privacy gate

The local Freebuff model picker displayed **"May use data for AI training"** for DeepSeek V4.1 Flash Fast. Freebuff's current README explains that when a model/feature carries a training notice, submissions may be retained and used to develop, train, test, evaluate or improve models/products, and may be shared with third parties. **Explicit operator authorization was given in this ChatGPT conversation on 2026-11-11.** The operator accepted the displayed data-use notice and authorized this ACIMA repository work to be submitted to DeepSeek V4.1 Flash Fast. This is the required approval. Do not ask for it again.

The model picker notice and actual selected model must still be captured in the execution record. Do not silently switch to another model if this model is unavailable.

Source: the locally installed Freebuff README and the model picker displayed during this session. Re-check the model notice at execution time.

## Your role

Act as the orchestrator and integration lead for a product-wide simplification of ACIMA.

The goal is not to shorten files mechanically. The goal is to make ACIMA straightforward to understand, assess, adopt, operate and maintain, from the product promise down through the user journey, skill instructions, workflow logic, data contracts, CLI, report and reference enforcers.

The product experience and guarantees are already defined in:
- docs/product/simplification/README.md
- docs/product/simplification/workstreams/00-product-contract.md

Read both before dispatching any worker. Treat the product contract as the shared source of truth for these tasks.

## First action: preserve and inspect the baseline

Before editing:
1. Inspect Git status, current branch and HEAD.
2. Record all current uncommitted changes.
3. The expected starting commit is 1236b37987a8523f5e5abb847372c34e07e8ecd4. Verify rather than assume.
4. At the time this plan was prepared, these six files were already uncommitted and belong to WS-05:
   - examples/dotnet/tools/Acima.ArchTests/Program.cs
   - examples/go/tools/archtest/main.go
   - examples/python/tools/acima_arch.py
   - examples/typescript/tools/acima-arch.mjs
   - conformance/test_waiver_fingerprints.py
   - conformance/test_value_ownership.py
5. Preserve those changes. Do not reset, overwrite, discard or stage them as unrelated cleanup.
6. Do not inspect or modify ailib.tools. ACIMA is the only product-development target.
7. Do not commit, push, switch branches, merge remotely, deploy or release.

## Parallel dispatch

Use separate Freebuff subagents/workspaces for these six workstreams. Keep file ownership disjoint. If true isolated parallel workspaces are unavailable, do not launch competing writers in one shared working tree. Report the limitation and use read-only parallel audits until safe editing can be arranged.

Dispatch these six briefs concurrently once the baseline has been recorded:

| Worker | Brief | Primary ownership |
|---|---|---|
| WS-01 | workstreams/01-product-language-and-docs.md | PRODUCT.md, README.md, docs/commands.md, quickstart/product docs |
| WS-02 | workstreams/02-adoption-skill-and-prompt-architecture.md | Skill entry point, adoption references and manifest |
| WS-03 | workstreams/03-workflow-domain-data-and-cli.md | Workflow engine, module map, report-model builder and CLI |
| WS-04 | workstreams/04-report-model-and-reader-experience.md | Report schema, renderer, stylesheet, DESIGN.md and report tests |
| WS-05 | workstreams/05-enforcement-engine-and-waiver-integrity.md | Four language enforcers and their fingerprints/waiver/profile tests |
| WS-06 | workstreams/06-independent-qa-and-regression.md | Read-only audit, acceptance matrix and QA results |

Each worker must:
- read WS-00 and its own brief;
- inspect the full current implementation before editing;
- only modify its owned paths;
- produce the handoff requested by its brief;
- explain every product or architecture decision that affects another workstream;
- keep unknowns and unsupported claims visible;
- run its focused tests and report the actual commands and results;
- stop and request integration when it needs to change another worker's files.

WS-06 is independent QA. It must not rewrite production files or weaken tests to create a pass. It may propose missing tests; the integrator decides where to add them.

## Shared architectural direction

The implementation should reflect the product's business responsibilities and authoritative data:

- Assessment owns repository observations, evidence and requirement dispositions.
- Ownership/conformance owns approved module mapping, dependency graph and deterministic findings.
- Adoption workflow owns phases, prerequisites, approvals, scope, resumption and one next action.
- Proposal/reporting projects authoritative evidence into reader-facing views.
- CLI, filesystem, Git, language processes, HTML renderer and agent runtime are adapters.

Apply functional core/imperative shell, ports-and-adapters, bounded contexts, explicit orchestration and single-source-of-truth data ownership where those patterns reduce real coupling.

Do not introduce microservices, event sourcing, generic plugin frameworks, elaborate CQRS or abstraction layers without a demonstrated need. Prefer small deterministic operations and explicit contracts.

## Product and safety invariants

All workers must preserve:
- read-only assessment;
- individual evidence-backed dispositions for all 56 current requirements;
- continued independent qualitative review when a map is absent;
- no inferred or layout-only ownership approval;
- ownership-dependent checks blocked until a sufficient map is explicitly approved;
- identical evidence quality and approval authority in guided and automated mode;
- mandatory six-page offline report and exact presentation/digest review before approval;
- explicit exact-path and stage authorization, including partial approval;
- no writes before approval and no scope expansion;
- existing architecture and user-authored instructions preserved;
- CI configuration never represented as an observed CI run;
- CI, adoption notifications, agent guidance and remediation decisions kept separate where required by the skill;
- no optional organizational artefacts by default;
- conformance claims computed from current evidence, never inferred from a clean error count;
- no health score or unsupported production-readiness claim;
- current unsupported languages, unexecuted rules, manual evidence and draft status kept visible.

Do not change the normative standard or 56-rule catalog as part of this simplification unless the operator separately approves a standard-governance change.

## Integration gate

After all workers finish, read:
- every workstream handoff;
- every changed file and diff;
- WS-06's independent acceptance matrix and QA results.

Then execute WS-07 from workstreams/07-integration-and-release.md.

Only the integrator may resolve shared-file conflicts. Reconcile the phase names, terminology, workflow state/data contracts, report schema, user approval language and "what happens next" wording across all surfaces.

Regenerate the standalone skill vendor bundle only after canonical skill sources are stable.

## Required validation

Run focused tests first, then the complete verification set:
- module-map tests;
- adoption-workflow tests;
- CLI tests;
- HTML-report tests;
- cross-language fingerprint/waiver tests;
- value/configuration tests;
- .NET profile and false-positive fixtures;
- executable adoption scenario matrix;
- full conformance runner;
- skill-bundle integrity check;
- whitespace/conflict checks.

Do not change test assertions merely to make the suite pass. If a test exposes a contradiction between current behaviour and the product contract, report the contradiction and resolve it in the owning workstream.

A deterministic scenario test does not prove a live model conversation is understandable. If no live conversation is run and scored, mark conversational validation "not executed".

## Final output

Return:
1. a workstream table: completed, partial, blocked, not started;
2. the product journey after changes, using the canonical phase names;
3. changed files grouped by workstream;
4. focused and full test commands with actual results;
5. all product guarantees checked and the evidence for each;
6. remaining risks, unknowns and manual checks;
7. current Git status and uncommitted diff summary;
8. the single next decision for the operator.

Do not report that all workers ran in parallel unless separate active worker sessions were observed. Do not report a task complete without its actual diff and test evidence.
