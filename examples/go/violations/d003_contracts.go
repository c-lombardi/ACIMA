//go:build ignore

// acima-unit: orders.contracts
package orderscontracts

import catalogcontracts "acima.example/internal/catalog/contracts"

// Coupled depends on another module's contract.
type Coupled struct {
	Product catalogcontracts.ProductView
}
