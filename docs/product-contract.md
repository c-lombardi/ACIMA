# ACIMA product contract

Status: **technical preview, version `1.9.0-draft.1`** (2026-11-09).

This document states what ACIMA promises consumers today, what it does not promise,
and what evidence supports the release disposition. It is subordinate to the
normative standard in `docs/standard/` and the rule catalog in
`tools/acima-spec/rules.json`; where they conflict, the standard and catalog win.

## What ACIMA does

ACIMA makes declared architectural boundaries executable:

- a **unit map** names modules, units, roles and paths;
- **contracts** are the only cross-module surface; implementations, persistence,
  configuration and statics are private;
- enforcers evaluate the portable rules and emit deterministic findings;
- **waivers** record owned, expiring, fingerprinted exceptions;
- a **library/framework profile** classifies declared public API and intentional
  adapter edges without deleting them from the report;
- the **agent skill** preflights, proposes units, measures a baseline and helps an
  agent work within the boundaries;
- a **claim gate** computes `FULL CONFORMANCE` or `PARTIAL ASSESSMENT` from the run and
  `acima/evidence/manual-evidence.json`; authors do not choose the label;
- a **read-only assessment** (`acima assess`) inventories a repository, names the applicable
  requirements and the rules it could not decide, and never modifies the target.

## Supported today

| Area | Supported | Evidence / limit |
|---|---|---|
| Python | 42 automated rules; reference enforcer | Source and AST analysis, not type-checking; the fourteen manual rules remain unevaluated |
| TypeScript | 41 of 42 automated rules; reference enforcer | Source-text analysis, not type-checking; `D017` and the fourteen manual rules remain unevaluated |
| Go | 27 of 42 automated rules; reference enforcer | Source/import scanning plus Go AST analysis for `A005`/`D015`/`N002` and `go.mod` dependency-policy scanning for `G006`, without type checking; the four tier rules (`L005`–`L007`, `D010`), two explicit-input rules, one value rule (`A006`), two composition rules, one functional-capture rule (`D016`), three lifecycle rules, one naming rule (`N001`) and the fourteen manual rules report `executed: false` |
| C#/.NET | 42 of 42 automated rules; reference enforcer; library profile | Project-level Roslyn semantic compilations plus source and MSBuild-evaluated project metadata, not assembly loading; the fourteen manual rules report `executed: false` |
| Java | Profile only | No reference enforcer; a selected Java assessment fails closed |
| Fourteen manual-evidence rules | Normative, not executable by the portable enforcers | `C003`, `C007`, `C008`, `L004`, `A002`, `A004`, `A010`–`A015`, `G004`, `N003` are `automation: "manual"` and require repository-scoped evidence for a full claim |
| Owned effects and business visibility | P1.7 and P15 are normative; manual evidence required | Ownership, retry/duplicate/consistency/cancellation semantics, truthful outcomes, recovery evidence and boundary visibility have no reliable portable detector |
| Brownfield adoption | Preflight, draft units, baseline waivers, ratchet guidance | Unit names and owners require human confirmation |
| AI agent skill | Pinned catalog, preflight, assessment validation, playbooks | No independent adversarial evaluation yet |

### Consumer contract

A consumer may rely on the following for the four implemented enforcers:

1. **Deterministic output.** Findings are ordered by path, line and rule; fingerprints
   are stable for the same rule, path and evidence.
2. **Explicit assessment identity.** JSON reports include the standard, level, source
   file count, profile summary, execution map, classified entries and findings.
3. **Visible completeness.** Every catalog rule appears in `execution`; every
   `executed: false` entry has a reason. A rule that did not execute is not a pass.
4. **Exit codes.** `0` means no unwaived error findings at the selected level, `1`
   means findings, and `2` means the tool or configuration could not run.
5. **Finding shape.** A finding has `rule`, `severity`, `message`, `path`, `line`,
   `evidence` and `fingerprint`. Classified entries are reported separately and keep
   their owner and reason.
