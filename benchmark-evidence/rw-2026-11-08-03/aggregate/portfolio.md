# Portfolio — `rw-2026-11-08-03`

Mechanical rerun over the pinned 15-repository set. Twelve repositories were assessed;
the three Java repositories remain blocked. This is raw enforcer output, not a
re-adjudication.

| Repository | Language | Analyzed | Findings | Classified | Status |
|---|---|---:|---:|---:|---|
| httpx | Python | 23 | 0 | 0 | clean |
| flask | Python | 24 | 0 | 0 | clean |
| fastapi | Python | 52 | 0 | 0 | clean |
| hono | TypeScript | 229 | 0 | 32 | clean after profile |
| drizzle-orm | TypeScript | 658 | 2 | 28 | findings |
| trpc | TypeScript | 390 | 0 | 0 | corrected scope |
| cobra | Go | 36 | 0 | 0 | clean |
| bubbletea | Go | 44 | 0 | 0 | clean |
| gin | Go | 99 | 0 | 0 | clean |
| fluentvalidation | .NET | 144 | 1 | 6 | findings |
| serilog | .NET | 113 | 0 | 0 | clean |
| spectre-console | .NET | 384 | 40 | 109 | findings |
| jsoup | Java | — | blocked | — | no enforcer |
| gson | Java | — | blocked | — | no enforcer |
| mall | Java | — | blocked | — | no enforcer |

## Totals

| Metric | Value |
|---|---:|
| Repositories | 15 |
| Assessed | 12 |
| Blocked | 3 |
| Valid JSON assessments | 12 / 12 |
| Raw unclassified findings | 43 |
| Classified entries | 175 |
| Zero-finding repositories | 9 |
| Repositories with findings | 3 |
| Injection-proven in this run | 0 |

The 43 findings are **unclassified**. Do not count them as true positives or add them to
a precision/recall score without a fresh adjudication.
