# ACIMA Architecture Glossary

**Status:** IN PROGRESS — internal review only
**Purpose:** Fix the meaning of terms used in the validation reports. Definitions are
reconstructed from `docs/standard/02-vocabulary.md` and the normative chapters; where a
term is used inconsistently, that is recorded rather than smoothed over.

## Core terms

| Term | Definition | Source | Notes / ambiguity |
|---|---|---|---|
| **ACIMA** | Autonomous, Contract-Isolated, Immutable Modular Architecture: a contract-based modular standard for systems with separately owned parts that must evolve without coordinated releases. | `00-preface.md` | "Autonomous" is a design goal, not a proven runtime property. |
| **Unit** | Any boundary the build system can see: project, package, module, compilation root, or configured directory. One role per unit. | `02-vocabulary.md` §2.1 | A unit is not a module. |
| **Module** | The smallest part of the system one team owns, can change without coordinating, and could extract. Has a name, contracts unit, implementation unit(s), owned persistence/configuration, and a bounded context's worth of meaning. | `02-vocabulary.md` §2.2 | In service mode, a service contains a primary module and layers; the module/service relationship is not fully specified. |
| **Contracts unit** | The complete, deliberate public surface of a module: commands, queries, events, views, values, provided ports, results/errors. | `02-vocabulary.md` §2.3 | Base mode: one per module. Service mode: one per outward-facing layer. |
| **Implementation unit** | The private code of a module: domain model, application services, handlers, persistence, adapters, mappers, migrations, jobs. | `02-vocabulary.md` §2.4 | Public types must be unreachable outside the module. |
| **Host** | The executable/delivery adapter: process entry, HTTP endpoints, consumers, scheduled jobs, DI registration, configuration binding. | `02-vocabulary.md` §2.5 | May reference everything. |
| **Composition root** | The one place where the object graph is assembled and ports are bound to implementations. | `02-vocabulary.md` §2.5, `06-runtime-boundaries.md` §6.7 | Must live in the host; modules must not know it exists. |
| **Shared kernel** | A legacy compatibility unit for dependency-free value types that genuinely cross all boundaries. | `02-vocabulary.md` §2.6, `04` §4.5 | Forbidden in the service profile's contracts (P12). |
| **Boundary crossing** | A reference from one module to another through a permitted contract mechanism: command, query, event, or port call. | `02-vocabulary.md` §2.7 | Anything else is a boundary breach. |
| **Provided port** | An interface in the provider's contracts unit that the provider implements. A promise. | `02-vocabulary.md` §2.8 | The provider owns its shape, subject to P4.2. |
| **Consumer-owned port** | An interface inside the consumer's implementation, shaped to the consumer's need, satisfied by an adapter or the composition root. A need, not a promise. | `02-vocabulary.md` §2.8 | Must never appear in a contracts unit. |
| **Command** | An imperative instruction addressed to the owning module. | `02-vocabulary.md` §2.3, `05` §5.1 | Consumer → provider. |
| **Query** | A request for a read model; returns a view, never an entity. | `02-vocabulary.md` §2.3 | Consumer → provider. |
| **Event** | A past-tense fact published by the owner; immutable and archived/replayable. | `02-vocabulary.md` §2.3, `05` §5.6 | Provider → subscribers. |
| **View** | A read-only projection returned to a caller. | `02-vocabulary.md` §2.3 | Must be immutable. |
| **Value** | A small immutable type used by messages; declared locally or represented by primitives. | `02-vocabulary.md` §2.3, `05` §5.5 | Kernel is legacy. |
| **Result/error** | A typed outcome including expected failures the caller must handle. | `02-vocabulary.md` §2.3, `05` §5.9 | Untyped bags violate C006. |
| **Boundary transform** | A pure, testable mapping from the caller's DTO to the callee's contract, owned by the calling layer. | `02-vocabulary.md` §2.17, `11` §11.4 | Mandatory at every service/layer boundary in the profile. |
| **Service (base sense)** | A top-level product ownership envelope: one responsibility, one directory, one name, layers and contracts. | `02-vocabulary.md` §2.12, `11` §11.1 | Not an HTTP endpoint, DI registration, domain service or necessarily a microservice. |
| **Layer** | A slice inside a service facing one direction: Api, Application, Domain, Infrastructure, Integrations.<Vendor>. | `02-vocabulary.md` §2.13 | Layers are not modules and are never shared across services. |
| **Layer contract** | The DTO/port surface one layer exposes to its caller, in `<Service>.<Layer>.Contracts`, with zero references. | `02-vocabulary.md` §2.14 | Service profile only. |
| **Inter-service contract** | The message vocabulary one service sends to another, in `<Source>.<Target>`, containing data only and exactly two service names. | `02-vocabulary.md` §2.15, `11` §11.6 | Owned by source, reviewed by target. |
| **Vendor contracts / adapter** | `<Service>.<Vendor>.Contracts` declares the port and request/result types; `<Service>.<Vendor>` implements the port using the vendor SDK. | `02-vocabulary.md` §2.16, `11` §11.7 | Application/domain see only the contracts project. |
| **Waiver** | The only permitted way to depart from a MUST-level rule; shaped by rule, scope, fingerprint, owner, reason, expiry, review date, ticket. | `02-vocabulary.md` §2.9, P9.1 | See the waiver identity conflict below. |
| **Finding** | One rule violation in the standard JSON shape: rule, severity, message, path, line, optional evidence. | `02-vocabulary.md` §2.10, `07` §7.2 | Tools may add fields; they may not omit the required ones. |
| **Conformance level** | L1 Structural, L2 Immutable, L3 Autonomous; each a superset of the previous. | `02-vocabulary.md` §2.11, `08` §8.1 | Level rules are category-based, not a per-rule list. |
| **Profile** | A contextual refinement of the base standard: service topology (P10–P13) or library/framework (chapter 12). | `11`, `12` | There is no single config field that selects a mode. |
| **Classification** | A declared, reviewable library-profile decision to report an intentional adapter or public API edge separately from ordinary findings. | `12` §12.3 | Not a waiver; it does not suppress unrelated edges. |
| **Executed rule** | A rule the enforcer evaluated on the run; false must carry a reason. | `08` §8.6 | "Executed" is not defined as "all code paths were exercised". |
| **Unclassified source** | A production source file that belongs to no declared unit; `G005` error. | `04` §4.2, `08` §8.3 | Zero findings from zero files is not a pass. |
| **Architecture kind** | The skill's classification: application, modular monolith, multi-service system, library, framework, SDK, plugin system, multi-package repository, or mix. | `skills/acima-adoption/SKILL.md` | Not a normative ACIMA term; useful for adoption but not part of the standard. |
| **Greenfield** | No config and no source files. | Skill / preflight | Skill-level classification, not an architecture term. |
| **Brownfield** | No config and at least one existing source file. | Skill / preflight | Skill-level classification; stale reference currently says 10 files. |
| **Adopting** | An `acima.config.json` exists. | Skill / preflight | Skill-level classification. |

