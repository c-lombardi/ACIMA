# Commands

Every command in this repository, what it guarantees, and which adoption step it serves. If you are
prompting an agent, point it here: this page is the whole surface.

Nothing here writes a score. Findings come from a rule catalog; a clean run means "no unwaived
errors at this level", never "the architecture is good".

## At a glance

| Command | Purpose | Writes? | Skill step |
|---|---|---|---|
| `tools/acima.py status` | which steps are evidenced, and the next command | no | any |
| `tools/acima.py inspect` | units, language, level, enforcer readiness | no | recon |
| `tools/acima.py assess` | read-only compatibility assessment and verdict | no | assessment |
| `tools/acima.py analyze` | run the reference enforcer, print findings | no | measure |
| `tools/acima.py fix` | 1..many findings → the catalog remedy and correction shape for each | no | slice |
| `tools/acima.py externals` | draft the third-party tier declaration from the manifest | only with `--write-draft` | Step 3 |
| `tools/acima.py report` | evidence report naming rules that did **not** run | no | report |
| `tools/acima.py claim` | `FULL CONFORMANCE` vs `PARTIAL ASSESSMENT`, bound to the current commit | no | claim |
| `tools/acima.py verify` | the full reference conformance suite | no | maintain |
| `skills/acima-adoption/scripts/preflight.py` | skill calibration + target classification | only with `--write-*`, after approval | Step 0 |
| `skills/acima-adoption/scripts/inject_violation.py` | prove the enforcer detects known violations | `--out` only | Step 5 |
| `skills/acima-adoption/scripts/summarize.py` | run artefact → plain-language adoption summary | `--out` only | report |
| `examples/<lang>/tools/...` | the enforcer itself, for one language | no | Step 5 |
| `conformance/run.py` | all profiles' clean + gallery fixtures | `--artifacts` only | maintain |

## Which phase am I in

The five phase names are canonical. Find the phase, then run its command. The commands below are
read-only unless the table says otherwise.

| Phase | Question | Command | Writes? |
|---|---|---|---|
| **Start** | which repository, and guided or automated? | none | no |
| **Phase 1 — Assess** | what is here, and does ACIMA fit? | `acima.py inspect`, `acima.py assess`, `preflight.py --project` | no |
| **Phase 2 — Explain and propose** | what exactly would change, at what cost? | `assets/adoption-proposal.md`, `render_report.py` | report files only, outside the target unless approved |
| **Phase 3 — Review and authorize** | which named paths and stages are approved? | none: record the approval in the scope record | the scope record, by the owner |
| **Phase 4 — Implement** | is this change inside the approval? | `preflight.py --write-draft`, `--write-waivers`, the enforcer | yes, approved paths only |
| **Phase 5 — Verify and hand off** | what is proven now? | the enforcer, `acima.py claim`, `summarize.py` | no |

No command grants write authority by itself. Approval is a separate, explicit decision naming the
paths and stages.

## From finding to correction — `fix`

```bash
python3 tools/acima.py fix --report acima.json ACIMA-D001
python3 tools/acima.py fix --report acima.json ACIMA-D001@src/orders/place.py C002
python3 tools/acima.py fix --root . --all --format markdown
```

Each selector is a rule id, `rule@path` (or `rule:path`), a path fragment, or a fingerprint. It
prints the finding, the catalog's `fix` text and the correction shape — `invert`, `localise`,
`remove`, `restructure`, `contract`, `governance` — for one entry or many. `--all` selects the whole
report.

It is a plan, not a patch: no file is edited. Exit `0` when every selector matched, `1` when one
matched nothing (a selector that silently does nothing is how a fix gets skipped), `2` when the
report or the run cannot be read.

## Which tier is this package — `externals`

```bash
python3 tools/acima.py externals --root .                 # print the draft declaration
python3 tools/acima.py externals --root . --write-draft   # merge it into acima.config.json
```

