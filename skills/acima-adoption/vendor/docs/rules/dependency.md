# Dependency rules (`D`) and layering rules (`L`)

Thirteen rules about what may reference what. Full context: [Dependency model](../standard/04-dependency-model.md).

---

## ACIMA-D001 · Implementation references another implementation

**Severity** `error` · **Level** L1 · **Principle** P5

> A module implementation MUST NOT reference, import or link another module's implementation.

### Violation

```python
# src/acima/orders/impl/place_order.py
from acima.catalog.impl.repository import SqlProductRepository   # ❌
```

### Finding

```
ACIMA-D001  error  Orders imports the implementation unit catalog (expected catalog.contracts).
  src/acima/orders/impl/place_order.py:2
  from acima.catalog.impl.repository import SqlProductRepository
```

### Why

This is the single reference that destroys the architecture. Once `Orders` can name
`SqlProductRepository`, Catalog's persistence, its ORM, its constructor arguments and its migrations
are all part of Orders' build. Catalog can no longer change its store, and Orders can no longer be
tested without it. Every other rule exists to keep this reference from being necessary.

### Fix

Import the contracts unit and use the provided port:

```python
from acima.catalog.contracts import CatalogReader, ProductView   # ✅
```

If the port does not offer what you need, that is a conversation with the owner (`P4.3`), not an import.

### Detection

Build the unit graph from the config, resolve each import to a target file, map the file to its unit,
and compare the `(from.role, to.role, from.module, to.module)` tuple against the matrix. In Go,
`internal/` usually catches it at compile time; in .NET it is impossible without a `ProjectReference`.
Both are still checked, because a reference added "temporarily" is invisible until it is in `main`.

---

## ACIMA-D002 · Contracts reference an implementation

**Severity** `error` · **Level** L1 · **Principle** P3

> A contracts unit MUST NOT reference any implementation unit, including its own.

### Violation

```csharp
// Acima.Catalog.Contracts/ProductView.cs
using Acima.Catalog.Infrastructure;            // ❌
public sealed record ProductView(Product Entity);
```

### Finding

```
ACIMA-D002  error  catalog.contracts references the implementation unit catalog.
  src/Acima.Catalog.Contracts/ProductView.cs:2
  using Acima.Catalog.Infrastructure;
```

### Why

It inverts the direction that makes the model work. Contracts exist so implementations depend on them,
not the other way round. A contracts project that references its own implementation cannot be published
alone, cannot be consumed by a module that does not want the implementation, and drags every package of
that implementation into every consumer.

### Fix

Define the contract shape independently and map in the implementation:

```csharp
public sealed record ProductView(ProductId Id, string Name, Money Price);   // ✅
```

The mapping lives in the Catalog implementation — a place that already knows both types.

---

## ACIMA-D003 · Contracts reference another contracts unit

**Severity** `error` · **Level** L1 · **Principle** P3, P7

> A contracts unit MUST NOT reference another contracts unit. Under the default it references nothing;
> duplicate the shape or carry identity. A shared kernel is a legacy migration allowance, not an
> option for a new contract.

### Violation

```typescript
// src/orders/contracts/index.ts
import { ProductView } from '../../catalog/contracts/index.js';   // ❌
export interface OrderLine { readonly product: ProductView; }
```

### Finding

```
ACIMA-D003  error  orders.contracts references catalog.contracts; duplicate the shape or carry identity at the boundary.
  src/orders/contracts/index.ts:1
  import { ProductView } from '../../catalog/contracts/index.js';
```

### Why

This is ACIMA's strictest deviation from published practice, and the reason is in
[the FAQ](../standard/10-faq.md): contract edges are how cycles reappear one level up, and how version
independence dies. `A → B.Contracts` plus `B.Contracts → A.Contracts` is a cycle the module graph does
not show.

### Fix

Three legitimate options:

1. **Local value (default)** — declare `Money`, `ProductId` and the rest of the value vocabulary in
   `orders.contracts`. If another contract needs the same shape, declare its own copy there.
