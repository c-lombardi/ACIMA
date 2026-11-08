//go:build ignore

// acima-unit: catalog.contracts
package catalogcontracts

import "github.com/google/uuid"

// Identified needs a third-party package to describe itself.
type Identified struct {
	ID uuid.UUID
}