It reads `manifests[]` from the config, or `package.json`, `pyproject.toml` and `requirements.txt`
when the list is absent, and prints one `externals` entry per package. Every draft entry is
`tier: utility` with `owner: UNASSIGNED`, a reason that says so, a `reviewedOn` of today and a
one-year expiry. That is a starting point for review, not a decision: `platform`, `integration` and
`utility` mean different things to the gate (chapter 4 §4.10).

`--write-draft` never overwrites an existing entry, so it is safe to re-run after a dependency is
added — the output is the delta. Exit `0` on success, `2` when there is no config or no manifest.

## Where am I — `status`

```bash
python3 tools/acima.py status --root .              # human summary
python3 tools/acima.py status --root . --format json
python3 tools/acima.py status --root . --format markdown
```

The eleven steps remain evidence diagnostics. Adoption completion is calculated from the
**approved scope** and the evidence for each objective, not from the universal sequence. The
response contains `scope`, `objectives`, `engagement` and one `next` action.

### The scope record

Approval is explicit. It is not inferred from `acima.config.json`, a template, a baseline or the
presence of a document. Record it in `acima/evidence/adoption-scope.json` (or
`acima/evidence/adoption-scope.json`; a config's `adoption` object is also accepted, but an external
file is preferred because it does not change the configuration hash):

```json
{
  "version": 1,
  "approvedBy": "repository-owner",
  "approvedOn": "2026-11-10",
  "proposal": "acima/report/adoption-proposal.md",
  "objectives": [
    {"id": "assessment", "disposition": "required"},
    {"id": "local-enforcement", "disposition": "approved"},
    {"id": "ci-enforcement", "disposition": "deferred", "reason": "next quarter"},
    {"id": "communication-governance", "disposition": "declined"}
  ]
}
```

Canonical objective ids are `assessment`, `local-enforcement`, `baseline-waivers`,
`ci-enforcement`, `full-conformance`, `developer-handoff` and `communication-governance`.
`required` and `approved` must complete; `declined`, `deferred`, `optional` and `not-applicable`
never block. `DECLINED`, `DEFERRED`, `OPTIONAL` and `NOT_APPLICABLE` are distinct states: a
declined plan is not the same as an objective that does not apply. A prerequisite is promoted to
`required` automatically; an approved objective whose prerequisite was explicitly declined is a
scope conflict, not silently ignored. Unknown ids, duplicate ids, a missing `approvedBy` or
`approvedOn`, a future approval date and an invalid disposition make the scope `BLOCKED` before any
action is proposed.

Assessment evidence is `acima/evidence/assessment.json` (or `acima/evidence/assessment.json`), written by
redirecting `acima.py assess --format json`. It must be read-only, belong to this repository and
record a recognized verdict. Assessment-only scope can complete without a config, baseline or CI.
Local-only scope can complete without CI, waivers or optional documents. If full conformance is
approved, every existing claim requirement still applies; adoption completion never weakens it.

### Evidence and next action

A step is complete only when its criterion is verified: calibration compares the manifest pin with
the catalog, a baseline must parse with `sourceFiles > 0` and an execution map. A gate workflow is
parsed for an actual `run:` invocation: the enforcer must use `--root .`, the declared level, and a
pull-request or merge trigger; disabled, advisory, conditional and unsupported reusable/composite
jobs do not count. A gate observation must reference that workflow and command, match the
repository, `HEAD`, standard, catalog hash, level and positive source count, and must not report a
skipped enforcer. A configured gate and a manually recorded observation are `in progress`; only a
provider-sourced run matching `HEAD` is complete. The proof record must show `L001` and `D001`
detected, and the claim is computed with `acima.py claim`. A claim completes the conformance
objective only when its repository, commit, standard, catalog hash, configuration hash, source
inventory and baseline match the current checkout; a historical or stale full result leaves it in
progress and names freshness as the limitation.

