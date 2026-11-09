# Lifecycle and state ownership validation — 1.6.0-draft.1

> **Historical record.** This report preserves the coverage measured for 1.6.0-draft.1. Catalog
> counts, manual-rule classifications and toolchain availability have since changed. Current
> coverage is in [`coverage.json`](coverage.json) and [`docs/status.md`](../docs/status.md).

This report covers `ACIMA-A007` (unnecessary transient lifetime), `ACIMA-A008` (captive scoped
dependency) and `ACIMA-A009` (shared mutable state without ownership). It is evidence about the
reference implementation in this repository, not a claim that an adopting application's runtime
container, thread safety, tenant isolation or resource cleanup has been proved.

## Coverage

| Profile | Rules executed | Rules not executed | Lifecycle evidence |
|---|---:|---:|---|
| Python | 39 / 39 | 6 manual | `A007`–`A009` automated; controlled violations and positive fixture |
| TypeScript | 39 / 39 | 6 manual | `A007`–`A009` automated; controlled violations and positive fixture |
| Go | 23 / 39 | 16 | catalog entries only; `A007`–`A009` report `executed: false` |
| .NET | 23 / 39 | 16 | catalog entries only; `A007`–`A009` report `executed: false` |
| Java | — | — | no reference enforcer; manual review only |

The six manual rules remain `C003`, `C007`, `L004`, `A002`, `A004` and `G004`. Go and .NET also
report the tier, explicit-input, value, composition and functional-capture rules `executed: false`;
the sixteen unexecuted rules are the thirteen from 1.5 plus `A007`–`A009`.

## Decision model

Chapter 17 defines the portable model:

| Component characteristics | Preferred lifecycle |
|---|---|
| Stateless, thread-safe service | Shared or singleton |
| Stateless service with expensive initialisation | Shared or explicitly cached |
| Request-specific state | Request or scope lifetime |
| Transaction-specific state | Transaction lifetime |
| Tenant-specific mutable state | Explicit tenant-owned lifecycle |
| Independent short-lived object identity | Transient or operation lifetime |
| Resource-owning component | Lifecycle appropriate to the resource |
| Shared mutable state | Explicitly owned and concurrency-safe |

The model is a preference with reasons, not a registration mandate. `A007` does not require sharing
a service that owns mutable state: the ownership finding (`A009`) must be resolved first.

## Controlled fixtures

### Negative fixtures

- Python: `examples/python/violations/lifecycle_registration.py`.
- TypeScript: `examples/typescript/violations/lifecycle_registration.ts`.
- Both files contain a stateless validator registered transient (`A007`), a scoped request context
  captured by a singleton service (`A008`) and a singleton price cache owning a mutable container
  (`A009`).
- Both galleries fire all three rules at exactly that path. Current totals: Python 52 findings / 39
  rules; TypeScript 51 findings / 39 rules.

### Positive fixtures

`conformance/fixtures/lifecycle/{python,typescript}` contain a host-only unit map and declare:

- a stateless validator shared at application lifetime;
- a request-scoped context and a consumer with the same scope, so no shared component captures it;
- a legitimate transient generator with independent mutable identity;
- a resource-owning client shared at application lifetime with an explicit `close()` method.

The positive fixtures produce zero findings for `A007`–`A009`, and every catalog rule is present in
the execution map. This is the false-positive half of the evidence: the detectors must not report
legitimate transient values, correct sharing or correctly scoped state.

## Brief scenario coverage

| Scenario | Evidence | Status |
|---|---|---|
| Stateless service correctly shared | positive fixture, `OrderValidator` | executable (`A007` inverse) |
| Stateless service unnecessarily transient | negative fixture | executable (`A007`) |
| Legitimate transient with independent identity | positive fixture, `IdGenerator` | executable (no finding) |
| Request-scoped state correctly isolated | positive fixture, scoped context/consumer | executable (no finding) |
| Singleton retaining a scoped dependency | negative fixture | executable (`A008`) |
| Singleton with unsafe mutable state | negative fixture | executable (`A009`) |
| Shared mutable state with explicit ownership and synchronization | chapter 17 example 17.12.6 | manual review; no automated proof |
| Tenant-specific state correctly isolated | chapter 17 §17.6 | manual review |
| Tenant-specific state accidentally shared | chapter 17 §17.6 | manual review |
| Resource-owning component with lifecycle and cleanup | positive fixture `SqlClient`; chapter 17 §17.8 | shape only; cleanup not proved |
| Resource-owning component without identifiable cleanup | chapter 17 §17.8 | manual review |
| Factory correctly managing a shorter-lived dependency | chapter 17 §17.5/§17.7; `D016` at the host | manual review for lifetime |
| Factory concealing lifecycle or dependency ownership | `D015`/`D016`; chapter 17 §17.5 | manual review for lifetime |
| Closure retaining request state beyond its lifetime | chapter 17 §17.4; `D015` | manual review |
| Background worker managing dependencies and resources | chapter 17 §17.8 | manual review |

