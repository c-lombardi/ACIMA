# Your architecture, enforced

ACIMA is an **architectural enforcement standard**, not an architecture. It does not ask a team to
abandon Clean Architecture, Hexagonal Architecture, domain-driven design, a modular monolith or a
microservices architecture. Those choices answer *how the system is shaped*. ACIMA answers a
different question: **which of the boundary properties that shape implies can a build verify, on
every commit, in the team's language?**

```
Your team chooses                    Clean Architecture · Hexagonal Architecture
                                     Domain-Driven Design · Modular monolith
                                     Microservices

ACIMA defines and enforces           the boundaries that choice declares:
                                     ownership, contracts, dependency direction

Language-specific enforcement        analyzers · architecture tests · CI gate
                                     · AI adoption guidance
```

Each of these is a mature practice with value independent of ACIMA. ACIMA does not rank them,
require one, or treat one as a prerequisite — it only asks that the boundaries the team already
believes in are made checkable.

The two layers compose. A team keeps the vocabulary and structure it already uses, declares its
units and contracts in `acima.config.json`, and lets the enforcer fail the build when the declared
boundary is crossed. Nothing in ACIMA requires a particular folder layout, framework, transport,
database or deployment model.

## What ACIMA enforces regardless of architecture

Every family below is subject to the same five obligations ([principles](../standard/01-principles.md)):

- a module owns its implementation and its data;
- other modules see only an explicit contracts surface;
- contracts are dependency-free leaves, so the graph is acyclic;
- persistence, configuration and static state belong to the module that uses them;
- the host is the only place that composes implementations.

Inside one module, four checkable edges (`L001`–`L004`) describe layering without prescribing a
particular ring model. Between modules, the dependency rules (`D001`–`D009`) enforce ownership. The
rules are the same whether the modules are folders, projects or services.

## If your team chose…

| Family | Valuable when | What ACIMA adds | Where ACIMA is more prescriptive |
|---|---|---|---|
| **Clean Architecture** | Domain logic is complex and must not depend on frameworks, databases or delivery. | Module ownership *across* the rings: each module has its own contracts, and `D001` stops one module reaching into another's use cases or adapters, which layering alone does not see. | It reduces layering to four checkable edges rather than mandating all rings, and it forbids implementation-to-implementation references between modules even when both sit in a "clean" layer. |
| **Hexagonal Architecture** (ports and adapters) | Many external systems, and tests need seams around them. | Ports are owned by the module that uses them (`P1.6`), contracts stay dependency-free, and adapter edges are reported rather than hidden. A declared adapter is classified only with publishable evidence (library profile), never silenced. | A single cross-module "core" that owns everyone's ports is the `Common`/`Core` failure P1 exists to prevent. Adapters may not become a shared kernel. |
| **Domain-Driven Design** | The domain is genuinely complex: aggregates, invariants, a ubiquitous language. | Bounded contexts become enforceable units, contracts carry commands, queries and events, and aggregates make immutable contract types natural (`C001`–`C007`). | A bounded context must be expressible as a unit with an explicit surface; a context that is only a package name is not a boundary. DDD's tactical patterns remain optional. |
| **Modular monolith** | One deployable, several team-owned capabilities, and a need for independent change. | This is ACIMA's home ground: it turns the seams from a folder convention into a gate (`D001`, `L003`, `A001`–`A006`), so the "modular" part does not decay. | In-process transactions across modules are forbidden even when technically possible; they are the coupling that prevents later extraction. Configuration and static state are owned per module. |
| **Microservices** | Independent deployment, scaling and ownership are the dominant constraint. | The service-topology profile (P10–P13) applies the same ownership and isolation obligations per service layer, with per-layer contracts and zero-reference contracts; `D001` becomes "no service reads another service's database". | Contracts may not reference other contracts at all, and a service boundary must be declared as evidence, not inferred from folder names. The adoption skill this revision ships does not implement the service workflow; it stops rather than forcing the base unit model. |

## Fit is not a family judgement

Before recommending adoption, assess six dimensions independently: technical compatibility,
architectural substance, existing enforcement, incremental value, adoption cost and practical
applicability. Then choose `RECOMMENDED`, `RECOMMENDED_WITH_LIMITATIONS`, `NOT_RECOMMENDED`,
`INSUFFICIENT_EVIDENCE` or `NOT_SUPPORTED`.

A clean report is one input, never a recommendation. A small utility with no meaningful ownership
boundaries, or an application whose existing boundary checks already cover the same guarantee, can
be `NOT_RECOMMENDED`. An unsupported language or service topology is `NOT_SUPPORTED`. If ownership
is not established, use `INSUFFICIENT_EVIDENCE` and ask only the question that changes the decision.
Benefits must be classified as available today, achievable through adoption, requiring additional
work, or not applicable; a proposed gate is never described as an existing capability.

## How to tell which one you are looking at

Use evidence, not the README:

- **Clean Architecture** — concentric layers, a domain project with no outward references, use-case
  and interface-adapter layers, dependency arrows pointing inward.
- **Hexagonal** — explicit `ports`/`adapters`, `driving`/`driven` vocabulary, interfaces owned next
  to the application core, adapters at the edge.
- **DDD** — bounded contexts, aggregates, repositories expressed as domain concepts, domain events,
  a ubiquitous language in names and docs.
- **Modular monolith** — a single deployable with modules or vertical slices, one database, shared
  process.
- **Microservices** — independently deployable services, per-service data stores, network contracts
  and deployment manifests.

Repositories are frequently a mix: Clean Architecture inside each service, DDD in the complex
contexts, a modular monolith for the rest. Do not force one label, and do not use ACIMA to argue for
a different family.

## What ACIMA does not decide

Deployment topology, database or transport choice, serialization, framework, folder names, the
number of modules, or whether the domain is modelled with aggregates. It also does not require a
rewrite: brownfield adoption measures the existing boundaries and ratchets.

## The qualification: ACIMA can be stricter

ACIMA's core requirements are, in specific places, **more prescriptive than the family a team
chose**. That is deliberate and acceptable only because each requirement is independently justified
and its scope is stated:

- **Contracts may not reference other contracts** — stricter than the published "no dependencies,
  ideally" guidance. Justified by acyclicity and independent versioning: one legal direction makes
  the reverse legal too, and a contracts package that references another cannot be versioned alone.
- **No cross-module in-process transaction**, even in a monolith — justified because it is invisible
  in the dependency graph and blocks extraction.
- **Non-contract types are unreachable** (`L003`, `D009`) — justified because a shared type is a
  shared release.
- **Zero-dependency contracts**, including validation and serialization packages — justified because
  the boundary must not dictate technology to every consumer.

The scope is equally explicit: ACIMA constrains **boundaries between units** and four **edges inside
a unit**. It does not prescribe the internal design of a module, and it does not claim that a clean
run means the architecture is good. When a requirement conflicts with a legitimate design, the
options are a recorded waiver with an owner and expiry, or an amendment to the standard — never a
silent exception, and never bending the code to satisfy a rule that is wrong.

If ACIMA's requirements exclude a legitimate architecture, that is a defect in the standard: see
[Contributing](../../README.md#contributing).
