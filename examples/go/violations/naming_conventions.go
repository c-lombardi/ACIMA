//go:build ignore

// acima-unit: orders
package orders

// OrderHelper hides an undecided responsibility behind a generic suffix.
type OrderHelper struct{}

// Manager is a generic placeholder rather than a domain responsibility.
type Manager interface{}

// PaymentProcessor names a role only by the generic processor suffix.
type PaymentProcessor struct{}

// OrderService is a qualified role name and must not match the exact Service token.
type OrderService struct{}

// RequestHandler is a qualified role name and must not match a generic suffix.
type RequestHandler interface{}

// OrderFactory names a precise factory role and must not be reported.
type OrderFactory struct{}