Status prints the single highest-value action whose prerequisites are satisfied, why it is next,
its done condition, whether approval is required and what an approval would change. It does not
advance past a blocked or unverified prerequisite. Without a scope record it reports `UNKNOWN` and
asks for the approved scope rather than assuming full adoption; the one exception is a repository
with no config and no run, where the first action stays the read-only preflight plus assessment.
Optional documents never appear in the next action. Two honest limits remain: step 3 stays
`UNKNOWN` until `inject_violation.py --out` is run, and step 9 needs two comparable measurements to
show a fall.

### Evidence contracts

**Gate observation** — `acima/evidence/gate-observed.json`:

```json
{"repository": "owner/name", "commit": "<sha>", "workflow": ".github/workflows/acima.yml",
 "command": "acima_arch.py --root .", "executedAt": "2026-11-09T10:00:00Z",
 "standard": "1.9.0-draft.1", "catalogSha256": "<64 hex>", "level": "L2",
 "sourceFiles": 69, "exitCode": 1,
 "manual": false, "verified": true, "provider": "github-actions", "runId": "123"}
```

Every field except `manual`, `verified`, `provider`, `runId` and optional `runUrl`/`enforcerExecuted`
is required. The workflow must exist and contain a valid, unconditional enforcer invocation for a
pull request or merge event. Its command must match the observation; the catalog hash, level and
repository must match, and the commit must match `HEAD` when it can be checked. `exitCode: 1`
means the gate ran and rejected the commit — reported as a failure, never as a milestone.
`enforcerExecuted: false`, a skipped outcome, a non-success `conclusion`, or an unverifiable
provider/run id never establishes a verified gate. `manual: true`, or a record without provider
provenance, is `IN_PROGRESS` and is not independently verified.

**Proof record** — `acima/evidence/proof.json`, written by
`inject_violation.py --project . --out acima/evidence/proof.json`: `standard`, `catalogSha256`,
`generatedAt`, `sourceFiles` and one result per rule with `detected` and `exitCode`. Both
`ACIMA-L001` and `ACIMA-D001` must be detected with exit `1`.

Exit `0` whenever a status is produced, `2` when the root or its config cannot be read. It never
writes, so it is safe to run first in any session — including on a repository you do not own.

## The natural order

Three questions, asked in this order: does ACIMA suit this repository, do we adopt it, and are we still
conformant at the level we claim.

| # | Stage | Question | Command | Move on when |
|---|---|---|---|---|
| 1 | Calibrate | is the skill right for this commit, and what kind of repository is this? | `preflight.py --project .` | exit 0 and a classification |
| 2 | Recon | what is in here? | `acima.py inspect --root .` | language, units and enforcer readiness are known |
| 3 | Fit | is it worth adopting? | `acima.py assess --root .` | verdict `ASSESSED`, or `NEEDS_UNIT_MAP` with a plan to declare units |
| 4 | Trust the tool | can it even see violations? | `inject_violation.py --project .` | `L001` and `D001` are both detected |
| 5 | Declare, after approval | what are the units? | `preflight.py --write-draft` | a human reviewed and committed `acima.config.json` |
| 6 | Freeze | how bad is it, exactly? | `preflight.py --format json > baseline.json` | the artefact is kept and dated |
| 7 | Own | who answers for each finding? | `preflight.py --write-waivers` | no `unassigned` owners, every expiry set |
| 8 | Gate | does CI block new debt? | enforcer in CI, `--baseline` where supported | a failing PR shows only `NEW` findings |
| 9 | Slice | one boundary per pull request | enforcer locally | the count is flat or falling |
| 10 | Claim | at what level is it conformant? | `acima.py claim` + `acima/evidence/manual-evidence.json` | the claim class matches the evidence |
| 11 | Maintain | do the rules still fire? | `conformance/run.py` | every selected profile conforms |

Steps 1–4 write nothing and are safe on any repository, including one you do not own. Steps 5–9
change the repository and need the owner's explicit approval of the named paths and scope; adoption
intent alone is not approval. Step 10 is a claim about a run, not a task, and step 11 is for people
changing the standard rather than adopting it.

