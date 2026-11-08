package orders

import (
	orderscontracts "acima.example/internal/orders/contracts"
	"acima.example/internal/sharedkernel"
)

// order is the aggregate. Mutable on purpose: immutability is a boundary rule.
type order struct {
	id       sharedkernel.OrderID
	customer string
	lines    []orderscontracts.OrderLine
	total    sharedkernel.Money
}

func newOrder(id sharedkernel.OrderID, customer string, zero sharedkernel.Money) *order {
	return &order{id: id, customer: customer, total: zero}
}

func (o *order) add(line orderscontracts.OrderLine) error {
	lineTotal, err := line.UnitPrice.Times(line.Quantity)
	if err != nil {
		return err
	}
	total, err := o.total.Add(lineTotal)
	if err != nil {
		return err
	}
	o.lines = append(o.lines, line)
	o.total = total
	return nil
}

func (o *order) summary() orderscontracts.Summary {
	lines := make([]orderscontracts.OrderLine, len(o.lines))
	copy(lines, o.lines)
	return orderscontracts.Summary{ID: o.id, CustomerID: o.customer, Lines: lines, Total: o.total}
}
