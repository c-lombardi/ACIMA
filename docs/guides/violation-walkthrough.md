# Violation walkthrough

This is the guided tour of everything ACIMA prohibits. Every section shows the offending code,
the finding the enforcer produces, why the rule exists, and what to write instead.

The fixtures live in `examples/<language>/violations/`. Each one is compiled into the gallery
run, and each one appears in that language's `violations/expected.json`. If a rule stops
firing, conformance fails — a rule that detects nothing is treated as a broken rule, not a
satisfied one.

Run the tour yourself:

```bash
cd examples/typescript && node tools/acima-arch.mjs --root . --config acima.gallery.config.json
cd examples/python     && python3 tools/acima_arch.py --root . --config acima.gallery.config.json
cd examples/go         && go run ./tools/archtest --root . --config acima.gallery.config.json
cd examples/dotnet     && dotnet run --project tools/Acima.ArchTests -- --root . --config acima.gallery.config.json
```

Not every language fires every rule. Python executes 42 automated rules, TypeScript 41 and .NET
42; Go executes 27. Go executes `G006` from direct `go.mod` requirements against
`approvedDependencies` and `N002` over type declarations, and reports the four tier rules (`L005`–`L007`, `D010`), the value rule
(`A006`), the two composition rules (`D013`, `D014`), the functional-capture rule (`D016`), the
three lifecycle rules (`A007`–`A009`) and `N001` `executed: false`.
Go also reports the explicit-input rules (`D011`, `D012`)
`executed: false`; TypeScript and Go report `D017` as not executed because they have no native
named-call syntax. The fourteen manual rules, including `N003`, report `executed: false` in every
language. Each profile documents
the other constructs it cannot see; the gaps are listed in [the language profiles](../languages/index.md).

---

## Dependency violations

### `ACIMA-D001` — implementation references another implementation

```ts
// violations/d001_d009_impl_impl.ts
// acima-unit: catalog
import { OrdersModule } from '../src/orders/impl/module.ts';
```

```
ACIMA-D001  error   Module catalog imports the implementation unit orders (expected orders.contracts).
  violations/d001_d009_impl_impl.ts:2
  import { OrdersModule } from '../src/orders/impl/module.ts';
```

**Why.** `Orders` is free to rename, split or delete `OrdersModule` at any time. Importing it
welds two modules into one deployment unit and makes the second impossible to extract.

**Instead.** Depend on `orders.contracts`. If the capability you need is not there, that is a
contract-design conversation, not an import.

### `ACIMA-D002` — contracts reference an implementation

```ts
// acima-unit: orders.contracts
import { CatalogModule } from '../src/catalog/impl/module.ts';

export interface SneakyOrder { readonly catalog: CatalogModule; }
```

**Why.** This is the same coupling as `D001` with worse consequences: the violation is now part
of the *published* surface, so every consumer of Orders inherits Catalog's implementation.

**Instead.** Contracts expose an interface owned by the consumer (P4). Orders declares
`interface CatalogReader`; the host passes Catalog's adapter in.

### `ACIMA-D003` — contracts reference another module's contracts

```ts
// acima-unit: orders.contracts
import type { ProductView } from '../src/catalog/contracts/index.ts';
```

**Why.** ACIMA is stricter than most published guidance here. If `orders.contracts` depends on
`catalog.contracts`, Catalog cannot version without recompiling Orders, and the two contract
packages must always be released together. That is not independent evolution.

**Instead.** Use identity (`ProductId`) or duplicate the two or three fields you actually need in
`orders.contracts`. The default declares value types locally; a shared kernel is a legacy migration
allowance, not a new-contract option.

### `ACIMA-D004` — contracts depend on a third-party package

```ts
// acima-unit: catalog.contracts
import { z } from 'zod';
export const schema = z.object({ name: z.string() });
```

**Why.** A contract that carries a validator, an ORM attribute or a JSON library forces that
package and its version on every consumer. P3 says contracts depend on the language core; the shared
kernel is a legacy compatibility allowance, not a default dependency.

**Instead.** Validate in the implementation; expose plain data in the contract.

### `ACIMA-D005` — a cycle between modules

```ts
// acima-unit: catalog
import { b } from './d005_cycle_b.ts';
export const a = (): number => b() + 1;
```

```
ACIMA-D005  error   Circular module dependency: catalog -> orders -> catalog
```

**Why.** A cycle means neither module can be built, tested, released or extracted alone. It is
the failure mode the contract split exists to make structurally impossible.

**Instead.** Find the direction that is wrong and invert it: the module being depended upon
should publish the abstraction, or the cycle should be broken by an event.

