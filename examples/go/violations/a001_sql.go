//go:build ignore

// acima-unit: catalog
package catalog

// Stolen reads another module's table.
const Stolen = "select * from orders_headers where id = '1'"
