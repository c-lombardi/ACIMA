//go:build ignore

// acima-unit: catalog
package catalog

import "database/sql"

// Load touches the database from the domain package.
func Load(db *sql.DB) error { return db.Ping() }
