//go:build ignore

// acima-unit: orders.contracts
package orderscontracts

import "net/http"

// Route speaks HTTP.
type Route struct {
	Handler http.Handler
}
