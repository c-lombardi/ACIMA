# Proposed ACIMA adoption — <repository>

> Fill this in the conversation or in a temporary file outside the target. Do not create target
> files from this template until the owner answers the approval question.

## 1. Recommendation

**Recommendation:** `RECOMMENDED` / `RECOMMENDED_WITH_LIMITATIONS` / `NOT_RECOMMENDED` /
`INSUFFICIENT_EVIDENCE` / `NOT_SUPPORTED`.

In two or three sentences: whether ACIMA fits this repository, the single strongest reason, and the
main limitation. Use the evidence gathered in the read-only assessment. A clean report is not a
recommendation: no meaningful boundaries, or existing checks that already cover the guarantee, can
make adoption not recommended. Do not argue for a different architecture and do not open with rule
ids, levels or catalog terminology. Never imply that every architecture is compatible, or that ACIMA
merely enforces boundaries the team already chose.

**Dimensions assessed:** technical compatibility; architectural substance; existing enforcement;
incremental value; adoption cost; practical applicability. Each has a status, evidence and
confidence. Distinguish observed facts, inferred layout and questions only the owner can answer.

Key findings that drive the recommendation:

- `<what the code does, why it matters, and where it occurs>` (`<path or module>`, N occurrences)
- `<what could not be checked>` — see limitations below

Keep internal requirement or check identifiers out of the recommendation. If the owner asks for
traceability, put the reference in a technical appendix after the explanation.

## 2. Software discovered

What this software does, in plain language, and what the inspection established:

- **Type:** application / modular monolith / multi-service / library / framework / plugin system.
- **Languages and frameworks:** `<...>`, from `<manifest evidence>`.
- **Structure:** `<projects/packages and their roles>`.
- **Composition boundaries and entry points:** `<paths; say whether any host exists>`.
- **Existing boundaries:** `<what already separates modules, and the evidence>`.
- **Persistence, configuration and external effects:** `<owners and gaps>`.
- **Existing architecture checks:** `<none | tests | linters | CI>`.
- **Architecture family:** `<Clean | Hexagonal | DDD | modular monolith | microservices | mixed>`,
  with the evidence that supports it.
- **Compatibility:** `compatible` / `compatible with adaptation` / `incompatible` /
  `insufficient evidence`, against the applicable ACIMA requirements, with the evidence. This is an
  explanatory assessment category, not a conformance level.

State confidence for each material inference and name what remains uncertain. Never present a
directory-name guess as an ownership decision.

When the repository has no sufficient authoritative module map, include the automatic module-map
proposal in this section: candidate module names and responsibilities, observed evidence, candidate
contracts and dependencies, unassigned production code, quality observations, recommendations and
the decisions the owner must make. Distinguish observed facts, inferred boundaries, recommendations
and unverified assumptions. State whether the map is absent, incomplete, stale or inconsistent, and
whether a proposal was reviewed or approved. The proposal is not an ownership decision; ownership-
dependent deterministic checks stay blocked until the owner accepts the relevant boundaries and
decisions. Record the proposal identity, reviewer, date and scoped decision in the approval artifact.

## 3. What ACIMA adds

The practical difference between the current repository and the proposed enforced boundaries. For
example: "today `Orders` reads `Billing`'s internal model directly, so a Billing refactor can break
Orders; the proposed contract makes that dependency explicit and the gate rejects a new one."

For each meaningful difference, give the existing design, the ACIMA requirement, why it matters,
and whether it is a confirmed problem, a suspected one, an acceptable design, or insufficient
evidence. State which applicable requirements the repository already satisfies and which are not
established. A different implementation is not automatically a violation; reserve "incompatible"
for a fundamental conflict, and use "insufficient evidence" when inspection cannot decide.

## 4. Expected benefits

Specific outcomes grounded in the evidence above, not generic claims:

- `<e.g. a change in Billing can no longer break Orders silently>`
- `<e.g. persistence details stop leaking into the host>`
- `<e.g. a new boundary violation fails the pull request with an exact remedy>`

Mark each as **available today**, **achievable through adoption**, **requires additional work**, or
**not applicable**. Never describe a proposed gate, exception process or contract check as an
existing capability. If ACIMA would add little relative to its cost, say so and recommend against
adoption.

## 5. Recommended adoption scope

The smallest useful scope that meets the stated objective:

