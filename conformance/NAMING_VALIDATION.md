# Intent-revealing naming validation — 1.7.0-draft.1

> **Historical record.** This report preserves the coverage measured for 1.7.0-draft.1. Catalog
> counts, manual-rule classifications and toolchain availability have since changed. Current
> coverage is in [`coverage.json`](coverage.json) and [`docs/status.md`](../docs/status.md).

This report records what the 1.7.0 naming work proves and what it does not. It is a validation
record, not a conformance certificate for any consumer repository.

## Scope

The catalog adds `N001`–`N003` and now contains 48 rules: 41 automated candidates and 7 manual
rules. Python and TypeScript execute all 41 portable rules. Go and .NET carry all 48 catalog entries
and report 19 `executed: false`; Java has no reference enforcer.

| Rule | Kind | What the reference profiles decide |
|---|---|---|
| `ACIMA-N001` | automated candidate | Python class declarations and TypeScript `class`/`interface`/`type`/`enum` declarations use `PascalCase`. |
| `ACIMA-N002` | automated candidate | A type declaration is named with an exact placeholder or generic suffix. |
| `ACIMA-N003` | manual | Responsibility, side effects, boolean polarity, units, abbreviations, domain terminology and contextual clarity. |

`N001` and `N002` are deliberately conservative. They are convention checks that prompt review;
they do not establish that a name communicates intent. `N003` is the semantic review and is never
reported as scanner output.

## Checks run

| Check | Result |
|---|---|
| `python conformance/test_naming.py` | 5/5 pass |
| Python gallery | clean tree; 41 rules / 54 findings |
| TypeScript gallery | clean tree; 41 rules / 53 findings |
| Python naming fixture | zero findings; `N001` and `N002` executed, `N003` `executed: false` |
| TypeScript naming fixture | zero findings; `N001` and `N002` executed, `N003` `executed: false` |
| Catalog claim model | 48 total, 41 portable, 7 manual; naming tests assert the counts |

Controlled violations:

- `examples/python/violations/naming_conventions.py`
- `examples/typescript/violations/naming_conventions.ts`

Each gallery makes `N001` and `N002` fire at exactly that path. Positive fixtures live in
`conformance/fixtures/naming/{python,typescript}` and cover idiomatic type declarations, a focused
responsibility, a positive boolean and unit-bearing names.

## False-positive controls

- Casing is checked only on supported type declarations, not on every identifier.
- `N002` matches exact placeholder names and generic suffixes. It does not flag a qualified name
  such as `OrderService` merely because it contains `Service`.
- Functions, methods, variables, parameters and domain terms are not parsed for semantic quality.
- Generated declarations, framework-required names and compatibility-sensitive external contracts
  can be recorded as owned exceptions; the rule is not weakened to accommodate them.
- A clean result means only that the two mechanical checks found no candidates. It does not mean the
  names are clear, consistent or idiomatic in context.

## Manual obligations

A full L3 claim requires recorded, repository-scoped manual evidence for `N003` (and for the other
six manual rules). Reviewers should record:

- the domain glossary and the terms used consistently across contracts, implementations, events
  and queries;
- evidence that boolean names express a positive condition and that negation is readable;
- units for durations, money, percentages, measurements, counts, rates and thresholds, unless the
  type or surrounding abstraction removes the ambiguity;
- the side-effect distinction between reads and mutations, including `Get`/`Find`, `Create`,
  `Save` and `GetOrCreate`;
- abbreviations retained or rejected, with their rationale;
- any generated, legacy or external name treated as an exception, with owner, scope and expiry.

The adoption skill's assessment remains read-only by default. Any rename proposal must name the
affected files and identifiers, explain what the new name makes clear, and wait for explicit
consent.

## Limits

- No static analysis proves that a name is semantically good.
- Go, .NET and Java do not execute `N001`–`N003` in this revision; their evidence is manual or
  native-analyzer output.
- The scanners do not resolve type aliases, generated code, framework conventions, public API
  compatibility constraints or cross-language domain terminology.
- No consumer repository was renamed or modified by this work.
- Hosted CI has not been observed.

Reproduce the automated evidence with:

```bash
python conformance/test_naming.py
python conformance/run.py python typescript
```
