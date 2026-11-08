# 4. Dependency model

This chapter is the normative core of ACIMA. Everything else either supports this matrix or describes
how to live with it.

## 4.1 The matrix

`→` means "may reference". Anything not listed is forbidden.

| From ↓ / To → | contracts (own) | contracts (other) | implementation (own) | implementation (other) | shared kernel | host |
|---|---|---|---|---|---|---|
| **contracts (own)** | — | ❌ `D003` | ❌ `D002` | ❌ `D002` | ❌ `ST-5` (default) | ❌ `D006` |
| **implementation** | ✅ | ✅ | — | ❌ `D001` | ✅ | ❌ `D006` |
| **shared kernel** | ❌ `D007` | ❌ `D007` | ❌ `D007` | ❌ `D007` | — | ❌ `D007` |
| **host** | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **test** | ✅ | ✅ | ✅ (unit under test) | ⚠️ only the module it tests | ✅ | ✅ |

Three things about this table are worth stating explicitly, because they are the parts people try to
negotiate:

1. **Contracts may not reference contracts.** This is stricter than most published guidance ("ideally
   no dependencies"). It is what makes acyclicity structural instead of aspirational.
2. **An implementation may reference only its own implementation.** The row looks permissive because
   it allows everything on the right; the constraint is in the *destination* column. A module's own
   inner code is free; another module's inner code is unreachable.
3. **The kernel is a leaf.** It may reference nothing, including the language's own convenience
   packages beyond the core library. A kernel that needs a JSON library is not a kernel.

## 4.2 How a tool decides what a unit is

Rules are only executable if the tool can classify every source file. ACIMA makes that
**configuration, not inference**, so that the same algorithm works in five languages and so that an
undeclared module cannot hide.

`acima.config.json` (schema in [Executable governance](07-executable-governance.md)) declares units:

```json
{
  "standard": "1.0.0",
  "level": "L2",
  "language": "python",
  "root": ".",
  "units": [
    { "id": "shared-kernel", "role": "shared-kernel", "paths": ["src/acima/shared_kernel"] },
    { "id": "catalog.contracts", "module": "catalog", "role": "contracts", "paths": ["src/acima/catalog/contracts"] },
    { "id": "catalog", "module": "catalog", "role": "implementation", "paths": ["src/acima/catalog/impl"] },
    { "id": "orders.contracts", "module": "orders", "role": "contracts", "paths": ["src/acima/orders/contracts"] },
    { "id": "orders", "module": "orders", "role": "implementation", "paths": ["src/acima/orders/impl"] },
    { "id": "host", "role": "host", "paths": ["src/acima/host"] }
  ],
  "exclude": ["tests", "violations"]
}
```

The classification algorithm:

1. Resolve every production source file under `root`, minus `exclude`.
2. Assign it to the **most specific** declared unit whose `paths` contain it.
3. If a file belongs to no unit, emit `ACIMA-G005` — unclassified source is a violation, not a pass.
4. Build the reference graph: for each file, resolve every import/reference to a target file, then to
   the target's unit.
5. For each edge `from-unit → to-unit`, apply the matrix. Report every failing edge as a finding at
   the line of the offending reference.

Step 5 is why findings have `path` **and** `line`: the message must point at the import, not the
project file. A finding you cannot act on in five seconds becomes a waiver.

## 4.3 Transitive references

Direct edges are the easy case. The interesting ones are transitive (`D008`).

A transitive leak exists when unit `A` references `B`, and `B` references `C`, and `A → C` is
forbidden. The classic: `Orders` references `Catalog.Contracts`, which (incorrectly) references
`Catalog`, which publishes `ProductEntity` — so `Orders` can now name `ProductEntity` without ever
declaring a reference to the Catalog implementation.

There are two ways to enforce this, and ACIMA requires at least one per language:

| Mechanism | Where it works | How |
|-----------|----------------|-----|
| **Reference redaction** | .NET, TypeScript, Java/JPMS, Rust | make the implementation's references private so they are not re-exported (`PrivateAssets="all"`, no re-export in `index.ts`, JPMS non-exported packages) |
| **Graph analysis** | everywhere | compute the transitive closure of the reference graph and check the matrix on *all* reachable pairs, not only direct edges |

The reference implementations do both: the build configuration redacts where the language allows it,
and the architecture test computes the closure regardless.

## 4.4 Cycles

`D005` reports each strongly connected component in the module graph with the shortest cycle path:

```
ACIMA-D005 error  Circular module dependency: orders → payments → orders
  orders    src/orders/impl/place_order.py:6     references payments.contracts
  payments  src/payments/impl/refund.py:5         references orders.contracts
  orders    ...                                    (cycle closes here)
```

Note what the message reveals: **the cycle goes through contracts**, which the matrix above forbids
(`D003`). In practice every cycle in an ACIMA system is either a `D003` violation or a genuine design
problem that has been smuggled in through the shared kernel. That is why `D005` is not redundant with
`D003`: it catches the cycle that a module-only view hides, and it names *modules*, which is the level
at which the design conversation happens.

## 4.5 The shared kernel exception

Under the default, contracts do not reference the kernel at all (`ST-5`). It survives as a legacy
compatibility unit for existing systems, so its admission test remains relevant during migration — but
a new type should be declared locally or duplicated instead.

**Admission test for a kernel type** — all four must be true:

1. It is a *value*: immutable, equality by value, no identity.
2. At least two modules need it **and** neither can own it without the other importing that module's
   contracts (`D003`).
3. It contains no business rule that could reasonably change (`C003`).
4. Its absence would force duplication of a *primitive with invariants* (money, quantity, ids), not of
   a convenience function.

If a candidate fails any test, it stays out. Common rejects:

| Candidate | Verdict | Why |
|---|---|---|
| `Money`, `Currency`, `Quantity` | ✅ in | value with invariants, needed everywhere |
| `OrderId`, `ProductId` | ✅ in | identity primitives that cross boundaries constantly |
| `Result<T>` | ⚠️ usually | include only if the language lacks one and every module needs the same shape |
| `IClock` | ❌ out | infrastructure abstraction; each module declares its own (`P1.6`) |
| `Address` | ⚠️ depends | if shipping and billing both own it, it is a value; if it has validation rules that differ, it is two types |
| `Customer` | ❌ out | an entity with a lifecycle — it belongs to exactly one module |
| `StringExtensions` | ❌ out | no invariants, no ownership; duplicate it |
| `AppConstants` | ❌ out | this is configuration, and configuration is owned (`A002`) |

## 4.6 Dependency budget

`D001`-style rules stop the *illegal* edges. A dependency budget stops the legal ones from becoming
unmanageable: a per-module maximum number of modules it may depend on.

```json
{ "budgets": { "orders": 3, "catalog": 0, "payments": 1 } }
```

A budget is not a rule in the catalog (it has no fixed threshold); it is a governance control that
teams set for themselves. Its value is that it makes the cost of a new dependency visible *at the
moment it is added*. A module with a budget of 0 is a leaf; a module with a budget of 8 is a hub and
should be examined for missing concepts.

## 4.7 The same matrix in five languages

| Obligation | C# / .NET | TypeScript | Python | Go | Java |
|---|---|---|---|---|---|
| No implementation → implementation | no `ProjectReference`; `dotnet` forbids cycles too | `no-restricted-imports` on `*/impl/*` + `exports` map | `D001` finding | `internal/` compile error + `D001` | package-private / JPMS + `D001` |
| Contracts zero-dependency | csproj with no `PackageReference`, enforced by a test over `Assembly.GetReferencedAssemblies()` | `D004` over package.json + import graph | `D004` over imports | `D004` over imports | `D004` over imports |
| Contracts → contracts forbidden | `D003` | `D003` | `D003` | `D003` | `D003` |
| No host reference | `D006` | `D006` | `D006` | `D006` | `D006` |
| Transitive redaction | `PrivateAssets="all"` | `exports` map, `sideEffects:false` | n/a — graph closure only | n/a — graph closure only | JPMS `exports` |
| Acyclicity | compiler + `D005` | `D005` | `D005` | `go list` + `D005` | `D005` |
| Kernel is a leaf | `D007` | `D007` | `D007` | `D007` | `D007` |

The per-language detail — including the exact configuration and the idiomatic third-party tools — is
in the [language profiles](../languages/index.md).

## 4.8 Reading a matrix violation

Every finding of category `D` answers four questions, in this order:

1. **Who** — which unit, and which module it belongs to.
2. **What** — the exact reference, quoted as `evidence`.
3. **Why** — which matrix cell it violates, phrased so the fix is obvious:
   `"Orders imports the implementation unit catalog (expected catalog.contracts)."`
4. **Where** — `path:line`.

If a rule cannot produce that, it is not ready to be enforced, because the reader will not know whether
to fix the code or the configuration. That distinction is the subject of the next two chapters.

## 4.9 Service topology edges

Chapter 11 adds a layer dimension to the matrix. The base matrix still applies inside every layer;
the profile adds the edges between layers and between services.

| From | May reference | Must not reference |
|---|---|---|
| `Api` | its own contracts, `Application.Contracts`, inter-service contracts it sends | `Application`, `Domain`, `Infrastructure` |
| `Application` | its own contracts, `Domain`, vendor contracts, inter-service contracts it sends | `Api`, `Infrastructure` implementations |
| `Domain` | the language core only (and the kernel outside absolute mode) | any contracts project, any vendor SDK |
| `Infrastructure` | `Domain` ports and types, infrastructure libraries | `Api`, vendor SDKs |
| `Integrations.<Vendor>` | its own contracts, the vendor SDK | `Domain`, `Application`, `Api` |
| `Host` | everything | — |

Cross-service edges are narrower still: a service may reference another service only through an
inter-service contract named `<Source>.<Target>`. It may not reference the other service's `Api`,
`Application`, `Domain` or `Infrastructure` projects, and it may not add a third service name to the
contract to avoid a copy.

The layer matrix is not a second source of truth: it is the module matrix applied to the layer
projects, with the transform at each boundary making the edge explicit.
