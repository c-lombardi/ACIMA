# Architecture families — place ACIMA beside the choice, never over it

ACIMA is an enforcement standard. The team's architecture — Clean Architecture, Hexagonal, DDD, a
modular monolith, microservices, or a mix — decides the shape. Your job is to enforce the boundaries
that shape already declares, not to replace it and not to relabel it.

Read this before proposing units, and write one sentence about it into the adoption plan and the
final message.

## What to do in the assessment

1. **Classify the family from evidence**, not from folder names alone: project references, ports and
   adapters, bounded-context vocabulary, deployment manifests, per-service data stores.
2. **Say what ACIMA adds here**, in the team's own vocabulary. Use the table below.
3. **Say what ACIMA does not decide**: deployment topology, database, transport, framework, module
   count, internal module design.
4. **Do not propose migrating to another family.** If the current family cannot express a boundary,
   say so as an ownership question for a human, not as a refactor.

| Detected family | Evidence you can cite | What ACIMA adds | Where it is stricter |
|---|---|---|---|
| Clean Architecture | inward dependency arrows, domain project with no outward refs, use-case/interfaces layers | module ownership across the rings; contracts per module; `D001` catches one module using another's use cases or adapters | layering reduced to `L001`–`L004`; no implementation-to-implementation edges between modules |
| Hexagonal | `ports`/`adapters`, driving/driven vocabulary, interfaces owned by the application core | ports owned per module (`P1.6`); zero-dependency contracts; declared adapters classified only with profile evidence | no shared core owning everyone's ports; adapters are not a shared kernel |
| DDD | bounded contexts, aggregates, domain events, repositories as domain concepts | contexts become units with explicit contracts; commands/queries/events in contracts; immutable messages | a context that is only a package name is not a boundary; tactical DDD stays optional |
| Modular monolith | one deployable, modules or vertical slices, one database | the seams become a gate (`D001`, `L003`, `A001`–`A003`); the ratchet keeps them from decaying | no cross-module in-process transaction; configuration and static state owned per module |
| Microservices | independent deployables, per-service data, deployment manifests | service-topology profile P10–P13; per-layer, zero-reference contracts; no cross-service data access | contracts cannot reference contracts at all; boundaries must be declared as evidence |
| Library / framework / SDK | published artifact, `files`/`exports`/`PackageId`, public surface | declared public API and intentional adapters are classified with owner and reason, never hidden | an undeclared edge outside the declared paths must still fail |

## How to say it

Write it as one sentence in the team's terms, for example:

> Your modules follow Clean Architecture internally; ACIMA adds the cross-module rule the rings do
> not express — `Orders` may use `Catalog.Contracts`, never `Catalog`'s application layer — and the
> gate fails a PR that breaks it.

Then name the evidence: which projects are contracts, which are implementations, which edges the
first slice changes.

## Guardrails

- **Never present ACIMA as an alternative** to the team's architecture, and never call it "DDD with
  extra steps" or "Clean Architecture enforced". The subject matter differs: the family shapes the
  system; ACIMA verifies boundary properties.
- **Never rename the team's concepts into ACIMA vocabulary in the plan.** Map them: context →
  module, port → capability interface in contracts, adapter → implementation, deployment unit →
  service.
- **Do not use a finding to argue for a different family.** A `D001` is a violated boundary, not
  evidence that a monolith should become microservices or that a clean solution should drop its
  rings. If the boundary itself is wrong, that is an ownership decision (chapter 9.4).
- **Respect the stop conditions.** A service-topology repository is `NOT SUPPORTED` in this revision
  of the skill; say so instead of applying the base unit model.
- **When ACIMA is more prescriptive than the family**, name the justification and the scope from
  `../vendor/docs/guides/architecture-families.md` §"The qualification". If the team disagrees, the
  options are an owned waiver or a standard amendment — never a silent exception.
- **A clean run is not an architecture review.** Say what the enforcer decided, what it did not, and
  that the six manual rules are unevaluated unless evidence exists.
