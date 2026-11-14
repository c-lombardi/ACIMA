//go:build ignore

// acima-unit: orders
package orders

type OrderStore struct{}

func (s *OrderStore) Save(id string) {}

var (
	orderStore = &OrderStore{}
)

func Lookup() func(string) {
	return func(id string) {
		orderStore.Save(id)
	}
}
