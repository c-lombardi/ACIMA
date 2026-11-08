//go:build ignore

// acima-unit: payments.contracts
package paymentscontracts

import "database/sql"

// Row leaks the database handle into the contract.
type Row struct {
	DB *sql.DB
}
