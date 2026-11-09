---
name: acima-adoption
description: Adopt, audit, and enforce the ACIMA architecture standard in a greenfield or brownfield repository. Use when the user asks to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, run an architecture audit against the ACIMA rule catalog, migrate a shared "Common" project, or onboard a team with no prior exposure to contract-based modular architecture. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.1.0-draft.1"
  skill-version: "1.9.0"
  catalog-sha256: "a699510322ec5decdb6bc212c7d65b23df106d5f2e6fc027a53fa800af350eea"
---

# ACIMA adoption

You are applying the ACIMA architecture standard — Autonomous, Contract-Isolated, Immutable
Modular Architecture — to a real repository. The standard lives in this repository:

- `tools/acima-spec/rules.json` — the 34-rule catalog. **Normative.**
- `docs/standard/` — the specification. Chapters 4 (dependency model), 5 (contract design),
  8 (conformance) and 9 (adoption) are the ones you will use most.
- `examples/<language>/` — a working ordering system (four modules in Python, three in
  TypeScript, Go and .NET), an enforcer, and a violation gallery.

Your job depends on the mode. Assessment is read-only: report fit, findings and gaps, then stop.
Adoption starts only after a written proposal and an explicit yes; then implement the approved
scope, verify it, and say plainly what is proven and what is not. **Analysis is never
authorization.**

## Positioning: enforcement, not an alternative

ACIMA is an architectural enforcement standard, not an architecture. The team's choice — Clean
Architecture, Hexagonal Architecture, domain-driven design, a modular monolith, microservices, or a
mix — decides the shape; ACIMA enforces the boundaries that shape declares. Never propose replacing
it, never relabel the team's concepts, and never use a finding to argue for a different family.

When you assess a repository, name the family you detected from evidence and say what ACIMA adds in
the team's own vocabulary. [references/05-architecture-families.md](references/05-architecture-families.md)
has the per-family table, the guardrails and the justification for the places where ACIMA is
stricter than the chosen architecture.

## Scope: where this skill must live

This skill is **repository-scoped**: it reads `tools/acima-spec/rules.json`, `docs/rules/`,
`docs/standard/`, and `examples/<language>/tools/`, and `preflight.py` resolves those from two
directories above itself. A copied skill uses the `vendor/` snapshot, and `bundle_skill.py --check`
catches drift. `preflight --deep` and `acima.py verify` still need a checkout; inside one, scripts
always use the live tree.

## Start here: route the request

Pick the mode from the user's words before running anything. One mode per session unless they move
it, and never upgrade an assessment into an adoption because the assessment found problems.

| The user says | Mode | Writes to the target? | First command | Ends when |
|---|---|---|---|---|
| "assess", "audit", "review", "evaluate", "is ACIMA a fit" | **Assess** | no | `python3 tools/acima.py assess --root <target>` | a verdict and named gaps; no config, waivers or CI |
| "adopt", "apply ACIMA", "set it up", "add the gate" | **Adopt** | not until consent | `python3 tools/acima.py assess --root <target>`, then [the proposal](assets/adoption-proposal.md) | explicit approval of named files and scope; never inferred from the request |
| "continue", "where are we", "what is next" | **Resume** | no | `python3 tools/acima.py status --root .` | the one next command, stated in the final message |
| "fix this", "why does the gate fail", "correct D001" | **Slice** | yes, smallest boundary | `python3 tools/acima.py fix --report <run> <selector>`, then the enforcer | one boundary changed, gate green |
| "what is ACIMA", "explain this rule" | **Explain** | no | `python3 tools/acima.py report --root <target>` or the rule page | the answer, with the rule id and its remedy |

If the request is ambiguous, run the read-only mode and say which you chose. If it mixes modes, do
the assessment first and ask before the first write.

## Four phases and one consent boundary

**Phase 1 — Assessment (the default).** Inspect, run read-only analysis, identify findings and
limits, classify the repository, and propose boundaries. The commands are read-only:

```bash
python3 tools/acima.py assess --root <target>
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
```

