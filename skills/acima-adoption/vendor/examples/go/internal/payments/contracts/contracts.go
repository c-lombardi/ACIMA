// Package paymentscontracts is Payments' public surface: a port, a request and a result.
// It imports nothing outside the standard library.
package paymentscontracts

// PaymentRequest asks the gateway to authorize an amount for an order.
type PaymentRequest struct {
	OrderID    OrderID
	Amount     Money
	CustomerID string
}

// Authorization is the gateway's answer.
type Authorization struct {
	Approved  bool
	PaymentID PaymentID
	Reference string
}

// Gateway is the capability Payments promises.
type Gateway interface {
	Authorize(req PaymentRequest) (Authorization, error)
	Refund(id PaymentID, amount Money) error
}
