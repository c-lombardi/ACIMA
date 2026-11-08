# TypeScript profile

Node 22+ · TypeScript 5 · ESM · one directory per unit, one package entry point per contracts unit.

## 1. Layout

```
src/
  shared-kernel/money.ts             shared-kernel
  catalog/contracts/index.ts         contracts   (public entry point)
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
- the shared kernel.

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
      "@acima/shared-kernel": ["./src/shared-kernel/index.ts"],
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
