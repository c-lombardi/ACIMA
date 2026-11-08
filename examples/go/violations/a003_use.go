//go:build ignore

// acima-unit: catalog
package catalog

import orders "acima.example/internal/orders/impl"

// Mutate reaches into another module's static state.
func Mutate() { orders.Cart["x"] = 1 }
