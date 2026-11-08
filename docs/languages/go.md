# Go profile

Go 1.23 · one module · packages per unit · `go test ./...` as the gate.

## 1. Layout

```
go.mod                          module github.com/acima/example
sharedkernel/money.go           shared-kernel
catalog/contracts/contracts.go  contracts
catalog/internal/...            implementation   (compiler-enforced private)
orders/contracts/contracts.go   contracts
orders/internal/...             implementation   → catalog/contracts, payments/contracts
payments/contracts/contracts.go contracts
payments/internal/...           implementation
cmd/host/main.go                host
tools/archtest/                 tooling
violations/                     fixtures, excluded by build tag
```

## 2. What the toolchain enforces without help

Go is the only language here where the compiler enforces ACIMA's core rule:

```go
// orders/internal/service.go
import "github.com/acima/example/catalog/internal/repo"   // compile error:
// use of internal package not allowed
```

`internal/` is importable only by packages rooted at its parent, so `catalog/internal` is unreachable
from `orders` — `D001` and `D009` cannot be violated by a direct import. Everything else still needs
the architecture test, and Go's own tooling helps:

| Obligation | Mechanism |
|---|---|
| Implementation private | `internal/` (compiler) |
| No cycles | `go build` refuses import cycles (package level) |
| Contracts have no dependency | `go list -deps` on the contracts package must contain only stdlib + kernel |
| Immutability | unexported fields + constructor + accessor returning a copy (`C001`, `C002`) |
| No untyped payload | `interface{}`/`any` denylist (`C006`) |

## 3. Architecture tests

**Idiomatic:** `go vet` with a custom `analysis.Analyzer`, or a plain `_test.go` that walks the source
tree. This repository uses the second, because it needs no external module:

```go
func TestArchitecture(t *testing.T) {
    findings := archtest.Run(t, archtest.Options{Root: "..", Config: "acima.config.json", Level: "L2"})
    archtest.AssertClean(t, findings)
}
```

```bash
go test ./...
go run ./tools/archtest --root . --format json
```

**Reference enforcer (this repository):** `tools/archtest` — uses `go/parser` and `go/ast`, so it sees
real imports and real declarations, not text. It classifies packages from `acima.config.json` (Go needs
the config too: `internal/` prevents cross-module *imports*, but not cross-module copies of a contracts
type, SQL strings, or mutable exported state).

## 4. Analyzers and linters

| Tool | Catches | Notes |
|---|---|---|
| `go vet` + custom `analysis.Analyzer` | `D001`–`D009`, `C004` | the production answer: runs in `go vet ./...` |
| `depguard` (golangci-lint) | `D001`, `D003`, `D009` import bans | one rule per module, config-driven |
| `golangci-lint` (`revive`, `gocritic`) | exported field checks, style | `revive:exported` helps `L003` |
| `staticcheck` | `SA1019` deprecations, unused code | not ACIMA, but keeps the surface honest |
| **`exhaustruct`** | struct literals missing required fields | a concrete `C007` helper |

```yaml
# .golangci.yml (excerpt)
linters-settings:
  depguard:
    rules:
      no-catalog-internals:
        files: ["**/orders/**"]
        deny:
          - pkg: "github.com/acima/example/catalog/internal"
            desc: "ACIMA-D001: use catalog/contracts"
```

## 5. Idioms and pitfalls

| Trap | Rule | Fix |
|---|---|---|
| Exported struct fields in `contracts` | `C001`, `C002` | unexported fields + `New…` constructor + accessors; use tags only on transport types |
| `Items []Item` with an accessor returning the slice | `C002` | `func (o Order) Items() []Item { return slices.Clone(o.items) }` |
| `map[string]any` payload | `C006` | one struct per event |
| `time.Now()` in a contracts constructor | `C004` | pass `time.Time` in |
| A second `go.mod` per module | — | legal, and the strongest expression of `P7`; it makes `D001` a compile error and `A001` a build-tag problem |
| `//go:build` tagged violation fixtures | — | always exclude fixtures from the product build |
| Copying a contracts struct into `internal/` and adding methods | `C003` | methods belong in the implementation, not on the contract type |

### One Go-specific note

Go's structural typing means a consumer can satisfy a provider's interface without importing it, which
is `P4.3` (consumer-owned ports) for free. Use it: declare the narrow interface you need in your own
package, and let the provider's concrete type satisfy it implicitly. That is the most idiomatic
expression of consumer-owned abstraction in any language in this standard.
