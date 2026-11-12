# TypeScript profile

Node 22+ · TypeScript 5 · ESM · one directory per unit, one package entry point per contracts unit.

> **Reference example.** The tree below is the compiled example in `examples/typescript`. It uses the
default: every contracts package imports nothing and owns its value types; see
[section 6](#6-service-topology-profile).

## 1. Layout

```
src/
  catalog/contracts/index.ts         contracts   (public entry point)
  catalog/contracts/values.ts        contract-owned Money and ids
  catalog/impl/*.ts                  implementation
  orders/contracts/index.ts          contracts
  orders/impl/*.ts                   implementation   → catalog/contracts, payments/contracts
  payments/contracts/index.ts        contracts
  payments/impl/*.ts                 implementation
  host/main.ts                       host         → everything
tools/acima-arch.mjs                 tooling
violations/                          fixtures (excluded from the build)
```

The boundary is **the import specifier**. Consumers may only import:

- `@acima/catalog-contracts` (the alias for `src/catalog/contracts/index.ts`), or
- the contracts entry point of another module.

Everything under `*/impl/` is off limits, and the lint rule plus the alias make the forbidden import
awkward to write, which is the TypeScript equivalent of a compiler error.

## 2. What the toolchain enforces without help

| Obligation | Mechanism |
|---|---|
| Contracts have no dependency | `package.json` `exports` map exposes only `index.ts`; nothing is re-exported from `impl` |
| No transitive leak | `"sideEffects": false` and no barrel re-export of `impl` |
| Immutability, at least for rebinding | `readonly` modifiers + `Readonly<T>` — **not enough on its own** (`C002`) |
| Import bans, author time | `no-restricted-imports` with a pattern per module |

```jsonc
// eslint.config.js (excerpt)
{
  "rules": {
    "no-restricted-imports": ["error", {
      "patterns": [
        { "group": ["**/impl/*", "**/impl"], "message": "ACIMA-D001/D009: import the contracts unit instead." },
        { "group": ["**/catalog/contracts/*"], "message": "Use @acima/catalog-contracts." }
      ]
    }]
  }
}
```

```jsonc
// tsconfig.json (excerpt) — the alias is the only legal way to reach another module
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "paths": {
      "@acima/catalog-contracts": ["./src/catalog/contracts/index.ts"],
      "@acima/orders-contracts": ["./src/orders/contracts/index.ts"],
      "@acima/payments-contracts": ["./src/payments/contracts/index.ts"]
    }
  },
  "exclude": ["violations", "node_modules"]
}
```

`exactOptionalPropertyTypes` matters more than it looks: without it, `foo?: string` silently accepts
`undefined`, which is how contracts acquire ambiguous optionality (`C007`).

## 3. Architecture tests

**Idiomatic:** [`dependency-cruiser`](https://github.com/sverweij/dependency-cruiser) for the dependency
graph, `eslint` for shapes, `tsd`/`expect-type` for contract types.

```js
// .dependency-cruiser.js (excerpt)
module.exports = {
  forbidden: [
    { name: 'acima-d001', severity: 'error',
      from: { path: '^src/([^/]+)/impl' }, to: { path: '^src/(?!\\1)([^/]+)/impl' } },
    { name: 'acima-d003', severity: 'error',
      from: { path: '^src/([^/]+)/contracts' }, to: { path: '^src/(?!\\1)([^/]+)/contracts' } },
    { name: 'acima-d004', severity: 'error',
      from: { path: '^src/[^/]+/contracts' }, to: { path: 'node_modules' } }
  ]
};
```

**Reference runner (this repository):** `tools/acima-arch.mjs`, driven by `node:test`.

```bash
npm test                      # runs behaviour tests + architecture tests
node tools/acima-arch.mjs --root . --format json
```

It parses import specifiers (static `import`, `export … from`, `import()`), resolves them to files,
classifies units, and checks the contract-shape rules with a lightweight source scan. No TypeScript
compiler needed: the runner must work in a repository whose build is broken, because that is exactly
when someone adds a bad import.

## 4. Analyzers and linters

| Tool | Catches | Notes |
|---|---|---|
| `@typescript-eslint` (`no-restricted-imports`, `explicit-module-boundary-types`) | `D001`, `D003`, `D009` | author-time, per package boundary |
| `dependency-cruiser` | `D001`–`D009` | graph rules, including transitive |
| `eslint-plugin-immutable` / `functional` | `C001`, `C002` | opinionated; enable per package |
| `typescript-eslint` `no-explicit-any` | `C006` | requires `strict` |
| **custom ESLint rule** | `C004` (`new Date()`, `Date.now()`, `crypto.randomUUID()` in contracts) | ~50 lines with the TS AST |

## 5. Idioms and pitfalls

| Trap | Rule | Fix |
|---|---|---|
| `readonly lines: OrderLine[]` | `C002` | `readonly lines: readonly OrderLine[]` |
| `interface` with optional members only | `C007` | required members in the constructor/factory |
| `export * from './impl/…'` in a contracts barrel | `D008` | the barrel is the boundary; never re-export `impl` |
| `import type { Order } from '../../orders/impl/order'` | `D009` | `import type` is still a dependency — it leaks the shape |
| `any` in a payload | `C006` | discriminated union per event |
| `class` with public fields in contracts | `C001` | `readonly` + constructor, or a plain type |
| Path aliases added ad hoc in `tsconfig` | `D009` | aliases are the contract surface; adding one is an architecture change |
| `enum` in contracts | — | legal (a language construct), but prefer string unions for serialization stability |

### One TypeScript-specific note

`import type` is erased at runtime but it is not erased from your architecture: it still ties the
consumer's compilation to the provider's internal shape, and it breaks as soon as the provider renames a
type. The runner flags type-only imports exactly like value imports.

### Explicit inputs (`D011`, `D012`)

`constructor(store: Store = new InMemoryStore())` and `create(request, notify = true)` are the two
shapes the rule reports. `payments?: Payments` is optional; `payments: Payments | null` is required and
legal — the caller chooses `null`. `exactOptionalPropertyTypes` keeps that distinction honest in
contracts. The reference enforcer scans constructors, class methods and `function` declarations; an
arrow function assigned to a variable is not scanned, so a default in `const f = (x = 1) => …` is a
review item, not a finding. Contracts, tests and tooling are out of scope (chapter 13).

### Values and configuration (`A005`, `A006`)

Define a `readonly` settings interface and require it in the constructor; resolve `process.env` once in
the host and pass the validated object in. The enforcer scans implementations and adapters for `process.env`/`import.meta.env` (`A005`). For
`A006` it scans implementation, adapter and host roles for meaningful inline literals, mutable
`let`/`var` or writable properties, and same-module duplicate immutable declarations. `const` and
`readonly` fields satisfy the immutability check; a readonly reference does not make its object
immutable. Local calls are traced to the callee's receiving parameter where both are in the same
file, and `capacity`, `threshold`, `secret` and similar names are candidate evidence. Every finding
is a candidate: static analysis cannot prove semantic equivalence, units or the highest appropriate
owner. Default parameters are `D012`'s concern, not `A006`'s. Destructuring defaults, aliases and
string contents are not parsed; an arrow function that embeds a timeout remains a manual review
item when the scanner cannot trace it.

### Composition and injection (`D013`, `D014`)

Construct at the host with `new CatalogModule(new InMemoryProductStore())`, or use an explicit
factory that names the implementation. `import.meta.glob` and `require.context` are `D013` candidates
when they select module-owned components; dynamic asset loading is not the same thing. Property
decorators such as `@Inject` above a field are `D014` candidates. Constructor parameter decorators are
not property injection: the dependency is still part of the declared constructor. NestJS/Angular
controllers may be framework-activated, but their application dependencies belong in the constructor
and the host must register the implementation.The scanner does not execute decorators or resolve a container.

### Functional capture (`D015`, `D016`)

A function or arrow must declare every collaborator it uses. Currying is allowed when each layer
declares its dependency; a module-level repository captured by an arrow is `D015`. `partial` and
`.bind` of a collaborator inside an implementation/adapter are `D016`; the same binding at the host
is valid composition. Pure HOFs and closures over value parameters are not findings. The scanner
does not type-check, resolve framework callbacks or evaluate dynamic dispatch.

### Lifecycle and state ownership (`A007`–`A009`)

Decide lifetime at the host: a stateless service is shared, request- or tenant-bound state is scoped,
and a shared service does not retain either. Registrations of the form
`register(Class, { lifetime: 'transient' })` and `addSingleton`/`addScoped`/`addTransient` are read by
the reference scanner. `A007` reports a transient registration whose class has no mutable field;
`A008` reports a shared class whose constructor declares a dependency registered scoped; `A009`
reports a shared class that initialises a mutable container. A module-level `export const service =
new Service(...)` is a process singleton regardless of the DI framework and is a manual-review item.
So are decorator scopes, factory closures, callback registrations and framework-managed providers.
A mutable field is not proof of a race, and sharing is not proof of thread safety: record the
owner, isolation key, synchronization, eviction and cleanup policy (chapter 17).

### Intent-revealing naming (`N001`–`N003`)

Types, interfaces, enums and React components use `PascalCase`; functions, variables and parameters
use `camelCase`. Name the responsibility (`OrderValidator`), not a generic role (`OrderHelper`).
Names must not hide a write behind `get*`, and units belong in the name when the type does not
carry them. `N001` checks type casing and `N002` checks generic type names; both are candidates.
`N003` is manual: side effects, boolean polarity, domain terminology, abbreviations, units and
context need review. Generated declarations, framework-required hook/component names and external
contract names need an owned exception (chapter 18).

## 6. Service topology profile

Chapter 11's naming maps to npm workspaces:

```
services/orders/
  orders.api/                       @acme/orders.api
  orders.api.contracts/             @acme/orders.api.contracts
  orders.application/               @acme/orders.application
  orders.application.contracts/     @acme/orders.application.contracts
  orders.domain/                    @acme/orders.domain
  orders.infrastructure/            @acme/orders.infrastructure
  orders.integrations.stripe/       @acme/orders.integrations.stripe
  orders.integrations.stripe.contracts/
  orders.catalog/                   messages orders -> catalog
  orders.host/                      composition root
```

### A contracts package with no dependencies

```json
{
  "name": "@acme/orders.application.contracts",
  "version": "1.0.0",
  "type": "module",
  "exports": { ".": "./src/index.ts" },
  "dependencies": {}
}
```

```ts
// src/index.ts
export interface OrderLine {
  readonly productId: string;
  readonly amount: number;
  readonly currency: string;
  readonly quantity: number;
}

export interface PlaceOrder {
  readonly customerId: string;
  readonly lines: readonly OrderLine[];
}

export type PlaceOrderResult =
  | { readonly accepted: true; readonly orderId: string }
  | { readonly accepted: false; readonly rejection: string };

export interface PlaceOrderHandler {
  handle(command: PlaceOrder): PlaceOrderResult;
}
```

No `zod`, no `class-validator`, no `date-fns`, no shared kernel package. Validation functions may
live in the contracts package if they use only the language runtime; they must not read clocks or
random sources (C004). Serialization is configured by the caller.

### Layer references

| Package | May import | Never imports |
|---|---|---|
| `orders.api` | `orders.api.contracts`, `orders.application.contracts` | `orders.application`, `orders.domain` |
| `orders.application` | `orders.application.contracts`, `orders.domain`, `orders.integrations.stripe.contracts` | `orders.api`, `orders.infrastructure` |
| `orders.domain` | language core only | any contracts package, any runtime dependency |
| `orders.infrastructure` | `orders.domain` ports, driver packages | `orders.api` |
| `orders.integrations.stripe` | `orders.integrations.stripe.contracts`, `stripe` | `orders.domain` |
| `orders.host` | everything | — |

The API maps its DTOs to `PlaceOrder` explicitly; it does not pass a request object through.
`tsconfig` project references make the same graph visible to `tsc --build`.

### Third-party isolation

`orders.integrations.stripe.contracts` exports `StripeGateway` and its request/result types with an
empty dependency list. `orders.integrations.stripe` imports that package and `stripe`, implements the
gateway, and maps vendor errors. A `Stripe` type in `orders.domain` is an ST-8 failure.

### Domain tests

```bash
npm test --workspace @acme/orders.domain -- --coverage --coverage.thresholds.lines=100
```

Coverage thresholds live in the domain workspace's config, not at the root, so another package cannot
lower them. Test names state the rule. The domain package's `dependencies` stay empty.

### What the toolchain checks without help

`npm ls --workspace @acme/orders.application.contracts --all` must show only the package itself.
`tsc --build` refuses an undeclared project reference. `dependency-cruiser` or
`eslint-plugin-boundaries` can encode the layer table; `@microsoft/api-extractor` records the
published surface for G004.

### Named call arguments (D017)

TypeScript/JavaScript has no native named-argument call syntax. The reference enforcer reports
D017 as executed:false rather than requiring artificial object wrappers or claiming ordinary
object properties are equivalent to native call-site labels. Use a request object when it is
already the natural contract for the operation, not solely to imitate named arguments.
