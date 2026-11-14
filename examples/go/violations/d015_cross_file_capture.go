//go:build ignore

// acima-unit: orders
package orders

func CrossFileLookup() func(string) {
	return func(id string) {
		crossFileStore.Save(id)
	}
}
