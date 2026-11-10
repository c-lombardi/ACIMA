# Architecture families — assess compatibility, never assume it

ACIMA defines its own portable architectural requirements. The team's architecture — Clean
Architecture, Hexagonal, DDD, a modular monolith, microservices, or a mix — decides the overall
shape; it does not decide whether the ACIMA requirements are met. Your job is to assess compatibility
against the actual requirements, identify what is already satisfied, and name any adaptation or
genuine conflict — not to replace or relabel the architecture.

Read this before proposing units, and write one sentence about it into the proposal and the final
message.

## What to do in the assessment

1. **Classify the family from evidence**, not from folder names alone: project references, ports and
   adapters, bounded-context vocabulary, deployment manifests, per-service data stores.
2. **State which applicable ACIMA requirements are already satisfied**, which need adaptation and
   which are not established. A difference in implementation is not automatically a violation.
3. **Say what ACIMA requires here**, in the team's own vocabulary. Use the table below.
4. **Choose one compatibility outcome**: compatible, compatible with adaptation, incompatible or
   insufficient evidence. Name the evidence; do not treat missing evidence as incompatibility.
5. **Say what ACIMA does not decide**: deployment topology, database, transport, framework, module
   count, internal module design.
6. **Do not propose migrating to another family.** If the current family cannot express a boundary,
   say so as an ownership question for a human, not as a refactor.

| Detected family | Evidence you can cite | What ACIMA requires here | Where it is stricter |
|---|---|---|---|
| Clean Architecture | inward dependency arrows, domain project with no outward refs, use-case/interfaces layers | module ownership across the rings; contracts per module; `D001` catches one module using another's use cases or adapters | layering reduced to `L001`–`L004`; no implementation-to-implementation edges between modules |
| Hexagonal | `ports`/`adapters`, driving/driven vocabulary, interfaces owned by the application core | ports owned per module (`P1.6`); zero-dependency contracts; declared adapters classified only with profile evidence | no shared core owning everyone's ports; adapters are not a shared kernel |
| DDD | bounded contexts, aggregates, domain events, repositories as domain concepts | contexts become units with explicit contracts; commands/queries/events in contracts; immutable messages | a context that is only a package name is not a boundary; tactical DDD stays optional |
| Modular monolith | one deployable, modules or vertical slices, one database | the seams become a gate (`D001`, `L003`, `A001`–`A003`); the ratchet keeps them from decaying | no cross-module in-process transaction; configuration and static state owned per module |
| Microservices | independent deployables, per-service data, deployment manifests | service-topology profile P10–P13; per-layer, zero-reference contracts; no cross-service data access | contracts cannot reference contracts at all; boundaries must be declared as evidence |
| Library / framework / SDK | published artifact, `files`/`exports`/`PackageId`, public surface | declared public API and intentional adapters are classified with owner and reason, never hidden | an undeclared edge outside the declared paths must still fail |

## Four compatibility outcomes

These are explanatory assessment categories, not conformance levels or rule outcomes. Record one
with the evidence behind it.

1. **Compatible** — the evidence shows the applicable ACIMA requirements are satisfied.
2. **Compatible with adaptation** — the overall architecture can remain, but named boundaries or
   implementation details must change for specific requirements.
3. **Incompatible** — a fundamental architectural decision conflicts with an ACIMA requirement.
   Name the conflict; do not describe it as a difference to refactor away.
4. **Insufficient evidence** — the available information does not establish compatibility. This is
   not incompatibility; ask only the question that changes the decision, or stop without a verdict.

Never imply that every architecture can satisfy ACIMA without tradeoffs. Some families will need
adaptation, and some designs will be genuinely incompatible.

## Fit is not a family judgement

Compatibility and the adoption recommendation are separate judgements. Assess six dimensions
independently before recommending adoption:

1. **Technical compatibility** — can the language and base mode express the boundaries at all?
2. **Architectural substance** — are there real ownership boundaries, or one undifferentiated source area?
3. **Existing enforcement** — are boundary checks already configured and required, and is their execution observed?
4. **Incremental value** — what boundary guarantee would ACIMA add beyond those checks?
5. **Adoption cost** — configuration, gate, ownership, remediation, migration and maintenance work.
6. **Practical applicability** — does the operational model match the supported base profile?

A clean report is one input, never a recommendation. A small utility with no module ownership, or a
repository whose existing checks already protect the same boundary, can be `NOT_RECOMMENDED`. An
unsupported language or service topology is `NOT_SUPPORTED`. If ownership is not established, use
`INSUFFICIENT_EVIDENCE` and ask only the ownership question that changes the decision.

## How to say it

Write it as one sentence in the team's terms, for example:

> Your modules follow Clean Architecture internally; ACIMA requires the cross-module rule the rings
> do not express — `Orders` may use `Catalog.Contracts`, never `Catalog`'s application layer — and
> the gate fails a PR that breaks it.

Then name the evidence: which projects are contracts, which are implementations, which edges the
first slice changes, and which requirements are already satisfied.

## Guardrails

- **Never present ACIMA as an alternative** to the team's architecture, and never call it "DDD with
  extra steps" or "Clean Architecture enforced". ACIMA defines its own requirements; the family
  shapes the system, and compatibility is assessed against those requirements.
- **Never describe every architecture as compatible.** If a fundamental decision conflicts with a
  requirement, say `Incompatible`; if the evidence cannot decide, say `Insufficient evidence`.
- **Never suggest that adopting ACIMA requires the service-topology profile.** It is optional and
  applies only when explicitly selected.
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
  that the fourteen manual rules are unevaluated unless evidence exists, including effect ownership
  (`A010`–`A013`) and business-behaviour visibility (`C008`).
