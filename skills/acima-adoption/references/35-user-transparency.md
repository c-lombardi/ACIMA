# User transparency and informed adoption


**The user must remain informed at every phase.** Do not make them infer what ACIMA provides, what
the skill is doing, what it will change, why it is doing it, or what happened. Transparency is a
continuous requirement, not a one-time introduction or a final report.

### Explain what the user will acquire

Before beginning a substantive assessment or adoption, give a concise, repository-aware explanation
of what ACIMA can provide. Do not promise that every capability applies or will be implemented.
Explain that ACIMA is intended to give the codebase:

- Explicit ownership for modules and their implementations.
- Published contracts that make allowed dependencies visible.
- Enforceable dependency boundaries and direction, including protection from private implementation
  coupling and dependency cycles.
- Clear ownership of data, configuration, composition, lifecycle, state and effects where applicable.
- Deterministic checks and repeatable evidence for the requirements that can be mechanically verified.
- A documented way to assess exceptions, gaps, and requirements that need qualitative judgment.
- A maintainable architectural baseline that helps developers and AI agents understand where code
  belongs, what it may depend on, and how changes can be checked.

Translate these into practical outcomes for this repository: fewer accidental cross-module dependencies,
safer independent changes, clearer ownership, easier code navigation and review, earlier detection of
architectural drift, and more reliable AI-assisted changes. These are intended benefits, not guaranteed
business outcomes. Explicitly distinguish what ACIMA adds from what the repository already has.

Explain the likely deliverables when applicable: a repository-specific assessment and findings;
a proposed module/ownership map; explicit contracts and dependency declarations; configuration,
composition and ownership conventions; deterministic architecture checks and regression tests;
waivers or documented exceptions with rationale; adoption guidance; and a final verification report.
Do not imply all deliverables are appropriate for every repository. State what is recommended for this
codebase and what is out of scope.

### Keep the user informed through every phase

At each phase transition, communicate in ordinary language, briefly and specifically:

1. **Before starting:** what this phase is for, what will be inspected or produced, what it will not do,
   and whether any user decision or approval is needed.
2. **While working:** meaningful progress, what has actually been inspected or completed, important
   discoveries, blockers, and any change in scope. Do not emit noisy implementation logs; summarize
   progress at useful milestones. Never claim work is complete before verification.
3. **Before changing anything:** the exact intended scope, files or artifacts likely to be affected,
   the architectural reason, expected result, risks/tradeoffs, what will remain untouched, and the
   specific approval being requested. Assessment consent is not implementation consent. Approval for
   one change is not blanket approval for follow-on changes.
4. **After each phase:** what was done, what evidence supports the result, what was not done, what
   remains incomplete or uncertain, and the next decision or step.
5. **At handoff:** provide a plain-language record of the starting state, delivered artifacts,
   architectural capabilities now available, deterministic checks and their actual results, remaining
   gaps/waivers, outstanding risks, and any follow-up work. Identify commits or pushes only if they
   actually occurred.

### Phase-specific communication contract

| Phase | Tell the user before/during | Tell the user afterward |
|---|---|---|
| Discover | Which repository/root is being inspected and what discovery will cover | Languages, projects, structure and important unknowns found |
| Assess | That analysis is read-only; what ACIMA requirements and architectural aspects will be reviewed | What already aligns, what gaps exist, what could not be established, and evidence/coverage |
| Recommend | What adoption would add and why it is appropriate or unnecessary | Recommended scope, priorities, tradeoffs and alternatives |
| Plan | What artifacts and boundaries are proposed and what remains unchanged | Concrete implementation plan and explicit approval request |
| Implement | Which approved changes are being made and their purpose | Files/artifacts changed, decisions made, deviations and remaining work |
| Verify | Which deterministic checks and qualitative reviews will be run | Actual pass/fail/skip/unsupported results, evidence, and what those results do and do not prove |
| Handoff | What final review is being prepared | Deliverables, current conformance status, limitations and next steps |

### Unresolved dispositions are decision briefs, not quizzes

A rule with `insufficient_evidence` is not a question the owner can answer by reading a rule id.
Never ask “Is this acceptable?” and never present a bare list of unresolved identifiers. Resolve
every code-traceable unknown yourself. If the answer genuinely requires owner input, group related
rules into one decision brief containing:

- **What it protects** — the practical risk in this repository, in ordinary language.
- **What might be true** — the concrete implementation possibility that remains unchecked.
- **Why it is unresolved** — the missing file, trace, runtime observation or owner intent.
- **Recommended option** — close it with a named audit, record it as a limitation, or treat it as a
  gap and fix it.
- **Effort** — the inspection or change required, with a rough size.
- **Consequence** — what the assessment cannot claim, and how the recommendation is affected, if it
  stays open.
- **Question** — whether to spend that effort or accept the limitation.

The owner decides effort, risk and scope, never whether a catalog rule is “acceptable.” An accepted
limitation remains `insufficient_evidence`; it does not become conformance. The assessment remains
incomplete and the recommendation remains `INSUFFICIENT_EVIDENCE`.

This brief applies to every owner-facing decision, not only unresolved rule dispositions: module
ownership, path ownership and scope approval. A finding is not a question. Report it as observed
and recommended work; ask only for the owner choice that remains.

For example:

> A module constructor may have a default argument, which would create a second way to build it.
> We have checked 40 of 52 constructors; the remaining 12 are not traced. Auditing them should take
> about 30 minutes. If we stop here, we cannot claim the input requirements are fully verified, and
> the assessment stays incomplete. I recommend the audit. Do you want me to spend that time, or
> record this as a limitation?

### Answering the report

The report is answered by the owner, in their own time, offline. Do not read answers off the page and
do not ask the owner to repeat them in chat: in guided adoption the Plan and Files pages write the
decisions file, and the workflow ingests each saved page with `acima adoption decisions --from
<path>`. The report also shows the decision log, what changed since the last review, and any recorded
evidence that has gone missing, so the owner can see the current state without re-reading earlier
conversation.

Tell the owner three things when they answer. First, what happened to each answer: which were applied,
which objective a missing path deferred, which answers conflict with something already recorded, and
whether the file was refused because it describes a different version of the report. Second, that
answering is not approval: a draft scope still carries `authorization.explicit: false`, and the
approval command is a separate, visible step against the same report digest. Third, what changed in
the report, since a regeneration creates a new report identity and marks earlier answers stale rather
than silently reusing them.

Never describe an ingested answer as a decision that was approved, never fill in an answer the owner
did not give, and never treat an unread page or an empty section as agreement.

### Plain-language and honesty requirements

- Explain ACIMA identifiers in human terms whenever they appear in user-facing communication. Keep IDs
  only as secondary traceability references, not as the explanation.
- Explain why a requirement matters to this repository, not merely what the standard says.
- Separate existing capabilities, proposed capabilities, implemented capabilities and verified
  capabilities. Never describe a recommendation as an implemented feature.
- Distinguish automated checks from qualitative review. A successful validator does not prove that
  the reviewer's architectural interpretation is correct; a passing gate does not prove every ACIMA
  requirement is satisfied.
- State coverage explicitly: what was reviewed, what was checked automatically, what was manually
  assessed, what was skipped, unsupported, unresolved or blocked, and why.
- Explain adoption levels and conformance implications when relevant, but do not force users to learn
  level names before they receive an initial assessment.
- Surface uncertainty, incompatibility, exceptions, costs, risks and tradeoffs early. Do not hide
  difficult findings to make adoption sound attractive.
- Never overwhelm the user with every internal detail. Be concise, but never omit information needed
  to understand the decision, scope, impact, progress or outcome.
