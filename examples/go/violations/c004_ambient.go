//go:build ignore

// acima-unit: orders.contracts
package orderscontracts

import "time"

// Stamped decides for itself what time it is.
type Stamped struct {
	At time.Time
}

// Now is the ambient read.
func Now() time.Time { return time.Now() }
