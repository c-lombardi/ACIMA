# Proposed ACIMA adoption — <repository>

> Fill this in the conversation or in a temporary file outside the target. Do not create target
> files from this template until the owner answers the approval question.

## 1. Recommendation

**Recommendation:** Recommended / Recommended with limitations / Not recommended / Insufficient
evidence to recommend.

In two or three sentences: whether ACIMA fits this repository, the single strongest reason, and the
main limitation. Use the evidence gathered in the read-only assessment. Do not argue for a different
architecture and do not open with rule ids, levels or catalog terminology.

Key findings that drive the recommendation:

- `<consequence in the team's terms>` (`ACIMA-...`, N occurrences, `<path or module>`)
- `<what could not be checked>` — see limitations below

## 2. Application discovered

What this application does, in plain language, and what the inspection established:

- **Type:** application / modular monolith / multi-service / library / framework / plugin system.
- **Languages and frameworks:** `<...>`, from `<manifest evidence>`.
- **Structure:** `<projects/packages and their roles>`.
- **Composition roots and entry points:** `<paths>`.
- **Existing boundaries:** `<what already separates modules, and the evidence>`.
- **Persistence, configuration and external effects:** `<owners and gaps>`.
- **Existing architecture checks:** `<none | tests | linters | CI>`.
- **Architecture family:** `<Clean | Hexagonal | DDD | modular monolith | microservices | mixed>`,
  with the evidence that supports it.

State confidence for each material inference and name what remains uncertain. Never present a
directory-name guess as an ownership decision.

## 3. What ACIMA adds

The practical difference between the current repository and the proposed enforced boundaries. For
example: "today `Orders` reads `Billing`'s internal model directly, so a Billing refactor can break
Orders; the proposed contract makes that dependency explicit and the gate rejects a new one."

For each meaningful difference, give the existing design, the ACIMA expectation, why it matters,
and whether it is a confirmed problem, a suspected one, an acceptable design, or insufficient
evidence. Recognise requirements the repository already satisfies.

## 4. Expected benefits

Specific outcomes grounded in the evidence above, not generic claims:

- `<e.g. a change in Billing can no longer break Orders silently>`
- `<e.g. persistence details stop leaking into the host>`
- `<e.g. a new boundary violation fails the pull request with an exact remedy>`

Mark each as achievable now, achievable with further engineering work, or not applicable here. If
ACIMA would add little, say so and recommend against adoption.

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
| `acima.config.json` | units, roles, paths, language, level, mode | makes the intended boundaries visible to tools and reviewers | Required |
| `.acima/baseline.json` | measured fingerprints at adoption | distinguishes existing findings from new ones | Conditional |
| `.acima/waivers.json` | owned, scoped, expiring exceptions | governs findings that will not be fixed now | Conditional |
| `<enforcer invocation>` | the check developers run | makes the rules executable | Required for automated enforcement |
| `.github/workflows/acima.yml` | runs the check on pull requests | prevents new violations from merging | Conditional |
| `.acima/manual-evidence.json` | evidence for manual required rules | supports a level claim | Conditional |
| `docs/acima/adoption-plan.md` | sequence, owners, metrics | coordinates a multi-person programme | Optional |
| `docs/acima/communication-plan.md` | audiences and messages | coordinates affected teams | Optional |
| `docs/acima/STATUS.md` | phase, findings, next action | lets a later session resume honestly | Conditional |

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

End with the decisions only the owner can make: shared-kernel status, host ownership, exception
owner, and whether integration blocking is approved. Recommend an answer for each with its evidence.

## 9. Approval

No persistent repository changes have been made. The assessment and this proposal are read-only.

**Would you like me to proceed with the listed files and scope?**

Approval covers only the paths and scope above. Partial approval is supported: say which rows are
approved. If implementation reveals a required change outside this list, I will stop and ask before
making it. Approval does not authorize merge, release or publication.