Do **not** create `acima.config.json`, `.acima/`, baselines, waivers, plans, CI, tooling, docs or
source changes. A verdict of `NEEDS_UNIT_MAP` means unassessed, never clean.

**Phase 2 — Proposal.** Present [the proposal](assets/adoption-proposal.md): recommendation, scope,
exact paths, what each file contains, required/conditional/optional status, architectural decisions,
tradeoffs and maintenance. Do not write the files yet. A request to “see the files” is not approval
to create them.

**Phase 3 — Approved adoption.** Only after an explicit affirmative response to that proposal,
create the named files and make the named changes. Approval covers the listed scope only; a new
requirement stops work and needs a new decision. Permission to adopt is not permission to merge,
publish or release.

**Phase 4 — Verification and handoff.** Verify what was actually created and run, then report
capabilities and limits. A config, baseline, passing gate or configured CI is not conformance.

| Action | Approval required? |
|---|---|
| Inspect, read docs, run read-only analysis, prepare a proposal | no |
| Create `acima.config.json`, `.acima/`, baseline, waivers, plans, tooling or CI | yes |
| Modify application source, build configuration or existing docs | yes |
| Merge, publish or release | separate yes |

[references/15-consent-and-scope.md](references/15-consent-and-scope.md) has the full boundary, the
artifact matrix, partial approval, module-map confidence and conversation rules.

Adoption adds a unit map, a measured baseline, owned waivers and a gate. It is a governance change,
not a refactor, and `preflight --write-*` is a write even when the path is relative.

## Outcomes (definition of done)

| Phase | Done when |
|---|---|
| Assessed | Read-only verdict, findings and limits; **no target file changed** |
| Proposed | Proposal names every path, its status, contents, decisions and tradeoffs |
| Consented | The user explicitly approves a named scope, level and file list |
| Baselined | Only if approved: a run artefact exists; every pre-existing finding is owned and expiring |
| Gated | Only if approved: CI fails on new `error` findings at the declared level |
| First slice | Only if separately approved: one boundary change is merged |
| Handed off | The team can run what was approved; outcomes and limits are reported in their terms |
| Navigable | Any adopted repository has `docs/acima/STATUS.md` naming the next step |

A repository is **fully conformant** at a level only when the run artefact shows **zero unwaived
errors** at that level on the current commit **and every rule required by that level was executed**,
with a recorded manual/native evidence artifact where no automated rule exists. If any required rule
is `executed: false`, the result is a **PARTIAL ASSESSMENT**, not conformance. Anything less is a
plan, and you must call it a plan.

## Reporting: the summary is the product

Every adoption ends with `docs/acima/adoption-summary.md`, generated by
[scripts/summarize.py](scripts/summarize.py) from the run artefact. An assessment ends with the
same summary in the response, or at a path outside the target; writing it into the repository is a
change and needs approval. It answers, in order: what was found, what it means, the key problems,
the next action, what is complete, what is unverified, and where the evidence is. Keep the run and
`acima.py report` as linked technical records, not pasted content.

- Lead with the consequence, not the identifier. Name the problem in the reader's terms, then cite
the rule once in parentheses. Never make a reader decode `ACIMA-D007` to understand a sentence.
- Group by the architectural problem and its remedy, not one row per file. A group keeps its rule
id, count, affected modules and fingerprints, so the claim stays traceable.
- Separate confirmed defects from detector artefacts and review items, per
[80-reporting](references/80-reporting.md). A detector problem is never presented as code debt, and
triage never suppresses a finding.
- Status vocabulary: `Not assessed`, `Assessment incomplete`, `Significant issues found`,
`Partially aligned`, `Baseline established`, `Verified`. Only a supplied full claim makes
`Verified`; a passing baseline is never conformance.
- Name one next action with why, where, done-when, verification and whether it needs human
judgement, then at most four more in priority order.
- Report completed work only from artefacts; keep limits (`executed: false`, CI not observed,
manual evidence absent) in the summary, not an appendix.

If no run artefact exists, fill the summary by hand and mark unsupported claims not assessed. Never
narrate the investigation: short milestone updates, blockers that change the outcome, and a final
message that is the summary.

