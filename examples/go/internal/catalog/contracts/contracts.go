// Package catalogcontracts is Catalog's complete public surface.
// It imports nothing outside the standard library.
package catalogcontracts

// ProductView is a purchasable product as other modules see it.
type ProductView struct {
	ID    ProductID
	Name  string
	Price Money
}

// Reader is the capability Catalog promises.
type Reader interface {
	Get(id ProductID) (ProductView, bool)
	All() []ProductView
}
