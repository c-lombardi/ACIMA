// Package catalog implements Catalog. Nothing here is importable from another module.
package catalog

import (
	"sort"

	catalogcontracts "acima.example/internal/catalog/contracts"
)

// store is the module's private persistence. A database would satisfy the same shape.
type store struct {
	rows map[catalogcontracts.ProductID]catalogcontracts.ProductView
}

func newStore() *store {
	return &store{rows: map[catalogcontracts.ProductID]catalogcontracts.ProductView{}}
}

// reader adapts the store to the provided port.
type reader struct{ s *store }

func (r reader) Get(id catalogcontracts.ProductID) (catalogcontracts.ProductView, bool) {
	p, ok := r.s.rows[id]
	return p, ok
}

func (r reader) All() []catalogcontracts.ProductView {
	out := make([]catalogcontracts.ProductView, 0, len(r.s.rows))
	for _, p := range r.s.rows {
		out = append(out, p)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out
}

// Module is the composition surface of Catalog.
type Module struct {
	store  *store
	reader reader
}

// New builds a Catalog module with in-memory persistence.
func New() *Module {
	s := newStore()
	return &Module{store: s, reader: reader{s: s}}
}

// Reader returns the port other modules consume.
func (m *Module) Reader() catalogcontracts.Reader { return m.reader }

// Add stores a product. Host-only: not part of the contract package.
func (m *Module) Add(p catalogcontracts.ProductView) { m.store.rows[p.ID] = p }
