# 0. Preface

## 0.1 What this document is

This is the **normative specification** of ACIMA. It states obligations. Where it says a design
*MUST* or *MUST NOT* do something, a conforming repository has to satisfy it, and every such
obligation maps to at least one machine-checkable rule in the [rule catalog](../rules/index.md).

It is written to be read by three audiences at once:

- **Engineers** who need to know where a piece of code belongs and why.
- **Reviewers** who need a shared vocabulary for rejecting a change without arguing about taste.
- **Tool authors** who need an unambiguous definition to implement, in any language.

## 0.2 Normative language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT** and **MAY** are used
as described in RFC 2119.

- **MUST / MUST NOT** — a rule. A violation is a defect and fails the build at the level that
  includes it.
- **SHOULD / SHOULD NOT** — a strong default. Deviating is allowed but requires a waiver (P9).
- **MAY** — genuinely optional.

Every rule has a stable identifier of the form `ACIMA-<category><number>`, for example `ACIMA-D001`.
Identifiers never change meaning. The categories are:

| Category | Concern |
|----------|---------|
| `D` | Dependency and structure — what may reference what |
| `L` | Layering inside a single module |
| `C` | Contract shape and immutability |
| `A` | Autonomy at runtime |
| `G` | Governance and exception hygiene |

## 0.3 Scope

ACIMA applies to any system built from more than one team-owned part that must evolve without
coordinating releases. In practice that means:

- **In scope:** modular monoliths, service-oriented back ends, and the internal structure of any
  service that has grown past one team.
- **Out of scope:** the choice of database, transport, serialization format, hosting model, or
  front-end framework. ACIMA constrains *boundaries*, not technology. Where a technology forces a
  decision (for example, a language with no enforced visibility), the language profile says how the
  same obligation is met.

ACIMA is also language-neutral in intent and **per-language in expression**. A rule is defined once,
here; how it is detected in C#, TypeScript, Python, Go or Java is defined in the
[language profiles](../languages/index.md).

## 0.4 Status

This is **Draft 1**. It is complete enough to adopt, and stable enough that the reference
implementations, analyzers and violation gallery in this repository are all built against it. It is
not yet ratified by any standards body, and no such ratification is claimed.

The original nine principles and the name ACIMA were proposed by the framework's author; this
specification is the attempt to turn them into something a build can enforce, and
[chapter 11](11-service-topology.md) extends them with a service topology profile.

## 0.5 Why a standard and not a template

A template gives you a folder layout. It cannot tell you that your `Common` project has become a
second architecture, that a contracts package quietly acquired a serializer, or that one module now
reads another module's table. Those failures are gradual, individually reasonable, and invisible in
review.

The reason ACIMA is written as obligations rather than advice is that **architecture decays one
permitted exception at a time**. A rule that cannot fail a build is a preference. Preferences lose.

## 0.6 Relationship to prior art and established architectures

ACIMA deliberately does not invent a new structural metaphor. It takes the Explicit Contract
Projects pattern as its core, and constrains the surrounding practice until the whole thing is
checkable:

| ACIMA concern | Established source | What ACIMA changes |
|---|---|---|
| Module + contracts split | [Explicit Contract Projects](https://modularmonoliths.com/patterns/explicit-contract-projects/) | Made normative, including the rule that contracts cannot reference other contracts |
| Rules as tests | NetArchTest, ArchUnit | One rule catalogue and one finding format across languages |
| Policy as data, reviewed waivers | [Purview Architests](https://purview.dev/projects/architests/) | Waivers become mandatory for *every* departure, with expiry, at L1 |
| Immutable messages | DDD value objects, functional core practice | Promoted from style to a build-blocking rule (`C001`–`C007`) |
| Module autonomy | Microservice / bounded-context thinking | Extended to persistence, configuration and static state (`A001`–`A003`) |
| Layering | Clean / Hexagonal architecture | Reduced to four checkable edges (`L001`–`L004`) |

ACIMA is an **enforcement standard, not an architecture**. Clean Architecture, Hexagonal
Architecture, domain-driven design, a modular monolith and a microservices architecture each define
how a system is shaped; ACIMA defines which boundary properties a build can verify. A team keeps its
chosen shape, declares its units and contracts, and ACIMA enforces the edges between them. The scope
in §0.3 is deliberate: boundaries, not technology and not domain methodology.

Where a requirement here is more prescriptive than a chosen family — contracts that cannot reference
other contracts (P3), no cross-module in-process transaction (P7), zero-dependency contracts (P3) —
the obligation is stated and justified in the chapter that introduces it, and its scope is limited to
boundaries between units and the four edges inside a unit. A departure is an owned waiver (P9), never
a silent exception. [Your architecture, enforced](../guides/architecture-families.md) maps each
family to the rules that enforce it.

## 0.7 How this specification is versioned

- **Patch** — clarifications, examples, wording. No rule changes.
- **Minor** — a new rule, a new conformance level, a new language profile. Existing rule ids keep
  their meaning.
- **Major** — a rule's meaning or severity changes, or a rule id is retired (retired ids are never
  reused).

A repository records the version it targets in `acima.config.json` (see
[Executable governance](07-executable-governance.md)).

## 0.8 Two architecture modes

ACIMA has one base standard and one profile. `acima.config.json.mode` selects which obligations
govern a repository; it is the **only** selector. `acima.topology.json` is profile evidence, not a
mode selector.

| Mode | Obligations in force | Superseded base obligations |
|---|---|---|
| `base` (default when `mode` is absent) | P1–P9 | — |
| `service-topology` | P1–P9 **plus** P10–P13 | P2.1 (one contracts unit per module) → P11.1/P11.2 per-layer contracts; P3.5 (shared-kernel allowance) → P12.2 zero-reference contracts |

The profile does **not** replace P1–P9 wholesale. Exactly the two named obligations are superseded;
immutability, acyclic dependencies, no implementation references, owned persistence, owned
configuration and owned data still apply.

Mode consistency is a configuration check, not a finding:

- a repository that declares `service-topology` MUST have `acima.topology.json` declaring
  `"profile": "service-topology"`;
- a repository with that manifest MUST declare `"mode": "service-topology"` in
  `acima.config.json`;
- an unknown mode, a base declaration with a topology manifest, or a service declaration without
  one is a tool failure (exit `2`), never a clean run;
- omitting `mode` is `base` for backward compatibility, but a manifest makes the declaration
  ambiguous, so it is rejected.
