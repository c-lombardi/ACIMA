# Composition and injection validation — 1.4.0-draft.1

> **Historical record.** This report preserves the coverage measured for 1.4.0-draft.1. Catalog
> counts, manual-rule classifications and toolchain availability have since changed. Current
> coverage is in [`coverage.json`](coverage.json) and [`docs/status.md`](../docs/status.md).

This report covers `ACIMA-D013` (implicit component registration) and `ACIMA-D014` (property or
field injection). It is evidence about the reference implementation in this repository, not a claim
that an adopting application's runtime container graph has been proved.

## Coverage

| Profile | Rules executed | Rules not executed | Composition evidence |
|---|---:|---:|---|
| Python | 34 / 34 | 6 manual | `D013`, `D014` automated; controlled violations and positive fixture |
| TypeScript | 34 / 34 | 6 manual | `D013`, `D014` automated; controlled violations and positive fixture |
| Go | 25 / 34 | 9 | `A005` and `D015` already validated elsewhere; `D013`, `D014` report `executed: false` |
| .NET | 23 / 34 | 11 | catalog entries only; `D013`, `D014` report `executed: false` |
| Java | — | — | no reference enforcer; manual review only |

The six rules that remain manual across the portable profiles are `C003`, `C007`, `L004`, `A002`,
`A004` and `G004`. `L004` is the service-locator rule; `D013`/`D014` do not duplicate it.

## Controlled fixtures

- Python violations: `examples/python/violations/d013_dynamic_registration.py` and
  `d014_property_injection.py`; both fire at the expected paths.
- TypeScript violations: `examples/typescript/violations/d013_dynamic_registration.ts` and
  `d014_property_injection.ts`; both fire at the expected paths.
- Positive fixtures: `conformance/fixtures/composition/{python,typescript}` contain an explicit
  host, constructor-injected components and a framework-managed controller with constructor
  injection. Both profiles report no findings and mark both rules executed.
- Gallery totals at the time of this report: Python 47 findings / 34 rules; TypeScript 46 findings /
  34 rules. The extra findings are the existing fixture set, not new false positives.

## Commands run

```bash
python3 conformance/run.py python typescript topology tools
python3 tools/bundle_skill.py --check
python3 skills/acima-adoption/scripts/preflight.py --project .
git diff --check
```

Result: all selected profiles conform; the bundle matches its sources; preflight exits `0`; the diff
check is clean. `conformance/test_composition.py` covers the catalog metadata, both galleries, the
positive fixtures and the chapter's limits.

## What the detectors actually decide

`D013` scans only `host` units for the dynamic discovery forms named in chapter 15. It does not
decide that every component is registered, and it does not inspect a framework's runtime container.
`D014` scans Python class-field `Provide[...]`/`Inject[...]`/`Autowired[...]` annotations and
TypeScript field decorators immediately above a field declaration. It does not flag constructor
parameter decorators, and it does not see framework-specific property injection implemented through
an unqualified wrapper.

## Remaining manual checks

- Confirm every module-owned component has an explicit registration or construction expression;
  a missing registration cannot be inferred from the absence of a scan.
- Confirm a framework-managed controller/handler's activation contract and constructor dependencies,
  including that it cannot fall back to a default implementation.
- Confirm service-locator/global-provider calls are absent or justified (`L004` is a manual rule).
- Review generated components: deterministic input, checked-in/reproducible output, visible
  registrations and a boot test that asserts the edges.
- Review scans and conventions that are genuinely plugin infrastructure: name the loader, its input
  and the capabilities each plugin receives, and record an owned, scoped, expiring exception.
- For Go, .NET and Java, record manual evidence for `D013`/`D014` until a validated native analyzer
  exists. Their catalog entries are not an execution claim.

## Toolchain limitation

This environment has no Go or .NET toolchain, and no Java reference enforcer. Their catalog and
coverage entries are checked statically, but their enforcers were not compiled or executed here.
A clean Python/TypeScript run therefore cannot be extended to those profiles.
