# Executive report — ACIMA real-world benchmark rerun

**Run:** `rw-2026-11-08-02`
**Verdict:** **Experimental, materially improved, not production-ready.**

## Bottom line

The remediated enforcers fixed the benchmark's most damaging tool failures.
All 12 supported repositories now return valid JSON; tRPC is no longer
truncated; FastAPI's substring false positive and Spectre's analyzer-cycle
false positives are gone; and Hono's adapter blind spot is resolved. Eight
zero-finding repositories are injection-proven for L001 and D001.

The unclassified queue is 62 findings, down from 120. Of those, 28 are
confirmed or probable defects, 3 are duplicates, 30 are valid architectural
choices, and 1 is a tooling false positive. Actionable yield is 45.2%, up from
21.7%. Another 150 valid architecture edges are now explicitly classified
rather than reported as defects.

That is a real improvement, but it is not a clean bill of health. Java still
has no enforcer, six rules do not execute, FluentValidation's library profile
is rejected by a tooling check, 30 valid choices remain unclassified, and
there is still no independent review or production adoption.

## What improved

1. **Assessment validity.** 12/12 supported repositories produced valid,
   non-truncated JSON. The old run had 11 valid assessments; tRPC was truncated
   at 65,536 bytes.
2. **Hono boundary visibility.** The previous zero was unverified. The current
   profile detects 25 adapter edges and 7 public-API items, all classified.
3. **False positives.** FastAPI's L001 identifier false positive is removed;
   Spectre's D005 analyzer cycles are gone. The remaining false positive is
   FluentValidation's `G001` profile rejection.
4. **Library profiles.** 150 legitimate edges across Hono, Drizzle and Spectre
   are now classified with owner and reason instead of being counted as
   defects.
5. **Queue quality.** Unclassified findings fell from 120 to 62; actionable
   yield rose from 21.7% to 45.2%.
6. **Repeatability.** This run publishes exact configs, raw outputs, commands,
   toolchain versions, enforcer hashes, and per-rule adjudications.

## What still blocks adoption

1. **Java is not supported.** jsoup, gson and mall are blocked, not passed.
2. **Six of 29 rules are non-executable.** The standard still cannot claim
   complete coverage.
3. **Library profiles are not dependable.** FluentValidation's profile is
   rejected because its `PackageId` is inherited; 5 valid public-API findings
   therefore remain unclassified.
4. **Configuration scope is fragile.** tRPC's original directory excludes did
   not match, admitting 105 out-of-scope files. The corrected run is clean, but
   the failure mode is easy to repeat.
5. **The remaining .NET queue is noisy.** 30 valid public-API choices remain
   unclassified, alongside the real D001/D009 defects.
6. **Evidence is still author-adjudicated.** No independent reviewer ran the
   benchmark; no upstream owner approved an adoption; no product code improved.

## Scorecards

| Scorecard | Prior | Updated | Interpretation |
|---|---:|---:|---|
| Adoption skill | 4.6 | **5.3** | Better verification, recall and repeatability; planning and implementation still weak. |
| ACIMA standard | 4.7 | **5.3** | Better applicability and reliability; Java, rule coverage and profile portability remain major gaps. |

Both scores are benchmark-local judgements, not certifications. A 0.6–0.7
point move is directionally meaningful, but the decimal is not a precision
claim.

## Recommendation

Use ACIMA in **advisory/pilot** mode only: run it for architectural drift
signals, keep findings human-triaged, and do not make it a required merge gate
yet. Before production adoption:

1. add a Java enforcer or explicitly exclude Java from the supported matrix;
2. make library-profile validation recognize inherited package metadata;
3. fix directory/prefix exclusion semantics and add regression tests;
4. classify or waive the remaining 30 valid public-API choices;
5. obtain an independent review of the classifications and a named owner for
   at least one real repository;
6. execute the six non-portable rules or narrow the standard's L1 claims.

## Evidence

- [`portfolio.md`](portfolio.md) — per-repository results and comparison.
- [`scorecards.md`](scorecards.md) — full dimension-level scoring.
- [`portfolio.json`](portfolio.json) — machine-readable rows and totals.
- [`../ground-truth/classifications.json`](../ground-truth/classifications.json) — adjudications.
- [`run-manifest.json`](run-manifest.json) — commands, hashes, toolchains.
- [`../runs/`](../runs/) — raw enforcer output and exit status.
