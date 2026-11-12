# WS-07: Integration and release gate

**Role:** integrator and final reviewer. Run only after WS-01 through WS-06 have returned their handoffs.

## Authority

The integrator owns shared contracts, conflict resolution, final file ownership and release verification. It does not silently rewrite a workstream's intent. Return a conflict to the relevant owner when a decision would change product guarantees.

## Required sequence

1. Check the baseline and all in-progress work. Confirm that no unrelated local change was discarded.
2. Read the WS-00 product contract and every workstream handoff.
3. Compare the same product terms, phase names, guided/automated definitions and completion criteria across PRODUCT.md, README.md, the adoption skill, CLI, report and supporting references.
4. Reconcile duplicate data fields and approval/state representations. Keep one authoritative source for each business fact.
5. Resolve overlapping file edits and merge each workstream's output without losing useful changes.
6. Run focused tests for every workstream.
7. Regenerate the standalone adoption-skill vendor bundle from canonical sources and run its integrity check.
8. Run the full conformance suite and the adoption scenario matrix.
9. Review generated report pages and inspect the human-facing output. Preserve known accessibility manual checks.
10. Verify the repository diff, status and file inventory. No commit or push is included in this task.

## Cross-cutting acceptance

- The product can be described in plain English without internal IDs.
- The user journey is identical in meaning across the skill, CLI, docs and HTML report.
- Guided and automated differ only in checkpoint cadence and grouping.
- All 56 requirement dispositions, map approval, report digest, exact scope, partial approval, CI/notification/guidance decisions, separate remediation, no-write-before-consent and fresh handoff gates remain intact.
- Assessment and report generation remain read-only with respect to target source and CI.
- Business rules have one owner. CLI, skill and report are adapters or projections.
- Agent instructions use progressive disclosure and clear per-phase/task contracts.
- Existing architecture and user-authored instructions are preserved.
- All tests and bundle checks have actual results. Unexecuted conversations and manual checks are identified.
- No full-conformance, production-readiness or independent-validation claim exceeds the available evidence.

## Handoff

Produce:
- the final integrated product journey and workstream completion table;
- changed files grouped by workstream;
- focused and full validation results;
- unresolved or intentionally deferred work;
- manual review tasks still required;
- the exact current Git status and commit baseline;
- one recommended next action for the product owner.

Do not commit, push, merge to a remote branch, deploy or release.
