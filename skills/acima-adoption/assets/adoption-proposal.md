# Proposed ACIMA Adoption

> Fill this in the conversation or in a temporary file outside the target. Do not create target
> files from this template until the owner answers the approval question.

## 1. Recommendation

**Recommendation:** Recommended / Recommended with limitations / Not recommended / Insufficient
evidence to recommend.

Explain in plain language whether ACIMA fits this repository, using the evidence gathered in the
read-only assessment. Name the architecture family and what ACIMA would add to it. Do not argue for
a different architecture.

Key findings that drive the recommendation:

- `<consequence in the team's terms>` (`ACIMA-...`, N occurrences, `<path or module>`)
- `<what could not be checked>` — see limitations below

## 2. Proposed scope

Describe the smallest adoption that meets the owner's stated objective. For example:

> Establish Level 1 enforcement for the existing services: declare the module boundaries, record
> the current findings, and add a check that prevents new violations.

State:

- **Level:** L1 / L2 / L3, and why that level is justified now.
- **Units in scope:** `<module list>` or “repository-wide”.
- **Explicitly out of scope:** source rewrites, boundary changes, CI, optional plans, etc.
- **What this will not accomplish:** e.g. “does not make the current findings disappear”, “does not
  prove runtime autonomy”, “does not block merges until CI is approved”.

## 3. Files to be created or modified

| Path | Contents | Why it is needed | Status |
|---|---|---|---|
| `acima.config.json` | units, roles, paths, language, level, mode | lets tools and reviewers see the intended boundaries | Required |
| `.acima/baseline.json` | measured fingerprints at adoption | distinguishes existing findings from new ones | Conditional |
| `.acima/waivers.json` | owned, scoped, expiring exceptions | governs findings that will not be fixed now | Conditional |
| `<enforcer invocation>` | the check developers run | makes the rules executable | Required for automated enforcement |
| `.github/workflows/acima.yml` | runs the check on pull requests | prevents new violations from merging | Conditional |
| `docs/acima/adoption-plan.md` | sequence, owners, metrics | coordinates a multi-person programme | Optional |
| `docs/acima/communication-plan.md` | audiences and messages | coordinates affected teams | Optional |
| `docs/acima/STATUS.md` | phase, findings, next action | lets a later session resume honestly | Conditional |
| `.acima/manual-evidence.json` | evidence for non-portable required rules | supports a full level claim | Conditional |

Remove rows that do not apply. For every retained row, add the exact path if it differs from the
example. Mark any existing file that would be modified, and quote the proposed change. Do not claim a
file is required when the objective does not need it.

**Total new files:** N. **Existing files modified:** N. **Dependencies added:** none / list.

## 4. Proposed module map

| Discovered path | Proposed unit | Role | Evidence | Confidence | Needs owner decision? |
|---|---|---|---|---|---|
| `src/orders` | `orders` | implementation | project reference, entry point | high | no |
| `src/shared` | `shared` | uncertain | imported by all modules; no owner metadata | low | yes — shared kernel or supporting library? |
| `tests` | — | test | test framework metadata | high | no |

Roles: contracts, implementation, host, supporting library, shared kernel, test, tooling, uncertain.
Do not present a low-confidence guess as confirmed. Ask the questions that remain.

## 5. Architectural decisions required

- Which projects are independently owned modules?
- Which code is a host/composition root?
- Which shared code is a supporting library, and which would become a shared kernel? (A shared
  kernel is an architectural exception, not a convenience.)
- Should existing findings be fixed now, or recorded and owned through a baseline/waivers?
- Who owns each exception, and when does it expire?
- Is integration blocking approved, or local enforcement only?

State the proposed answer and its evidence for each. Do not silently decide on the owner's behalf.

## 6. Tradeoffs and maintenance

- **Checks added:** what developers and CI will run, and how long it takes.
- **New findings:** blocked, reported, or ignored — be exact.
- **Exceptions:** who reviews, how renewal works, and what expiry means.
- **Maintenance:** catalog updates, tool upgrades, baseline refresh, waiver review, CI ownership.
- **Limitations:** rules that did not execute, unsupported language/toolchain, no CI observation,
  no runtime evidence, and anything the assessment could not establish.
- **Risk of not adopting:** the coupling or failure mode this would make visible.

## 7. Approval

No persistent repository changes have been made. The assessment and this proposal are read-only.

**Would you like me to proceed with this adoption plan and create the listed files and changes?**

Approval covers only the paths and scope above. If implementation reveals a required change outside
this list, I will stop and ask before making it.
