# 11. Service topology and layer contracts

ACIMA's module (chapters 3–5) is a boundary of ownership. This chapter adds a **service topology
profile** for products that organize many modules into services: one directory per service, one
project per layer, an independent contracts project per layer, and a total-isolation rule for every
contract.

The profile is domain-agnostic. The examples use orders and payments because this repository does,
not because the standard assumes commerce. A service may model a hospital ward, a shipping route, a
game session or a billing run; the obligations are the same.

> **Status.** This is the default architecture for new systems. The base module rules remain the
> compatibility path for existing systems; their shared-kernel allowance is legacy. These requirements
> are checked by [`conformance/topology.py`](../../conformance/topology.py) as `ACIMA-S001`–`S012`,
> against the manifest described in §11.10. A conformance claim MUST cite the JSON run, per §8.8.

## 11.1 The service is the unit of ownership

A **service** is the top-level product unit: the thing a team owns, deploys and scales, and the thing
a user experiences as one capability. In this profile:

- a service has **one responsibility** in its product domain;
- a service lives in **one directory**, named for the service, containing every project it owns;
- a service is **deployment-agnostic**: no cloud, vendor or platform SDK appears in its contracts,
  domain or application layers;
- a service is **product-driven**: its boundaries and scaling follow the user experience and the
  product's needs, not the shape of the infrastructure it happens to run on.

A service is not the same as a module, and it is not a microservice by definition. It is an ownership
envelope that contains one primary module and its layers. If a service needs two bounded contexts,
it is two services, even if they deploy together today.

> Chapter 2 warns against using "service" loosely. This chapter is the exception: within the profile,
> *service* means exactly the envelope defined here.

## 11.2 Naming

Names are load-bearing: a project name is how a reviewer, an enforcer and a new joiner discover who
owns what. The profile fixes the patterns.

| Element | Pattern | Example |
|---|---|---|
| Service directory | `services/<Service>/` | `services/Orders/` |
| Layer project | `<Service>.<Layer>` | `Orders.Application` |
| Layer contracts | `<Service>.<Layer>.Contracts` | `Orders.Application.Contracts` |
| Inter-service contracts | `<Source>.<Target>` | `Orders.Catalog` |
| Vendor adapter | `<Service>.<Vendor>` | `Payments.Stripe` |
| Vendor contracts | `<Service>.<Vendor>.Contracts` | `Payments.Stripe.Contracts` |
| Host | `<Service>.Host` | `Orders.Host` |

Two naming rules make the rest checkable by inspection:

- **One service name per project**, plus at most one vendor qualifier for `Integrations.<Vendor>`.
  An inter-service contract contains **exactly two** service names: the source that sends and the
  target that receives.
- **The directory name is the service name.** A project under `services/Orders/` MUST start with
  `Orders.`; a project named `Orders.*` MUST live under `services/Orders/`.

There is no third form. `Orders.Catalog.Payments` is not a contract; it is a design that has not
decided who owns the message.

## 11.3 The layers

| Layer | Responsibility | Owns | May reference |
|---|---|---|---|
| **Api** | Transport: endpoints, authentication, request validation, mapping to application | `Api.Contracts` | `Application.Contracts` (to call), inter-service contracts it sends, mapping code |
| **Application** | Use cases, orchestration, transaction boundaries, policy | `Application.Contracts` | `Domain`, `Application.Contracts`, vendor contracts, inter-service contracts it sends |
| **Domain** | Entities, aggregates, invariants, domain services, ports | no contracts project | the language core only (the shared kernel is legacy and not used in the default) |
| **Infrastructure** | Persistence, messaging, filesystem, clocks, adapters for domain ports | persistence models (internal) | `Domain`, `Application` ports, infrastructure libraries |
| **Integrations.\<Vendor\>** | One third-party integration, isolated | `<Service>.<Vendor>.Contracts` | that contracts project and the vendor SDK |
| **Host** | Composition root, configuration, process entry point | — | everything |

**Contracts are not a layer.** Each layer that faces outward has its own contracts project; the
domain does not, because the domain model is not a boundary type. If a domain concept must cross a
boundary, it is copied into that boundary's contract, deliberately.

## 11.4 Layer contract independence