2. **Carry identity, not the model** — `OrderLine { ProductId, Money UnitPrice, int Quantity }` is
   usually better than embedding Catalog's view: it freezes the price at order time, which is what the
   business means.
3. **Duplicate the shape** — a local `ProductSnapshot` in `orders.contracts` that happens to look like
   Catalog's today.

A shared kernel is not a fourth option in the default. It is a migration allowance for an existing
system that has not removed its kernel yet.

Option 2 is almost always right and is worth the argument it causes.

---

## ACIMA-D004 · Contracts carry a third-party dependency

**Severity** `error` · **Level** L1 · **Principle** P3

> A contracts unit MUST NOT reference a third-party package. The only permitted reference is the
> language's core library. The shared kernel is a legacy compatibility allowance, not a default
> dependency (`ST-5`).

### Violation

```csharp
<!-- Acima.Catalog.Contracts.csproj -->
<PackageReference Include="Newtonsoft.Json" Version="13.0.3" />      <!-- ❌ -->
```

```python
# acima/catalog/contracts/product_view.py
import pydantic                                                        # ❌
```

### Finding

```
ACIMA-D004  error  contracts unit catalog.contracts depends on a third-party package: pydantic.
  src/acima/catalog/contracts/product_view.py:1
  import pydantic
```

### Why

A dependency in contracts is a dependency imposed on every consumer, forever, at your version. It also
makes the contracts unit unusable in a context that cannot take that package (a CLI, a different
runtime, a sandboxed function). The package is usually there for validation or serialization — both of
which belong to the boundary's adapter, not to the type.

### Fix

- Replace validation attributes with constructor checks.
- Move serializer attributes to a transport type in the host, or rely on a convention-based serializer.
- Framework/standard-library namespaces are not third-party; the rule does not fire on them.

### Detection

.NET: inspect `Assembly.GetReferencedAssemblies()` of the contracts assembly, excluding the framework
(and the legacy kernel only in compatibility mode). TypeScript: the contracts `package.json` must have
no `dependencies`, and imports must resolve to relative paths. Python/Go/Java: classify each import;
anything not in the standard library or the same contracts package is third-party. In the default,
any reference to the kernel or another unit is also a violation (`ST-5`).

---

## ACIMA-D005 · Circular module dependency

**Severity** `error` · **Level** L1 · **Principle** P5

> The module dependency graph MUST be acyclic.

### Violation

```
orders   → payments.contracts
payments → orders.contracts        (the cycle: orders ⇄ payments)
```

### Finding

```
ACIMA-D005  error  Circular module dependency: orders → payments → orders
  src/orders/impl/place_order.py:6    references payments.contracts
  src/payments/impl/refund.py:5       references orders.contracts
```

### Why

A cycle is two modules that cannot be separated. Neither can be tested alone, versioned alone or
extracted; a change to either is a change to both. In .NET it is also unbuildable, which is how most
teams discover it — but only after the design has committed to it.

### Fix

In order of preference (`6.4`):

1. introduce a process manager that owns the workflow;
2. replace one direction with an event;
3. merge the modules, if they are one bounded context.

Do not use the shared kernel to break a cycle. Moving the shared type to the kernel hides the cycle and
makes the kernel grow, which is `D007` next month.

### Detection

Tarjan or DFS over the module-level graph; report each strongly connected component with a shortest
cycle path. A component with one module is not a cycle (self-references are legal within a module).

---

## ACIMA-D006 · Contracts reference the host

**Severity** `error` · **Level** L1 · **Principle** P2, P4

> A contracts unit MUST NOT reference the host, the composition root, or any delivery mechanism.

### Violation

```csharp
// Acima.Orders.Contracts/PlaceOrder.cs
using Acima.Host.DependencyInjection;     // ❌
public sealed record PlaceOrder(Guid CustomerId) { public IServiceProvider Services { get; init; } }
```

### Finding

```
ACIMA-D006  error  orders.contracts references the host unit; contracts must not know how they are hosted.
  src/Acima.Orders.Contracts/PlaceOrder.cs:2
  using Acima.Host.DependencyInjection;
```

