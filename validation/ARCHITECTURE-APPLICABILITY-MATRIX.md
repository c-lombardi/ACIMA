# Architecture Applicability Matrix

**Status:** IN PROGRESS — internal review only
**Question:** Can ACIMA describe and govern each architectural style without forcing the
system to abandon legitimate design choices?

## How to read this matrix

These are **evaluation scenarios**, not claims that ACIMA must prescribe every style.
"Applicable" means the model can represent the system's ownership, boundaries and
dependencies consistently. It does not mean the current enforcers can check every
obligation, and it does not mean a real repository of that style has been adopted.

Key:

- **Y** — can be represented/interpreted without changing the architecture's meaning.
- **P** — possible with stated qualifications, a profile, or human judgment.
- **N** — not representable or directly applicable.
- **?** — not tested; no evidence.

The ten criteria are those required by the mandate:

1. Apply without abandoning legitimate design.
2. Represent boundaries accurately.
3. Interpret principles consistently.
4. Accommodate valid implementation differences.
5. Prevent meaningful architectural problems.
6. Avoid unnecessary restrictions.
7. Avoid excessive exceptions.
8. Allow evolution without violating fundamentals.
9. Support consistent multi-team interpretation.
10. Represent important patterns.

## Matrix

| Scenario | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Modular monolith | Y | Y | Y | Y | Y | P | Y | Y | Y | Y | **PARTIALLY VALIDATED** |
| Microservices | P | P | P | Y | Y | P | P | Y | P | P | **PARTIALLY VALIDATED** |
| Layered application | P | P | P | P | P | P | P | P | P | P | **PARTIALLY VALIDATED** |
| Domain-driven application | P | P | Y | Y | P | P | P | Y | P | P | **PARTIALLY VALIDATED** |
| Hexagonal / ports-and-adapters | Y | Y | Y | Y | Y | P | Y | Y | Y | Y | **VALIDATED (concept)** |
| Clean architecture implementation | P | P | P | P | P | P | P | P | P | P | **PARTIALLY VALIDATED** |
| Event-driven application | P | P | P | Y | P | P | P | Y | P | P | **PARTIALLY VALIDATED** |
| Multi-tenant SaaS | N | P | N | P | P | P | N | P | N | N | **NOT SUPPORTED / NOT TESTED** |
| Full-stack application | P | P | P | P | P | P | P | P | P | P | **AMBIGUOUS** |
| Shared platform / infrastructure | P | P | P | P | P | P | P | P | P | P | **AMBIGUOUS** |
| Library / framework | P | Y | P | Y | P | P | P | Y | P | P | **PARTIALLY VALIDATED** |
| Enterprise legacy system | P | P | P | P | P | P | N | P | P | P | **PARTIALLY VALIDATED** |
| Greenfield system | Y | Y | P | Y | Y | P | Y | Y | P | Y | **PARTIALLY VALIDATED** |

## Scenario detail

### 1. Modular monolith — PARTIALLY VALIDATED

**Fit.** This is ACIMA's native case. A module with one contracts unit, one or more
implementation units, a host and a composition root maps directly onto the base model.
`D001`–`D009`, `L001`–`L003`, `C001`–`C006` and `A001`/`A003` have clear referents. The
dependency matrix is expressed in the same vocabulary as the target.

**Strengths.** Boundaries are structural, not documentary. The contracts unit is a build
boundary; implementation privacy is a real constraint; acyclicity is meaningful. The
"module that could be extracted" test is a coherent ownership discipline.

**Limits.** A monolith with a legitimate shared domain kernel must use the legacy allowance
or duplicate values. A monolith with no separate contracts projects must first introduce
them, which is a real restructuring, not a neutral measurement. The architecture has not
been validated on an application-scale monolith; the benchmark portfolio is almost entirely
libraries and frameworks.

**Verdict reason.** The conceptual mapping is strong; empirical applicability is not
established. The six unexecuted rules also prevent a full conformance claim.

### 2. Microservices — PARTIALLY VALIDATED

**Fit.** Chapter 11 supplies service envelopes, inter-service contracts, layer contracts,
transforms and vendor seams. The base model supplies module autonomy. A service can be one
deployable or several; ACIMA deliberately does not equate service with microservice.

**Strengths.** Inter-service contracts named `<Source>.<Target>` make direction and
ownership explicit. The rule that only the two named services may reference the contract
is a good guard against a shared-model service mesh. The profile forbids vendor SDKs in
domain/application.

