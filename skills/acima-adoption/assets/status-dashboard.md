# ACIMA status — <repository>

Updated: <date> by <name>   Phase: <assess | propose | authorize | implement | verify>
Declared level: <L1 | L2 | L3 | none>   Run artefact: <path to baseline JSON>
Reader report: `docs/acima/adoption-summary.md`   Evidence: <path to gate-status / assessment>

## 1. Where you are

<One paragraph: what exists now, what was measured, and the single number that matters — unwaived
findings at the declared level. Say explicitly what is NOT proven: unexecuted rules, tests not run,
gate not observed in CI.>

## 2. What is wrong, and the correction

Every finding, as an instruction. Never a bare rule ID, never "see the report".

| # | Finding | Where | Why it matters | Correction | Rule | Owner |
|---|---|---|---|---|---|---|
| 1 | <the problem in plain words> | <module: path:line> | <the consequence for a consumer> | <the exact change: name the project, type or reference to remove> | <ACIMA-D00x> | <name> |

Rule identifiers stay in their own column so the problem is readable first. A grouped finding
names its occurrence count here; the individual paths and fingerprints are in the technical run.

If a finding is a tool artefact rather than a defect, say so here and name the defect instead.

## 3. The next step

**<One action, imperative.>**

```bash
<the exact command to run, or the exact edit to make>
```

Why this one: <one sentence tying it to the highest-value finding or the blocked phase>.
Owner: <name>. Done when: <observable result, e.g. "the gate prints 0 NEW and exit 0">.

## 4. What remains

In order. Tick what is finished so the route to the next level is visible.

- [x] Preflight — <evidence>
- [x] Classified — <greenfield | brownfield | adopting>
- [ ] Planned — scope agreed in the proposal (an adoption plan is optional)
- [ ] Baselined — every pre-existing finding waived with owner + expiry
- [ ] First slice — <boundary> changes and the gate stays green
- [ ] Gated — CI blocks new errors on the default branch
- [ ] L2 — contracts immutable and consumed through contracts only
- [ ] L3 — persistence, configuration and statics owned per module

## 5. Blocked, and by what

| Blocker | Impact | Owner | Next action | Revisit |
|---|---|---|---|---|
| <waiver defect / missing toolchain / unnamed owner> | <phase it stops> | <name> | <what unblocks it> | <date> |

## 6. Read this next

- Findings detail: `<path>` — <what it contains, why to open it>
- Raw run: `<path>` — <command that regenerates it>
- Plans (optional, if created): `docs/acima/adoption-plan.md`, `docs/acima/communication-plan.md`
- Rule meanings: `docs/acima/README.md`
- Correction recipes: the rule page's Fix section in `docs/rules/`, and `references/70-corrections.md` in the skill
- Commands: `docs/commands.md` in the ACIMA repository — run one, not a programme