### `ACIMA-D006` — a unit references the host

```ts
// acima-unit: catalog.contracts
import { catalog } from '../src/host/main.ts';
```

**Why.** The host is the only unit allowed to know everyone. If a module knows the host, the
dependency graph has no top, and the composition root can no longer be replaced by a test
harness.

**Instead.** The host depends on modules; nothing depends on the host.

### `ACIMA-D007` — the shared kernel is not a leaf

```go
// acima-unit: shared-kernel
import catalogcontracts "acima.example/internal/catalog/contracts"
```

**Why.** The kernel is what every module is allowed to depend on. The moment it depends on one
module, that module becomes special and the kernel becomes a back door into it.

**Instead.** A shared kernel contains value types with no dependencies, or it contains nothing.

### `ACIMA-D008` — transitive reach into an implementation

```ts
// acima-unit: catalog
import { cart } from './a003_static.ts';
```

```
ACIMA-D008  error   catalog reaches the implementation unit orders transitively through orders.contracts.
```

**Why.** You did not write the offending import; it arrived through a chain. That is precisely
why it needs a rule: transitive coupling is invisible in review and obvious in the graph.

**Instead.** Depend on the contract that exposes the behaviour, not on a package that happens
to re-export the implementation.

### `ACIMA-D009` — private identifiers crossing a boundary

```go
// acima-unit: catalog
import . "acima.example/internal/orders/impl"
```

**Why.** A dot-import dumps another module's entire namespace into yours, including names that
were never intended to be public. In languages with real visibility (`internal`, package-private,
unexported) this cannot even be expressed, which is the point: make the private surface
unimportable rather than politely ask.

**Instead.** Import the contract package with a name, or widen the contract deliberately.

---

## Layering violations

### `ACIMA-L001` — the domain talks to the database

```ts
// acima-unit: catalog
import { prisma } from 'zod';
export const load = async () => prisma.query('select 1');
```

**Why.** Once a domain type holds a database handle, it cannot be tested without one, and the
persistence choice becomes part of the domain model.

**Instead.** Define a repository port in the module's own contracts or implementation, and put
the adapter in `infrastructure/`.

### `ACIMA-L002` — contracts expose a framework type

```ts
// acima-unit: orders.contracts
import { Router } from 'express';
export interface OrderRoute { readonly router: Router; }
```

**Why.** The contract now says "this capability is HTTP-shaped". Every non-HTTP consumer — a
worker, a CLI, a test — must depend on the web framework to call it.

**Instead.** Describe the capability in domain terms; let the host adapt it to HTTP.

### `ACIMA-L003` — an implementation type is public API

```
ACIMA-L003  error   implementation unit catalog publishes the public type CatalogModule outside the module
  src/catalog/impl/module.ts:1
```

**Why.** An exported class in an implementation unit is a public API with no contract, no
versioning and no documentation. Consumers will find it.

**Instead.** Keep implementation types internal to the module, or move the type into contracts
if it is genuinely part of the promise.

---

## Contract-shape violations

### `ACIMA-C001` — mutable contract state

```ts
// acima-unit: catalog.contracts
export interface CatalogDraft {
  name: string;          // no readonly
}
```

**Why.** A message that can be mutated by its consumer is a shared variable. It makes caching
unsafe, testing order-dependent and concurrency a lottery.

**Instead.** `readonly name: string`, `readonly struct`, `frozen dataclass`, or value semantics.

### `ACIMA-C002` — mutable collection exposure

```ts
export interface PaymentBatch {
  readonly payments: PaymentBatchItem[];   // readonly binding, mutable array
}
```

**Why.** `readonly` protects the field, not the contents. A caller can still `push`, `splice`
or `sort` the array the contract handed them.

**Instead.** `readonly payments: readonly PaymentBatchItem[]`, `IReadOnlyList<T>`,
`Sequence[T]`, or return a defensive copy.

### `ACIMA-C004` — ambient state in a contract

```ts
// acima-unit: orders.contracts
export const timestamp = (): Date => new Date();
```

**Why.** A contract that reads the clock, the random generator or the environment cannot be
replayed. Recording and replaying events stops reproducing the same result.

**Instead.** Put the timestamp in the message: `placedAt` is data the caller supplies.

### `ACIMA-C005` — persistence types in a contract

```ts
import type { DbContext } from 'zod';
export interface PaymentRow { readonly db: DbContext; }
```

**Why.** The contract now depends on the database. It cannot be used by a consumer that has no
database, and it cannot be versioned independently of the schema.

**Instead.** Contracts carry data; repositories carry the database.

### `ACIMA-C006` — untyped contract members

```ts
export interface Envelope { Payload any }
```

