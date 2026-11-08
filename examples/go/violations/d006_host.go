//go:build ignore

// acima-unit: catalog.contracts
package catalogcontracts

import "acima.example/cmd/host"

// HostBound knows how it is hosted.
type HostBound struct {
	Host host.Root
}
