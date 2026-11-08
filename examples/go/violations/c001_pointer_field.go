//go:build ignore

// acima-unit: catalog.contracts
package catalogcontracts

import "acima.example/internal/sharedkernel"

// Draft exposes a pointer, so any consumer can rewrite the price.
type Draft struct {
	Price *sharedkernel.Money
}
