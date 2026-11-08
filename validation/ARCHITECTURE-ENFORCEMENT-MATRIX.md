# Architecture → Enforcement Matrix

**Status:** IN PROGRESS — internal review only
**Purpose:** Trace every normative ACIMA obligation to the enforcement mechanism, language
coverage, regression evidence and remaining human judgment.
**Legend for implementation:** `P/T/G/N` = Python / TypeScript / Go / .NET reference
enforcer; `—` = not executed; `4` means all four execute; `M` = manual/native or no
portable rule; `S` = service-topology runner (`.NET`-shaped fixture). A rule being listed
does **not** mean it is semantically complete.

## Base principles

| Principle | Normative obligation (exact source) | Rule(s) | Implementation | Regression evidence | Human judgment? |
|---|---|---|---|---|---|
| P1.1 | A module MUST NOT require another module's implementation to be present, compiled or version-aligned to build (`P1.1`) | D001, D008 | 4 | gallery `expected.json`; `test_injected_violation` (D001) | No for direct/closure; yes for runtime coupling |
| P1.2 | Non-contract types MUST NOT be reachable outside the module (`P1.2`) | D009, L003 | 4 | gallery; `test_library_profile` (L003 public API) | Yes for language visibility semantics |
| P1.3 | No module reads/writes another's persistent state or shares a schema (`P1.3`) | A001 | 4 (static only) | gallery A001 | **Yes** for runtime grants/actual queries |
| P1.4 | No module reads another module's configuration keys (`P1.4`) | A002 | — | none | **Yes** (rule is warning and not executed) |
| P1.5 | No shared mutable static state (`P1.5`) | A003 | 4 | gallery A003 | Yes for cross-process/global state |
| P1.6 | Infrastructure abstractions belong to the using module's implementation, never a cross-module core (`P1.6`) | D002, L003 (indirect); no dedicated rule | 4 (indirect) | gallery D002/L003 | **Yes** for placement/ownership review |
| P2.1 | Exactly one contracts unit per module (`P2.1`) | none directly; `G005` only requires classification | M | `conformance/run.py` config checks; no one-contract rule | **Yes**; service mode changes granularity |
| P2.2 | Contracts contain only messages, values and provided ports (`P2.2`) | D003, D004, L002, C005 (partial) | 4 (partial) | gallery | **Yes** for the seven contract kinds |
| P2.3 | No implementation type, ORM entity, framework object or transport concern in contracts (`P2.3`) | L002, C005, D009 | 4 | gallery | Yes for framework/type classification |
| P2.4 | Implementation MUST NOT publish public types outside contracts (`P2.4`) | L003 | 4 | gallery; `test_library_profile` | Yes for public API profiles |
| P2.5 | Public contract types SHOULD be documented (`P2.5`) | G003 | 4 | gallery G003 | **Yes** to write/review docs |
| P3.1 | Contracts MUST NOT reference third-party packages (`P3.1`) | D004 | 4 | gallery | No for import/package manifests; yes for generated code |
| P3.2 | Contracts MUST NOT reference another contracts unit (`P3.2`) | D003 | 4 | gallery | No |
| P3.3 | Contracts MUST NOT reference an implementation, including its own (`P3.3`) | D002 | 4 | gallery | No |
| P3.4 | Contracts MUST NOT expose framework types (`P3.4`) | L002, C005 | 4 | gallery | Yes for framework classification |
| P3.5 | Shared kernel is legacy; new contracts MUST NOT reference it (`P3.5`) | D007; S005 in service mode | 4 (D007); S (ST-5) | gallery D007; `test_topology` | **Yes** to decide legacy vs new |
| P4.1 | Dependencies declared through constructor/initialisation; no runtime peer resolution (`P4.1`) | L004 | — | none | **Yes** (rule not executed) |
| P4.2 | Provider contracts not shaped around one consumer (`P4.2`) | G003 (docs), C007 (not executed) | partial | gallery G003; no C007 | **Yes**; no objective test |
| P4.3 | Consumer declares its own narrow port and adapts; must not demand a new provider contract (`P4.3`) | none directly | M | manual review | **Yes** |
| P4.4 | Infrastructure abstractions live in the using module, not a cross-module project (`P4.4`) | D002, L003 | 4 (indirect) | gallery | Yes for placement |
| P4.5 | Wiring happens in the composition root, not inside modules (`P4.5`) | D006 (host reference); no dedicated wiring rule | 4 (partial) | gallery D006 | **Yes** for construction review |
| P5.1 | Depend on other modules only through contracts (`P5.1`) | D001 | 4 | gallery; injection proof | No for static imports |
| P5.2 | Module graph MUST be acyclic (`P5.2`) | D005 | 4 | gallery; injection proof | No |
| P5.3 | A reference MUST NOT deliver an implementation transitively (`P5.3`) | D008 | 4 | gallery | No for graph closure |
| P5.4 | Domain/application MUST NOT depend on infrastructure/delivery (`P5.4`) | L001 | 4 (four edges) | gallery | **Yes** for unlisted edges |
| P5.5 | A module MUST NOT reference the host/composition root (`P5.5`) | D006 | 4 | gallery | No for direct host refs |
| P6.1 | No setters, mutable public fields or post-construction mutation (`P6.1`) | C001 | 4 | gallery | Yes for languages without property semantics |
| P6.2 | No mutable collection exposure; immutable/defensive copy (`P6.2`) | C002 | 4 | gallery | Yes for aliasing semantics |
| P6.3 | No business behaviour, IO, orchestration or lifecycle hooks (`P6.3`) | C003 | — | none | **Yes**; semantic judgement |
| P6.4 | No clocks, random sources, id generators or static mutable caches (`P6.4`) | C004 | 4 (denylist) | gallery | Yes for unlisted APIs |
| P6.5 | No persistence types/query abstractions (`P6.5`) | C005 | 4 (heuristic) | gallery | Yes for custom ORMs |
| P6.6 | Explicit types; no object/dynamic/any/bare maps (`P6.6`) | C006 | 4 | gallery | No for listed forms; yes for aliases |
| P6.7 | Constructible in one step; required state obvious (`P6.7`) | C007 | — | none | **Yes**; warning not executed |
| P7.1 | Own persistence: schema, tables, migrations, buckets, caches (`P7.1`) | A001 | 4 (static) | gallery | **Yes** for runtime/grants |
| P7.2 | Own configuration namespace (`P7.2`) | A002 | — | none | **Yes** |
| P7.3 | No shared mutable statics/global state (`P7.3`) | A003 | 4 | gallery | Yes for hidden globals |
| P7.4 | Consumers depend on contracts version, never implementation version (`P7.4`) | A004 | — | none | **Yes** |
| P7.5 | Classify contract changes; breaking changes reflected in version and API baseline (`P7.5`) | G004 | — | none | **Yes** |
| P7.6 | Contracts independently releasable; X.Contracts does not require X (`P7.6`) | none | M | manual release evidence needed | **Yes** |
| P8.1 | Every level rule MUST execute in CI on every change (`P8.1`) | harness; `conformance/run.py` | partial | runner enforces coverage contract, but six are explicitly non-executed | **Yes** to resolve claim |
| P8.2 | Standard finding format (`P8.2`) | harness + all enforcers | 4 | `test_cli` structured findings; runner compares JSON | No for shape; yes for extra fields |
| P8.3 | Failing test not silenced by disabling; fixed or waived (`P8.3`) | `rules` severity config; G001/G002 | partial | no dedicated test for disable/raise | **Yes** |
| P8.4 | Every module declared; unclassified source is a violation (`P8.4`) | G005 | 4 | gallery; `test_library_profile` zero source | No |
| P8.5 | Config, catalog version and waivers version controlled (`P8.5`) | none | M | repo practice | **Yes** |
| P9.1 | Waiver names rule, unit/path, exact fingerprint, owner, justification, expiry (`P9.1`) | G001 | 4 (implementation); docs conflict | `test_waiver_fingerprints` | Yes for reason quality |
| P9.2 | Expired waiver fails build (`P9.2`) | G002 | 4 | gallery/waiver tests | No |
| P9.3 | Narrow waiver; no repository-wide disabling (`P9.3`) | G001 + fingerprint | 4 | `test_waiver_fingerprints` | Yes for scope quality |
| P9.4 | Waivers reviewed on cadence (`P9.4`) | G002 (date) | partial | expiry only | **Yes** |
| P9.5 | C001–C006 waiver not longer than one minor version (`P9.5`) | none | M | none | **Yes**; unenforceable |
| P10.1 | Every service under `services/<Service>/`; projects start with `<Service>.` (`P10.1`) | S001, S003 | S | `test_topology` good/bad | Yes for product boundary |
| P10.2 | One service name per project; two for inter-service (`P10.2`) | S007 | S | `test_topology` | Yes for names |
| P10.3 | One responsibility; "and" means two services (`P10.3`) | S002 | S (README sentence) | `test_topology` | **Yes** |
| P10.4 | Deployable independently of platform (`P10.4`) | S012 | S (partial) | `test_topology` | **Yes** |
| P11.1 | Each outward-facing layer owns `<Service>.<Layer>.Contracts`, zero references (`P11.1`) | S004, S005 | S | `test_topology` | Yes for layer mapping |
| P11.2 | No contract project serves two layers; no re-export/inheritance/alias (`P11.2`) | S004 | S | `test_topology` | Yes for language-specific aliases |
| P11.3 | Caller maps its DTO to callee contract; callee does not reference caller (`P11.3`) | S006 | S | `test_topology` | Yes for semantic transform |
| P11.4 | Domain has no contracts project; crossing concepts copied (`P11.4`) | S004, S009 | S | `test_topology` | Yes |
| P11.5 | Transform pure, testable, caller-owned, no business rules (`P11.5`) | S006 (existence only) | S (partial) | `test_topology` | **Yes**; purity not checked |
| P12.1 | Contracts zero project/package/module references (`P12.1`) | S005 | S | `test_topology` bad fixture | No for declared refs |
| P12.2 | Shared kernel not referenced from contracts (`P12.2`) | S005 | S | `test_topology` | No |
| P12.3 | No serializer/ORM/DI/validation-framework attributes (`P12.3`) | S005 (refs only) | S (partial) | `test_topology` | **Yes** for attributes |
| P12.4 | Constructor/factory validation allowed; no business/IO/ambient state (`P12.4`) | C003/C004 (not executed C003) | partial | gallery C004 | **Yes** |
| P12.5 | Contracts compile alone (`P12.5`) | S005 (zero refs, not compile) | S (partial) | `test_topology` | **Yes** |
| P13.1 | UI/API enforce same states, transitions, validations, permissions, errors (`P13.1`) | S011 | S (token presence) | `test_topology` | **Yes**; semantic equivalence not checked |
| P13.2 | API domain enforces core product rules; UI is not the only enforcement (`P13.2`) | S009, S011 | S (partial) | `test_topology` | **Yes** |
| P13.3 | Deployment/vendor SDK only in adapters/host (`P13.3`) | S008, S012 | S | `test_topology` | Yes for SDK classification |
| P13.4 | Service boundary follows product outcome/scaling, not schema/framework/org chart (`P13.4`) | S002 (weak) | S (partial) | `test_topology` | **Yes** |

