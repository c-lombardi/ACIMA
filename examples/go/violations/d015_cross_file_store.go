//go:build ignore

// acima-unit: orders
package orders

type CrossFileStore struct{}

func (s *CrossFileStore) Save(id string) {}

var crossFileStore = &CrossFileStore{}
