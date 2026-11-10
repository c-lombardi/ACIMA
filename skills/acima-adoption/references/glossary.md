# Glossary

Plain-language definitions, written to be reused verbatim in onboarding material. The normative
definitions are in `docs/standard/02-vocabulary.md`; if the two disagree, the standard wins and
this file should be corrected.

**ACIMA** — Autonomous, Contract-Isolated, Immutable Modular Architecture. An architectural standard
with portable requirements for module ownership, contracts, dependency isolation, data and
configuration ownership, and controlled composition, enforced by a machine where supported.

**Architecture family** — the shape the team chose: Clean Architecture, Hexagonal (ports and
adapters), domain-driven design, a modular monolith, microservices, or a mix. ACIMA does not replace
it; compatibility is assessed against ACIMA's own requirements, some of which may require adaptation.

**Architectural standard** — a standard that defines its own checkable boundary requirements. ACIMA
is one: it decides what a conforming system must satisfy, not which overall architecture to choose.
Automated coverage varies by language; missing coverage is reported as not executed, never as a pass.

**Architecture mode** — `base` or `service-topology`, selected by `acima.config.json.mode`.
Base applies P1–P9, P14 and P15. Service topology applies P1–P9, P10–P15 and supersedes exactly P2.1
(one contracts unit per module) and P3.5 (shared-kernel allowance). The topology manifest is
evidence, not a selector. The service-topology profile is optional and applies only when explicitly
selected; the base mode remains the foundation.

**Autonomous** — a module can change, deploy and fail without requiring coordinated changes in
other modules. Depends on owning its data and configuration.

**Bounded context** — the business area inside which one model and one vocabulary are consistent.
A module should map to one; if it maps to two, the boundary is wrong.

**Contract** — the stable data and interface a module shows to the outside world. Data only: no
business logic, no database types, no clock, no framework annotations.

**Contracts unit** — the package/project containing a module's contracts. The only thing other
modules may reference.

**Dependency budget** — a declared limit on how many units a unit may depend on. Optional, but a
useful early-warning signal for a module becoming a hub.

**Enforcer** — a program or test suite that reads the repository and reports rule violations.
Never executes the product. Exits non-zero when the declared level is not met.

**Finding** — one rule violation: rule ID, severity, message, path, line, evidence.

**Greenfield** — a repository with no ACIMA config and no source files. Adopt the full shape
immediately; build the gate before the second module, and do not claim a level before its evidence
exists.

**Brownfield** — a repository with no ACIMA config and at least one existing source file. Adopt by
measuring, waiving, gating and ratcheting, starting at L1.

**Host / composition root** — the only place that wires implementations together. May reference
everything; nothing may reference it.

**Implementation unit** — everything a module keeps private: domain logic, adapters, persistence.
Other modules may not reference it.

**Immutable** — a contract member cannot change after construction. In practice: `readonly`,
`final`, frozen dataclasses, value semantics, immutable collections.

**Level (L1/L2/L3)** — the declared conformance level: Structural, Immutable, Autonomous. A
repository declares one and is measured against it.

**Module** — a business capability with one contracts surface in base mode (one per outward-facing
layer in service mode) and one or more implementation units. Owns its data, its configuration and
its vocabulary.

**Portable rule** — a rule implementable in every supported language without a language-specific
analyzer. This revision has 23; six need human or framework-specific review.

**Ratchet** — the adoption mechanism: baseline the findings, gate on new ones, reduce monotonically.

**Shared kernel** — a legacy compatibility unit of dependency-free value types (`Money`, ids).
It is not the default: each contracts project declares and owns the value types it publishes. Not
a utility library; admission is deliberately hard.

**Unit** — any declared piece of the architecture: a contracts unit, an implementation unit, the
host, or a legacy kernel. The config declares units; the enforcer classifies files by them.

**Waiver** — a recorded, owned, expiring exception to one exact finding fingerprint. Not a
suppression: it carries a person, a reason, a scope, a fingerprint, an expiry and a review date.

**Zero findings from zero files** — the canonical false pass. A run that discovers nothing exits
successfully and proves nothing; `G005` exists to make it fail.
