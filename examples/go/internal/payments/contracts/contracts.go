// Package paymentscontracts is Payments' public surface: a port, a request and a result.
package paymentscontracts

import "acima.example/internal/sharedkernel"

// PaymentRequest asks the gateway to authorize an amount for an order.
type PaymentRequest struct {
	OrderID    sharedkernel.OrderID
	Amount     sharedkernel.Money
	CustomerID string
}

// Authorization is the gateway's answer.
type Authorization struct {
	Approved  bool
	PaymentID sharedkernel.PaymentID
	Reference string
}

// Gateway is the capability Payments promises.
type Gateway interface {
	Authorize(req PaymentRequest) (Authorization, error)
	Refund(id sharedkernel.PaymentID, amount sharedkernel.Money) error
}
