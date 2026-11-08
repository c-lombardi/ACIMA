# Autonomy rules (`A`) and governance rules (`G`)

Nine rules. The `A` rules constrain what happens at runtime — data, configuration and state. The `G`
rules constrain the standard's own bookkeeping, and they are what keep the other 20 rules honest.

Full context: [Dependency model](../standard/04-dependency-model.md) ·
[Runtime boundaries](../standard/06-runtime-boundaries.md) ·
[Executable governance](../standard/07-executable-governance.md).

---

## ACIMA-A001 · Shared database ownership

**Severity** `error` · **Level** L3 · **Principle** P1, P7

> Each module owns its persistence: its own schema, tables, store and migrations. No other module reads
> or writes them.

### Violation

```sql
-- orders module
SELECT p.name, p.price FROM catalog.products p WHERE p.id = ?   -- ❌ reading Catalog's table
```

```python
# orders/impl/repository.py
self.db.execute("SELECT * FROM catalog_products WHERE id = %s", (product_id,))   # ❌
```

### Finding

```
ACIMA-A001  error  Orders queries the catalog schema (catalog.products); each module owns its own tables.
  src/acima/orders/impl/repository.py:42
  self.db.execute("SELECT * FROM catalog_products WHERE id = %s", (product_id,))
```

### Why

A shared table is the strongest coupling in software: it bypasses every contract, every version and
every boundary you built. Catalog cannot rename a column, split a table, change a type or move to a
different store without breaking Orders — and the compiler will never tell you.

This is the rule that turns "modular monolith" from a folder structure into an architecture, and it is
the one that makes extraction to a service possible at all.

### Fix

- Call the owner's provided port (`CatalogReader.Get(productId)`) for reads.
- Subscribe to the owner's events for data you need to keep (`ProductPriceChanged` → your own
  projection table).
- Give the consuming module its own schema for its own copy. Duplicated data with a clear owner is
  normal in ACIMA; shared data with no owner is not.

### Detection

Two levels:

1. **Static**: SQL string literals and ORM model definitions in a module that name another module's
   schema/table prefix. The reference enforcer checks string literals and `__tablename__` /
   `@Table` / `[Table]` declarations.
2. **Runtime (recommended)**: a database user per module, with grants only on its own schema. This is
   the only enforcement that cannot be bypassed, and it is worth doing at L3.

---

## ACIMA-A002 · Cross-module configuration key

**Severity** `warning` · **Level** L3 · **Principle** P1, P7

> A module MUST NOT read another module's configuration keys or secrets.

### Violation

```python
# orders/impl/shipping.py
rates_url = config["catalog.pricing.endpoint"]      # ❌ reading Catalog's configuration
```

### Finding

```
ACIMA-A002  warning  Orders reads the configuration key 'catalog.pricing.endpoint', which belongs to module catalog.
  src/acima/orders/impl/shipping.py:17
```

### Why

Configuration is part of a module's implementation surface. Reading another module's key means that
module can no longer rename, restructure or remove its settings, and that a deployment change in Catalog
silently breaks Orders. It also leaks secrets across module boundaries, which is a security issue rather
than an architectural one.

### Fix

Pass what the module needs as constructor configuration under its own namespace
(`orders.shipping.ratesUrl`), supplied by the host. If the value genuinely belongs to Catalog, ask
Catalog for it through a port — not through the configuration system.

### Detection

Key-prefix analysis: a read of a key whose first segment is another module's name. Warning severity
because shared infrastructure keys (`logging.*`, `otel.*`) are legitimate and must not fire.

---

## ACIMA-A003 · Cross-module mutable static state

**Severity** `error` · **Level** L3 · **Principle** P1, P7

> Modules MUST NOT communicate through shared mutable statics or global state.

### Violation

```csharp
public static class GlobalCache
{
    public static Dictionary<Guid, Product> Products { get; } = new();   // ❌ shared mutable state
}
```

```python
# catalog/impl/cache.py
PRODUCT_CACHE: dict[str, Product] = {}     # ❌ imported and mutated by Orders
```

### Finding

```
ACIMA-A003  error  orders imports and mutates the static state PRODUCT_CACHE owned by catalog.
  src/acima/orders/impl/pricing.py:9
```

### Why

Static state is a boundary crossing that no dependency graph can see, with no lifecycle, no ownership
and no isolation between tests. It also silently breaks the "extract to a service" promise: the state
cannot leave the process.

### Fix

Make the cache an instance owned by the module, injected into whatever needs it. If two modules need the
same cache, the host constructs one instance and passes it — still a dependency, still injectable, still
replaceable in tests.

### Detection

Identify module-level mutable declarations (`static` fields, module-level dict/list assignments,
`global` statements) and flag any access from outside the owning module.

---

## ACIMA-A004 · Version-lock coupling

**Severity** `warning` · **Level** L3 · **Principle** P7

> Consumers depend on a contracts version, never on an implementation version.

### Violation

```json
// orders/package.json
"dependencies": { "@acima/catalog": "1.4.2" }        // ❌ implementation package
```

### Finding

```
ACIMA-A004  warning  Orders depends on the implementation package @acima/catalog; depend on @acima/catalog-contracts.
  src/orders/package.json:12
```

### Why

Depending on the implementation version forces the consumer to upgrade when the provider's internals
change, which is precisely the coupling a contracts boundary is meant to remove. In a monorepo with
project references this shows up as "we all rebuild together"; in a package-based setup it shows up as a
version conflict nobody can resolve.