After step 9 the loop is 8 → 9 → 8: each pull request either lowers the count or leaves it flat, and
the gate stops it rising. Monthly, revisit waivers that are near expiry — individually, never in
bulk. Quarterly, decide whether to raise the level: raising it means the count is zero and every
rule at that level has executed.

## `tools/acima.py`

```bash
python3 tools/acima.py --help
python3 tools/acima.py inspect --root examples/python
python3 tools/acima.py assess  --root /path/to/repo --format markdown
python3 tools/acima.py analyze --root examples/python --format json > acima.json
python3 tools/acima.py report  --root examples/python --format markdown
python3 tools/acima.py claim   --report acima.json --level L2 --require full
python3 tools/acima.py verify  python typescript
```

- `assess` verdicts: `ASSESSED`, `NEEDS_UNIT_MAP`, `UNSUPPORTED_LANGUAGE`,
  `UNSUPPORTED_PROFILE`, `TOOLCHAIN_MISSING`, `INVALID_ROOT`, `NO_SOURCE`, `INVALID_CONFIG`,
  `INVALID_ASSESSMENT`. `NEEDS_UNIT_MAP` means unassessed, never clean. Exit `0` when a report was
  produced, `2` when it could not be.
- `assess` also returns an evidence-based fit result with one outcome: `RECOMMENDED`,
  `RECOMMENDED_WITH_LIMITATIONS`, `NOT_RECOMMENDED`, `INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`.
  It assesses technical compatibility, architectural substance, existing enforcement, incremental
  value, adoption cost and practical applicability independently. Zero findings do not imply
  adoption; existing findings do not imply `RECOMMENDED_WITH_LIMITATIONS`. Benefits are classified
  as available today, achievable through adoption, requiring additional work, or not applicable.
- `claim` exits `0` only when the requested class is satisfied **and** the claim is current: the run
  must record the current repository, `HEAD`, standard, catalog hash, configuration hash, enforcer
  version, level, source inventory, baseline hash and positive source count, and no relevant tracked
  file may be modified in the working tree. A rule-complete claim from an older commit, another
  repository, or a changed catalog/configuration is still printed as `FULL CONFORMANCE`, but with
  `current: false` and a `currentness` state (`historical`, `stale`, `uncommitted`, ...), and
  `--require full` exits `1`. Missing Git metadata leaves currentness unestablished; it never
  defaults to current. `2` means the run or evidence document is invalid.
- Run provenance is additive: older reports stay readable and retain their historical claim, but
  because they lack the fields above they cannot establish current conformance.
- `inspect`, `analyze`, `report`, `claim`, `assess` never write to the target.

## The adoption skill's scripts

```bash
python3 skills/acima-adoption/scripts/preflight.py --project <target> --format text
python3 skills/acima-adoption/scripts/preflight.py --project . --write-draft acima.config.json
python3 skills/acima-adoption/scripts/preflight.py --project . --write-waivers acima/evidence/waivers.json
python3 skills/acima-adoption/scripts/preflight.py --project <target> --deep
python3 skills/acima-adoption/scripts/inject_violation.py --project <target> --format json
python3 skills/acima-adoption/scripts/inject_violation.py --project <target> --out acima/evidence/proof.json
```

| Flag | Meaning |
|---|---|
| `--project` | target repository root |
| `--format {text,json}` | human summary or machine report |
| `--manifest` | alternate skill manifest (used by tests) |
| `--deep` | also run every reference enforcer against its example |
| `--write-draft` | heuristic `acima.config.json`; **requires explicit approval**, and a human must review it |
| `--write-waivers` | scoped waivers from the measured baseline; **requires explicit approval**, owner `unassigned` until you fill it |
| `--strict` | treat warnings as blockers |

`preflight.py` exit codes: `0` ready, `1` blocked, `2` the tool could not run. `inject_violation.py`
exit `1` means **not proven** — never report it as a pass.

## The adoption summary — `summarize.py`