## Terms ACIMA avoids

| Avoided term | Reason | Use instead |
|---|---|---|
| "Layer" as a synonym for module | Layers are slices inside a service; modules are ownership boundaries. | Module for ownership; layer only in the service profile. |
| "Shared" as a project name | It names a hope, not an owner. | Shared kernel with constraints, or the owning module. |
| "Service" used loosely | It can mean HTTP service, DI registration, domain service, business unit. | Service only for the chapter 11 envelope; module for the contract boundary; provided port for a capability. |
| "Contract" as a synonym for interface | An interface is one kind of contract type. | Contract for the whole public surface; provided port for the interface. |
| "Common", "Core", "Utils" | Anti-patterns the kernel and contracts rules exist to bound. | The owning module, or a local value type. |

## Waiver identity: a term-level conflict

P9.1 requires **the exact finding fingerprint**. `docs/rules/autonomy.md` G001 says a unit
or path waiver without a fingerprint is rejected. But `docs/standard/07-executable-governance.md`
§7.5 says a waiver matches only when `rule` and `scope` match, and lists only owner, reason,
expires and reviewedOn as mandatory; its example has no fingerprint. The catalog summary
for G001 also omits the fingerprint.

The implementation and the skill's baseline writer use fingerprints. For the purpose of
these reports, **a waiver is finding-scoped and requires a fingerprint**. The §7.5 wording
is treated as a stale inconsistency (C-05), not as permission for broad waivers.

## Term-level conflict: contract granularity

P2.1 says every module MUST expose exactly one contracts unit. P11.1 says every
outward-facing layer MUST have its own contracts project, and P11.4 says the domain layer
must not have one. In service mode, a service therefore has multiple contracts projects.
The profile is explicitly allowed to tighten/refine the base, but the word "module" is not
redefined in chapter 11. For these reports, **contracts are one per module in base mode and
one per outward-facing layer in service mode**; the mode must be stated whenever a rule is
applied.
