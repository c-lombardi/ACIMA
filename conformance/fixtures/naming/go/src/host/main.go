package host

// OrderValidator validates an order request.
type OrderValidator struct{}

// PaymentAuthorizer authorizes a payment.
type PaymentAuthorizer interface {
	Authorize() bool
}

// OrderRepository stores and retrieves orders.
type OrderRepository struct{}

// OrderService is a qualified role name, not the exact generic Service token.
type OrderService struct{}

// RequestHandler is a qualified role name, not a generic suffix.
type RequestHandler interface {
	Handle()
}

// OrderFactory is a precise factory role.
type OrderFactory struct{}
