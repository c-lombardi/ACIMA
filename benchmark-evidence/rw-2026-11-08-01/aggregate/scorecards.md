# Scorecards — ACIMA and adoption skill

Judgement scores are 1–10, anchored to this benchmark. They are not statistical estimates or certifications. Critical failures remain visible below regardless of averages.

## Adoption skill effectiveness

| Dimension | Score | Evidence |
|---|---:|---|
| Architectural discovery | 4 | Auto-drafts were useful but wrong for Go test scope and collapsed separate .NET/TypeScript packages; human correction was required. |
| Boundary identification | 4 | FluentValidation's DI/core edge was hidden by a same-module map; Hono adapters returned zero even after separation. |
| Finding precision | 4 | Four clear false positives, plus 84 valid library-design findings. |
| Finding recall | 3 | Six rules never execute; Hono zero is a probable false negative; Java has no enforcer; tRPC has no parseable result. |
| False-positive avoidance | 4 | D005 traverses analyzer-only references; L001 matches a parameter name and product adapters. |
| Adoption planning | 4 | Plans correctly stop for ownership, but none produced a validated green adoption. |
| Implementation quality | 3 | Only a configuration/gate slice was possible; it correctly failed on eight baseline findings. No product code improved. |
| Verification quality | 4 | Tests and fingerprints were captured, but 64 KiB truncation and invalid JSON were not caught by the pipeline. |
| Human oversight | 8 | No production code changed without an owner; the stop was correct. |
| Efficiency | 4 | Large installs, toolchain setup and reruns dominated; cost/tokens unavailable. |
| Repeatability | 6 | SHAs, configs, logs and scripts exist; `/tmp` is not durable and setup is heavy. |
| Transparency about limits | 7 | Unsupported rules and Java are explicit; the initial false green was found only after a sensitivity check. |

**Skill average: 4.6/10.**

## ACIMA standard effectiveness

| Dimension | Score | Evidence |
|---|---:|---|
| Specification clarity | 7 | Principles are understandable; library/contracts semantics remain under-specified. |
| Rule applicability | 4 | L001/D001/L003 do not distinguish product infrastructure, public library API, or intentional adapters. |
| Language support | 5 | Python, TypeScript, Go and .NET have enforcers; Java has none. |
| Enforcement reliability | 4 | tRPC truncates at 65,536 bytes; Spectre D005 false cycles; Hono zero is unverified. |
| Semantic coverage | 4 | Six of 29 rules are marked non-executable; import/name matching creates false positives. |
| Legitimate architecture flexibility | 3 | Public library surfaces and analyzer references are treated as violations. |
| Brownfield adoption friction | 5 | Unit mapping is workable but fragile; no owner workflow was exercised end to end. |
| Actionability of findings | 4 | Fingerprints/paths are useful; severity and remediation context are thin. |
| Developer experience | 5 | JSON output and CI wiring are simple; invalid output and hand-built unit maps are not. |
| CI integration | 4 | A gate can be wired, but it was not run on hosted CI and was not green. |
| AI-agent compatibility | 4 | The agent needed repeated correction of module semantics and did not validate JSON. |
| Governance and exception management | 7 | Fingerprints and owner requirements are sound; no approved exception was created. |

**Standard average: 4.7/10.**

## Critical failures

1. No Java enforcement exists.
2. tRPC produced no usable assessment because stdout is capped at 65,536 bytes.
3. FastAPI's only finding is a substring false positive (`sqlalchemy_safe`).
4. Spectre's D005 cycles are analyzer-reference artifacts.
5. The benchmark produced no verified architectural improvement.
