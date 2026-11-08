# Portfolio metrics — ACIMA real-world benchmark

Run `rw-2026-11-08-01`. Raw data: `aggregate/portfolio.json`.

| Repository | Language | Commit | Files | LOC | Units | Findings | /1k LOC | Baseline |
|---|---|---|---:|---:|---:|---:|---:|---|
| httpx | python | `b5addb64f0` | 23 | 7,448 | 1 | 0 | 0.00 | pass-with-upstream-failure |
| flask | python | `49943b5a94` | 24 | 7,608 | 1 | 0 | 0.00 | pass |
| fastapi | python | `8f9f47de69` | 52 | 20,176 | 1 | 1 | 0.05 | pass |
| hono | typescript | `61f7c59e50` | 386 | 81,694 | 2 | 0 | 0.00 | fail-upstream |
| drizzle-orm | typescript | `eab8bedbb6` | 838 | 307,055 | 8 | 39 | 0.13 | blocked |
| trpc | typescript | `c7ae414970` | 520 | 82,373 | 6 | n/a | n/a | fail-upstream |
| cobra | go | `adbc881390` | 19 | 6,037 | 1 | 0 | 0.00 | pass |
| bubbletea | go | `67b4c7a8a2` | 34 | 4,065 | 1 | 0 | 0.00 | pass |
| gin | go | `0f09c3a9b4` | 59 | 7,044 | 1 | 0 | 0.00 | pass |
| fluentvalidation | dotnet | `a8ca6ac3e7` | 143 | 11,675 | 2 | 8 | 0.69 | pass |
| serilog | dotnet | `43105b3509` | 113 | 12,576 | 1 | 0 | 0.00 | pass |
| spectre-console | dotnet | `e8045f7c53` | 373 | 44,929 | 5 | 72 | 1.60 | pass |
| jsoup | java | `d90d57521d` | 102 | 27,722 | 1 | n/a | n/a | pass |
| gson | java | `65df6e5a99` | 94 | 18,850 | 2 | n/a | n/a | partial-fail |
| mall | java | `dcaa93b315` | 519 | 68,487 | 7 | n/a | n/a | blocked |

## Coverage

- 15 selected (3 each Python, TypeScript, Go, .NET, Java).
- 11 parseable ACIMA reports; 0 Java; tRPC unusable.
- 3,299 production files; 707,739 nonblank production LOC; 120 findings.
- Baselines: 12 complete, 1 partial (Gson), 2 blocked (Drizzle, mall).

## Interpretation

- 26 confirmed/probable defects.
- 84 valid architectural choices under the product model.
- 6 duplicates.
- 4 false positives.

The 84 valid choices are the central rule-fit problem: public library APIs and intentional database adapters are treated as boundary leaks. This is an author-labelled sample, not an independent precision estimate.

## Baseline limitations

- Drizzle: native `better-sqlite3` build failed; tests not run.
- tRPC: 1 upstream failure (`httpSubscriptionLink.memory.test.ts`, #6156); assessment unusable.
- Hono: 5 upstream declaration/JSX emit failures.
- httpx: 1 upstream async-generator warning failure.
- Gson: JPMS boot failure (`Module com.google.gson not found`).
- mall: Maven timeout at 295 seconds.
- Java: no enforcer; `executed:false` is not a pass.
