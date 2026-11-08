//go:build ignore

// acima-unit: orders
package orders

import catalog "acima.example/internal/catalog/impl"

// B closes the loop.
func B() int { return catalog.A() + 1 }