## Matrix-level findings

1. **No principle is completely unrepresented.** Every P1–P13 has at least one rule or
   manual evidence path. That is not the same as complete enforcement.
2. **The most important unrepresented obligations are P1.4, P4.1, P4.2, P4.3, P6.3, P6.7,
   P7.2, P7.4, P7.5, P7.6, P9.4 and P9.5.** Six of those (A002, L004, C003, C007, A004,
   G004) are catalog rules that simply do not execute; the rest have no rule at all.
3. **Several rules are intentionally redundant.** D001/D008/D009 overlap; D006 serves P4/P5;
   G001/G002 serve P8/P9. Redundancy is defensible when it catches different graph shapes,
   but it makes a raw finding count a poor measure of coverage.
4. **Indirect mapping is not enforcement.** P1.6, P4.4, P4.5 and P2.2 rely on rules that
   detect a consequence, not the obligation itself. The matrix marks them indirect.
5. **Profile rules are not portable.** S rules run through one .NET-shaped fixture; the
   prose claims language neutrality. See `LANGUAGE-SUPPORT-MATRIX.md`.
6. **A manual requirement is not a failed automated rule.** P4.2, P4.3, P7.6 and P13.4 are
   legitimate human judgments. They become defects only when the standard calls the level
   fully machine-checked or a run "conformant" without recording the manual evidence.

## Disposition by principle

| Principle | Automation status | Correct classification |
|---|---|---|
| P1 | Partial | Automated for static code; manual for config/runtime data |
| P2 | Partial | Automated for shape/leakage; manual for one-unit and contract kinds |
| P3 | Automated (base) | 4 execute; profile precedence unresolved |
| P4 | Partial | L004 missing; P4.2/P4.3 manual |
| P5 | Automated (static) | 4 execute; L001 limited |
| P6 | Partial | 5/7 execute; C003/C007 missing |
| P7 | Partial | A001/A003 execute; A002/A004/G004/P7.6 missing |
| P8 | Partial/contradictory | Harness works; the claim contract does not |
| P9 | Partial/contradictory | G001/G002 execute; fingerprint docs conflict; P9.5 manual |
| P10 | Profile only | S runner; .NET fixture |
| P11 | Profile only | S runner; purity not checked |
| P12 | Profile only | S runner; compile-alone/attributes not fully checked |
| P13 | Profile only | S runner; UI semantics not checked |
