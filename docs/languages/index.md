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

The reference enforcers implement the same **23** portable rules with the same ids and the same
finding format, so one conformance run can compare profiles. Six rules are **not** implemented by
the portable enforcer:

| Rule | Why not portable | Where it is covered |
|---|---|---|
| `C003` public setters | a setter is only a violation at the contract surface, which needs symbol analysis | Roslyn / ArchUnit / ESLint analyzers |
| `C007` constructor validation | requires judging whether a guard clause is present and correct | native analyzers, property-based tests |
| `L004` service locator | needs framework-specific call knowledge (DI containers differ per ecosystem) | documented per language; production analyzers where available |
| `A002` cross-module config key | configuration APIs differ per ecosystem | documented per language |
| `A004` version-lock coupling | only meaningful with published packages | package manifests, reviewed at release |
| `G004` API baseline | needs a stable surface format per language | specified in [07](../standard/07-executable-governance.md); regeneration is a per-language command |

Each profile implements what its language can express. This table is the measured coverage of
the reference enforcers, not the coverage of the standard:

| Coverage | Python | TypeScript | Go | .NET | Java |
|---|---|---|---|---|---|
| Portable rules fired by the gallery | 23 / 23 | 19 / 23 | 20 / 23 | 23 / 23 | — |
| Documented gaps | none | `A001`, `A003`, `C005`, `L001` | `D009`, `G001`, `G002` | none | — |

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
concrete project names, dependency rules, adapter seams and domain test gates. The profile is manual
in this revision: the language sections describe the mechanics that a person or a future runner can
check, not a runner that already exists.

## Adding another language

The standard is deliberately written so a new language is a profile, not a fork. See
[Adding a language](adding-a-language.md) for the exact deliverables and the conformance requirements.