> **No contracts project is the boundary type of two layers. A layer may reference the contracts of
> the layer it calls; it may not re-export them, inherit them, or return them as its own.**

In practice:

- `Orders.Api.Contracts` contains HTTP request and response DTOs. It never contains an application
  command.
- `Orders.Application.Contracts` contains commands, queries, results and provided ports. It never
  contains an HTTP DTO or a vendor type.
- A boundary has a **transform**: the caller maps its own DTO to the callee's contract. The callee
  never knows the caller's contract exists.
- A contracts project has **zero references**. Independence is not a convention; it is a property of
  the project file.

| Boundary | Caller's contract | Callee's contract | Transform lives in |
|---|---|---|---|
| Api → Application | `Orders.Api.Contracts` | `Orders.Application.Contracts` | `Orders.Api` |
| Application → Domain | `Orders.Application.Contracts` | domain model (no contract project) | `Orders.Application` |
| Application → inter-service | `Orders.Application.Contracts` | `Orders.Catalog` | `Orders.Application` |
| Application → vendor | `Orders.Application.Contracts` | `Orders.Stripe.Contracts` | `Orders.Application` |
| Infrastructure → Domain | persistence models | domain ports | `Orders.Infrastructure` |

The trade-off is deliberate: two DTOs and a mapper cost less than a shared type that couples two
layers' release cycles. Duplication at a boundary is cheap; coupling is not.

### The host is the DI layer

The **host is the service's dependency-injection layer and composition root**. It is the only project
that references every layer's implementation; it constructs the object graph, binds each port to its
adapter, and passes dependencies through constructors. A layer never constructs or imports another
layer's implementation. Contracts are the only vocabulary a layer shares with its caller, and they are
immutable (`C001`, `C002`). This is what lets the layers stay isolated while the host does the wiring.

## 11.5 Absolute contract isolation

> **A contracts project references nothing: no other project, no package, no shared kernel, no
> framework. Only the language's core library.**

This is the default. Base P3.5 permits the shared kernel inside contracts as a legacy compatibility
allowance; the default removes that exception. The reasons are the same ones P3 gives, taken to their
conclusion:

- a kernel reference makes every contract release depend on the kernel's release;
- a kernel value type in a contract is a type every consumer must share, which is the definition of
  coupling;
- "total isolation" is checkable in one line: the dependency list is empty.

What to do instead:

- use primitives at the contract edge (`decimal` + `string` currency code, a string id), or declare
  the value type **inside the contract project** and duplicate it where another contract needs it;
- keep validation in the constructor or factory — validation is allowed, frameworks are not;
- configure serialization outside the contract; no serializer attributes, no ORM annotations, no DI
  attributes;
- if generation is the only way to keep duplicated values consistent, generate them into each
  contract project; generated code still has zero dependencies.

The test is mechanical: **can this project compile alone, with no other project on the machine?** If
not, it is not totally isolated.

## 11.6 Inter-service contracts

An **inter-service contract** is the message vocabulary one service sends to another. It is its own
project, named `<Source>.<Target>`:

- `Orders.Catalog` contains what Orders sends to Catalog;
- `Catalog.Orders` contains what Catalog sends back.

Rules:

- **Exactly two service names.** If a third service needs the same message, it gets its own contract
  or maps the payload; a triad is an unowned shared model.
- **Direction is explicit.** The source owns the file; the target reviews it. The source may not
  change it without the target's review.
- **Only the two named services may reference it.** A third service that needs the same payload
  defines its own `<Third>.<Target>` contract and maps. Importing `Orders.Catalog` from another
  service is an `ST-7` violation even when the types compile.
- **It is immutable.** The payload is set at construction and never mutated (`C001`, `C002`).
- **Data only.** No behaviour, no vendor types, no domain entities, no shared kernel.
- **Immutable and additive.** New fields are optional; removals are breaking and versioned.

The contract is not a substitute for the target's own contracts. Catalog still owns
`Catalog.Contracts`; `Orders.Catalog` is only the wire vocabulary Orders uses.

## 11.7 Third-party isolation

A third-party library is a dependency of one adapter, never of the domain:

```
Orders.Stripe.Contracts   // the seam: DTOs and the port the service needs
Orders.Stripe             // the adapter: Stripe SDK, mapping, retries, vendor errors
```