**Limits.** The profile does not define service discovery, network failure semantics,
version negotiation, distributed tracing, deployment topology, or data consistency beyond
sagas/outbox prose. Service extraction is described as cheap in design terms, but
operational cost is acknowledged, not modelled. The topology runner is .NET-shaped and has
no multi-language proof. There is no service-to-service integration fixture.

**Verdict reason.** The ownership model is applicable; the runtime/distributed system
model is incomplete and untested.

### 3. Layered application — PARTIALLY VALIDATED

**Fit.** L001 constrains domain/application → infrastructure. The service profile's layer
matrix is more explicit. A conventional layered app can map its layers to units, with the
host as composition root.

**Limits.** ACIMA's module is an ownership boundary, not a layer. A layered app whose
"layers" are technical tiers (web, service, data) may have no team-owned modules; forcing
one contracts unit per module can be artificial. L001 is only four checkable edges; it does
not capture a full layered architecture. Base mode has no layer-contract concept; the
service profile does, but requires a service directory and naming scheme.

**Verdict reason.** Applicable after a module map exists; not a drop-in description of a
classic layered codebase.

### 4. Domain-driven application — PARTIALLY VALIDATED

**Fit.** Bounded contexts map naturally to modules; aggregates and invariants live in the
implementation; domain events are contract types; persistence ownership is P1/P7. ACIMA is
compatible with DDD without requiring CQRS or event sourcing.

**Limits.** ACIMA does not define aggregate boundaries, ubiquitous language, context maps,
or domain services. A DDD system with a legitimate shared domain model across contexts will
collide with P3/P12; the answer (duplicate or split ownership) is a design choice with real
cost. The domain layer's 100% coverage requirement in the service profile is a policy, not
a DDD requirement.

**Verdict reason.** The ownership model fits; DDD-specific modelling is outside the
standard and must be supplied by the team.

### 5. Hexagonal / ports-and-adapters — VALIDATED (concept)

**Fit.** This is the closest architectural match. Provided ports live in contracts;
consumer-owned ports live in implementation; adapters sit at the edge; the composition root
wires them; the domain has no infrastructure dependency. P4's distinction between provided
and consumer-owned ports is directly hexagonal.

**Limits.** The contracts unit is a stronger packaging constraint than most hexagonal
implementations use; a hexagonal app that exposes application services directly through a
shared "ports" package may need restructuring. The profile's per-layer contracts and
transforms are stricter than canonical hexagonal architecture. Runtime adapter behaviour is
not checked.

**Verdict reason.** The concepts map with high fidelity. This is conceptual validation, not
a real adoption.

### 6. Clean architecture implementation — PARTIALLY VALIDATED

**Fit.** Dependency inversion, inward dependencies, domain independence and use-case
boundaries are compatible. The host/composition root matches the outer layer. L001 checks
one important edge.

**Limits.** Clean architecture's "entities/use cases/interface adapters/frameworks" layers
are not ACIMA layers. ACIMA's contracts are a packaging and ownership device, not
Clean's boundary entities. A Clean codebase may have one project with folders, not
build-visible units; ACIMA would require restructuring to make each boundary a unit.

**Verdict reason.** Compatible in dependency direction, not isomorphic in structure.

### 7. Event-driven application — PARTIALLY VALIDATED

**Fit.** Events are first-class contract types; immutable, past-tense, versioned, archived;
outbox and idempotency are described; process managers own cross-module workflows;
consumers project data rather than joining. This is a coherent event model.

**Limits.** The catalog does not check outbox presence, consumer idempotency, event schema
compatibility, replay safety, poison-message handling, or broker configuration. `G004`
(API baseline) is not executed, so event evolution is not machine-checked. Event sourcing
is neither required nor evaluated. The runtime requirements are prose.

**Verdict reason.** The architecture can describe an event-driven system; enforcement and
runtime validation are partial.

### 8. Multi-tenant SaaS — NOT SUPPORTED / NOT TESTED

**Fit.** A001/A002/A003 can express per-module data and configuration ownership, which is
useful. The service profile can model a product service.

**Gaps.** ACIMA has no concept of tenant, tenant isolation, tenant-scoped schema, row-level
security, per-tenant configuration, data residency, cross-tenant reporting, or tenant
onboarding. A multi-tenant system can be modular and still leak data across tenants; none
of the rules would detect it. P13's product orientation does not define tenancy.