## Hard rules

1. **Never invent a rule ID.** Every finding cites an ID from `rules.json`.
2. **Never edit `rules.json`, an `expected.json`, or a manifest hash to make a check pass.**
   If the catalog has moved, stop and re-read it; the mismatch is the point.
3. **Never waive without owner, reason, scope, finding fingerprint, expiry and review date.**
   `ACIMA-G001` exists because unowned exceptions become permanent, and a fingerprint is what
   stops a baseline from hiding a new finding in the same unit.
4. **Never bulk-renew waivers.** Renewal is an individual decision by the named owner.
5. **Never declare conformance without a run.** "The architecture tests pass" is not evidence
   unless the run discovered files — zero findings from zero files is the most common false claim.
   Zero findings require all of the following: `sourceFiles > 0`, a complete execution map, exit
   code 0 or 1, valid JSON, the expected catalog and level, and controlled violations detected in
   disposable fixtures. Use `scripts/inject_violation.py` for that last check: it proves `L001` by
   injecting one violation into a copy of the target and proves `D001` with a disposable two-unit
   fixture, so a green result cannot come from an enforcer that saw nothing. If any condition is
   missing, report `not proven`, never `conformant`.
6. **Never treat invalid, truncated or missing output as zero findings.** Check the exit code,
   parse the JSON, and confirm the run is complete. A tool failure is `invalid assessment`, not a
   clean baseline. Keep the raw output where it can be inspected.
7. **Never start brownfield adoption at L3.** Start at L1, ratchet upward.
8. **Never rewrite the target to satisfy the standard.** Change the smallest boundary, then measure.
9. **Never apply ACIMA to a codebase whose owner has not asked for it.** This is a governance
   change, not a refactor.
10. **Never declare a library profile to silence a finding.** A profile needs publishable evidence,
    a named owner, a justification, and path-scoped declarations. Classified findings stay in the
    report; a new edge outside the declared paths must still fail. See
    [the library profile](vendor/docs/standard/12-library-profile.md).
11. **A required `executed: false` rule makes the result partial unless manual evidence is accepted.**
    Name every such rule. Keep the evidence in `.acima/manual-evidence.json` with a repository
    scope, owner, reviewer, method, artifact, review date and expiry. Compute the class with
    `acima claim`; never report `FULL CONFORMANCE` from an incomplete execution map, even when the
    error count is zero.
12. **Never write before consent.** Analysis, a good finding, an inferred need, or a request to
    adopt is not approval to create files. Present the exact paths, contents and consequences, and
    act only on an explicit affirmative response to that proposal.

Re-entering an adopted repository: run `python3 tools/acima.py status --root .` first; it reports
the evidenced steps and the one next command. Name artefacts by path: a reader who has to ask
"what now?" was given data, not an answer.

## Command index

The commands you are expected to run. Full flags, exit codes and the step each serves are in
[vendor/docs/commands.md](vendor/docs/commands.md); read it before using a flag you have not seen.
Never guess a flag — `--help` is authoritative.

| Command | Does | Writes? |
|---|---|---|
| `acima.py status --root .` | which steps the artefacts evidence, and the next command | no |
| `acima.py inspect --root .` | languages, units, level, enforcer readiness | no |
| `acima.py assess --root .` | read-only fit assessment and verdict | no |
| `acima.py analyze --root .` | run the reference enforcer, print findings | no |
| `acima.py fix --report <run> [selector]` | finding → catalog remedy and correction shape | no |
| `acima.py report --root .` | evidence report, including rules that did not run | no |
| `acima.py claim --report <run> --level <L> --require full` | compute `FULL`/`PARTIAL` and gate it | no |
| `summarize.py --root <target> --report <run>` | run artefact → plain-language, grouped summary | only with `--out` |
| `preflight.py --project <target>` | skill calibration and target classification | only with `--write-*` |
| `inject_violation.py --project <target>` | prove `L001`/`D001` fire on controlled input | no |
| `<language enforcer> --root <target> --format json` | the gate itself, for one language | no |
| `conformance/run.py` | verify the standard's own fixtures | `--artifacts` only |

