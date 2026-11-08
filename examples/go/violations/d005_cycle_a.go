//go:build ignore

// acima-unit: catalog
package catalog

import orders "acima.example/internal/orders/impl"

// A closes the loop.
func A() int { return orders.B() + 1 }
