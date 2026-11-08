# ACIMA Architecture Model

**Status:** IN PROGRESS — internal review only
**Repository commit:** `25ed9f8c672c4e8031af7b50cc6b60b8635a0a2b`
**Normative sources:** `docs/standard/00-preface.md` through `12-library-profile.md`, `docs/rules/*`, `tools/acima-spec/rules.json`
**Review date:** 2026-11-08

This document reconstructs what ACIMA actually defines. It does not assume that an
analyzer's current behaviour is the definition, and it does not add principles to fill
gaps. Where the specification does not decide something, the gap is recorded here and in
[`ARCHITECTURE-CONSISTENCY-REPORT.md`](ARCHITECTURE-CONSISTENCY-REPORT.md).

## 1. What ACIMA is

ACIMA is a **contract-based modular architecture standard** for systems whose parts are
owned by different teams and must evolve without coordinated releases. Its core move is to
make a module's public surface a separate, deliberately minimal build unit (the contracts
unit) and make every other implementation type unreachable across the boundary.

The standard is expressed at three levels:

| Level | Artifact | Nature |
|---|---|---|
| Principles | `docs/standard/01-principles.md` | Thirteen normative principles with numbered obligations |
| Rules | `tools/acima-spec/rules.json`, `docs/rules/*` | A 29-rule enforcement catalog with severity and conformance level |
| Profiles | Chapter 11 (service topology), Chapter 12 (library/framework) | Contextual refinements that change or add requirements |

The 29-rule catalog is **not** the architecture. It is an enforcement catalog for a
subset of the architecture's obligations. Several obligations are review procedures or
runtime properties; several catalog rules exist to keep the governance mechanism honest.

## 2. Two normative modes, not one

ACIMA currently contains two related normative modes:

### 2.1 Base mode (P1–P9)

The base mode describes a **module** as the unit of ownership:

- one contracts unit per module;
- one or more implementation units per module;
- a host/composition root that knows all modules;
- an optional **legacy shared kernel** for dependency-free value types (P3.5);
- boundary crossings through commands, queries, events, provided ports or
  consumer-owned ports;
- L1–L3 conformance over the D/L/C/A/G catalog.

The base mode is the compatibility path for existing systems. Its shared-kernel allowance
is explicitly legacy, not the preferred default.

### 2.2 Service-topology mode (P10–P13)

The service profile describes a **service** as the top-level ownership envelope:

- one directory per service under `services/<Service>/`;
- one project per layer (`Api`, `Application`, `Domain`, `Infrastructure`,
  `Integrations.<Vendor>`, `Host`);
- one zero-reference contracts project per outward-facing layer;
- no contracts project on the domain layer;
- inter-service contracts named `<Source>.<Target>`;
- vendor seams named `<Service>.<Vendor>.Contracts` with adapters in
  `<Service>.<Vendor>`;
- explicit transforms at every boundary;
- twelve profile requirements, `ST-1`–`ST-12`, implemented as `ACIMA-S001`–`S012`.

The profile **refines and in two places tightens** the base standard: contracts may not
reference the shared kernel, and a service has one contracts unit per outward-facing layer
rather than one per module. Chapter 11.12 states this relationship, but there is no
machine-readable mode selector in `acima.config.json`; the topology profile uses a
separate `acima.topology.json`.

### 2.3 Consequence for interpretation

A statement such as "every module has one contracts unit" is true in base mode and false
in service mode. A statement such as "contracts may use the shared kernel" is a legacy
allowance in base mode and forbidden in the default service mode. Any reader, analyzer, or
agent that does not first establish the mode can apply the wrong obligation. This is a
material ambiguity, not a harmless documentation nuance.

## 3. Core architectural concepts

### 3.1 Unit and module

A **unit** is any boundary the build system can see: project, package, module, compilation
root, or a configured directory. Every unit has one role: `contracts`, `implementation`,
`host`, `shared-kernel`, `test` or `tooling`.

A **module** is the ownership concept: the smallest part of the system one team owns, can
change without coordinating with another team, and could in principle extract. A module
has a name, a contracts unit, one or more implementation units, its own persistence and
configuration, and a bounded context's worth of meaning.

The service profile adds a larger envelope: a **service** contains one primary module and
its layers. That means "module" and "service" are not synonyms, and the service profile
changes the granularity at which contracts are owned.

### 3.2 Contracts

A contracts unit is the complete, deliberate public surface. The seven permitted contract
kinds are command, query, event, view, value, provided port, and result/error. Contracts
must not contain entities, persistence types, framework types, or cross-module
composition.

### 3.3 Implementation, host, and composition root

The implementation contains domain model, application services, handlers, persistence,
adapters, mappers, migrations and jobs. Its public types are invisible outside the module,
and its dependency choices belong to it.