`status`, `inspect`, `assess`, `analyze`, `fix`, `report` and `claim` are safe on a repository you do
not own. `preflight --write-draft`, `--write-waivers`, edits to `acima.config.json`, and the CI gate
are adoption acts and need the owner's authorization.

## Context files: read them before you propose

These files are the programme's memory. Read them at the start of every session, and update them
when the thing they record changes; never reconstruct state from the conversation.

| File | Holds | Read | Write |
|---|---|---|---|
| `acima.config.json` | units, roles, paths, architecture mode | Step 0 and every resume | only after approval, with human review |
| `.acima/baseline.json` | the fingerprints measured at adoption | before the gate | only after approval; generated from a run |
| `.acima/waivers.json` | one owned, fingerprinted, expiring exception per finding | before claiming, before editing | only after approval, when an owner accepts an exception |
| `.acima/manual-evidence.json` | recorded evidence for the six judgement rules | before any level claim | after approval, when a required rule is manual |
| `docs/acima/adoption-plan.md` | boundaries, architecture family, phases, metrics | Step 2 and every resume | only if approved; when scope, owner or dates change |
| `docs/acima/STATUS.md` | phase, findings, next step, blockers | every resume | at the end of every session that changes map, baseline or gate |
| `docs/acima/gate-*.json` | the run artefacts a claim rests on | claim and status | each measured run |
| `docs/acima/adoption-summary.md` | the reader-facing report, generated from the run | every resume | after every assess, adopt or re-measure |
| `.acima/triage.json` | which matches are defects, review items or detector artefacts | before summarising | when triage changes; never to hide a finding |
| `.github/workflows/*` | the gate CI runs | before claiming it is gated | when the level or command changes |

If a file is missing, that is the finding: say which artefact is absent and which phase produces it.
Do not invent its contents and do not substitute the conversation for it.

## Workflow

### Step 0 — Preflight (always, before anything else)

```bash
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
```

Exit codes: `0` ready, `1` blocked, `2` the tool could not run. **Do not continue past a blocker.**
Report the blocker to the user in its own words, with the remedy the preflight printed.

The preflight asserts the skill is calibrated to the catalog in this repository *at this commit*:
`SKL-002` compares `rules.json` against the pinned SHA-256 in `manifest.json`, and `SKL-003`
checks that all 28 portable rule IDs still exist. If either fails, the standard changed after
this skill was written. Re-read the changed rules, update the skill deliberately, and only then
continue. Never silence the check.

### Step 1 — Classify

The preflight reports one of:

| Mode | Evidence | You do |
|---|---|---|
| `greenfield` | no `acima.config.json` and no source files | [greenfield playbook](references/10-greenfield.md) — propose the full shape; scaffold only if approved |
| `brownfield` | no `acima.config.json` and at least one existing source file | [brownfield playbook](references/20-brownfield.md) — measure, freeze, ratchet |
| `adopting` | `acima.config.json` present | verify the baseline, then resume at the current level |

Then read the **architecture mode** from `acima.config.json.mode` before proposing units. `base`
(or an absent field) applies P1–P9 and P2.1's one-contracts-unit rule. `service-topology` applies
P1–P9 plus P10–P13 and supersedes exactly P2.1 and P3.5 with per-layer contracts and total
isolation; this revision has no service workflow, so stop and report `NOT SUPPORTED`. Do not infer
the mode from directory names, and do not let `acima.topology.json` substitute for the config field.

Also classify the **architecture kind** before proposing units: application, modular monolith,
multi-service system, library, framework, SDK, plugin system, multi-package repository, or a mix.
A repository can be several at once; do not force one label. Use manifests, published artifacts
(`private`, `files`, `exports`, `IsPackable`, `PackageId`), deployment files and entry points as
evidence, and say which evidence you used.

Classify the **architecture family** as well: Clean Architecture, Hexagonal, DDD, a modular
monolith, microservices, or a mix. Use evidence — project references and layer direction, ports and
adapters, bounded-context vocabulary, deployment manifests, per-service data stores. Record it in
the adoption plan and read [references/05-architecture-families.md](references/05-architecture-families.md)
before proposing units, so the plan says what ACIMA adds rather than implying it replaces the
architecture.

