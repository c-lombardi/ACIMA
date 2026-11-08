# Portfolio — `rw-2026-11-08-02`

Reassessment of the 15 pinned repositories from `rw-2026-11-08-01`. Twelve
repositories have valid L1 assessments. The three Java repositories remain
blocked.

`Source files` below is the repository production-file count from the original
portfolio. `Analyzed` is the current enforcer's reported `sourceFiles`; the
difference is mostly test and out-of-scope paths that are now correctly
excluded (Hono, Drizzle and tRPC most visibly).

| Repository | Language | Source files | Analyzed | Findings | Classified | Status |
|---|---|---:|---:|---:|---:|---|
| httpx | Python | 23 | 23 | 0 | 0 | clean, injection-proven |
| flask | Python | 24 | 24 | 0 | 0 | clean, injection-proven |
| fastapi | Python | 52 | 52 | 0 | 0 | clean, injection-proven |
| hono | TypeScript | 386 | 229 | 0 | 32 | clean after profile |
| drizzle-orm | TypeScript | 838 | 658 | 2 | 28 | 2 defects |
| trpc | TypeScript | 520 | 390 | 0 | 0 | selected corrected scope; raw 105 scope FP |
| cobra | Go | 19 | 36 | 0 | 0 | clean, injection-proven |
| bubbletea | Go | 34 | 44 | 0 | 0 | clean, injection-proven |
| gin | Go | 59 | 99 | 0 | 0 | clean, injection-proven |
| fluentvalidation | .NET | 143 | 144 | 7 | 1 | defects + profile false positive |
| serilog | .NET | 113 | 113 | 0 | 0 | clean, injection-proven |
| spectre-console | .NET | 373 | 384 | 53 | 89 | defects + valid public API |
| jsoup | Java | 102 | — | blocked | — | no enforcer |
| gson | Java | 94 | — | blocked | — | no enforcer |
| mall | Java | 519 | — | blocked | — | no enforcer |

## Totals

| Metric | Value |
|---|---:|
| Repositories | 15 |
| Assessed | 12 |
| Blocked | 3 |
| Valid JSON assessments | 12 / 12 |
| Repository production files | 3,299 |
| Analyzed source files | 2,196 |
| Repository production LOC | 707,739 |
| Supported-language LOC | 592,680 |
| Unclassified findings | 62 |
| Classified findings | 150 |
| Confirmed true positives | 24 |
| Probable true positives | 4 |
| Confirmed or probable | 28 |
| Duplicates | 3 |
| Valid architectural choices still unclassified | 30 |
| False positives | 1 |
| Actionable yield | 45.2% |
| False-positive rate | 1.6% |
| Duplicate rate | 4.8% |
| Valid-choice rate, unclassified queue | 48.4% |
| Classified share of all detections | 70.8% |
| Portable / total rules | 23 / 29 |
| Zero-finding repositories | 9 |
| Zero-finding repositories injection-proven | 8 |

## Repository notes

### httpx, flask, fastapi, cobra, bubbletea, gin, serilog

All reported zero unclassified findings and are injection-proven for L001 and
D001 with disposable fixtures. FastAPI's old `sqlalchemy_safe` L001 false
positive is gone. These results do **not** mean the repositories have no
architecture problems; only the executed rules were exercised.

### hono

The old benchmark's zero was `insufficient_evidence` because adapter units
resolved to zero edges. With the library profile and package mapping, the
current run detects 25 adapter `D001` edges and 7 `L003` public-API items, all
classified with owner and reason. The unclassified result is 0. Hono is also
L001/D001 injection-proven.

### drizzle-orm

Two `L001` findings remain in core code:

- `drizzle-orm/src/mysql-core/db.ts` imports `ResultSetHeader` from `mysql2/promise`.
- `drizzle-orm/src/singlestore-core/db.ts` imports the same driver type.

These are genuine core→driver type leaks. The other 28 `L001` detections are
driver/migration-CLI integrations and are classified as intentional adapters.

### trpc

The raw output is valid JSON: 105 `G005` findings over 396 reported files. All
105 paths are under `tooling/`, `scripts/`, `packages/tests/`, or
`packages/upgrade/`, or are the two root Vitest configs. The original config's directory strings did not match under
the TypeScript enforcer, so out-of-scope files were admitted.

The selected run adds `tooling/**`, `scripts/**`, `packages/tests/**`,
`packages/upgrade/**`, `next/**`, and the root Vitest configs to the excludes.
It reports 0 findings over 390 files. The raw run is preserved and classified
as a configuration false positive, not as a product defect. tRPC has no
injection proof in this run.

### fluentvalidation

Seven unclassified findings:

- 1 `D001` true positive: the DependencyInjectionExtensions assembly references
  the implementation assembly and there is no contracts assembly.
- 1 `G001` false positive: the library profile is rejected because `PackageId`
  is inherited from shared build props instead of declared in the `.csproj`.
- 5 `L003` valid public-API items remain unclassified because that profile
  rejection prevents the classifier from applying.
- 1 additional `L003` item is classified.

### spectre-console

Fifty-three unclassified findings:

- 21 `D009` true positives: ANSI/JSON assemblies reference internal console
  types such as `StringBuffer`, `Constants`, `ColorTable` and `DecorationTable`.
- 4 `D001` probable true positives: extension/testing projects reference the
  core implementation assembly rather than a contracts assembly.
- 3 `D008` duplicates derived from those same project references.
- 25 `L003` valid public-API items.
- 89 further `L003` items are classified by the console library profile.

The previous D005 analyzer-reference false cycles are gone. D008 is still
duplicate noise, but it is no longer reported as an independent false positive.

## Original comparison

| Metric | Original | Rerun |
|---|---:|---:|
| Valid JSON assessments | 11 / 12 | 12 / 12 |
| Unclassified findings | 120 | 62 |
| Confirmed/probable defects | 26 | 28 |
| Duplicates | 6 | 3 |
| Valid choices, unclassified | 84 | 30 |
| Classified valid edges | 0 | 150 |
| False positives | 4 | 1 |
| Actionable yield | 21.7% | 45.2% |

The unclassified queue fell 48.3%. False positives fell 75%, and unclassified
valid-choice noise fell 64.3%. Those improvements are offset by the remaining
Java gap, six non-executable rules, 30 unclassified valid choices, and the
absence of an independent review or production adoption.

## Baseline tests

Baseline test states are carried forward from `rw-2026-11-08-01`. The source
commits are identical, and this rerun was scoped to the remediated enforcer
layer. Baseline tests were not re-executed in this run.
