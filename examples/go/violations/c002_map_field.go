//go:build ignore

// acima-unit: payments.contracts
package paymentscontracts

// Batch exposes a map, which the caller keeps and mutates.
type Batch struct {
	Amounts map[string]int64
}