If `acima.topology.json` exists, or the tree is organized as `services/<Service>/` with per-layer
`.Contracts` projects, this revision has **no supported service-topology workflow**. Stop and report
`NOT SUPPORTED`; do not apply base P2.1's one-contracts-unit rule to that repository. The service
profile is specified in [chapter 11](vendor/docs/standard/11-service-topology.md) and implemented by
`conformance/topology.py`, but this skill does not yet generate or validate its manifest.

If the mode is ambiguous, say so and ask one question: *"Is this repository allowed to gain a
build-blocking architecture gate, and who owns the exceptions?"* Do not proceed without an owner.

### Step 2 — Propose before planning files

Fill [`assets/adoption-proposal.md`](assets/adoption-proposal.md) in the conversation. Do not copy
any plan, template or config into the target yet. The proposal names the exact paths, what each
contains, why it is needed, whether it is required/conditional/optional, the decisions only the
owner can make, and the maintenance it creates. If approval is later given for plans, use
[`assets/adoption-plan.md`](assets/adoption-plan.md) and
[`assets/communication-plan.md`](assets/communication-plan.md) then.

For every proposed module, show the evidence and confidence: discovered project, proposed role,
why, and what remains unconfirmed. A heuristic draft is not an authoritative map. Ask about shared
kernels, hosts, test/tooling projects, duplicate names and projects whose role the directories
cannot settle.

When two boundaries are plausible, test both maps in disposable copies; the better one attributes
today's findings to the units the team owns. Show the owner both and let them choose.

### Step 3a — Greenfield: scaffold only the approved scope

Only after approval for a greenfield scaffold. Follow [references/10-greenfield.md](references/10-greenfield.md).
The order is fixed: contracts → implementation → host → `acima.config.json` → empty waiver file →
CI gate. Each contract owns its value types; there is no shared kernel. The gate goes in **before**
the second module exists, so the rules are never optional. If the approved scope excludes CI or
source scaffolding, stop at what was approved and say what remains unavailable.

### Step 3b — Brownfield: measure only the approved paths

Only after approval for the named config/baseline/waiver/gate scope. Follow
[references/20-brownfield.md](references/20-brownfield.md). Skip every command whose output the
user did not approve; a draft config is not a baseline and a baseline is not a gate. The ratchet is:

```bash
# 1. draft a unit map (heuristic, review it before committing)
python3 skills/acima-adoption/scripts/preflight.py --project . --write-draft acima.config.json

# 2. measure at L1 and write the review artefact
python3 skills/acima-adoption/scripts/preflight.py --project . --format json > acima-baseline.json

# 3. turn the baseline into scoped waivers, then replace "unassigned" with real owners
python3 skills/acima-adoption/scripts/preflight.py --project . --write-waivers .acima/waivers.json

# 4. gate CI on "no new findings", then reduce the count one PR at a time
```

Do not fix the architecture first. Freeze the measurement first; the number is what makes the
programme discussable.

### Step 4 — Execute one approved slice

Source edits, contract extraction and boundary changes need their own approval; adoption consent
for configuration does not cover them. Pick the slice by the migration order in `docs/standard/09-adoption.md` §9.2: contracts extraction
for the two most-coupled modules, then cycle breaking, then immutability, then persistence
ownership. **Never start with persistence.** It needs a data migration and it is where adoption
programmes die.

One slice means one merged pull request that changes one boundary and leaves the gate green.

Run the enforcer as soon as the first file changes, not at the end of the slice. The gate is the
detector: if it reports a different finding than the one you set out to fix, stop, read that rule's
page, and correct or report it — never stack a second change on an unexplained one.

Before editing, read the finding's **Fix** section in `docs/rules/` and choose one of the four
correction shapes — invert, localise, remove, restructure — in
[references/70-corrections.md](references/70-corrections.md). That file also lists the traps that turn
one finding into another (breaking a cycle with a shared kernel produces `D007`), the per-language
idioms for contract findings, and the fingerprint rule: a rename changes the fingerprint, so the
baseline or waiver must move in the same pull request. Never invent a remedy the rule page does not
support, and never lower the count by widening an exclusion.

