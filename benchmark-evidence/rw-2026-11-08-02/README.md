# ACIMA real-world benchmark — `rw-2026-11-08-02`

Rerun of the 15-repository real-world benchmark against the current reference
enforcers at L1. Twelve repositories were assessed; the three Java repositories
remain blocked because there is still no Java enforcer.

This run is separate from, and does not modify, `rw-2026-11-08-01`.

## Headline

| Metric | `rw-2026-11-08-01` | `rw-2026-11-08-02` |
|---|---:|---:|
| Supported repositories executed | 12 | 12 |
| Valid JSON assessments | 11 / 12 | 12 / 12 |
| Unclassified findings | 120 | 62 |
| Confirmed or probable defects | 26 | 28 |
| True positives (confirmed / probable) | not split | 24 / 4 |
| Duplicates | 6 | 3 |
| Valid architectural choices, still unclassified | 84 | 30 |
| Valid choices classified by profile | 0 | 150 |
| False positives | 4 | 1 |
| Actionable yield | 21.7% | 45.2% |
| Java repositories blocked | 3 | 3 |
| Zero-finding repositories | 8 | 9 |
| Zero-finding repositories proven by injection | 0 | 8 |

The remaining 62 unclassified findings comprise 28 confirmed/probable defects,
3 duplicates, 30 valid library/API choices, and 1 tooling false positive. A
further 150 valid architecture edges are now explicitly classified rather than
reported as defects.

**Provisional scorecards: adoption skill 5.3/10; ACIMA standard 5.3/10.** These
are author-adjudicated and are not a certification. The prior run scored 4.6
and 4.7 respectively.

## Selected results

| Repository | Language | Unclassified | Classified | Adjudication |
|---|---|---:|---:|---|
| httpx | Python | 0 | 0 | clean; injection-proven |
| flask | Python | 0 | 0 | clean; injection-proven |
| fastapi | Python | 0 | 0 | prior L001 false positive fixed; injection-proven |
| hono | TypeScript | 0 | 32 | 25 adapter edges + 7 public-API items classified |
| drizzle-orm | TypeScript | 2 | 28 | 2 genuine core→driver type leaks |
| trpc | TypeScript | 0 | 0 | parseable; selected corrected-scope run |
| cobra | Go | 0 | 0 | clean; injection-proven |
| bubbletea | Go | 0 | 0 | clean; injection-proven |
| gin | Go | 0 | 0 | clean; injection-proven |
| fluentvalidation | .NET | 7 | 1 | 1 D001 defect, 1 G001 tooling false positive, 5 valid public API |
| serilog | .NET | 0 | 0 | clean; injection-proven |
| spectre-console | .NET | 53 | 89 | 21 D009 + 4 probable D001 defects, 3 duplicates, 25 valid API items |
| jsoup | Java | blocked | — | no enforcer |
| gson | Java | blocked | — | no enforcer |
| mall | Java | blocked | — | no enforcer |

## tRPC scope correction

The raw tRPC run is valid JSON but reports 105 `ACIMA-G005` findings. Every path
is under `tooling/`, `scripts/`, `packages/tests/`, or `packages/upgrade/`, or is one of the two root Vitest configs.
Those are assessment-scope exclusions, not product defects. The original config
listed `packages/tests` and `packages/upgrade` as directory strings; the
TypeScript enforcer's non-glob exclusion only matches an exact path or a path
segment, so those multi-segment directory patterns did not match.

The selected run uses `/**` globs (plus `tooling/**`, `scripts/**`, `next/**`,
and the root Vitest configs) and reports 0 findings over 390 files. The raw
105-finding output is preserved in `runs/typescript/trpc/raw/` and is classified
as `scope_configuration_false_positive`, not as a product defect.

This is an adoption-configuration finding, not a claim that the raw output was
correct.

## Evidence map

- [`aggregate/EXECUTIVE-REPORT.md`](aggregate/EXECUTIVE-REPORT.md) — verdict and remaining blockers.
- [`aggregate/scorecards.md`](aggregate/scorecards.md) — updated skill and standard scorecards.
- [`aggregate/portfolio.md`](aggregate/portfolio.md) — per-repository table and notes.
- [`aggregate/portfolio.json`](aggregate/portfolio.json) — machine-readable run rows and totals.
- [`ground-truth/classifications.json`](ground-truth/classifications.json) — per-rule adjudications.
- [`aggregate/run-manifest.json`](aggregate/run-manifest.json) — toolchains, enforcer hashes, commands and source roots.
- `configs/` — exact ACIMA configs used for the selected runs.
- `runs/` — enforcer stdout, stderr and exit status for every repository; Java has a blocked record.

## Method and limits

The source commits are the same pinned commits used by `rw-2026-11-08-01`.
Upstream trees are clean apart from untracked ACIMA configs, waivers and
assessment artifacts. No upstream source was changed.

Baseline test states were carried forward from the original run because the
source commits are unchanged; this rerun exercised the enforcer layer, not the
language test suites. Hosted GitHub Actions was not observed.

No independent reviewer was available. No production repository was modified
or adopted, and the run produced no verified product improvement. Six of the
29 rules are non-executable, and Java still has no enforcer. Read the
scorecards as a benchmark-local judgement, not a production readiness claim.
