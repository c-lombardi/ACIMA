//go:build ignore

// acima-unit: shared-kernel
package sharedkernel

import catalogcontracts "acima.example/internal/catalog/contracts"

// Product makes the kernel depend on a module.
type Product struct {
	View catalogcontracts.ProductView
}