### Why

A contract that knows the host cannot be consumed by a different host — a worker, a CLI, a test
harness, or the service the module becomes. It also makes the contract untestable without the
composition root, which is the opposite of what a boundary is for.

### Fix

Remove the reference; pass what the handler needs as a contract member, or resolve it inside the
implementation through a consumer-owned port (`P4.3`).

---

## ACIMA-D007 · Shared kernel violation

**Severity** `error` · **Level** L1 · **Principle** P3

> The shared kernel MUST NOT reference modules, contracts or third-party packages, and MUST NOT contain
> business behaviour.

### Violation

```python
# src/acima/shared_kernel/pricing.py
from acima.catalog.contracts import ProductView          # ❌ kernel referencing a module
def best_price(products): ...                            # ❌ business rule in the kernel
```

### Finding

```
ACIMA-D007  error  shared-kernel references catalog.contracts; the kernel must be a leaf.
  src/acima/shared_kernel/pricing.py:1
  from acima.catalog.contracts import ProductView
```

### Why

Under the legacy shape the kernel was referenced by every contracts unit, so it was the most expensive
place in the system to put anything. A kernel that references a module couples every module to that
module. A kernel with behaviour becomes a domain model nobody owns. The default avoids the problem by
not referencing the kernel from contracts at all (`ST-5`).

### Fix