The host is the executable and delivery adapter. The composition root is the one place
where object construction and port binding happen. The host may reference everything;
modules must not know it exists.

### 3.4 Shared kernel

The shared kernel is a legacy, dependency-free value-type unit (money, currency, quantity,
strongly typed ids, occasionally `Result`). It may not reference modules, contracts or
third-party packages, and may not contain business behaviour, IO, clocks or ambient state.
It is a bounded migration allowance, not the default home for shared concepts.

### 3.5 Boundary crossings

There are exactly four permitted kinds: command dispatch, query, event publication, and
port call. Everything else — reading a table, importing a type, touching a static — is a
boundary breach. Runtime chapters add three mechanisms (synchronous port call, command
dispatch, event publication) and require explicit failure behaviour, outbox semantics for
events, consumer idempotency, process managers for cross-module workflows, and one
transaction per module.

### 3.6 Ports and transforms

A **provided port** is an interface in the provider's contracts unit; the provider
implements it. A **consumer-owned port** is an interface inside the consumer's
implementation, shaped exactly as the consumer needs; an adapter or the composition root
satisfies it. A **transform** is the pure, testable mapping at a boundary from the caller's
DTO to the callee's contract. The service profile makes transforms mandatory at every
layer boundary.

### 3.7 Ownership surfaces

ACIMA assigns ownership over:

| Surface | Owner | Normative consequence |
|---|---|---|
| Domain model and invariants | module | Only the owner decides them |
| Implementation types | module | Unreachable outside the module |
| Contracts | module/service | Complete and only public surface |
| Persistence/schema | module | No cross-module reads or writes |
| Configuration namespace | module | No cross-module keys or secrets |
| Mutable static state | module/process | No communication through it |
| Dependency versions | module | Consumers use contracts versions |
| Exceptions | named human owner | Owner, reason, scope, fingerprint, expiry, review date |

## 4. Principles and obligations

The following table records the principle, its core obligation, its enforcement mapping in
the specification, and its mode. "Enforced by" is the specification's own mapping, not a
claim that every listed rule executes.

| Principle | Core obligation | Spec enforcement | Mode |
|---|---|---|---|
| P1 Service Ownership | A module owns implementation, abstractions, dependencies, domain and data; others may not reach in | D001, D009, L003, A001, A002, A003 | Base |
| P2 Contract Isolation | One contracts unit is the complete and only public surface | D002, D006, D009, L003, G003 | Base; granularity changed by P11 |
| P3 Zero-Dependency Contracts | Contracts reference only the language core; shared kernel is legacy | D003, D004, D008, L002, C005 | Base; tightened by P12 |
| P4 Dependency Inversion | Consumers own integration abstractions; providers own promises; wiring in composition root | D002, L003, L004, G003 | Base |
| P5 Strict Dependency Boundaries | No implementation-to-implementation reference; acyclic; inward layering | D001, D005, D008, L001 | Base |
| P6 Immutable by Default | Contract state is set once and never changes | C001–C007 | Base and profile |
| P7 Independent Evolution | Modules own persistence and configuration; consumers depend on contracts versions; changes are classified | A001–A004, G004 | Base |
| P8 Executable Governance | Violations fail the build; a rule not executed is not a rule | G001–G005 and harness | Base |
| P9 Explicit Exceptions | Every departure is owned, justified, scoped, fingerprinted and dated | G001, G002 | Base |
| P10 Service-Aligned Topology | One product responsibility, one directory, one naming root per service | ST-1–ST-3, ST-7 | Service profile |
| P11 Layer Contract Independence | Every outward-facing layer owns its contracts; every boundary has a transform | ST-4, ST-6 | Service profile |
| P12 Absolute Contract Isolation | Contracts reference nothing, including the shared kernel | ST-5 | Service profile, default for new systems |
| P13 Product-Oriented Services | UI/API enforce the same workflow; domain owns core rules; deployment/vendor code stays at the edge | ST-11, ST-12 | Service profile |

The full obligation text is in the source chapters; this model deliberately does not
paraphrase obligations into weaker or stronger statements.

## 5. Dependency model

The normative matrix is in `docs/standard/04-dependency-model.md` §4.1. In summary:

| From | May reference | Must not reference |
|---|---|---|
| Own contracts | Language core only (base compatibility: kernel) | Other contracts, implementation, host |
| Implementation | Own contracts, other modules' contracts, own implementation, legacy kernel | Other implementation, host |
| Shared kernel | Nothing | Modules, contracts, third-party packages |
| Host | Anything | — |
| Test | What the tested module may reference, plus that module | Another module's implementation except through permitted test seams |