### Step 5 — Verify, with the run artefact

```bash
# the enforcer for the target language, from this repository
python3 examples/python/tools/acima_arch.py      --root <target> --format json
node     examples/typescript/tools/acima-arch.mjs --root <target> --format json
(cd examples/go && go run ./tools/archtest --root <absolute-target> --format json)
dotnet run --project examples/dotnet/tools/Acima.ArchTests -- --root <target> --format json
```

Then, from the target repository, run its own wired command (the one CI runs) and keep the JSON.
Validate before reporting anything:

1. exit code is 0 or 1 (2 or a crash is a tool failure, not architecture debt);
2. the JSON parses, and its byte size matches the file you kept — never read a large report through
   a fixed-size pipe or a terminal capture that can truncate it;
3. `sourceFiles` is greater than zero and matches the expected scope;
4. `execution` names every catalog rule, and every `executed: false` has a reason;
5. the report's standard, level and catalog identity are the ones you intended;
6. any `classified` entries have a rule, path, owner and reason — they are reported decisions, not
   suppressed findings;
7. the expected units were discovered (a run that classifies nothing is a false pass — `ACIMA-G005`
   should have fired);
8. if any rule required by the declared level is `executed: false`, record repository-scoped manual
   evidence in `.acima/manual-evidence.json`; missing or expired evidence is **PARTIAL ASSESSMENT**,
   not full conformance;
9. compute and gate the claim class explicitly:

```bash
python3 tools/acima.py claim --report acima.json \
  --evidence .acima/manual-evidence.json --level L2 --require full
```

`claim` exits `0` only when the requested class is satisfied, `1` when a full claim is requested but
the run is partial, and `2` when the run or evidence document is invalid. A zero error count does
not make a partial assessment full.

A zero-finding result additionally requires controlled violations. The prover runs both by
default:

```bash
python3 skills/acima-adoption/scripts/inject_violation.py --project <target> --format json
```

`ACIMA-L001` copies the target to a disposable directory, injects one language-appropriate
forbidden dependency, and requires that rule at that exact path. `ACIMA-D001` builds a disposable
two-unit fixture where one implementation unit imports another and requires the cross-module
finding; it does not depend on the target's unit map, so single-module repositories are proven
too. Use `--rule L001` or `--rule D001` to run one. The prover never writes to the working copy,
and it withholds injection details unless `--reveal` is passed, so an assessment agent can run it
before being told what was injected. Exit `1` means `not proven`; if the check cannot run, report
`not proven`.

Then render the reader's report — this, not the JSON, is the deliverable. For an assessment, print
it or write it outside the target; writing into `docs/acima/` needs approval:

```bash
python3 skills/acima-adoption/scripts/summarize.py --root <target> --report acima.json
```

Read it before sending it. Every key finding must be understandable without the catalog, and §6
must name every unexecuted rule, unobserved gate and unowned exception.

### Step 6 — Hand off after approved adoption

Always end by telling the reader where they are and what to do next: phase, level and supporting
run; every finding as `rule · file · why · correction`; one next action with its command and done
state; and the phases that remain. Write [`docs/acima/STATUS.md`](assets/status-dashboard.md) only
when adoption was approved and the map, baseline or gate changed.

- Fill the conformance self-certification in `docs/standard/08-conformance.md` §8.5.
- Deliver the [communication plan](references/40-communication.md) — kickoff, first finding,
  first waiver negotiation, and the recurring update.
- Run the [newcomer onboarding](references/30-adoption-for-newcomers.md) for anyone who has never
  seen contract-based modular architecture. Assume zero background; do not assume they will read
  the spec.

- State the architecture family you detected and what ACIMA adds to it, in the team's vocabulary:
  the gate enforces the chosen boundaries, it does not choose them. Name it in `docs/acima/STATUS.md`
  and in the final message.
