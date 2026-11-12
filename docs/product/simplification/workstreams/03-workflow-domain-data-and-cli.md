# WS-03: Workflow, domain data and CLI

**Outcome:** adoption behaviour is easy to reason about because the business rules, authoritative data, orchestration and external interfaces have clear responsibilities.

**Depends on:** WS-00 product and adoption experience contract.

## Owned files

- conformance/adoption_workflow.py
- conformance/module_map.py
- conformance/adoption_reports.py
- tools/acima.py
- conformance/test_adoption_workflow.py
- conformance/test_module_map.py
- conformance/test_cli.py
- conformance/test_adoption_scenarios.py, only when required by a behaviour change

Do not edit skills/acima-adoption, report renderer/schema/CSS, language enforcers or product-facing Markdown.

## Objective

Inspect the adoption engine and CLI as a business workflow, not as a collection of long Python files. Separate responsibilities where they have distinct meaning and change independently. Keep the system small and deterministic.

## Required investigation

Map these responsibilities and their current source of truth:

1. repository discovery and evidence collection;
2. module-map discovery, candidate evidence, review and approval provenance;
3. the 56-rule qualitative review and coverage validation;
4. deterministic conformance run and formal claim;
5. fit/value assessment and level recommendation;
6. proposal and report-model preparation;
7. workflow state, phase prerequisites, resume and next-action calculation;
8. exact report digest and approval receipt;
9. approved scope, stage selection and remediation decision;
10. local implementation, CI integration decision and verification;
11. CLI parsing, output formatting and error translation.

Identify duplicated business rules, hidden data dependencies, stale state, accidental coupling and places where the CLI or agent performs decisions that belong to the deterministic workflow.

## Architecture direction

Apply these patterns selectively:

- Functional core, imperative shell for deterministic assessment decisions, approval validation and state transitions.
- Ports and adapters around repository access, Git, filesystem writes, subprocess execution and report rendering.
- One bounded responsibility and one canonical data owner for assessment, module ownership, conformance, adoption workflow and report preparation.
- One application orchestrator to coordinate the sequence and enforce prerequisites.
- Explicit versioned contracts between the workflow and the CLI, skill and renderer.

Do not introduce microservices, event sourcing, CQRS infrastructure, a generic plugin system or abstractions that have no concrete testability or change-isolation benefit.

## Required behaviour

- The engine owns state transitions and prerequisites. The CLI displays and invokes them; it must not reimplement workflow policy.
- An approval receipt is a canonical record with reviewer, date, report/proposal digest, repository identity and exact scope. It cannot be inferred from files or conversation text.
- The module map has one authoritative representation. Proposed candidates remain distinct from approved ownership.
- The report model is a projection of assessment, map, conformance and workflow evidence. It must not become a second source of facts.
- Every state has a clear meaning. Complete, in progress, awaiting review, approved, declined, deferred, blocked and failed are not interchangeable.
- Resume reuses valid evidence but invalidates evidence made stale by repository, report, proposal, config or approval changes.
- Every response provides one next action with prerequisite, user-visible effect, write effect and approval requirement.
- A missing map blocks only ownership-dependent work; it must not stop independent assessment.
- Scope and partial approval are respected. New paths or dependencies require a new decision.
- Preserve the separate CI, notifications, agent-guidance and remediation decisions required by the existing skill.
- CLI errors are concise and human-readable without hiding detailed technical evidence from JSON/diagnostic output.

## Refactoring rules

- First establish current contracts and tests, then extract one responsibility at a time.
- Preserve public CLI commands and JSON compatibility unless there is a deliberate, documented versioned change.
- Prefer a small pure function and a clear input/output contract over a generic class hierarchy.
- Do not pass a global mutable context object through every helper when explicit parameters are clearer.
- Do not copy the same assessment or approval facts into several mutable files.
- Keep filesystem and subprocess effects at explicit boundary functions.
- If the code should remain in one file, explain why its responsibilities genuinely change together.

## Acceptance

- A phase cannot advance unless its actual prerequisites are satisfied.
- No code path can write to the target before explicit exact-scope approval.
- Guided and automated modes share the same requirements and authorization checks.
- Stale report/proposal/repository evidence invalidates stale approval and triggers a clear next review.
- Map/config state and review provenance cannot diverge silently.
- Report model outputs reconcile to authoritative records.
- Status and errors make it apparent what ACIMA did, what remains and what happens next.
- Focused workflow, module-map, CLI and scenario tests pass without weakening existing assertions.

## Handoff

Return:
- a component/contract map of the resulting workflow;
- authoritative data owner for each record;
- state-transition diagram and invalid transitions;
- adapters and external side effects;
- changed files and compatibility notes;
- focused test results and unresolved design choices.
