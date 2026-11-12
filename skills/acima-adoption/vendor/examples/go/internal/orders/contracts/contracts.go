// Package orderscontracts is Orders' complete public surface: messages, events and the
// port other modules may call. No catalog types, no payments types, no framework.
package orderscontracts

// OrderLine is one product in one order, with the price captured at placement time.
type OrderLine struct {
	ProductID ProductID
	UnitPrice Money
	Quantity  int
}

// PlaceOrder asks Orders to place an order. Lines is private so callers cannot
// mutate the command after construction; Lines returns a copy.
type PlaceOrder struct {
	CustomerID string
	lines      []OrderLine
}

// NewPlaceOrder builds a place-order command and copies the supplied lines.
func NewPlaceOrder(customerID string, lines []OrderLine) PlaceOrder {
	return PlaceOrder{CustomerID: customerID, lines: append([]OrderLine(nil), lines...)}
}

// Lines returns a copy of the requested lines.
func (p PlaceOrder) Lines() []OrderLine {
	return append([]OrderLine(nil), p.lines...)
}

// Summary is what Orders returns about an accepted order. Lines is private so
// callers cannot mutate retained order state; Lines returns a copy.
type Summary struct {
	ID         OrderID
	CustomerID string
	lines      []OrderLine
	Total      Money
}

// NewSummary builds an order summary and copies the supplied lines.
func NewSummary(id OrderID, customerID string, lines []OrderLine, total Money) Summary {
	return Summary{ID: id, CustomerID: customerID, lines: append([]OrderLine(nil), lines...), Total: total}
}

// Lines returns a copy of the order's lines.
func (s Summary) Lines() []OrderLine {
	return append([]OrderLine(nil), s.lines...)
}

// Placed is emitted when an order is accepted and paid for.
type Placed struct {
	OrderID    OrderID
	CustomerID string
	Total      Money
}

// RejectionReason is the closed set of reasons an order can be refused.
type RejectionReason string

const (
	// OutOfStock means a product was unknown or unavailable.
	OutOfStock RejectionReason = "out_of_stock"
	// PaymentDeclined means the gateway refused the authorization.
	PaymentDeclined RejectionReason = "payment_declined"
)

// Rejected is emitted when an order is refused.
type Rejected struct {
	OrderID OrderID
	Reason  RejectionReason
}

// Reader is the read capability Orders promises.
type Reader interface {
	Get(id OrderID) (Summary, bool)
}
