# 0. Preface

## 0.1 What this document is

This is the **normative specification** of ACIMA. It states obligations. Where it says a design
*MUST* or *MUST NOT* do something, a conforming repository has to satisfy it, and every such
obligation maps to at least one automated rule in the [rule catalog](../rules/index.md), or to a
manual-evidence rule where no reliable automated decision exists. A manual rule is still normative;
it is not a suggestion and it cannot be satisfied by a clean automated run.

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
| `N` | Intent-revealing naming and semantic clarity |
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
[chapter 11](11-service-topology.md) extends them with an optional service topology profile.

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
| Module autonomy | Microservice / bounded-context thinking | Extended to persistence, configuration, values, static state, lifetime and state ownership (`A001`–`A009`) |
| Layering | Clean / Hexagonal architecture | Reduced to four checkable edges (`L001`–`L004`) |

ACIMA defines its own architectural requirements. It is not a template, and it is not merely an
enforcement layer for boundaries chosen elsewhere. The requirements cover module ownership, explicit
contracts, dependency isolation and direction, data and configuration ownership, controlled
composition, and the applicable lifecycle, state and effect ownership requirements. Existing
approaches can often satisfy them, but compatibility is evaluated against the requirements
themselves, not inferred from the architecture's name.

**What ACIMA governs:**

- module ownership;
- explicit contracts;
- dependency isolation and direction;
- data and configuration ownership;
- controlled composition;
- applicable lifecycle, state and effect ownership requirements.

**What ACIMA deliberately leaves to the team:**

- the overall architecture family;
- application and system decomposition, subject to ACIMA's module requirements;
- internal module design;
- language and framework;
- database, transport and infrastructure choices;
- deployment topology;
- team and organisational structure;
- project and folder layout, except where an explicitly adopted profile requires otherwise.

Architectural freedom is not an exemption from the normative requirements. Where a design conflicts
with a requirement, the team must adapt the boundary or use the standard's normal exception process;
if neither is acceptable, ACIMA is not a fit. This division is what lets ACIMA sit beside Clean
Architecture, Hexagonal Architecture, domain-driven design, a modular monolith or microservices
without replacing or ranking them.

Where a requirement here is more prescriptive than a chosen family — contracts that cannot reference
other contracts (P3), no cross-module in-process transaction (P7), zero-dependency contracts (P3) —
the obligation is stated and justified in the chapter that introduces it, and its scope is limited to
boundaries between units and the four edges inside a unit. A departure is an owned waiver (P9), never
a silent exception. [Architecture compatibility](../guides/architecture-families.md) maps each
family to the applicable requirements and explains where adaptation may be needed.

## 0.7 How this specification is versioned

- **Patch** — clarifications, examples, wording. No rule changes.
- **Minor** — a new rule, a new conformance level, a new language profile. Existing rule ids keep
  their meaning.
- **Major** — a rule's meaning or severity changes, or a rule id is retired (retired ids are never
  reused).

A repository records the version it targets in `acima.config.json` (see
[Executable governance](07-executable-governance.md)).

## 0.8 Two architecture modes

ACIMA has one base standard and one optional profile. `acima.config.json.mode` selects which
obligations govern a repository; it is the **only** selector. `acima.topology.json` is profile
evidence, not a mode selector.

`base` is the default **mode**, not a default architecture. The `service-topology` profile is an
optional, opinionated architecture and applies only when explicitly selected; adopting ACIMA does
not select it.

| Mode | Obligations in force | Superseded base obligations |
|---|---|---|
| `base` (default when `mode` is absent) | P1–P9, P14 and P15 | — |
| `service-topology` | P1–P9, P10–P15 | P2.1 (one contracts unit per module) → P11.1/P11.2 per-layer contracts; P3.5 (shared-kernel allowance) → P12.2 zero-reference contracts |

The profile does **not** replace P1–P9 wholesale, and P14 and P15 apply in both modes. Exactly the two
named obligations are superseded; immutability, acyclic dependencies, no implementation references,
owned persistence, owned configuration, owned data and owned effects still apply.

Mode consistency is a configuration check, not a finding:

- a repository that declares `service-topology` MUST have `acima.topology.json` declaring
  `"profile": "service-topology"`;
- a repository with that manifest MUST declare `"mode": "service-topology"` in
  `acima.config.json`;
- an unknown mode, a base declaration with a topology manifest, or a service declaration without
  one is a tool failure (exit `2`), never a clean run;
- omitting `mode` is `base` for backward compatibility, but a manifest makes the declaration
  ambiguous, so it is rejected.
