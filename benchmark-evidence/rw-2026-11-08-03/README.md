# ACIMA real-world benchmark — `rw-2026-11-08-03`

> Raw per-repository artifacts for this run are archived in git history (commit 5c74eb4); this tree keeps the headline results, ground truth and configs. See the [directory README](../README.md).

Mechanical rerun of the pinned 15-repository benchmark against the current reference
enforcers. This run preserves `rw-2026-11-08-01` and `rw-2026-11-08-02` unchanged.

**This is not a re-adjudication.** The numbers below are raw enforcer output. A finding
is not called a defect, a clean result is not injection-proven, and no precision/recall
estimate is inferred. The previous ground-truth classifications were not reused or
rewritten.

## Method

- Source copies and pinned commits are the same disposable copies used by the prior runs.
- The exact reviewed run-02 configs in `benchmark-evidence/rw-2026-11-08-02/configs/`
  were installed into the disposable adoption copies. The uncorrected run-01 configs are
  retained under `configs/*.run01.acima.config.json`.
- Upstream source was not edited. Only untracked ACIMA configs, waivers and assessment
  artifacts exist in the disposable copies.
- Baseline language test suites were not rerun; the source commits are unchanged. This
  run exercises the enforcer layer only.
- The Java repositories remain blocked: there is no Java reference enforcer.
- No independent reviewer and no hosted CI run participated in this evidence.

## Result

| Metric | `rw-2026-11-08-02` | `rw-2026-11-08-03` |
|---|---:|---:|
| Repositories | 15 | 15 |
| Assessed | 12 | 12 |
| Java blocked | 3 | 3 |
| Valid JSON assessments | 12 / 12 | 12 / 12 |
| Raw unclassified findings | 62 | 43 |
| Classified entries | 150 | 175 |
| Zero-finding repositories | 9 | 9 |
| Repositories with findings | 3 | 3 |
| Injection-proven in this run | 8 (historical) | 0 |

The reduction from 62 to 43 unclassified findings is concentrated in the .NET profile
results: FluentValidation reports 1 finding (was 7) and Spectre.Console reports 40 (was
53), while classified entries rise to 175. This is consistent with the post-run-02
profile/large-output fixes, but this run does not adjudicate whether each remaining
finding is a defect, a duplicate, a valid architectural choice or a false positive.

## Per-repository raw result

| Repository | Language | Analyzed | Findings | Classified | Status |
|---|---|---:|---:|---:|---|
| httpx | Python | 23 | 0 | 0 | clean |
| flask | Python | 24 | 0 | 0 | clean |
| fastapi | Python | 52 | 0 | 0 | clean |
| hono | TypeScript | 229 | 0 | 32 | clean |
| drizzle-orm | TypeScript | 658 | 2 | 28 | findings |
| trpc | TypeScript | 390 | 0 | 0 | clean, corrected scope |
| cobra | Go | 36 | 0 | 0 | clean |
| bubbletea | Go | 44 | 0 | 0 | clean |
| gin | Go | 99 | 0 | 0 | clean |
| fluentvalidation | .NET | 144 | 1 | 6 | findings |
| serilog | .NET | 113 | 0 | 0 | clean |
| spectre-console | .NET | 384 | 40 | 109 | findings |
| jsoup | Java | — | blocked | — | no enforcer |
| gson | Java | — | blocked | — | no enforcer |
| mall | Java | — | blocked | — | no enforcer |

`trpc` uses the reviewed corrected-scope config; the raw scope error remains recorded in
`rw-2026-11-08-02`. `drizzle-orm` retains the two core→driver `L001` findings recorded in
the prior run and 28 classified adapter entries.

## Evidence map

- `aggregate/portfolio.json` — machine-readable rows for all 15 repositories.
- `aggregate/portfolio.md` — per-repository table and totals.
- `runs/` — raw enforcer JSON, stderr and exit status for each assessed repository;
  `blocked.json` for each Java repository.
- `configs/` — the uncorrected run-01 backups; the executed configs are the exact run-02
  files under `benchmark-evidence/rw-2026-11-08-02/configs/`.
- `tooling/run.py` — the runner used for this run.
- `SHA256SUMS` — checksums of the evidence files in this directory.

## What this run does not establish

- It does not validate the architecture or the adoption skill.
- It does not prove that a zero-finding result is clean; no injection proof was rerun.
- It does not reclassify the 43 findings.
- It does not cover Java, runtime ownership, operational autonomy, a real application
  pilot, independent review or hosted CI.
- It must not be cited as a precision/recall measurement or a production-readiness claim.