The service profile adds a layer matrix: `Api` → own contracts and `Application.Contracts`;
`Application` → own contracts, `Domain`, vendor/inter-service contracts it sends;
`Domain` → language core only; `Infrastructure` → `Domain` ports and infrastructure
libraries; `Integrations.<Vendor>` → own contracts and vendor SDK; `Host` → everything.
Cross-service references are only through `<Source>.<Target>`.

The graph is intended to be acyclic **by construction**. Contracts cannot reference
contracts, and implementations cannot reference other implementations, so cycles must be
smuggled through a forbidden edge or the kernel.

## 6. Runtime model

The runtime model is deliberately thinner than the static model:

- **Port call** — synchronous, consumer depends on provider's promise, one provider-owned
  transaction; the consumer must define failure behaviour and must not call inside its own
  transaction.
- **Command dispatch** — consumer knows provider; provider owns the transaction.
- **Event publication** — provider knows nobody; event is published in the transaction
  that produced the fact, using an outbox across processes; delivery is at-least-once and
  every consumer must be idempotent.
- **Saga/process manager** — one module owns a cross-module workflow, stores its own state,
  reacts to facts, issues commands, and carries compensations.
- **Transactions** — one module, one transaction; no write spans two modules; reads cross
  only through contracts/views; reporting uses projections.
- **Configuration** — each module reads only its own namespace; secrets follow the same
  rule; the host passes configuration in.
- **Composition root** — explicit construction order, no module singleton/global state,
  lifetime decided once in the host.

These runtime properties are mostly not in the 29-rule catalog. They are architectural
requirements that need design review, runtime tests, database grants, or operational
evidence.

## 7. Conformance and evidence model

L1 Structural, L2 Immutable, L3 Autonomous; each is a superset. The catalog's level
mapping is category-based (`D*`, `L*`, `G*` at L1; `C*` added at L2; `A*` added at L3).

A credible conformance claim requires:

1. `acima.config.json` with units and level;
2. a run on the current commit at the declared level with zero unwaived errors;
3. the JSON findings artifact;
4. a waiver report (count, owners, soonest expiry, expired count);
5. a pull-request gate that blocks on `error` findings.

Chapter 8.6 adds an escape hatch: an enforcer that cannot evaluate a rule must report it
as `info` with `"executed": false`, and a conformance claim must list unenforced rules
explicitly. This is honest reporting, but it collides with P8.1's statement that every
rule required by the level must execute. The collision is unresolved (see C-01/C-02).

The service profile has its own 12-item claim format and JSON artifact. The library profile
is optional and reports classified findings separately; it is not a waiver and does not
change the base rule set.

## 8. Evolution and governance model

- Standard versions use patch/minor/major semantics; rule ids are permanent and never
  reused.
- Contract changes are additive or breaking; breaking changes require a new version or
  event version and an updated reviewed API baseline (`G004`).
- Waivers are per finding, with a fingerprint; they expire and must be reviewed.
- A rule must ship with a violation fixture and at least one language implementation.
- A rule that cannot answer who/what/why/where is not ready to enforce.

## 9. Architecture claims

ACIMA claims, explicitly or by direct implication:

1. Contract isolation reduces accidental coupling and makes ownership structural.
2. Zero-dependency contracts make the module graph acyclic by construction and allow
   independent versioning.
3. Consumer-owned ports and a composition root allow providers and consumers to evolve
   separately.
4. Immutable contracts make messages safe to retry, replay, compare, archive and reason
   about concurrently.
5. Owned persistence and configuration make extraction to a service cheap in design terms.
6. Executable governance prevents architectural decay better than review alone.
7. Explicit, expiring, fingerprinted exceptions keep debt visible.
8. The service profile makes service and layer ownership readable from names and
   directories.
9. The same model can be applied across languages and to libraries/frameworks through
   profiles.

These are architectural claims, not measured business outcomes. The evidence for each is
assessed in [`ARCHITECTURE-VALIDATION-REPORT.md`](ARCHITECTURE-VALIDATION-REPORT.md).

## 10. What ACIMA does not define

The following are outside the current normative model or are left to profiles:

- database, transport, serialization, hosting and front-end framework choice;
- tenancy isolation, tenant identity, per-tenant schema or data residency;
- deployment topology, availability targets, SLOs or capacity;
- observability, security threat modelling, privacy or compliance;
- team topology and funding beyond the ownership expectation;
- migration sequencing beyond the brownfield ratchet and extraction recipe;
- a machine-readable way to select base mode versus service mode;
- a complete executable definition for six catalog rules;
- a way to prove runtime autonomy, as opposed to compile-time isolation.

These omissions are not automatically defects. They become defects only where ACIMA
claims applicability or conformance that depends on them, which is assessed in the
applicability and validation reports.