- Write `docs/acima/STATUS.md` from the dashboard template and put the human-first summary at
  `docs/acima/adoption-summary.md`; state the next command verbatim, not the whole programme.
- In the final message use the summary's seven sections, not a chronological account of commands.
  Rule ids appear in parentheses; the evidence stays in the linked run and triage files.
- End with the route: which phase is next, and which are blocked and by whom.

## Stop conditions

Stop and ask the user when any of these is true:

| Condition | Why |
|---|---|
| `preflight.py` exits 1 | the skill is not calibrated, or the target is not what it appears to be |
| The target has no named owner for exceptions | waivers would become anonymous, which `G001` forbids in spirit |
| Two modules disagree about who owns a concept | this is org design; no rule fixes it (`09-adoption.md` §9.4) |
| A rule produces waivers for legitimate designs repeatedly | the rule may be wrong — amend the standard, do not bend the code |
| The target language is Java | the profile exists, the reference implementation does not; say so |
| `acima.config.json.mode` is `service-topology`, or `acima.topology.json` exists | this skill revision has no supported service-profile workflow; do not force the base unit model |
| A library profile is requested without publishable evidence | the declaration would be an undocumented exemption (`G001` in spirit) |
| A library profile is requested for Python or Go | there is no reference implementation for that profile; do not silently treat public API as a leak |
| A unit map hides a dependency that the manifests prove exists | remap the boundary or disclose the finding; never report clean |
| The requested change would require editing the catalog | that is a standards change, not an adoption task |
| Implementation needs a file, source change, build change or CI workflow outside the approved list | approval of one scope is not approval of another; stop and present the addition |
| The module map still has a material ambiguity | guessed architecture must not become authoritative configuration |

## Reference map

| File | Use it for |
|---|---|
| [00-preflight.md](references/00-preflight.md) | every check ID, what it means, how to fix it |
| [05-architecture-families.md](references/05-architecture-families.md) | placing ACIMA beside Clean, Hexagonal, DDD, a modular monolith or microservices — and where it is stricter |
| [10-greenfield.md](references/10-greenfield.md) | day-zero sequence and file skeletons |
| [20-brownfield.md](references/20-brownfield.md) | ratchet, seams, extraction recipe, sequencing |
| [70-corrections.md](references/70-corrections.md) | per-rule correction recipe, the trap for each, and how to prove the fix |
| [30-adoption-for-newcomers.md](references/30-adoption-for-newcomers.md) | teaching people with no background |
| [40-communication.md](references/40-communication.md) | what to say to teammates, managers, skeptics |
| [50-outcomes.md](references/50-outcomes.md) | metrics, reporting, definition of done per level |
| [60-troubleshooting.md](references/60-troubleshooting.md) | false positives, waiver storms, monorepos, gaps |
| [80-reporting.md](references/80-reporting.md) | the two-level report, status and priority vocabulary, triage schema, progress etiquette |
| [15-consent-and-scope.md](references/15-consent-and-scope.md) | phases, approval boundary, artifact statuses and dependencies, partial approval, module-map confidence |
| [glossary.md](references/glossary.md) | plain-language definitions to reuse verbatim |
| [vendor/docs/commands.md](vendor/docs/commands.md) | every command, flag and exit code, mapped to the step that uses it |

## Maintaining this skill

The manifest pins the catalog hash, the standard version, the portable rule set and the enforcer
paths. When the standard changes:

1. run `preflight.py`; `SKL-002`, `SKL-003` or `SKL-006` will fail;
2. read the changed rules and the affected references;
3. update the manifest hash and `skill-version`, and the references that describe the change;
4. re-run `preflight.py --deep` so the examples are proven, not assumed;
5. commit the skill change separately from any product change.

Drift has three forms; check all three: the copied skill against its sources
(`bundle_skill.py --check`), the skill against this catalog (`preflight.py`; `SKL-002`/`SKL-003`), and
the target's artefacts against its evidence (`acima.py status`). A green gate with a drifted skill is
confident, outdated advice.

A skill that silently follows a moving standard is worse than no skill: it produces confident,
outdated advice.
