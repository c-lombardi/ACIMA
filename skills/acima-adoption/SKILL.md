---
name: acima-adoption
description: Adopt, audit, and enforce the ACIMA architecture standard in a greenfield or brownfield repository. Use when the user asks to apply ACIMA, split a monolith into contract-isolated modules, add architecture tests or dependency rules, run an architecture audit against the ACIMA rule catalog, migrate a shared "Common" project, or onboard a team with no prior exposure to contract-based modular architecture. Not for general refactoring, formatting, or framework upgrades.
license: MIT
compatibility: Python 3.9+ for the preflight script. The target language toolchain is only needed to run that language's enforcer.
allowed-tools: Read Grep Glob Bash Edit Write
metadata:
  standard: "1.9.0-draft.1"
  skill-version: "1.18.0"
  catalog-sha256: "084d53a04582b955a4f64f80ca41067ff609bba812f2437ff8cc5c2306454822"
---

# ACIMA adoption

ACIMA makes an application's module boundaries explicit and enforceable. It stops one module from
depending on another module's private implementation, and it turns architectural requirements into
checks and recorded evidence instead of a document nobody reads. It can be introduced one boundary
at a time into a running system, and it does not ask the team to replace Clean Architecture,
Hexagonal, DDD, a modular monolith or microservices.

You do the discovery, explanation, recommendation and implementation. The user supplies business
context, resolves genuinely ambiguous ownership, and approves changes. Never make them learn the
catalog, the levels or the command set to get value. Analysis is never authorization.

## Positioning

ACIMA defines portable architectural requirements: module ownership, explicit contracts,
dependency isolation and direction, data and configuration ownership, and controlled composition.
Applicable lifecycle, state and effect ownership requirements also apply. It is not a template for
the application's overall architecture, and it is not merely an enforcement layer for boundaries
chosen elsewhere.

Existing architecture families can often satisfy these requirements, but compatibility is evaluated
against the actual requirements, not assumed from the family's name. Some requirements are
intentionally stricter than common practice; name them and explain why. A compatible family may need
a limited boundary adaptation. A fundamental conflict is incompatibility, not a violation to
refactor away. Distinguish incompatibility from insufficient evidence.

Never propose replacing or relabelling the team's architecture, or use a finding as an argument for
a different family. Never suggest that adopting ACIMA requires the `service-topology` profile. Name
the family you detected from evidence and state which ACIMA requirements it already satisfies, which
need adaptation, and which are not established — [05-architecture-families](references/05-architecture-families.md).

## Where you are running

Three execution contexts exist. Detect yours before printing a command; a path that does not exist
in the active context is not a runnable command.

| Context | What exists | How to invoke |
|---|---|---|
| ACIMA source checkout | `tools/`, `docs/`, `examples/`, the skill | `python3 tools/acima.py ...`, `python3 skills/acima-adoption/scripts/...`, `examples/<lang>/tools/...` |
| Copied or installed skill | `skills/acima-adoption/` with its `vendor/` snapshot | `python3 <skill>/scripts/preflight.py ...`, `python3 <skill>/vendor/tools/acima.py ...`, `python3 <skill>/vendor/examples/<lang>/tools/...` |
| A different target repository | the user's application only | run ACIMA commands from the checkout or skill directory with `--root`/`--project <target>` |

`preflight --deep` and `acima.py verify` need the full checkout; if it is absent, say so and offer
the read-only assessment that the skill can run. Verify a command's path and `--help` before calling
it executable, and never present a flag you have not confirmed.

## Route the request

Pick one mode from the user's words. If intent is unclear, run the read-only assessment and say so.
Never upgrade an assessment into an adoption because the findings are interesting.

| The user says | Mode | Writes? | First action | Ends when |
|---|---|---|---|---|
| "what is ACIMA", "would it help", "assess", "audit", "review" | **Assess** | no | explain in plain English, then read-only analysis | a verdict, named gaps and limits |
| "adopt", "apply ACIMA", "set it up", "add the gate" | **Adopt** | only after consent | the assessment, then the proposal | an approved scope, implemented and verified |
| "continue", "where are we", "what next" | **Resume** | no | `acima.py status --root .` | one next action, stated plainly |
| "fix this", "why does the gate fail", "correct D001" | **Slice** | smallest named change | `acima.py fix`, then the rule page | one boundary changed, gate re-measured |
| "explain this rule" | **Explain** | no | the rule page, then `acima.py report` | the answer and its remedy |

