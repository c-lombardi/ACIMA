# Adoption orchestration

## Pre-flight choice

Ask the user to choose one mode before consequential work:

- **Guided adoption** — assess, propose, generate every deliverable, then wait for explicit
  module-map and scope approval before implementation.
- **Full automation** — explicitly authorized adoption. Apply supported decisions, implement
  enforcement, integrate a detected CI provider where safe, verify, and write the handoff.

A request to “assess”, “adopt”, or “do the whole thing” does not select full automation. The
choice is recorded in `.acima/adoption-workflow.json`; it persists across stages and is not
re-asked. Full automation requires the explicit `--authorize-full` flag and a named consent basis.

Full automation still does **not** authorize deployment, release, publishing, commits, pushes,
secret access, destructive operations, changes outside the selected repository, or overriding an
owner's architectural decision. Those actions need a separate authorization.

## Stages and completion

| Stage | Deliverable | Completes when |
|---|---|---|
| Pre-flight | workflow state with mode and authorization | the mode is explicit and persisted |
| Discovery | inventory plus module-map proposal or authoritative-map evaluation | evidence is recorded |
| Module map | approved config or a pending proposal | map review covers production source |
| Adoption proposal | proposal and scope | every recommendation has an implementation or explicit deferral path |
| Enforcement | config, enforcer copy, waiver file, test record | artifacts exist and do not overwrite user-owned files silently |
| Architectural tests | positive and negative evidence | compliant input passes and a controlled violation is rejected |
| CI | workflow or provider-specific instructions | an existing provider is integrated where safe, or concrete manual steps are recorded |
| Immediate remediation | none, selected, or all decision and result | a separate final decision is recorded after CI; authorized changes are applied or explicitly deferred |
| Verification | fresh map assessment and run results | the post-remediation assessment distinguishes implemented and verified |
| Handoff | changes, commands, limits, reassessment triggers | no dangling stage remains |

For Python and TypeScript targets, the workflow may copy the reference enforcer into
`tools/` and run it. For unsupported languages or toolchains, it records the block and gives the
exact manual command instead of claiming enforcement. A CI file is configuration, not a remote run.

## Resume and stale artifacts

`python3 <skill>/scripts/preflight.py --project <target>` is read-only. Use
`acima.py adoption start --root <target> --mode guided`, or `--mode full --authorize-full`, to create
the persisted workflow. `acima.py adoption status` shows the current stage and one next action.
`acima.py adoption continue` resumes without repeating completed approvals.

If the repository revision changes materially, the workflow marks its artifacts stale. Reassess
the affected map, proposal, scope and verification before treating them as current. Approval of a
module map is not blanket approval to modify application code; full automation or a separate scope
is required.

## Stage outputs

- `.acima/adoption-workflow.json` — mode, stage states, artifacts, decisions, blockers and revision.
- `.acima/module-map.proposal.json` — non-authoritative map candidates.
- `.acima/module-map.approval.json` and `acima.config.json` — only after scoped review.
- `docs/acima/adoption-proposal.md` and `.json` — existing strengths, changes, enforcement,
  impact, risks and verification criteria.
- `.acima/adoption-scope.json` — the approved objective dispositions and consent boundary.
- `docs/acima/enforcement.json`, `.acima/architecture-tests.json` — enforcement and test evidence.
- `docs/acima/ci-integration.json` — provider discovery, integration status and limits.
- `docs/acima/verification.json` — fresh assessment, positive run and controlled negative probe.
- `docs/acima/adoption-handoff.md` — outcome, commands, limitations and reassessment triggers.

## Final remediation decision

The remediation question comes **after** the CI decision and is independent of it. Offer:

- **none** — preserve the implementation and keep the recommendation plan, commands and sequence;
- **selected** — implement only the named recommendations, including clearly disclosed prerequisites;
- **all** — implement every applicable recommendation with a deterministic, evidence-supported change.

Classify maturity from implementation, tests, ownership units, manifests and history, never age alone.
If the evidence is ambiguous, ask the owner and require `--maturity-choice`; do not choose a risk
model silently. The plan records that classification is required and keeps source untouched.
Greenfield work should explicitly recommend applying all applicable fixes, but still requires the
user's confirmation. Small or moderate brownfield work needs one affirmative confirmation. A large or
high-risk brownfield change (broad file scope, contract change, migration or data change) needs two
distinct affirmations: first the scope and risk acknowledgement, then explicit implementation
authorization. Declining preserves the completed map, enforcement and CI work.

Before applying a fix, revalidate it against the current application revision. Preserve unrelated
user changes, do not expand the selected scope, and stop an affected item if it needs an unapproved
design decision or exposes a material regression. Record completed, failed, blocked, deferred and
newly discovered items separately. After implementation, run a fresh assessment; a failed or manual
item stays outstanding and a partial remediation is not complete. A configured CI file remains
complementary and is not a remote-run claim.

Never describe a generated proposal, configured gate or copied enforcer as a verified adoption.
Never describe a partial or blocked stage as complete.