**Why.** `any`, `object`, `interface{}` and `unknown` move the type system's job to runtime
casting, at the one boundary where precision matters most.

**Instead.** Name the shape. If the shape is open, model it as a discriminated union.

---

## Autonomy violations

### `ACIMA-A001` — reading another module's schema

```go
// acima-unit: catalog
const Stolen = "select * from orders_headers where id = '1'"
```

**Why.** The table is `orders`' private state. Reading it couples Catalog to Orders' schema and
silently breaks the day Orders renames a column — with no compile error and no test failure.

**Instead.** Call the contract, or subscribe to an event. Data you do not own is not yours to
query.

### `ACIMA-A003` — cross-module mutable static state

```go
// acima-unit: orders
var Cart = map[string]int{}
```

```go
// acima-unit: catalog
func Mutate() { orders.Cart["x"] = 1 }
```

**Why.** A package-level mutable map is shared memory across every consumer in the process. It
defeats independent evolution, makes tests order-dependent, and cannot be scaled out.

**Instead.** Own the state inside the module and expose a capability that mutates it under the
module's rules.

---

## Governance violations

### `ACIMA-G001` — an incomplete waiver

```json
{ "rule": "ACIMA-A001", "scope": "unit:catalog", "owner": "", "reason": "legacy report" }
```

**Why.** A waiver without an owner is nobody's decision. P9 requires every exception to be
owned, justified, scoped and dated, because an unowned exception is permanent by default.

**Instead.** Fill every field, including `owner`, `reason`, `expires` and `reviewedOn`.

### `ACIMA-G002` — an expired waiver

```json
{ "rule": "ACIMA-D009", "owner": "team-orders", "expires": "2020-01-01" }
```

**Why.** Expiry is what turns a waiver into a ratchet. Without it, "temporary" means "until
someone remembers", which is never.

**Instead.** Renew deliberately with a new date and a new reason, or fix the violation.

### `ACIMA-G003` — an undocumented contract

```ts
// acima-unit: catalog.contracts
export interface UnnamedThing { readonly id: string; }
```

**Why.** The contract is the only thing a consumer reads. A public type with no explanation is
a reverse-engineering task, and the semantics that are not written down are the ones that get
broken by accident.

**Instead.** Document the type and every member that is not self-evident.

### `ACIMA-G005` — a file that belongs to no unit

```
ACIMA-G005  error   Source file is not part of any declared unit: violations/g005_orphan.ts
```

**Why.** Unclassified code is ungoverned code. It is subject to no rule, owned by no module,
and will be imported by the first person who finds it convenient.

**Instead.** Declare the unit, move the file, or delete it.

---

## Rules without fixtures

Fourteen rules are in the catalog but not in the portable enforcer, because detecting them needs
information the source text does not carry:

| Rule | Why it has no fixture |
|---|---|
| `ACIMA-C003` behaviour in contracts | a method is only a violation if it contains business logic, IO or orchestration; that is a semantic judgment |
| `ACIMA-C007` constructor validation | needs to know whether a guard clause is present and correct, which is a semantic judgment |
| `ACIMA-C008` business behaviour visibility | whether an operation makes its outcome, failures and effects visible is a semantic judgment |
| `ACIMA-L004` service locator | resolving a dependency through a container is framework-specific |
| `ACIMA-A002` shared configuration keys | configuration APIs differ per ecosystem |
| `ACIMA-A004` version-lock coupling | only observable across published packages |
| `ACIMA-A010` effect ownership | the owner and execution boundary are design intent, not syntax |
| `ACIMA-A011` effect semantics | retry, duplicate, consistency and cancellation semantics require failure-path reasoning |
| `ACIMA-A012` outcome truthfulness | whether an outcome represents a durable commit or an unknown remote state requires design context |
| `ACIMA-A013` critical-effect evidence | criticality and evidence proportionality are business judgments |
| `ACIMA-G004` API baseline | needs a per-language surface format |
| `ACIMA-N003` naming clarity | whether a name communicates responsibility, side effects and units is a semantic judgment |

They remain normative. They are enforced by native analyzers, review, or the per-language
tooling named in [analyzers-and-linters.md](analyzers-and-linters.md). A clean portable run says
nothing about them, and a full claim needs repository-scoped evidence.

## Adding a fixture

1. Create the smallest file that breaks exactly one rule.
2. Put `acima-unit: <unit>` in the first three lines so the enforcer can classify it.
3. Run the gallery config and confirm the rule fires.
4. Add the rule and path to `violations/expected.json`.
5. Run the language's architecture test.

Step 3 is not optional. A fixture that does not fire is a test of nothing.