6. **Waiver control.** A waiver needs a rule, scope, owner, reason, fingerprint,
   expiry and review date. Broad or fingerprint-less waivers are rejected. `P9.5` is
   advisory in Draft 1 and is not represented as machine-enforced.
7. **Claim class and currentness.** `acima claim` emits `FULL CONFORMANCE` only when every rule
   required by the level executed or has accepted repository-scoped manual evidence, with zero
   unwaived errors, **and** the run's repository, commit, standard, catalog hash, configuration
   hash, enforcer version, level, source inventory and baseline match the current checkout.
   Otherwise it emits `PARTIAL ASSESSMENT` and names the missing rules; a rule-complete run from
   another commit is reported as `FULL CONFORMANCE` with `current: false`, never as current
   conformance. Malformed input exits `2`, and `--require full` exits `1` unless the claim is
   current. Older reports remain readable but are historical evidence only.
8. **Scope control.** Literal exclusions match a file or directory subtree, not an
   arbitrary sibling prefix. Globs remain globs; bare segments retain legacy
   any-directory matching.
9. **Calibration.** The adoption skill’s manifest pins the catalog SHA-256 and the
   portable rule IDs. A mismatch blocks the skill rather than silently changing scope.

### Known contract gaps

- Path-glob semantics are **not yet uniform** across the reference enforcers. The
  .NET enforcer treats `**/` as zero or more directories; Python, TypeScript and Go
  retain their library-specific glob behavior. Portable profiles should use explicit
  paths or verify the pattern in the target enforcer.
- The four enforcers are source-text/heuristic analysis. They do not prove runtime
  isolation, type correctness, framework behavior or every indirect dependency.
- The published benchmark (`rw-2026-11-08-02`) predates the current exclusion,
  catalog and .NET fixes. It must be rerun before portfolio-level claims are updated.
- No hosted CI run or independent reviewer has validated this revision.

## What ACIMA does not promise

- Support for Java, or for any language without a reference enforcer.
- Detection of the fourteen semantic/non-portable rules listed above.
- Automatic discovery of the correct architecture, module ownership or exceptions.
- Replacement for architecture review, engineering judgement or design authority.
- Proof that a zero-finding assessment is correct; zero findings require a complete
  run, non-zero source count, execution coverage and controlled violation injection.
- A health score, trend dashboard, hosted service or organizational metrics.
- Compatibility guarantees beyond the documented versioning policy; this is a draft.

## Release gates

| Gate | Status | What is missing |
|---|---|---|
| Public technical preview | **PARTIAL** | Independent review/CI, full benchmark rerun, Java decision, application-oriented validation, portable glob contract |
| Public beta | **BLOCKED** | Complete rule coverage, application validation, independent pilots, skill adversarial coverage, trustworthy completeness across wrappers |
| General availability | **BLOCKED** | Independent finding-quality evaluation, reproducible application/library benchmarks, organizational adoption, reviewed security/supply-chain posture |

A gate is not marked PASS because code exists. Its required evidence must be present.

## Versioning and change control

- The standard version is `1.9.0-draft.1`; the skill version is `1.18.0`.
- Assessment is read-only. Adoption artifacts require explicit owner approval of a proposal naming
  the paths, scope and level; partial approval is supported and must be described honestly.
- Rule IDs are never renumbered. A meaning change requires a catalog version change,
  a skill re-pin, conformance updates and a migration note.
- Exclusion and glob semantics are consumer contracts. Changes require positive,
  negative, boundary and adversarial fixtures.
- Benchmark evidence is immutable: headline results are versioned in the repository, raw per-repository artifacts are archived in git history, and a rerun is published in a new dated directory.
- This contract is reviewed whenever a release gate moves or a supported-language
  claim changes.

## Reporting a problem

Include the enforcer and version, target language/profile, config, raw JSON (not a
terminal capture), exit code, source count, execution map and a minimal reproduction.
An invalid, truncated or unsupported assessment must be reported as such, not as a
clean architecture.