Move the *type* to the owning module. In the default, declare it in the contract project that needs
it. In a legacy repository, keep in the kernel only values that survive the
[admission test](../standard/04-dependency-model.md#45-the-shared-kernel-exception).

### Detection

Apply the contracts rules to the kernel, plus: no imports that resolve to a module unit, no function or
method bodies beyond construction/validation/equality, no third-party packages.

---

## ACIMA-D008 · Transitive implementation leak

**Severity** `error` · **Level** L1 · **Principle** P3, P5

> A reference MUST NOT deliver another module's implementation transitively.

### Violation

`Orders` depends on `Catalog.Contracts`; `Catalog.Contracts` (illegally) depends on `Catalog`; therefore
`Orders` can name `Product` without any direct reference.

```
orders → catalog.contracts → catalog        ❌  orders can reach catalog
```

### Finding

```
ACIMA-D008  error  orders reaches the implementation unit catalog transitively through catalog.contracts.
  path: orders → catalog.contracts → catalog
```

### Why

It is the loophole that makes `D001` useless in practice: nobody adds the forbidden reference, the
dependency simply arrives. This is also why the .NET reference implementation uses
`PrivateAssets="all"` on an implementation's reference to its own contracts — redaction at the build
level, not just detection.

### Fix

Remove the reference that creates the leak. In .NET: `PrivateAssets="all"` on implementation-internal
references. In TypeScript: do not re-export `impl` from the contracts entry point. In Go/Java: `internal/`
or JPMS `exports`.

### Detection

Compute the transitive closure of the unit graph and apply the matrix to **every reachable pair**, not
just direct edges. Report the path, not just the endpoints, because the path is the fix.

---

## ACIMA-D009 · Access to another module's internals

**Severity** `error` · **Level** L1 · **Principle** P1, P2

> Non-contract types of a module MUST NOT be reachable from outside it.

### Violation

```python
# src/acima/reports/impl/dashboard.py
from acima.orders.impl.order import Order          # ❌ reaching inside Orders
```

### Finding

```
ACIMA-D009  error  reports imports the internal type Order from module orders.
  src/acima/reports/impl/dashboard.py:1
  from acima.orders.impl.order import Order
```

### Why

Even when the type is not "public API", importing it makes it API. The owner cannot rename it, change
its invariants or move it without breaking a module that was never supposed to know it exists.

### Fix

Ask the owner for a view (`OrderSummary`) through a provided port. If the consumer needs something the
owner does not offer, the consumer declares its own port and adapts (`P4.3`) — it does not read the
owner's model.

### Detection

Compare the target unit with the source unit; any reference into an `implementation` unit from a
different module is this rule. In languages with `internal`/JPMS this is unreachable, so the rule is a
no-op there — but it still runs, because it catches the case where someone widened visibility to make
it compile.

---

## Layering (`L`)

---

## ACIMA-D010 · Port exposes a vendor shape

**Severity** `error` · **Level** L1 · **Principle** P3

> A port unit is dependency-free: it imports no third-party package and names no vendor type.

### Violation

```python
# src/editor/port/__init__.py
from monaco_editor import IEditor                              # ❌ the port carries the vendor

class EditorPort(Protocol):
    """Open a note in an editor."""
    def open(self, note: str) -> IEditor: ...
```

### Finding

```
ACIMA-D010  error  port unit editor.port imports the third-party package monaco_editor; a port
                   declares the capability, never the vendor.
  src/editor/port/__init__.py:2
  from monaco_editor import IEditor
```

### Why

A port is the contract a consumer compiles against. If it names a vendor type, the consumer inherits
the vendor through the seam: the swap the port was supposed to make cheap now changes every caller,
and the dependency the adapter was isolating is back in the build. This is `D004` for ports, and it
is a separate rule because a port is not a contracts unit in the base matrix — it has its own role
and its own edge.

### Fix

Declare the capability in the port's own vocabulary — handles, requests and results it owns — and
convert to the vendor type inside the adapter. Constructor and method bodies are not required in a
port; a behavioural signature (a method that takes and returns port-owned types) is exactly right.
`C007` does **not** apply to interfaces, and no DTO is required: a port is allowed to be behaviour
rather than a message.

### Detection

Every import in a port unit is a finding, plus every vendor type token in its signatures, fields and
exports (`L007`'s token set). Declared vendors and undeclared third-party packages are treated the
same way: a port has no third-party dependencies at all. **Implemented for Python and TypeScript**;
Go and .NET report the rule `executed: false` in this revision.

---

## ACIMA-L001 · Domain references infrastructure

**Severity** `error` · **Level** L1 · **Principle** P5

> Inside a module, domain and application code MUST NOT reference infrastructure or delivery
> mechanisms.

### Violation

```csharp
// Acima.Orders/Domain/Order.cs
public void Place(SqlConnection connection) { }        // ❌ domain knows the database
```

### Finding

```
ACIMA-L001  error  Orders.Domain references infrastructure (SqlConnection); dependencies must point inward.
  src/Acima.Orders/Domain/Order.cs:7
```

### Why

A domain that knows the database cannot be tested without it, reasoned about without it, or moved when
the database changes. It is also the load-bearing wall of every mocking strategy: if the domain depends
on the ORM, every test needs the ORM.

### Fix

Declare the port in the application layer (`OrderRepository`), implement it in infrastructure, inject it.

### Detection

Directory-based layer classification (`domain/`, `application/`, `infrastructure/`) combined with
import analysis, plus a configurable list of framework namespaces per language (`System.Data.*`,
`Microsoft.EntityFrameworkCore.*`, `sqlalchemy.*`, `database/sql`, `java.sql.*`, `pg`, `prisma`).

---

## ACIMA-L002 · Contracts reference a framework type

**Severity** `error` · **Level** L1 · **Principle** P3

> Contracts MUST NOT expose hosting, transport, ORM or serialization framework types.

### Violation

```csharp
public sealed record PlaceOrder(Guid CustomerId, CancellationToken CancellationToken, HttpContext Context);
//                                              ❌ transport      ❌ hosting
```

### Finding

```
ACIMA-L002  error  orders.contracts exposes the framework type HttpContext.
  src/Acima.Orders.Contracts/PlaceOrder.cs:3
```

### Why

A contract that carries `HttpContext` can only be produced by HTTP. It cannot be produced by a message
consumer, a scheduler, a CLI or a test. The boundary silently becomes "whatever the web framework gives
us", which is the opposite of a boundary.

### Fix

Keep the message about the business: `PlaceOrder(Guid CustomerId)`. Transport concerns
(`CancellationToken`, request context, correlation ids) belong to the handler in the host, or to an
explicit envelope type in the host.

### Detection

A per-language denylist of framework namespaces and types, applied to contract type signatures and
members. The denylist is data and can be extended in `acima.config.json`.

---

## ACIMA-L003 · Implementation type published outside the module

**Severity** `error` · **Level** L1 · **Principle** P2

> Only contracts types may be public outside a module.

### Violation

```csharp
// Acima.Catalog/Product.cs
public sealed class Product { }                        // ❌ public in the implementation project
```

### Finding

```
ACIMA-L003  error  implementation unit catalog publishes the public type Product.
  src/Acima.Catalog/Product.cs:3
  public sealed class Product
```

### Why

If it is public, it will be used. The contract stops being the surface and becomes a suggestion. This
rule is what makes `D009` enforceable rather than aspirational, and it forces the "should this be in
contracts?" conversation at the moment it matters.

### Fix

Make it `internal` (C#), unexported (TS), `_`-prefixed (Python), lowercase (Go), package-private
(Java) — and move anything that genuinely needs to cross into the contracts unit.

### Detection

Language-specific visibility analysis over implementation units. Where visibility cannot be expressed
(Go, Python), it degrades to import analysis: any symbol imported from outside the module is flagged.

---

## ACIMA-L004 · Module resolved through a service locator

**Severity** `warning` · **Level** L1 · **Principle** P4

> Modules MUST declare their dependencies explicitly. Resolving a peer module at runtime hides coupling.

### Violation

```csharp
public sealed class PlaceOrderHandler
{
    public PlaceOrderHandler(IServiceProvider services) { _services = services; }   // ❌
    public void Handle(PlaceOrder cmd) => _services.GetRequiredService<ICatalogReader>().Get(...);
}
```

### Finding

```
ACIMA-L004  warning  Orders resolves ICatalogReader from a service locator instead of declaring it.
  src/Acima.Orders/Application/PlaceOrderHandler.cs:12
```

### Why

The dependency is real but invisible: it does not appear in the constructor, so it cannot be found by
reading the class, and it fails at runtime rather than at construction. For a *peer module* it is worse
than a hidden dependency — it is a boundary crossing the dependency graph cannot see, which means
`D001`–`D005` cannot check it.

### Fix

Take the port as a constructor parameter. Resolving your own infrastructure (a logger, a clock) from a
container is a lesser sin and is why this rule is a warning; resolving a *module* is not.

### Detection

Look for calls that take a container or registry and return a type from another module:
`GetRequiredService<T>`, `resolve(T)`, `inject(T)`, `container.Lookup`, `app.get(...)`,
`SpringContext.getBean(...)`.

---

## ACIMA-L005 · Integration library used outside its declared adapter

**Severity** `warning` → `error` at 2.0.0 · **Level** L1 · **Principle** P3

> A package declared with tier `integration` is imported only by its declared adapter unit. Every
> other unit reaches the capability through the port.

### Violation

```python
# src/notes/impl/service.py — an application unit importing the editor library directly
import monaco_editor                                    # ❌ declared tier: integration

def render(note: str) -> str:
    return monaco_editor.render(note)
```

### Finding

```
ACIMA-L005  warning  orders imports the integration library monaco-editor; only its adapter
                      (editor.monaco) may import it, everyone else takes the port.
  src/notes/impl/service.py:1
  import monaco_editor
```

### Why

A library whose tier is `integration` owns IO, state, a wire format or a UI surface you cannot
replace without touching every caller. Importing it from application code means the port is
decorative: the moment the library ships a breaking change, or the vendor changes, the whole module
changes with it. The adapter is the one place allowed to know the vendor, and the port is what the
rest of the system compiles against.

### Fix

Move the import into the adapter named by the entry's `adapter` unit and call the port from
application code. If the package is genuinely pure and stateless, declare it `utility` instead — the
tier is a reviewable decision, not an inference. If it is a runtime or framework surface, declare it
`platform`; it then stays banned from contracts (`D004`, `L002`) and needs no adapter.

### Detection

For every `externals` entry with `tier: integration`, every import specifier outside the entry's
adapter unit is a finding. Specifiers are matched against the entry key and its `specifiers` list, so
a PyPI distribution name and its import name can differ. Host code is not exempt: the host names the
adapter, never the vendor. **Implemented for Python and TypeScript**; Go and .NET report the rule
`executed: false` in this revision.

---

## ACIMA-L006 · Adapter without a port

**Severity** `error` · **Level** L1 · **Principle** P3

> Every adapter unit is declared in `externals` with exactly one port unit, and every integration
> entry names both.

### Violation

```jsonc
// acima.config.json — an adapter unit with no port and no entry
{ "id": "legacy.pdf", "module": "legacy", "role": "adapter", "paths": ["src/legacy/pdf"] }
```

### Finding

```
ACIMA-L006  error  adapter unit legacy.pdf is declared in no externals entry; it has no port and
                    no reviewed vendor.
  src/legacy/pdf/__init__.py:1
```

### Why

An adapter with no port is an unguarded vendor import with a directory name. It reads as isolation in
a diagram — the vendor is in one place — while every consumer still depends on the adapter's own
signatures, which are the vendor's signatures wearing a local name. `L006` is what makes "isolated
behind a contract" a checkable sentence rather than a layout convention.

### Fix

Declare the port unit and complete the entry:

```jsonc
"externals": {
  "monaco-editor": {
    "tier": "integration",
    "owner": "team-editor",
    "reason": "Browser code editor for note authoring.",
    "adapter": "editor.monaco",
    "port": "editor.port",
    "reviewedOn": "2026-11-09",
    "expires": "2027-11-09"
  }
}
```

If the adapter has no consumer that needs a capability, delete the adapter rather than inventing a
port: an unused adapter is a dependency you are paying for without a user.

### Detection

Two halves, both a finding: an `integration` entry that omits `adapter` or `port`, and an
`adapter`-role unit that no entry names. An entry naming an unknown unit id is `G001`, because a
dangling seam is a configuration error, not an architecture decision. **Implemented for Python and
TypeScript**; Go and .NET report the rule `executed: false` in this revision.

---

## ACIMA-L007 · Vendor type outside the adapter

**Severity** `warning` → `error` at 2.0.0 · **Level** L1 · **Principle** P3

> A vendor type appears in a signature, field or export outside the adapter unit.

### Violation

```python
# src/notes/impl/service.py
def open_note(editor: monaco_editor.IEditor) -> str:      # ❌ vendor type in an application signature
    return editor.text()
```

### Finding

```
ACIMA-L007  warning  notes names the vendor type IEditor from monaco-editor outside its adapter.
  src/notes/impl/service.py:2
  monaco_editor
```

### Why

`L005` catches the import; `L007` catches the leak that survives a local wrapper. A function that
takes `IEditor` is not portable, a test for it needs the vendor, and a swap has to change the
signature even though the import disappeared. The port exists so the signature is the system's, not
the vendor's.

### Fix

Name the port's own type (`EditorHandle`) and map it to the vendor type inside the adapter, where the
conversion is visible and testable. For a `utility` package the rule is narrower on purpose: its
types may not cross a **contract or port**, and it is otherwise free inside implementations.

### Detection

Type-name tokens come from the entry's `types` list, or — only when that list is absent — from the
package name and its PascalCase and flattened variants. The declaration wins because a derived token
such as `MonacoEditor` is more often the adapter's own class name than a vendor type. Lines that are
imports are excluded (they are `L005`/`D010`). Port units are excluded here and judged by `D010`, so
one leak is one finding. A token shorter than three characters is ignored to avoid matching unrelated
code. When one adapter covers a vendor and a wrapper around it (`monaco-editor` and
`@monaco-editor/react`) and both entries declare the same type, a line is reported once and named
after the shorter package, so the finding points at the vendor rather than its wrapper.
**Implemented for Python and TypeScript**; Go and .NET report the rule `executed: false` in this
revision.
