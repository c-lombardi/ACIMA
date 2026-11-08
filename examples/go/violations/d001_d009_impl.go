//go:build ignore

// acima-unit: catalog
package catalog

import . "acima.example/internal/orders/impl"

// Stolen pulls another module's implementation into this module's namespace.
func Stolen() string { return newID() }
