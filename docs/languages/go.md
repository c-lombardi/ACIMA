# Go profile

Go 1.23 · one module · packages per unit · `go test ./...` as the gate.

> **Compatibility example.** The tree below is the legacy shape with a shared kernel. Under the
default, contracts reference nothing; see [section 6](#6-service-topology-profile).

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
| Contracts have no dependency | `go list -deps` on the contracts package must contain only stdlib (the legacy example may also show the kernel) |
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

## 6. Service topology profile

Chapter 11's naming maps to packages, with `internal/` doing the ownership work:

```
services/orders/
  api/                              import .../services/orders/api
  api/contracts/                    .../services/orders/api/contracts
  application/                      .../services/orders/application
  application/contracts/            .../services/orders/application/contracts
  internal/domain/                  .../services/orders/internal/domain
  internal/infrastructure/          .../services/orders/internal/infrastructure
  integrations/stripe/              .../services/orders/integrations/stripe
  integrations/stripe/contracts/    .../services/orders/integrations/stripe/contracts
  contracts/catalog/                .../services/orders/contracts/catalog
  cmd/orders-host/main.go
```

Domain and infrastructure live under `internal/`, so no other service can import them. Contracts and
inter-service contracts are outside it, because they are the surface other services consume.

### A contracts package with no third-party imports

```go
// services/orders/application/contracts/contracts.go
package contracts

type OrderLine struct {
    ProductID string
    Amount    string // decimal as a string at the boundary
    Currency  string
    Quantity  int
}

type PlaceOrder struct {
    CustomerID string
    Lines      []OrderLine
}

type PlaceOrderResult struct {
    Accepted  bool
    OrderID   string
    Rejection string
}

type PlaceOrderHandler interface {
    Handle(PlaceOrder) PlaceOrderResult
}
```

Stdlib only. `Money` is the primitive pair or a type declared in this package; it does not come from
a shared kernel. Constructors (`NewOrderLine`) may validate and return an error; they must not read a
clock or generate an id (C004).

### Layer references

| Package | May import | Never imports |
|---|---|---|
| `api` | `api/contracts`, `application/contracts` | `application`, `internal/domain` |
| `application` | `application/contracts`, `internal/domain`, `integrations/stripe/contracts` | `api`, `internal/infrastructure` |
| `internal/domain` | stdlib only | any contracts package, any third-party package |
| `internal/infrastructure` | `internal/domain`, driver packages | `api` |
| `integrations/stripe` | `integrations/stripe/contracts`, Stripe SDK | `internal/domain` |
| `cmd/orders-host` | everything | — |

The API maps its request type to `contracts.PlaceOrder`; it does not pass the HTTP struct through.
Go's `internal/` rule makes the domain unimportable from another service without any custom tool.

### Third-party isolation

`integrations/stripe/contracts` declares `StripeGateway` and the request/result structs, importing
only stdlib. `integrations/stripe` imports that package and the vendor SDK, implements the gateway
and maps vendor errors. A vendor import in `internal/domain` is an ST-8 failure.

### Domain tests

```bash
go test -cover -coverprofile=coverage.out ./services/orders/internal/domain/...
go tool cover -func=coverage.out
```

Gate the domain package at 100% statement coverage and add table-driven cases for every rule and
boundary. Test names state the rule (`TestPlaceOrder_RejectsMoreThanAvailableStock`).

### What the toolchain checks without help

`go list -deps ./services/orders/application/contracts` must show only stdlib. `go list -deps` also
proves the domain imports no vendor package. `go vet` and `staticcheck` catch type leaks; the
`internal/` rule enforces the service boundary at compile time.
