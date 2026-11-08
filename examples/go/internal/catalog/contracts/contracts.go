// Package catalogcontracts is Catalog's complete public surface.
// It imports only the shared kernel.
package catalogcontracts

import "acima.example/internal/sharedkernel"

// ProductView is a purchasable product as other modules see it.
type ProductView struct {
	ID    sharedkernel.ProductID
	Name  string
	Price sharedkernel.Money
}

// Reader is the capability Catalog promises.
type Reader interface {
	Get(id sharedkernel.ProductID) (ProductView, bool)
	All() []ProductView
}