**Verdict reason.** This is a legitimate architectural variation that ACIMA does not
represent. It should be stated as out of scope or given a tenancy profile, not claimed as
covered.

### 9. Full-stack application — AMBIGUOUS

**Fit.** The back-end service profile, contracts, layers and API/domain rules apply.
P13.1 says UI and API must enforce the same workflow, and ST-11 checks that declared UI and
API sources mention the same states/transitions/errors.

**Gaps.** Chapter 0 excludes front-end framework choice, and ACIMA has no UI component,
state-management, client-server contract, authentication or accessibility model. ST-11 is a
token-presence check, not semantic equivalence. A UI can mention the same strings and
enforce a different workflow. The applicability claim is therefore ambiguous.

**Verdict reason.** Back-end portion is applicable; the full-stack claim is not validated.

### 10. Shared platform / infrastructure — AMBIGUOUS

**Fit.** A platform can be a module/service with a contracts surface and adapters. Its
consumers can depend on contracts. The host can own deployment and vendor SDKs.

**Gaps.** Platform code often provides cross-cutting infrastructure (logging, messaging,
identity) that looks like a shared kernel or a "Common" library. ACIMA's answer is to make
each capability a provider with a port, or to keep infrastructure in the host. That may be
reasonable, but it can force a platform team into many tiny contracts projects. There is no
platform-specific profile for shared operational concerns, versioning across many consumers,
or backwards compatibility commitments.

**Verdict reason.** Applicable with significant design interpretation; not directly
supported.

### 11. Library / framework — PARTIALLY VALIDATED

**Fit.** Chapter 12 explicitly handles the two main false-positive sources: intentional
public API (`L003`) and intentional adapter dependencies (`D001`/`D009`/`L001`). It
classifies rather than deletes, keeps the findings visible, and requires publishable
evidence.

**Limits.** The profile is implemented only for TypeScript and .NET. Python and Go
libraries have no profile; a Python library with a public API will be told its public types
are leaks. The profile's `publicApi` declaration is path-scoped but can still be incomplete;
it does not prove the declared surface matches the package's actual exports. The benchmark
shows 30 valid library/API choices still unclassified and FluentValidation's profile
rejected by tooling.

**Verdict reason.** The architecture has a credible library story; its portable
implementation is incomplete.

### 12. Enterprise legacy system — PARTIALLY VALIDATED

**Fit.** The shared kernel, waivers, brownfield ratchet, extraction recipe and
"measure, freeze, ratchet" adoption model are designed for this case. A001/A002/A003 can
surface the most damaging shared-state couplings.

**Limits.** There is no formal legacy profile beyond the kernel allowance. The six
unexecuted rules include A002/A004, two of the most important for legacy autonomy. The
waiver model's expiry is a date, not a migration plan; P9.5 is unenforceable. Large
monorepos require per-context config roots, which the skill recommends but the standard
does not define. There is no application-scale legacy adoption evidence.

**Verdict reason.** The architecture acknowledges legacy reality, but the path is not
validated end to end.

### 13. Greenfield system — PARTIALLY VALIDATED

**Fit.** The service profile is explicitly the default for new systems. The day-zero
sequence (contracts → implementation → host → config → empty waiver file → CI gate) is
coherent, and the per-layer contracts avoid the shared-DTO problem.

**Limits.** Greenfield is the least evidenced case. No greenfield application was built
and operated under ACIMA in this repository. The profile runner is .NET-specific, and the
six base rules still do not execute. "Default for new systems" is a claim about intended
use, not an observed outcome.

**Verdict reason.** Architecturally coherent; empirically untested.

## Cross-cutting conclusions

1. **Strongest fit:** modular monolith, hexagonal/ports-and-adapters, greenfield service
   back ends.
2. **Credible but incomplete:** microservices, event-driven, DDD, layered, Clean, libraries,
   enterprise legacy.
3. **Not supported:** multi-tenant SaaS, full-stack semantics, shared platform operations.
4. **Recurring cause of non-applicability:** ACIMA models ownership and static dependency
   direction well, but does not model tenancy, runtime/operational behaviour, UI semantics,
   or service discovery/deployment.
5. **Do not classify every variation as a defect.** A multi-tenant system or a UI-heavy
   product is not "wrong" for failing ACIMA; ACIMA simply lacks the vocabulary. The correct
   disposition is an explicit scope limitation or a new profile.