- **Level:** L1 / L2 / L3, with the practical consequence explained before the label — which
  violations become blocking and which obligations remain manual evidence.
- **Units in scope:** `<module list>` or "repository-wide".
- **Explicitly out of scope:** source rewrites, boundary changes, CI, optional plans, persistence
  migration, and anything else deliberately deferred.
- **What this will not accomplish:** e.g. "does not make the current findings disappear", "does not
  prove runtime autonomy", "does not block merges until CI is approved".

## 6. Proposed changes

| Path | Contents | Purpose | Status |
|---|---|---|---|
| `acima/evidence/adoption-scope.json` | approved objectives, dispositions and approval metadata | makes completion and the next action reflect what was actually approved | Required to record approval |
| `acima.config.json` | units, roles, paths, language, level, mode | makes the intended boundaries visible to tools and reviewers | Required |
| `acima/evidence/baseline.json` | measured fingerprints at adoption | distinguishes existing findings from new ones | Conditional |
| `acima/evidence/waivers.json` | owned, scoped, expiring exceptions | governs findings that will not be fixed now | Conditional |
| `<enforcer invocation>` | the check developers run | makes the rules executable | Required for automated enforcement |
| `.github/workflows/acima.yml` | runs the check on pull requests | prevents new violations from merging | Conditional |
| `acima/evidence/manual-evidence.json` | evidence for manual required rules | supports a level claim | Conditional |
| `acima/optional/adoption-plan.md` | sequence, owners, metrics | coordinates a multi-person programme | Optional |
| `acima/optional/communication-plan.md` | audiences and messages | coordinates affected teams | Optional |
| `acima/handoff/STATUS.md` | phase, findings, next action | lets a later session resume honestly | Conditional |

Remove rows that do not apply, add exact paths where they differ, and quote any change to an
existing file. Never mark optional work as required.

**Total new files:** N. **Existing files modified:** N. **Dependencies added:** none / list.

## 7. Tradeoffs and risks

### Effort and disruption (estimates)

Use repository evidence and label every figure as an estimate. Do not invent dates or prices.

- **Source changes:** `<n>` modules and roughly `<n>` files are likely touched for the first
  boundary; `<n>` findings are pre-existing and need no immediate change. *(Estimate)*
- **Configuration and enforcement:** `<n>` new files (config, baseline, waivers, gate, manual
  evidence) — the table in section 6 is the exact list.
- **Tests:** `<n>` tests may change if they assert internal types; contract tests usually need none.
- **CI and developer workflow:** one required check; developers run the same command locally.
- **Ongoing maintenance:** waiver review per cycle, catalog upgrades when the standard moves,
  baseline refresh after an approved scope change.
- **Compatibility and migration risk:** `<schema, deployment ordering, published API, framework
  activation>`; name the riskiest boundary and why it is not first.
- **Incremental?** Yes/No, and which steps can be postponed without weakening the first gate.

- **Maintenance:** catalog updates, tool upgrades, baseline refresh, waiver review, CI ownership.
- **Tooling limitations:** rules that cannot execute in this language, missing toolchains, no
  observed CI, no runtime evidence.
- **Migration:** which boundary is hardest and why; what must not be attempted first.
- **Compatibility:** contracts, published APIs, generated code, framework activation.
- **What ACIMA does not prove:** runtime autonomy, correctness, performance, organisational
  ownership.
- **Risk of not adopting:** the coupling or failure mode this would make visible.

## 8. Next steps

The implementation sequence, and what the user should expect at each stage:

1. `<first approved change>` — result, verification, whether approval is needed.
2. `<measurement>` — the artefact produced and what it proves.
3. `<gate or slice>` — how it is observed and who owns the merge.

End with the decisions only the owner can make: shared-kernel status, composition-boundary ownership, exception
owner, and whether integration blocking is approved. Recommend an answer for each with its evidence.

## 9. Approval

No persistent repository changes have been made. The assessment and this proposal are read-only.

**Would you like me to proceed with the listed files and scope?**

Approval covers only the paths and scope above. Partial approval is supported: say which rows are
approved. If implementation reveals a required change outside this list, I will stop and ask before
making it. Approval does not authorize merge, release or publication.

After approval I will record the accepted objectives in `acima/evidence/adoption-scope.json` (approved,
declined, deferred, optional or not applicable) so later status reports name what remains without
treating an absent file or template as approval. Declined and deferred work will not block the
approved scope.
