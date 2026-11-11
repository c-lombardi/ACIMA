# 42 Communication And Interaction


## Communication contract

**All user-facing communication MUST express the actual meaning of an architectural requirement,
finding, recommendation or decision in plain, human-comprehensible language. Internal identifiers
MUST NOT be presented as the explanation or primary description of that information.**

This applies to the initial assessment, findings, recommendations, implementation plans, approval
requests, progress updates, final reports, error messages and spoken or conversational output. It is
not a final-summary formatting rule.

For every material observation, describe in proportion to its importance:

1. what the requirement means;
2. what was observed in this codebase;
3. why it matters for this software;
4. the practical consequence or risk;
5. the recommended action in understandable terms;
6. whether the observation is confirmed, probable, uncertain, or still needs review.

Use language suited to the reader's apparent technical familiarity without assuming ACIMA knowledge.
Do not oversimplify a technically meaningful distinction; explain it accurately and concisely.

### Resolve identifiers before speaking

Internal IDs remain valuable in machine-readable findings, source, tests, waivers, baselines and
evidence. They are not user-facing terminology. Translate them from authoritative material at the
point of use:

- catalog rules: the `title`, `summary`, `fix` and coverage notes in `rules.json`;
- principles and requirements: the heading and normative text in `docs/standard/`;
- evaluation criteria: the active benchmark rubric's statement and evidence requirement;
- repository-local identifiers: the repository document that defines them.

Do not infer a meaning from an identifier's shape or maintain a small hand-written translation
table. Identifiers can be scoped or reused: if a repository's requirement register defines `R3` as
dependency isolation while ACIMA's lifecycle chapter defines `R3` as separating behaviour from
mutable state, name the source you are using rather than guessing. If the authoritative definition
cannot be found, say the check is unresolved, label that as a reporting defect, preserve the
evidence and do not invent a meaning.

Internal traceability is preserved separately: requirement ID, rule ID, classification, source
evidence, enforcement mechanism and authoritative reference may live in structured metadata or a
technical appendix. If an identifier is useful for advanced traceability, make it secondary and
optional, for example: “Operational values are embedded instead of owned by named immutable
declarations. (Internal reference: A006)” Never use “A006: operational literal” as the explanation.
Normally omit identifiers unless the user asks for technical traceability.

### Finding and approval shape

A meaningful finding explains **what was found**, **why it matters**, **the recommended improvement**,
**the evidence**, and **confidence** — confirmed, probable, uncertain, or requiring review. Do not
force every finding into a long template; group findings that share a cause and explain the shared
meaning once.

An approval request names the actual files, components, responsibilities and behaviour the user is
authorizing. Never ask to “resolve A006” or “apply R3”. Progress updates describe meaningful
activities and outcomes, not evaluator stages, catalogue codes or benchmark classifications. Spoken
output follows the same rule: translate the meaning rather than reading an identifier aloud.

The detailed wording, examples and exception handling are in
[80-reporting](80-reporting.md).



## Interaction contract

Every phase ends in the same shape, in plain English:

- **Current state** — where the user is, in one sentence.
- **What happened** — the meaningful work, not a command log.
- **What it means** — the consequence for this software.
- **What happens next** — the next phase and why it is needed.
- **User involvement** — the one decision or approval required, or "none".
- **Next action** — one action with a completion condition.

Never use an internal identifier as a heading, table label or substitute for the explanation. Never
ask twice for information the repository already answers. Never claim completion from intent,
configuration or file presence. Six milestone updates at most; a blocker gets a message only when it
changes the outcome.
