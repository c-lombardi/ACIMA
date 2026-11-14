# Language profiles

ACIMA is one standard with five expressions. A rule means the same thing everywhere; *how* it is
enforced depends on what the language and its ecosystem give you.

| Language | Profile | Reference enforcer | Compiler-enforced boundary? |
|---|---|---|---|
| C# / .NET 8 | [dotnet.md](dotnet.md) | `tools/Acima.ArchTests` + `--verify` | partly — separate projects, `internal`, `PrivateAssets` |
| TypeScript 5 / Node 22+ | [typescript.md](typescript.md) | `tools/acima-arch.mjs` + `npm test` | partly — `exports` maps, `no-restricted-imports` |
| Python 3.12 | [python.md](python.md) | `tools/acima_arch.py` + `pytest` | no — the test is the boundary |
| Go 1.23 | [go.md](go.md) | `tools/archtest` + `go test ./...` | yes — `internal/` |
| Java 21 | [java.md](java.md) | not included yet — profile only | yes — JPMS `exports` if used |

## Coverage matrix

Python executes **42** automated rules, TypeScript 41, Go 27 and .NET 42, all with the same ids and
finding format. Fourteen rules are **manual in every profile**:

| Rule | Why not portable | Where it is covered |
|---|---|---|
| `C003` behaviour in contracts | whether a method contains business logic, IO or orchestration needs semantic analysis | Roslyn / ArchUnit / ESLint analyzers |
| `C007` constructor validation | requires judging whether a guard clause is present and correct | native analyzers, property-based tests |
| `C008` business behaviour visibility | requires judging whether an operation's outcome, preconditions, failures and effects are visible | contract/implementation review |
| `A010` effect ownership | requires identifying the owner and execution boundary from design intent | effect-ownership review; chapter 6 |
| `A011` effect semantics | retry, duplicate, consistency and cancellation semantics are not decidable from syntax | contract and failure-path review |
| `A012` outcome truthfulness | requires reasoning about commits, unknown outcomes and partial completion | failure-path review; tests/runbooks |
| `A013` critical-effect evidence | criticality and evidence proportionality are business judgements | test, reconciliation and operational evidence review |
| `A014` telemetry observes decisions | whether telemetry observes behaviour or replaces a business decision is a semantic judgement | observability review; chapter 6 |
| `A015` consistency ownership | consistency boundaries, guarantees and recovery intent are design decisions | consistency review; chapter 6 |
| `L004` service locator | needs framework-specific call knowledge (DI containers differ per ecosystem) | documented per language; production analyzers where available |
| `A002` cross-module config key | configuration APIs differ per ecosystem | documented per language |
| `A004` version-lock coupling | only meaningful with published packages | package manifests, reviewed at release |
| `G004` API baseline | needs a stable surface format per language | specified in [07](../standard/07-executable-governance.md); regeneration is a per-language command |
| `N003` naming clarity | responsibility, side effects, units, boolean polarity and domain consistency are semantic judgements | adoption skill review; chapter 18 |

Go executes `G006` from direct `go.mod` requirements against `approvedDependencies`, `N002` over
Go type declarations, and `A005`/`D015`; it reports the remaining fifteen automated rules
`executed: false`: the four tier rules, two explicit-input rules, `A006`, two composition rules,
`D016`, three lifecycle rules, one naming rule (`N001`) and `D017`.
.NET now executes all 42 automated rules: the five tier rules from project-level Roslyn semantic compilations,
the explicit-input rules (`D011`, `D012`) from Roslyn syntax trees, and the value, composition,
functional-capture, lifecycle and naming rules from the project-level source model. `N003` is one of
the fourteen manual rules, not an automated gap.

Each profile implements what its language can express. This table is the measured coverage of
the reference enforcers, not the coverage of the standard:

| Coverage | Python | TypeScript | Go | .NET | Java |
|---|---|---|---|---|---|
| Automated rules fired by the gallery | 42 / 42 | 41 / 42 | 27 / 42 | 42 / 42 | — |
| Manual rules executed | 0 / 14 | 0 / 14 | 0 / 14 | 0 / 14 | 0 / 14 |
| Documented gaps | fourteen manual | one automated + fourteen manual | fifteen automated + fourteen manual | fourteen manual | no enforcer |

A rule counts only when a violation fixture makes it fire **and** the resulting finding is checked by
`conformance/run.py`. Rules in the documented-gap column are still normative for that language; the
profile explains which native analyzer carries them.

## The common shape

Every profile follows the same five sections, so you can jump to the one you need:

1. **Layout** — what a module looks like as units.
2. **Compiler and toolchain enforcement** — what fails without any custom code.
3. **Architecture tests** — the executable rules, the idiomatic library, and the reference runner.
4. **Analyzers and linters** — what to add to catch violations at author time.
5. **Idioms and pitfalls** — the language-specific traps, and the ACIMA rules they violate.

## Service topology profile

Every language profile ends with a **Service topology** section that translates chapter 11 into
concrete project names, dependency rules, adapter seams and domain test gates. The profile is
checked by [`conformance/topology.py`](../../conformance/topology.py); the language sections show the
shape the runner expects and the evidence it reads.

## Adding another language

The standard is deliberately written so a new language is a profile, not a fork. See
[Adding a language](adding-a-language.md) for the exact deliverables and the conformance requirements.
