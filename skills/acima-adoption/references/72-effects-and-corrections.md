# 72 Effects And Corrections


## Reviewing effects and choosing a correction

Effect, lifecycle, naming and per-rule remedies are conditional judgements, not a checklist:
read [70-corrections](70-corrections.md) before editing. In short — identify the effect and
its owner; decide which of retry, duplicate handling, consistency, cancellation, outcome and
evidence actually apply; fix the dependency path rather than banning closures; choose lifetime from
state ownership, never to reduce registrations; and keep naming advice targeted, never a bulk rename
and never a conformance gate.

For `A006`, use the same discipline: start from the receiving identifier, trace the value through its
data flow, and compare units, domain meaning and ownership — not just the literal or the name. A
matching value or a matching name is not evidence of the same semantic value. Consolidate only at
the highest appropriate genuine owner and pass the value explicitly; keep environment-dependent
values in configuration and secrets out of source constants. When equivalence is uncertain, report a
candidate with evidence and ask for human review rather than consolidating.

Conformance is per repository and per commit. `FULL CONFORMANCE` requires zero unwaived errors at the
level, every required rule accounted for, **and** provenance that matches the current checkout —
repository, `HEAD`, standard, catalog hash, configuration hash, enforcer version and source
inventory. Manual rules need accepted, current, repository-scoped evidence — a catalog-manual rule
reported as executed is not evidence. A rule-complete claim from an older commit is historical, not
current; a changed catalog, configuration, baseline or source tree requires fresh measurement.
Anything less is a **PARTIAL ASSESSMENT** or a plan, and you call it what it is.