## Canonical workflow

One order, everywhere. Preflight establishes that this skill matches the catalog on disk and
classifies the target; the assessment establishes fit. Neither writes to the target.

| Phase | Purpose | Command | Ends when |
|---|---|---|---|
| 1. Assess | preflight first, then read-only fit, findings and limits | `preflight.py --project <target>`, then `acima.py assess --root <target>` | exit 0, a classification, and a verdict with named gaps |
| 2. Propose | the decision document | fill `assets/adoption-proposal.md` | a recommendation, exact paths, one question |
| 3. Authorize | explicit, scope-specific approval | none | an unambiguous yes to that proposal |
| 4. Implement | only the approved scope | the approved commands | the named files exist and measure |
| 5. Verify | prove what changed and what did not | the enforcer and `acima.py claim` | artefacts support every claim, limits named |

Do not run the same expensive analysis twice for two phases: reuse the assessment's run for the
proposal, and the implementation's run for the handoff. `status` reports which phase is evidenced.

**Phase 1 — Assessment.** Preflight runs first, always: it compares `rules.json` with the pinned SHA-256
and rule ids (`SKL-002`/`SKL-003`), classifies `greenfield`, `brownfield` or `adopting`, and lists
blockers. Exit `1` is a stop: report it in the user's terms with the printed remedy, never work
around it. Then run the read-only fit analysis and assess six dimensions independently: technical
compatibility, architectural substance, existing enforcement, incremental value, adoption cost and
practical applicability. Choose one outcome: `RECOMMENDED`, `RECOMMENDED_WITH_LIMITATIONS`,
`NOT_RECOMMENDED`, `INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`. A clean report is not a
recommendation: a utility with no meaningful boundaries, or an application whose existing checks
already cover the guarantee, is a `NOT_RECOMMENDED`. Explain the application, discovered
boundaries, existing enforcement, what ACIMA requires and does not require, cost, confidence and
unresolved questions. Record one compatibility outcome — compatible, compatible with adaptation,
incompatible or insufficient evidence — against the applicable requirements. Distinguish an
implementation difference from a genuine conflict, and never treat missing evidence as
incompatibility. Name any requirement that is stricter than the team's current practice and why it
exists. No config, waivers, baselines, CI, docs or source changes. `NEEDS_UNIT_MAP` means
unassessed, never clean.

**Phase 2 — Proposal.** Present [the proposal](assets/adoption-proposal.md) as a decision document:
recommendation first, then the compatibility outcome and evidence, requirements already satisfied,
the smallest useful scope, exact paths with required/conditional/optional status, stricter
constraints and tradeoffs, and the one approval question. Do not write files "so the user can see
them".

**Phase 3 — Explicit authorization.** Approval covers the listed scope only — the named paths,
level and changes. Partial approval
is supported: implement exactly what was approved and name the capability that stays unavailable.
Wait for an unambiguous yes to that proposal before touching a path. Interest, silence, "looks good"
about the diagnosis, or a request to see files is not approval.
Approval to change files never authorizes merge, release, publication or external systems.

**Phase 4 — Approved implementation.** Only approved changes. A new path, level, dependency or enforcement
mechanism outside the approved list stops work for a new decision.

**Phase 5 — Verification and handoff.** Verify with a run artefact, not intent, and report what is
proven separately from what is not.

| Action | Approval |
|---|---|
| Inspect, read, run read-only analysis, prepare a proposal | not needed |
| Create config, baseline, waivers, tooling, docs or CI | required, named paths |
| Modify source, build configuration or existing docs | required, named paths |
| Merge, publish or release, or change an external system | separate, explicit |

Full boundary and artifact matrix: [15-consent-and-scope](references/15-consent-and-scope.md).

## Discovery: the agent's job

Inspect before asking architectural questions. Establish, with evidence and confidence: application
purpose and type; languages, frameworks and manifests; project/package layout; entry points and
composition roots; construction and injection patterns; existing boundaries and dependency
direction; shared libraries; persistence and configuration ownership; external effects; tests and
existing architecture checks; build, packaging and CI. A repository may be several kinds at once —
say so, and never present a directory name as an ownership decision.

For each material inference give what was found, the evidence, confidence, and what remains
uncertain. Ask only what the repository cannot settle: shared-kernel status, host ownership,
duplicate names, and who owns exceptions.

