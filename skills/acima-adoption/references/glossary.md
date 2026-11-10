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

**Composition boundary / host** — an explicitly designated place that constructs and wires the
modules it assembles. It may be a host, a library consumer, a public factory, a package initializer,
a framework integration point, a plugin loader or a test fixture. There may be several, and a
library or package may have no host. A host-role unit may reference everything in its scope; nothing
may reference it.

**Implementation unit** — everything a module keeps private: domain logic, adapters, persistence.
Other modules may not reference it.

**Immutable** — a contract member cannot change after construction. In practice: `readonly`,
`final`, frozen dataclasses, value semantics, immutable collections. An immutable binding prevents
rebinding; it does not by itself make a referenced mutable object immutable.

**Meaningful value** — a primitive whose exact content influences behaviour, a business or security
decision, an operational limit, an integration identity or a protocol. It needs one identifiable
immutable declaration at its highest appropriate owner, or an explicit configuration source
(`A006`). Equal literals do not make two values semantically identical.

**Semantic identity** — the meaning of a value in its domain: units, type, ownership, downstream use
and whether it must change with another value. It is not established by matching literals or names.

**Value ownership** — the boundary that genuinely decides a meaningful value's content and change
process. A source constant is code-owned; environment or deployment values belong to the host;
runtime configuration needs validation, authorization, audit and rollback; secrets never become
ordinary constants.

**Level (L1/L2/L3)** — the declared conformance level: Structural, Immutable, Autonomous. A
repository declares one and is measured against it.

**Module** — an identifiable architectural ownership boundary. It owns its implementation, state and
data, exposes explicit contracts, controls access to its implementation, declares its dependencies,
participates in composition and has identifiable lifecycle and effect responsibilities. It may be
represented by one or more implementation units, but it is not defined by a project, package,
directory, service, deployment unit or runtime process.

**Portable rule** — a rule implementable in every supported language without a language-specific
analyzer. This revision has 23; six need human or framework-specific review.

**Ratchet** — the adoption mechanism: baseline the findings, gate on new ones, reduce monotonically.

**Shared kernel** — a legacy compatibility unit of dependency-free value types (`Money`, ids).
It is not the default: each contracts project declares and owns the value types it publishes. Not
a utility library; admission is deliberately hard.

**Unit** — an artifact representation the build or repository can identify: a contracts unit, an
implementation unit, a composition-boundary (`host`) unit, a test unit, tooling or a legacy kernel.
The config declares units; the enforcer classifies files by them. A module may span several units.

**Waiver** — a recorded, owned, expiring exception to one exact finding fingerprint. Not a
suppression: it carries a person, a reason, a scope, a fingerprint, an expiry and a review date.

**Zero findings from zero files** — the canonical false pass. A run that discovers nothing exits
successfully and proves nothing; `G005` exists to make it fail.
