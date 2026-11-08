//go:build ignore

// acima-unit: catalog.contracts
package catalogcontracts

import catalogcontracts "acima.example/internal/catalog/contracts"

// Draft exposes a pointer, so any consumer can rewrite the price.
type Draft struct {
	Price *catalogcontracts.Money
}