The first six rows are the executable fixture set. The remaining rows are review requirements, not
automated coverage; the fixture suite does not claim to prove them.

## Commands run

```bash
python3 conformance/run.py python typescript topology tools
python3 conformance/test_lifecycle_ownership.py
python3 tools/bundle_skill.py
python3 tools/bundle_skill.py --check
python3 skills/acima-adoption/scripts/preflight.py --project .
git diff --check
```

Result: both portable profiles pass their clean tree, gallery and execution map; the five
lifecycle tests pass; the bundle matches its 41 sources; preflight exits `0` with `READY`; the diff
check is clean.

## What the detectors decide

- Python reads explicit host registrations through `register(... lifetime=...)`,
  `add_singleton`, `add_scoped` and `add_transient`. It builds a unique class index, then:
  `A007` fires for a transient class with no `self` field writes; `A008` fires when a shared class's
  constructor annotation names a scoped registration; `A009` fires when a shared class initialises a
  list/dict/set or other mutable container.
- TypeScript reads `register(Class, { lifetime })` and `addSingleton`/`addScoped`/`addTransient`.
  It uses the same class-body, constructor-dependency and mutable-container checks. Lifetime strings
  are read from the original source because the masking pass blanks string literals; the masked
  companion rejects matches inside comments or strings.
- The rules are **candidates**, not proofs. A class with no mutable field can still use unsafe global
  state; a mutable field can be correctly guarded; a shared registration can still be wrong for
  reasons the scanner cannot see.

## Deliberately not flagged

- ordinary transient domain entities, value objects, commands, events and job descriptors;
- immutable objects with harmless independent allocation;
- framework-required lifetimes;
- legitimate request-, transaction- or operation-scoped services;
- explicitly owned, synchronised shared state;
- resource-owning components with a documented acquisition, lifetime and cleanup path.

## Remaining manual checks

- Confirm a shared component does not retain request ids, users, tenants, transactions, cancellation
  tokens or request contexts through a factory, property, decorator, callback or module-level binding
  the scanner does not resolve.
- Confirm tenant-specific state is keyed and isolated, including fallback and failure paths.
- Confirm resource acquisition and cleanup on success, failure, cancellation and shutdown.
- Confirm shared mutable state has an owner, mutation authority, synchronization, initialization,
  eviction/expiration, failure and consistency policy.
- Confirm a process-local singleton is not described as globally consistent in a multi-replica
  deployment.
- For Go, .NET and Java, record repository-scoped manual evidence for `A007`–`A009` until a validated
  native analyzer exists.

## Generality and adversarial review

Internal review checked the model against modular monoliths, microservices, event-driven and
functional architectures, libraries, plugins, serverless, multi-tenant SaaS and applications without
a DI container. Findings:

- **Not too prescriptive.** `A007` is scoped to explicit host registrations and a class with no
  instance state; it does not require singleton registration and does not inspect ordinary
  allocations. `A008` and `A009` identify a specific retention or ownership question rather than
  banning scoped services or mutable fields.
- **Not a singleton mandate.** The chapter states the longest appropriate lifecycle, lists legitimate
  transient cases and warns that promoting a stateful service to singleton is not a correction.
- **Not redundant.** `A003` covers cross-module static state, `A009` covers mutable state owned by a
  shared component. `D013`/`D014` make construction visible; `A008` makes the lifetime compatibility
  visible. `D015`/`D016` cover captured dependencies; chapter 17 adds how long the capture lives.
- **Not framework-biased.** The decision model applies without a container; the automated rules read
  only explicit registrations where a host makes them available. Module-level singletons, package
  values and Go structs are documented as manual-review shapes.
- **Not a safety claim.** The standard explicitly says a clean scan does not prove thread safety,
  tenant isolation, resource cleanup, distributed consistency or the runtime graph.

Unresolved questions: whether a future release should add a resource-cleanup rule with native
analyzer evidence; whether framework-specific scope decorators can be modelled without privileging
one container; and whether distributed singleton behaviour should become a service-topology
requirement rather than a review note.

## Toolchain limitation

No Go or .NET toolchain and no Java reference enforcer are available in this environment. Their
catalog and coverage entries are checked statically, but those enforcers were not compiled or
executed. The Python/TypeScript result cannot be extended to them. No independent external evaluator
has reviewed this revision; the review above is internal.
