//go:build ignore

// acima-unit: orders.contracts
package orderscontracts

import catalog "acima.example/internal/catalog/impl"

// Sneaky reaches into an implementation.
type Sneaky struct {
	Catalog *catalog.Module
}