```bash
python3 skills/acima-adoption/scripts/summarize.py --root . --report acima.json \
  --initial-report acima/evidence/gate-L1-baseline.json \
  --triage acima/evidence/triage.json \
  --out acima/handoff/adoption-summary.md
```

An assessment summary goes in the response or outside the target; writing into the target needs
approval. One run artefact in, one reader-facing summary out. It groups findings by rule and cause, uses
human titles from the catalog, separates confirmed defects from detector artefacts, names one next
action, and lists what is completed and unverified. `--format json` emits the same model for tests
and other tools; `--claim` accepts the JSON from `acima.py claim` and is the only way the status
becomes `Verified`. It never edits the target unless `--out` names a path.

Exit `2` means the report, catalog or triage file is unusable. The summary is an interpretation of
evidence: it cannot raise a claim, suppress a finding or soften a rule. Its `Verified` status requires
`"current": true` on the supplied claim; a historical, stale or unprovenanced claim is reported with
its `claimState` and a limitation saying that freshness, not architecture, is the problem.

## The language enforcers

```bash
python3 examples/python/tools/acima_arch.py         --root <target> --format json
node     examples/typescript/tools/acima-arch.mjs   --root <target> --format json
(cd examples/go && go run ./tools/archtest --root <absolute-target> --format json)
dotnet run --project examples/dotnet/tools/Acima.ArchTests -- --root <target> --format json
```

Shared flags: `--root`, `--config`, `--format {json,text}`, `--level`. The .NET enforcer adds:

| Flag | Meaning |
|---|---|
| `--baseline <file>` | label findings `KNOWN`/`NEW` and fail only on findings outside the baseline |
| `--verify` | run the clean tree and the violation gallery against `violations/expected.json` |

Exit codes for all four: `0` clean, `1` findings, `2` invalid config or unreadable input.

## The conformance suite

```bash
python3 conformance/run.py                      # every supported profile
python3 conformance/run.py python typescript    # a subset
python3 conformance/run.py --artifacts artifacts/
```

Profiles: `python`, `typescript`, `go`, `dotnet`, `tools`, `topology`. Each runs a clean fixture and
a violation gallery, so a green suite proves the enforcers still detect what they claim.

## Which command when

| You are… | Run |
|---|---|
| deciding whether ACIMA fits a repo | `acima.py assess` — read-only, no config written |
| assessing fit | `acima.py assess` — read-only; no proposal artifacts required |
| proposing adoption | present the artifact list and approval question from `assets/adoption-proposal.md` |
| adopting after approval, step 0 | `preflight.py --project <target>` |
| adopting after approval, step 1–2 | `preflight.py --write-draft`, then review and commit the map |
| adopting after approval, step 3 | `preflight.py --write-waivers`, then replace `unassigned` with real owners |
| adopting, step 5 | the language enforcer, then `inject_violation.py` to prove it detects violations |
| reporting a claim | `acima.py claim` with the run and manual evidence, then `summarize.py --claim` |
| explaining results to a team | `summarize.py` — the reader-facing summary, not the JSON |
| maintaining the standard | `conformance/run.py` after any rule or enforcer change |


### Evidence-backed qualitative assessment review

A comprehensive qualitative review is a separate artefact from deterministic conformance output.
Validate all catalog requirements with:

```sh
python3 tools/acima.py validate-review --root /path/to/repository --file /path/to/qualitative-review.json --format json
```

Attach the validated review to a read-only compatibility assessment with `assess --review`.
The validator requires exact catalog coverage, one disposition per rule, reviewer/date metadata,
a matching catalog SHA-256, repository-local evidence paths, valid line ranges and exact quoted
source text. `insufficient_evidence` remains unresolved. Its JSON result includes `gapRegister`,
which enumerates every gap and insufficient-evidence item by catalog rule, and `unresolvedRules`.
Report those items from the register; a gap count that does not reconcile with the listed rule ids
is a reporting defect. Assessment completion additionally requires a declared unit map and
successful deterministic assessment; completion is not conformance.
