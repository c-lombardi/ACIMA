# ACIMA status — <repository>

Updated: <date> by <name>   Phase: <assess | propose | authorize | implement | verify>
Approved scope: `acima/evidence/adoption-scope.json` — <approved by / date>
Declared level: <L1 | L2 | L3 | none>   Run artefact: <path to baseline JSON>
Reader report: `acima/handoff/adoption-summary.md`   Evidence: <path to gate-status / assessment>

## 1. Where you are

<One paragraph: what exists now, what was measured, and the single number that matters — unwaived
findings at the declared level. Say explicitly what is NOT proven: unexecuted rules, tests not run,
gate not observed in CI.>

## 2. What is wrong, and the correction

Every finding, as an instruction. Never a bare rule ID, never "see the report".

| # | What was found | Where | Why it matters | Recommended improvement | Confidence | Owner |
|---|---|---|---|---|---|---|
| 1 | <the problem in plain words> | <module: path:line> | <the consequence for a consumer> | <the exact change: name the project, type or reference to remove> | <confirmed | probable | uncertain | review> | <name> |

A grouped finding names its occurrence count here; the individual paths, fingerprints and internal
check references are in the technical run. Do not add an identifier column unless the reader asked
for advanced traceability, and never use an identifier as the description.

If a finding is a tool artefact rather than a defect, say so here and name the defect instead.

## 3. The next step

**<One action, imperative.>**

```bash
<the exact command to run, or the exact edit to make>
```

Why this one: <one sentence tying it to the highest-value finding or the blocked phase>.
Owner: <name>. Done when: <observable result, e.g. "the gate prints 0 NEW and exit 0">.

## 4. Approved scope and what remains

Completion is relative to these objectives. Do not add a universal checklist: declined, deferred,
optional and not-applicable work is not outstanding.

| Objective | Disposition | State | Evidence | Next action |
|---|---|---|---|---|
| <assessment / local enforcement / baseline and waivers / CI / full conformance / handoff / communication> | <required / approved / declined / deferred / optional / not applicable> | <state> | <artifact or reason> | <one action, or none> |

Remember: an adoption plan is optional, as are the communication plan, STATUS dashboard and
summary. Do not turn an absent optional document into an outstanding requirement.

## 5. Blocked, and by what

| Blocker | Impact | Owner | Next action | Revisit |
|---|---|---|---|---|
| <waiver defect / missing toolchain / unnamed owner> | <phase it stops> | <name> | <what unblocks it> | <date> |

## 6. Read this next

- Findings detail: `<path>` — <what it contains, why to open it>
- Raw run: `<path>` — <command that regenerates it>
- Plans (optional, if created): `acima/optional/adoption-plan.md`, `acima/optional/communication-plan.md`
- Explanation sources: the catalog and standard pages that define the checks.
- Correction recipes: the catalog fix text and the relevant standard page.
- Commands: `docs/commands.md` in the ACIMA repository — run one, not a programme
