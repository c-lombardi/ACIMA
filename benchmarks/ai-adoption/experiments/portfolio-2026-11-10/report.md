# Portfolio experiment — portfolio-2026-11-10

**Phase 4 (model execution) is blocked.** No agent ran, so this report contains no assessment, no score and no success claim for any repository.

## Model under test

- Provider `freebuff`, requested model `deepseek-v4.1-flash` — unverified.
- Freebuff CLI 0.2.36 exposes interactive start, `login`, `doctor`, `--continue`, `--cwd`, `--trust-agents`: no unattended prompt, no model selection flag, no structured event stream and no programmatic authentication. The harness therefore refuses to run.

## Frozen inputs

- Rubric `acima-ai-adoption-rubric` v1.0.0 — 865d7f5177d49bf2…
- Manifest — 98c3db2a91b4ca41…
- References — 15 files, combined 2de87f1693c14f66…
- Skill `1.18.0` a6f2348e5fda…, catalog `1.9.0-draft.1` 084d53a04582…

## Repository preparation

| Repository | Language | Pinned commit | Snapshot | Files | Boundaries (reference) |
|---|---|---|---|---|---|
| encode/httpx | python | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` | verified | 125 | 1 |
| pallets/flask | python | `49943b5a94413a530761350f04e896f76e8d620e` | verified | 236 | 1 |
| fastapi/fastapi | python | `8f9f47de69982705d96e4165a9f03c6537e8c9fe` | verified | 3239 | 1 |
| honojs/hono | typescript | `61f7c59e50244ab4d2dd83c151928cf7ea448510` | verified | 584 | 2 |
| drizzle-team/drizzle-orm | typescript | `eab8bedbb65d5429c54e612ddbd88aa23091d398` | verified | 1392 | 9 |
| trpc/trpc | typescript | `c7ae414970de8e8de4fb252a4e2eed2a9f41c759` | verified | 1923 | 6 |
| spf13/cobra | go | `adbc8813901bba65827259daa8e22ff94ec1f30e` | verified | 66 | 2 |
| charmbracelet/bubbletea | go | `67b4c7a8a2b34a0b1ce15261b0c705bc7e1a04b7` | verified | 233 | 2 |
| gin-gonic/gin | go | `0f09c3a9b4626d9fe9979cf4d0521d6ae32ab646` | verified | 130 | 2 |
| FluentValidation/FluentValidation | dotnet | `a8ca6ac3e7f35da9448a28e0ab84ae914cca4fb1` | verified | 296 | 3 |
| serilog/serilog | dotnet | `43105b35095337d77f022561a8f2d3db2f9a7937` | verified | 285 | 1 |
| spectreconsole/spectre.console | dotnet | `e8045f7c53c3c217a7f93f362f5256f1fadc0020` | verified | 871 | 7 |
| jhy/jsoup | java | `d90d57521d931db7bf7ee464a4c0a1a9293db088` | verified | 330 | 0 |
| google/gson | java | `65df6e5a99747f73d386f3a61d887a0257255e0f` | verified | 315 | 0 |
| macrozheng/mall | java | `dcaa93b3150352e5044708d7211b5bed0af4509f` | verified | 717 | 0 |

- Verified snapshots: 15 of 15; failures: 0.
- Each snapshot is acquired by exact SHA, checked against `rev-parse HEAD`, and hashed; the disposable working copy is created from the snapshot when an execution happens.

## Reference availability

| Repository | Boundary truth | Finding truth | Precision/recall | Profiles |
|---|---|---|---|---|
| encode/httpx | adjudicated-unit-map | none | unavailable | base |
| pallets/flask | adjudicated-unit-map | none | unavailable | base |
| fastapi/fastapi | adjudicated-unit-map | none | unavailable | base |
| honojs/hono | adjudicated-unit-map | none | unavailable | base, library |
| drizzle-team/drizzle-orm | adjudicated-unit-map | adjudicated-rule-counts | unavailable | base, library |
| trpc/trpc | adjudicated-unit-map | none | unavailable | base |
| spf13/cobra | adjudicated-unit-map | none | unavailable | base |
| charmbracelet/bubbletea | adjudicated-unit-map | none | unavailable | base |
| gin-gonic/gin | adjudicated-unit-map | none | unavailable | base |
| FluentValidation/FluentValidation | adjudicated-unit-map | adjudicated-rule-counts | unavailable | base, library |
| serilog/serilog | adjudicated-unit-map | none | unavailable | base |
| spectreconsole/spectre.console | adjudicated-unit-map | adjudicated-rule-counts | unavailable | base, library |
| jhy/jsoup | unavailable | none | unavailable | base |
| google/gson | unavailable | none | unavailable | base |
| macrozheng/mall | unavailable | none | unavailable | base |

## What is deliberately unavailable

- Finding precision and recall for all 15 repositories: adjudication is per rule and count, not per location.
- Boundary accuracy for the three Java repositories: no unit map was adjudicated.
- Compatibility and recommendation accuracy: no reference establishes a defensible set for these repositories, and inventing one would grade the agent against a guess.
- Every assessment dimension, because no execution occurred.

## Next phase

Obtain a supported unattended provider invocation that can select the model, receive the skill by path, run in an isolated workspace and emit structured events. Then run one fresh execution per repository, evaluate each against the frozen reference, and publish the consolidated result. Nothing in this directory needs to change first: the rubric and references are already frozen and hashed.