### Fix

Depend on `X.Contracts` (or its package), with a version range. If a consumer needs something only the
implementation offers, the boundary is wrong — see `D001`.

### Detection

Package manifests: any dependency on another module's implementation package/artifact from within the
product graph.

---

## Governance (`G`)

---

## ACIMA-G001 · Undocumented exception

**Severity** `error` · **Level** L1 · **Principle** P9

> Every waiver carries an owner, a reason, a scope, a review date and an expiry date.

### Violation

```json
{ "rule": "ACIMA-D001", "scope": "unit:orders" }        // ❌ no owner, reason or date
```

### Finding

```
ACIMA-G001  error  Waiver for ACIMA-D001 on unit:orders is missing owner, reason, expires, reviewedOn.
  .acima/waivers.json:4
```

### Why

An exception without an owner is nobody's problem; without a reason it cannot be reviewed; without an
expiry it is permanent. Undocumented exceptions are how a standards-compliant repository becomes a
non-compliant one with a clean build.

### Fix

Write every field, including the finding fingerprint. If you cannot name an owner or a date, the
exception is not a decision yet. A unit or path waiver without a fingerprint is rejected: it would
hide every future finding in that scope, not just the measured baseline.

### Detection

Validate the waivers file against its schema. Also validate that every waived rule id exists in the
catalogue — a typo must not silently excuse nothing.

---

## ACIMA-G002 · Expired waiver

**Severity** `error` · **Level** L1 · **Principle** P9

> An expired waiver no longer suppresses anything; the finding returns until it is fixed or renewed.

### Violation

```json
{ "rule": "ACIMA-C001", "scope": "unit:legacy", "fingerprint": "sha256:…",
  "owner": "team-a", "reason": "…", "expires": "2026-01-01", "reviewedOn": "2025-01-01" }
```

### Finding

```
ACIMA-G002  error  Waiver for ACIMA-C001 on unit:legacy expired on 2026-01-01 (owner: team-a).
  .acima/waivers.json:11
```

### Why

Expiry is the mechanism that makes waivers debt rather than permission. Without it, the file grows
monotonically and the architecture is whatever was true three years ago.

### Fix

Fix the code, or renew the waiver with a new date and a fresh review — and expect to explain why a year
was not enough.

### Detection

Compare `expires` to the current date at analysis time. Report expired waivers even when the underlying
finding no longer occurs: a stale waiver is also a finding, because it means nobody is reading the file.

---

## ACIMA-G003 · Undocumented contract surface

**Severity** `warning` · **Level** L2 · **Principle** P2

> Every public contract type documents its meaning, and its invariants where they exist.

### Violation

```csharp
public sealed record PlaceOrder(Guid CustomerId, IReadOnlyList<OrderLine> Lines);   // ❌ no docs
```

### Finding

```
ACIMA-G003  warning  Contract type PlaceOrder has no documentation.
  src/Acima.Orders.Contracts/PlaceOrder.cs:1
```

### Why

A contract is a promise; a promise nobody explained is a guess. Consumers will infer semantics from
names and types, and infer them wrong — particularly around units, nullability, idempotency and what
happens on failure.

### Fix

Document what it means and what must be true: units, required invariants, idempotency, failure
semantics. One or two sentences is enough; the rule is about presence, not volume.

### Detection

Presence of a doc comment (`///`, `/** */`, `"""`, Go doc comment, Javadoc) on every public type in a
contracts unit. Warning severity: it must be reported, not block a hotfix.

---

## ACIMA-G004 · Unreviewed contract change

**Severity** `error` · **Level** L2 · **Principle** P7

> A change to a published contracts surface is captured in the versioned API baseline.

### Violation

A breaking change (`ProductView.Price` changed from `Money` to `decimal`) with an unchanged
`.acima/api-surface.json`.

### Finding

```
ACIMA-G004  error  Breaking change to catalog.contracts: ProductView.Price (Money -> decimal).
  baseline: .acima/api-surface.json:14
```

### Why

Breaking a published contract is the one change that reaches beyond the repository. Capturing the
surface in a reviewed file means the change is visible in the pull request that causes it, which is the
only moment anyone has the context to decide whether it is acceptable.

### Fix

Either make the change additive (add a member, do not change one), or regenerate the baseline in the
same commit and mark the release as breaking. Both are fine; doing it silently is not.

### Detection

Compute the current public surface of every contracts unit, compare with the baseline; classify each
difference as additive or breaking. Regeneration is an explicit command, never automatic.

---

## ACIMA-G005 · Unclassified source

**Severity** `error` · **Level** L1 · **Principle** P8

> Every production source file belongs to a declared unit.

### Violation

A new directory `src/acima/analytics/` appears with no entry in `acima.config.json`.

### Finding

```
ACIMA-G005  error  Source file is not part of any declared unit: src/acima/analytics/report.py
  src/acima/analytics/report.py:1
```

### Why

A file that belongs to no unit is checked by no rule, and the architecture test still passes — which is
the most dangerous outcome, because it looks like success. Undeclared modules are how a compliant
codebase quietly acquires a non-compliant one.

### Fix

Declare the unit, with a role and a module name. If it is a new module, follow the checklist in
[Module anatomy](../standard/03-module-anatomy.md#36-adding-a-module-the-checklist).

### Detection

After classification, any production source file with no unit is a finding. `exclude` patterns are
applied first, so fixtures and tests never fire this.