- `Orders.Stripe.Contracts` has zero references. It defines the port (`IStripeGateway`) and the
  request/result types the service understands.
- `Orders.Stripe` references that project and the vendor SDK. It implements the port, maps to vendor
  types, and translates vendor failures into the contract's typed failures.
- Application and Domain reference **only** `Orders.Stripe.Contracts`. They never see a Stripe type,
  a Stripe exception or a Stripe configuration key.
- Tests use a fake implementing the port; the vendor SDK never appears in a domain test.

Swapping the vendor means writing `Orders.Adyen.Contracts` + `Orders.Adyen`, changing the
composition root, and leaving the domain untouched. If the port itself must change, that is a
contract change with its own review — which is the correct amount of friction.

## 11.8 The domain owns the business logic

The domain layer is the product's decision-making core. In this profile:

- **all business rules live in the domain**: invariants, calculations, eligibility, pricing,
  allocation, state transitions;
- **no persistence, transport, framework or vendor code** appears in the domain; repositories,
  clocks, id generators and message publishers are ports, implemented in infrastructure;
- **100% unit test coverage on domain projects** is the gate. Coverage is a floor, not a proof:
  every rule, branch and boundary case gets a named test; mutation testing is recommended where the
  cost is justified;
- the database is an implementation detail. A rule that can only be expressed in SQL is a rule the
  domain does not own yet.

Test projects are named `<Service>.Domain.Tests` and live beside the service. A domain test needs no
container, no database and no network.

## 11.9 Product orientation

The profile exists to serve the product, not the other way around.

**UI and API enforce the same workflow.** The states, transitions, validations, permissions and error
semantics a user experiences MUST match what the API enforces. The UI may present them differently
and may pre-validate for speed, but it MUST NOT be the only place a rule exists. The API domain is
the enforcement point, because it is the boundary every client shares.

**Services are deployment-agnostic.** A service describes what the product needs; the host and the
infrastructure projects describe where it runs. Moving from one queue, database or cloud to another
changes adapters and configuration, not the domain. Scaling decisions follow the user experience of
that service, not the shape of the platform.

**One responsibility per service.** A service that needs "and" in its description is two services.
The test is not size; it is whether a single product outcome owns the decisions inside it.

## 11.10 Profile conformance checklist

A repository claims the profile only when every item passes the runner. The runner reads
`acima.topology.json`; the manifest is the declared evidence, and the runner checks it against the
project files, source imports, coverage reports and workflow sources.

```bash
python3 conformance/topology.py --root . --config acima.topology.json --format json
```

The manifest names the services, their layers and contracts, domain tests, coverage reports,
business rules, workflows, vendor seams, inter-service contracts, boundary transforms and deployment
packages. The minimal shape is:

```json
{
  "standard": "1.0.0",
  "profile": "service-topology",
  "services": [{
    "name": "Orders",
    "path": "services/Orders",
    "layers": [
      { "name": "Api", "path": "services/Orders/Orders.Api", "contracts": "services/Orders/Orders.Api.Contracts" },
      { "name": "Application", "path": "services/Orders/Orders.Application", "contracts": "services/Orders/Orders.Application.Contracts" },
      { "name": "Domain", "path": "services/Orders/Orders.Domain", "contracts": null },
      { "name": "Host", "path": "services/Orders/Orders.Host" }
    ],
    "domain": "services/Orders/Orders.Domain",
    "domainTests": "services/Orders/Orders.Domain.Tests",
    "coverage": { "line": 100, "branch": 100, "report": "services/Orders/coverage.json" },
    "businessRules": [{ "id": "ORD-1", "test": "Order_rejects_empty_lines" }]
  }],
  "interService": [],
  "boundaries": [{
    "caller": "Orders.Api",
    "callee": "Orders.Application",
    "callerContract": "services/Orders/Orders.Api.Contracts",
    "calleeContract": "services/Orders/Orders.Application.Contracts",
    "transform": "services/Orders/Orders.Api/PlaceOrderMapper.cs"
  }],
  "deploymentPackages": []
}
```

