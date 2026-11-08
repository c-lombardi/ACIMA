# 3. Module anatomy

Every module, in every language, has the same four artifacts. Only the packaging differs.

```
<Module>.Contracts     public, immutable, zero dependencies
<Module>               private, owns domain + data + adapters
<Module>.Tests         behaviour tests (not architecture tests)
<host>                 composition root — references everything, publishes nothing
```

Plus, shared by the whole system:

```
<SharedKernel>         dependency-free value types (optional but usually justified)
<ArchTests>            the rule engine, executed by the build
```

## 3.1 What belongs where

| Concern | Belongs in | Never in |
|---------|-----------|----------|
| Aggregates, entities, invariants | implementation (`domain/`) | contracts |
| Application services, handlers, orchestration | implementation (`application/`) | contracts |
| Repositories, DB context, migrations, ORM mapping | implementation (`infrastructure/`) | contracts |
| HTTP endpoints, message consumers, schedulers | host | implementation |
| DI registration / object graph assembly | host | implementation |
| Commands, queries, events, views | contracts | implementation |
| Provided ports (what the module promises) | contracts | implementation |
| Consumer-owned ports (what this module needs) | implementation | contracts |
| Repositories over infrastructure, clocks, buses | implementation | any shared unit |
| Cross-boundary value types (Money, ids) | shared kernel | contracts of a module |

The right-hand column is the important one. **Every rule in ACIMA is ultimately a test of this
table.**

## 3.2 The shape of a module's implementation

ACIMA does not mandate a folder scheme, but it does mandate the direction of dependencies inside a
module (`L001`):

```
<Module>/
  domain/          aggregates, entities, value objects, domain events, domain policies
  application/     use cases, command/query handlers, ports (consumer-owned), transactions
  infrastructure/  database, messaging, HTTP clients, file storage, adapters
  Composition.cs|ts|py|go|java   the module's own registration function (no peer wiring)
```

- `domain/` depends on nothing except the shared kernel.
- `application/` depends on `domain/` and on its own ports.
- `infrastructure/` implements those ports and may depend on anything.
- The wiring that connects `infrastructure/` to `application/` happens either inside a module
  composition function (allowed: it is the module's own graph) or in the host. It MUST NOT be
  resolved lazily at call time (`L004`).

Layer count is not the point. What matters is that **the inner code never names an outer type**, so
the domain can be tested without a database, a broker or a web server. Three folders are enough; five
are fine; one is a design smell only if the domain is untestable.

## 3.3 The same shape in five languages

The obligations are identical. The mechanism that makes a unit private is not.

| Language | Contracts unit | Implementation unit | Enforcement mechanism |
|----------|----------------|---------------------|-----------------------|
| **C# / .NET** | `Acima.Catalog.Contracts.csproj` | `Acima.Catalog.csproj` | separate project + `<InternalsVisibleTo>` denied; `PrivateAssets="all"` stops transitive leaks |
| **TypeScript** | `src/catalog/contracts/index.ts` | `src/catalog/impl/**` | package `exports` map + path aliases + lint rule; the *only* allowed import specifier is `@acima/catalog-contracts` |
| **Python** | `acima/catalog/contracts/` | `acima/catalog/impl/` | nothing in the language; enforced entirely by the architecture test (`D001`, `D009`) |
| **Go** | `catalog/contracts` | `catalog/internal/...` | `internal/` makes the compiler refuse the import from other packages |
| **Java** | `acima.catalog.contracts` | `acima.catalog.internal` (or JPMS `exports`) | JPMS `module-info` `exports` is the only compiler-level mechanism; without it, ArchUnit enforces |

That table is the most useful thing in this chapter. Two languages give you a compiler that refuses
the wrong import (Go, Java-with-JPMS); one gives you a package manager that can refuse it
(TypeScript, .NET); one gives you nothing (Python). In every case the rules are still worth running,
because **no language prevents the subtle violations**: a contracts package that acquires a JSON
dependency, an event class with a setter, a module that reads another module's table.

## 3.4 Visibility inside the module

The rule (`L003`) is: *nothing outside contracts is public outside the module.*

| Language | How |
|----------|-----|
| C# | `internal` by default for every type in the implementation project; contracts are the only `public` surface. No `InternalsVisibleTo` to other modules. |
| TypeScript | `src/catalog/impl` is not exported from the package; `index.ts` exports contracts only. |
| Python | module-private by convention (`_`-prefixed names in `impl`) plus the rule `D009`; `__all__` in contracts defines the surface. |
| Go | `internal/` directory, plus lowercase type names for anything not meant to leave the package. |
| Java | package-private types where possible; `module-info` `exports acima.catalog.contracts;` and nothing else. |

Python is the honest case: there is no mechanism, only the test. That is precisely why
`D009` exists and why its finding message names the import that broke the boundary.

## 3.5 The host

A host does four things and nothing else:

1. reads configuration and constructs the modules;
2. satisfies provided ports with implementations (the object graph);
3. adapts the outside world to commands/queries (HTTP, messages, CLI, jobs);
4. starts and stops.

```python
# src/acima/host/main.py  — the one place where every module is known
catalog = CatalogModule(products=InMemoryProductStore())
payments = PaymentsModule(gateway=FakeGateway())
orders = OrdersModule(catalog=catalog.reader(), payments=payments.gateway())
```

Rules for hosts:

- A host MAY reference every module. It is the only unit with that right.
- A host MUST NOT contain business rules. If it does, they are unreachable by the module's tests and
  invisible to its contracts — which is the same mistake as putting them in a controller.
- A module MUST NOT reference a host (`D006`). This is what allows one module to be hosted by many
  applications (an API, a worker, a test harness) unchanged.

## 3.6 Adding a module: the checklist

Adding a module is the moment to get all of this right, because afterwards it is a migration.

- [ ] Choose a name that is a **noun in the business's language** (`catalog`, `orders`, `payments`),
      not a technical grouping (`core`, `shared`, `data`, `services`).
- [ ] Create `<module>.contracts` with zero dependencies.
- [ ] Create `<module>` implementation, referencing its own contracts **only as a private
      dependency** so it is not transitively exported.
- [ ] Create `<module>.tests` (behaviour) and add the module to the architecture configuration.
- [ ] Declare the module to the rule engine (`acima.config.json`) — an undeclared module is `G005`.
- [ ] Declare its ports: what it promises (contracts) and what it needs (constructor parameters).
- [ ] Decide its persistence: its own schema, tables or store. Never another module's.
- [ ] Decide its configuration namespace: `catalog:*`, never `orders.database`.
- [ ] Add at least one contract test that proves an event/command shape is constructible and immutable.
- [ ] Run the architecture tests at the target conformance level: zero findings, zero waivers.

## 3.7 What a module is not

| Not a module | Because |
|---|---|
| `Utils`, `Common`, `Shared`, `Core` | No owner, no domain, unbounded growth. The kernel exists for the one legitimate case. |
| A technical layer (`Persistence`, `Web`, `Domain`) | Layers are vertical slices; a layer that every module references destroys ownership (P1). |
| A database table | Storage is an implementation detail of a module, not a boundary. |
| A single class or feature | Too small to own data, contracts or configuration; it will borrow all three. |
| A team's whole product | Too big; it cannot be tested, versioned or extracted as a unit. |
