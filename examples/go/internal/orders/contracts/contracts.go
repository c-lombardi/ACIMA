// Package orderscontracts is Orders' complete public surface: messages, events and the
// port other modules may call. No catalog types, no payments types, no framework.
package orderscontracts

import "acima.example/internal/sharedkernel"

// OrderLine is one product in one order, with the price captured at placement time.
type OrderLine struct {
	ProductID sharedkernel.ProductID
	UnitPrice sharedkernel.Money
	Quantity  int
}

// PlaceOrder asks Orders to place an order.
type PlaceOrder struct {
	CustomerID string
	Lines      []OrderLine
}

// Summary is what Orders returns about an accepted order.
type Summary struct {
	ID         sharedkernel.OrderID
	CustomerID string
	Lines      []OrderLine
	Total      sharedkernel.Money
}

// Placed is emitted when an order is accepted and paid for.
type Placed struct {
	OrderID    sharedkernel.OrderID
	CustomerID string
	Total      sharedkernel.Money
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
	OrderID sharedkernel.OrderID
	Reason  RejectionReason
}

// Reader is the read capability Orders promises.
type Reader interface {
	Get(id sharedkernel.OrderID) (Summary, bool)
}