Add `workflow` when the service has a UI, and `vendors` for each `<Service>.<Vendor>` seam. The
runner checks that every declared business rule appears in the domain source and in a named test,
that the coverage report is 100% line/branch, and that both UI and API sources mention every declared
state, transition event and error. Those declarations are review evidence, not a substitute for
review; the runner's job is to keep them from drifting.

- [ ] **ST-1** One directory per service under `services/`, named for the service.
- [ ] **ST-2** Each service has one responsibility, stated in its README in one sentence.
- [ ] **ST-3** Every project is named `<Service>.<Layer>` (or `<Service>.<Vendor>` for an adapter)
      and lives under that service's directory.
- [ ] **ST-4** Every outward-facing layer has its own contracts project; no contract project is
      shared by two layers.
- [ ] **ST-5** Every contracts project has zero references (project, package, kernel, framework).
- [ ] **ST-6** Every boundary has an explicit transform; no layer re-exports another layer's DTOs.
- [ ] **ST-7** Every inter-service contract is named `<Source>.<Target>` and contains exactly two
      service names.
- [ ] **ST-8** Every third-party library is isolated behind `<Service>.<Vendor>.Contracts` and
      implemented only in `<Service>.<Vendor>`.
- [ ] **ST-9** The domain contains all business rules and no persistence, transport or vendor code.
- [ ] **ST-10** Domain projects have a 100% line/branch coverage gate and tests that name the rules.
- [ ] **ST-11** UI and API share the same workflow states, transitions and error semantics; the API
      domain enforces the core rules.
- [ ] **ST-12** No deployment or vendor SDK appears outside an adapter or the host; services are
      described independently of their infrastructure.

Each item maps directly to the profile finding namespace: `ST-1` → `ACIMA-S001`, through `ST-12` →
`ACIMA-S012`. The checklist is the human-readable form of the same rule set.

Claim format:

```markdown
## ACIMA conformance

- Base: L3 (machine-checked)
- Profile: service-topology, automated, 12/12 on <date>
- Evidence: acima.topology.json and the `conformance/topology.py` JSON artifact
```

## 11.11 Anti-patterns

| Anti-pattern | Why it violates the profile |
|---|---|
| A `Shared` or `Common` contracts project across services | ST-4, ST-5: contracts are shared vocabulary, not a boundary |
| Passing an API DTO into the application layer | ST-6: no transform; the layers are now coupled |
| A contract project referencing `Orders.Domain` "for the entity type" | ST-5, ST-9: the domain is not a contract |
| `Orders.Catalog.Payments` | ST-7: a triad has no owner |
| Stripe types in a domain method signature | ST-8: the vendor is not the domain |
| Business rules in stored procedures or ORM hooks | ST-9: the domain does not own the rule |
| A UI that hides a rule the API does not enforce | ST-11: the workflow is not enforced at the shared boundary |
| An `Orders.Infrastructure` project referenced by `Orders.Api` | layering: the API depends on the composition root, not on persistence |

## 11.12 Relationship to base ACIMA

`acima.config.json` selects the mode. `"mode": "service-topology"` puts the profile in force;
`"mode": "base"` or an absent field keeps only P1–P9. `acima.topology.json` is the profile's
evidence manifest and does not select anything by itself. The runner rejects an inconsistent
declaration with exit `2`: a topology manifest without `mode: service-topology`, a service mode
without the manifest, an unknown mode, or a manifest whose `profile` is not `service-topology`.

Precedence is deliberately narrow. The profile refines, and in exactly two places tightens, the base
standard:

| Compatibility (legacy) | Default |
|---|---|
| P3.5: contracts may reference the shared kernel (legacy compatibility) | ST-5 (default): contracts reference nothing; the kernel is not permitted inside contracts |
| A module has one contracts unit | A service has one contracts unit **per outward-facing layer**, each zero-reference |
| Boundary crossings are module-to-module | Boundary crossings are layer-to-layer **and** service-to-service, each with an explicit transform |
| Conformance is L1–L3, machine-checked | Profile conformance is automated by `conformance/topology.py` as `ACIMA-S001`–`S012` (§8.8) |

Everything else in the base standard still applies: immutability, acyclic dependencies, no
implementation references, owned persistence, owned configuration and owned data. The profile is an
answer to "how do we arrange services and layers", not a replacement for "what may reference what".