Then explain ACIMA against the application: for each meaningful difference, the existing design, the
ACIMA expectation, why it matters, whether it is a confirmed problem, a suspected one, an acceptable
design or insufficient evidence, what would change, and whether judgement is required. Recognise what
already satisfies a requirement — do not sell existing good practice back as work. If ACIMA would add
little, say that plainly and recommend against adoption.

Ground benefits in observed characteristics: preventing a change in one implementation from breaking
its consumers, making ownership visible, stopping persistence or vendor details leaking across
boundaries, giving immediate feedback at the boundary, and enforcing the same constraint for people
and agents. Distinguish what this repository can achieve now from what needs organisational work.

## Status: what is actually proven

`acima.py status --root .` reports the evidence diagnostics and a scope-aware engagement summary.
The vocabulary is `NOT_STARTED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `COMPLETE`, `NOT_APPLICABLE`
and `UNKNOWN`; objective dispositions also distinguish `declined`, `deferred`, `optional` and
`not-applicable`. A step or objective is complete only when its criterion is verified:

- **scope** is an explicit owner artifact (`.acima/adoption-scope.json` or an `adoption` object in
  the config) naming `required`, `approved`, `declined`, `deferred`, `optional` and
  `not-applicable` objectives. File presence never implies approval, and a missing scope is
  `UNKNOWN`, not full adoption. Required and approved objectives must complete; the others never
  block. A prerequisite is promoted to required, and a declined prerequisite for an approved
  objective is a scope conflict.
- **fit** is complete only when the approved scope exists and a read-only assessment artifact
  (`docs/acima/assessment.json`) records a valid verdict for this repository. A config file proves
  neither fit nor approval.
- **trust the tool** requires a proof record naming the standard and catalog hash with `L001` and
  `D001` detected; an empty or stale record blocks.
- **calibration** compares the manifest pin with the catalog on disk; a config file proves nothing.
- **declare** requires a parsable config with at least one unit that covers source; review and
  approval are not proven by the file.
- **freeze** requires a run artefact with `sourceFiles > 0`, an `execution` map and a findings list.
  A fingerprint file alone is in progress, not measured.
- **own** requires owners, scopes, fingerprints and unexpired waivers; invalid, unowned or expired
  exceptions block, and are never accepted as exceptions.
- **gate** reads the actual `run:` command, not just the file name: it must invoke a recognized
  enforcer with `--root .`, the declared level, and a pull-request or merge trigger. Disabled,
  advisory, conditional or reusable/composite steps are blocked; a valid configured step is
  *in progress, not observed*. An observation must name the repository, commit, workflow, command,
  time, standard, catalog hash, level, source count and exit status, and its workflow/command must
  match a valid invocation in that same workflow. A manually recorded result is *in progress, not
  independently verified*; only a provider-sourced, non-skipped run with a successful conclusion
  against the matching repository and `HEAD` completes the step. CI configuration alone never
  proves enforcement.
- **slice** compares runs only when standard, level, source scope and execution map match; a lower
  count from a different scope is not an improvement, and a resolved finding must be named with no
  new errors.
- **claim** computes the class with `acima.py claim` and binds it to the repository state. A
  manual-evidence file is not proof; invalid or expired evidence blocks, missing evidence is a
  partial assessment, and a full result from another commit, catalog or configuration is historical
  or stale. `--require full` succeeds only for a current claim; missing Git metadata never counts as
  current.

Assessment-only and local-only engagements can complete without CI, waivers or optional documents.
When full conformance is approved, every claim requirement still applies; adoption completion and
architectural conformance stay separate. Optional documents (adoption plan, communication plan,
STATUS dashboard, summary) never block progress and never appear in "next". Do not create optional
artifacts unless the approved scope includes them or the owner asks. Do not create a communication
plan by default.

Status output states what is complete, in progress, remaining and blocked within the approved
scope; what is declined, deferred, optional or not applicable; the single next action with its
prerequisite, command, done condition and effect; and whether approval is required. A status
command never recommends a write unless that scope was approved; it proposes instead.

## Interaction contract

Every phase ends in the same shape, in plain English:

- **Current state** — where the user is, in one sentence.
- **What happened** — the meaningful work, not a command log.
- **What it means** — the consequence for this application.
- **What happens next** — the next phase and why it is needed.
- **User involvement** — the one decision or approval required, or "none".
- **Next action** — one action with a completion condition.

Never expose internal identifiers when plain words work. Never ask twice for information the
repository already answers. Never claim completion from intent, configuration or file presence.
Six milestone updates at most; a blocker gets a message only when it changes the outcome.

## Proposal: a decision document

Nine sections, in this order: **Recommendation** (`RECOMMENDED`, `RECOMMENDED_WITH_LIMITATIONS`,
`NOT_RECOMMENDED`, `INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`, and why); **Application
discovered**; **What ACIMA adds**; **Expected benefits** grounded in evidence and classified as
available today, achievable through adoption, requiring additional work, or not applicable;
**Recommended scope** (smallest useful, level in plain English, what is excluded and why);
**Proposed changes** (exact paths, purpose, required/conditional/optional, modified files,
dependencies, CI); **Tradeoffs and risks** (maintenance, tooling limits, migration, compatibility,
what ACIMA does not prove); **Next steps** (sequence, what the user sees, decisions); **Approval**
(one question, scope-limited, partial approval allowed).

Recommend; do not turn the proposal into a questionnaire. State the level's practical consequence
before naming L1/L2/L3.

## Document lifecycle

Build documents only as the work earns them.

| Stage | Deliverable | Written where |
|---|---|---|
| A. Assessment brief | what the app is, what was found, fit, limits, recommendation | conversation, or outside the target |
| B. Proposal | the decision document above | conversation / temporary file |
| C. Implementation guide | steps, commands, files, verification, failure handling | in the approved scope only |
| D. Handoff and developer guide | what changed, what was verified, what remains, how to run and read the gate | approved docs, or the final message |If a document is not approved, deliver its content in the response — that is not a lesser outcome.

## Commands

Every command below is read-only unless marked.

| Command | Purpose | Writes |
|---|---|---|
| `acima.py status --root .` | scope-aware objectives, evidenced steps, blockers, one next action | no |
| `acima.py inspect --root .` | language, units, level, enforcer readiness | no |
| `acima.py assess --root .` | fit assessment and verdict | no |
| `acima.py analyze --root .` | run the reference enforcer, print findings | no |
| `acima.py fix --report <run> [selector]` | finding → catalog remedy and correction shape | no |
| `acima.py report --root .` | evidence report naming rules that did not run | no |
| `acima.py claim --report <run> --level <L> --require full` | `FULL`/`PARTIAL`, bound to current provenance, and gate it | no |
| `summarize.py --root <target> --report <run>` | run → reader-facing summary | `--out` only |
| `preflight.py --project <target>` | calibration and classification | `--write-*` only |
| `inject_violation.py --project <target> --out docs/acima/proof.json` | prove the enforcer detects controlled input | `--out` only |
| `<language enforcer> --root <target> --format json` | the gate for one language | no |

When a user must run a command, give purpose, working directory, prerequisites, whether it writes,
one copyable form, expected success output, and what to do on failure. Support PowerShell and POSIX
where the user runs it.

## Context files

Read these before proposing or resuming; never reconstruct state from the conversation:
`acima.config.json` (units, level, mode), `.acima/adoption-scope.json` (approved objectives and
approval metadata), `docs/acima/assessment.json` (the read-only assessment evidence),
`.acima/baseline.json` (frozen fingerprints), `.acima/waivers.json` (owned exceptions),
`.acima/manual-evidence.json` (manual-rule evidence), `docs/acima/STATUS.md` (next step),
`docs/acima/gate-*.json` (the runs a claim rests on), `.acima/triage.json` (recorded defect /
artefact / review decisions). Missing means missing: name the artefact and the phase that produces
it; do not invent contents. Optional docs: `docs/acima/adoption-plan.md`,
`docs/acima/communication-plan.md`, `docs/acima/adoption-summary.md`, `docs/acima/handoff.md`.

## Hard rules

1. **Never invent a rule ID.** Every finding cites one from `rules.json`.
2. **Never edit the catalog, a fixture's `expected.json`, or a manifest hash to make a check pass.**
3. **Never waive without owner, reason, scope, fingerprint, expiry and review date.**
4. **Never bulk-renew waivers.** Renewal is one owner's decision at a time.
5. **Never declare conformance without a run.** Zero findings require `sourceFiles > 0`, a complete
   execution map, exit `0`/`1`, valid JSON, the expected catalog and level, and controlled violations
   detected by `inject_violation.py`. Otherwise report `not proven`.
6. **Never treat invalid, truncated or missing output as zero findings.**
7. **Never start brownfield adoption at L3.** L1 first, then ratchet.
8. **Never rewrite the target to satisfy the standard.** Smallest boundary, then measure.
9. **Never apply ACIMA to a codebase whose owner has not asked for it.**
10. **Never declare a library profile to silence a finding**; a profile needs publishable evidence,
    an owner, a justification and path scoping ([12-library-profile](vendor/docs/standard/12-library-profile.md)).
11. **A required `executed: false` rule makes the result partial** unless accepted manual evidence
    covers it. Compute the class with `acima.py claim`; never report full from a clean error count.
12. **Never write before consent.** Analysis, interest or "adopt" is not approval of unseen files.
13. **Never require an organisational artefact.** Plans, dashboards and summaries are optional.
14. **A fix plan is not a patch.** `fix` explains a correction; changing source needs its own
    approval, and a request to fix one finding never authorizes other findings, CI or a redesign.

## Reviewing effects and choosing a correction

Effect, lifecycle, naming and per-rule remedies are conditional judgements, not a checklist:
read [70-corrections](references/70-corrections.md) before editing. In short — identify the effect and
its owner; decide which of retry, duplicate handling, consistency, cancellation, outcome and
evidence actually apply; fix the dependency path rather than banning closures; choose lifetime from
state ownership, never to reduce registrations; and keep naming advice targeted, never a bulk rename
and never a conformance gate.

Conformance is per repository and per commit. `FULL CONFORMANCE` requires zero unwaived errors at the
level, every required rule accounted for, **and** provenance that matches the current checkout —
repository, `HEAD`, standard, catalog hash, configuration hash, enforcer version and source
inventory. Manual rules need accepted, current, repository-scoped evidence — a catalog-manual rule
reported as executed is not evidence. A rule-complete claim from an older commit is historical, not
current; a changed catalog, configuration, baseline or source tree requires fresh measurement.
Anything less is a **PARTIAL ASSESSMENT** or a plan, and you call it what it is.

## Stop conditions

Stop and ask when: preflight exits 1; no owner exists for exceptions; two modules disagree about
concept ownership; one rule repeatedly produces waivers for legitimate designs; the target is Java
(profile only, no reference implementation); the mode is `service-topology` or
`acima.topology.json` exists (this revision has no supported service workflow); a library profile
lacks publishable evidence, or is requested for Python/Go; a unit map would hide a dependency the
manifests prove; the requested change would edit the catalog; implementation needs a path, source,
build or CI change outside the approved list; or the module map still has a material ambiguity.

## Reference map

| File | Load it for |
|---|---|
| [00-preflight](references/00-preflight.md) | check ids, blockers, remedies |
| [15-consent-and-scope](references/15-consent-and-scope.md) | phases, approval boundary, partial approval, artifact statuses |
| [05-architecture-families](references/05-architecture-families.md) | assessing compatibility with the team's architecture |
| [10-greenfield](references/10-greenfield.md) / [20-brownfield](references/20-brownfield.md) | approved implementation sequences |
| [70-corrections](references/70-corrections.md) | per-rule remedy, traps, effect and lifecycle review |
| [30-adoption-for-newcomers](references/30-adoption-for-newcomers.md) | teaching someone with no background |
| [40-communication](references/40-communication.md) | coordinating a multi-team programme, only if asked |
| [50-outcomes](references/50-outcomes.md) | metrics and definition of done per level |
| [60-troubleshooting](references/60-troubleshooting.md) | false positives, waiver storms, monorepos |
| [80-reporting](references/80-reporting.md) | report structure, status vocabulary, triage |
| [glossary](references/glossary.md) | plain-language definitions |
| [commands](vendor/docs/commands.md) | every flag, exit code and step |

## Maintaining this skill

The manifest pins the catalog hash, standard version, rule ids and enforcer paths. When the catalog
changes: run preflight (`SKL-002`/`SKL-003`/`SKL-006` fail first), read the changed rules, update the
manifest and this file, run `preflight --deep`, and commit the skill change separately. Check drift
three ways: copied skill against sources (`bundle_skill.py --check`), skill against catalog
(preflight), and target artefacts against evidence (`acima.py status`).
