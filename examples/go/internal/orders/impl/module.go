// Package orders implements Orders. Nothing here is importable from another module.
package orders

import (
	"crypto/rand"
	"encoding/hex"
	"errors"

	catalogcontracts "acima.example/internal/catalog/contracts"
	orderscontracts "acima.example/internal/orders/contracts"
	paymentscontracts "acima.example/internal/payments/contracts"
	"acima.example/internal/sharedkernel"
)

func newID() string {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		panic(err)
	}
	return hex.EncodeToString(buf)
}

// Module is Orders' application service. It depends only on contracts and its own domain.
type Module struct {
	catalog  catalogcontracts.Reader
	payments paymentscontracts.Gateway
	orders   map[sharedkernel.OrderID]*order
	events   []any
}

// New wires Orders to the ports the host provides.
func New(catalog catalogcontracts.Reader, payments paymentscontracts.Gateway) *Module {
	return &Module{catalog: catalog, payments: payments, orders: map[sharedkernel.OrderID]*order{}}
}

// Place runs the place-order workflow. A rejection is returned as a value, not an error.
func (m *Module) Place(cmd orderscontracts.PlaceOrder) (orderscontracts.Summary, *orderscontracts.Rejected, error) {
	if len(cmd.Lines) == 0 {
		return orderscontracts.Summary{}, nil, errors.New("an order needs at least one line")
	}

	id := sharedkernel.OrderID(newID())
	lines := make([]orderscontracts.OrderLine, 0, len(cmd.Lines))
	for _, line := range cmd.Lines {
		product, ok := m.catalog.Get(line.ProductID)
		if !ok {
			return orderscontracts.Summary{}, m.reject(id, orderscontracts.OutOfStock), nil
		}
		lines = append(lines, orderscontracts.OrderLine{
			ProductID: line.ProductID,
			UnitPrice: product.Price,
			Quantity:  line.Quantity,
		})
	}

	zero, err := sharedkernel.NewMoney(0, lines[0].UnitPrice.Currency())
	if err != nil {
		return orderscontracts.Summary{}, nil, err
	}
	ord := newOrder(id, cmd.CustomerID, zero)
	for _, line := range lines {
		if err := ord.add(line); err != nil {
			return orderscontracts.Summary{}, nil, err
		}
	}

	auth, err := m.payments.Authorize(paymentscontracts.PaymentRequest{
		OrderID:    id,
		Amount:     ord.total,
		CustomerID: cmd.CustomerID,
	})
	if err != nil {
		return orderscontracts.Summary{}, nil, err
	}
	if !auth.Approved {
		return orderscontracts.Summary{}, m.reject(id, orderscontracts.PaymentDeclined), nil
	}

	m.orders[id] = ord
	summary := ord.summary()
	m.events = append(m.events, orderscontracts.Placed{
		OrderID:    id,
		CustomerID: summary.CustomerID,
		Total:      summary.Total,
	})
	return summary, nil, nil
}

// Get returns an accepted order.
func (m *Module) Get(id sharedkernel.OrderID) (orderscontracts.Summary, bool) {
	ord, ok := m.orders[id]
	if !ok {
		return orderscontracts.Summary{}, false
	}
	return ord.summary(), true
}

// Events returns the events this module has published, in order.
func (m *Module) Events() []any {
	out := make([]any, len(m.events))
	copy(out, m.events)
	return out
}

func (m *Module) reject(id sharedkernel.OrderID, reason orderscontracts.RejectionReason) *orderscontracts.Rejected {
	rejected := &orderscontracts.Rejected{OrderID: id, Reason: reason}
	m.events = append(m.events, *rejected)
	return rejected
}
