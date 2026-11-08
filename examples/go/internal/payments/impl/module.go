// Package payments implements Payments behind the Gateway port.
package payments

import (
	"crypto/rand"
	"encoding/hex"
	"errors"

	paymentscontracts "acima.example/internal/payments/contracts"
)

// FakeGateway is a deterministic gateway for development and tests.
type FakeGateway struct {
	declineAboveMinor int64
}

// NewFakeGateway refuses anything above the given amount.
func NewFakeGateway(declineAboveMinor int64) *FakeGateway {
	return &FakeGateway{declineAboveMinor: declineAboveMinor}
}

func token() string {
	buf := make([]byte, 8)
	if _, err := rand.Read(buf); err != nil {
		panic(err)
	}
	return hex.EncodeToString(buf)
}

// Authorize implements the port.
func (g *FakeGateway) Authorize(req paymentscontracts.PaymentRequest) (paymentscontracts.Authorization, error) {
	if req.Amount.Minor() > g.declineAboveMinor {
		return paymentscontracts.Authorization{Approved: false}, nil
	}
	return paymentscontracts.Authorization{
		Approved:  true,
		PaymentID: paymentscontracts.PaymentID(token()),
		Reference: "ref-" + token(),
	}, nil
}

// Refund implements the port.
func (g *FakeGateway) Refund(id paymentscontracts.PaymentID, amount paymentscontracts.Money) error {
	if id == "" {
		return errors.New("refund needs a payment id")
	}
	return nil
}

// Module is Payments' composition surface.
type Module struct{ gateway *FakeGateway }

// New builds Payments with the fake gateway.
func New(declineAboveMinor int64) *Module { return &Module{gateway: NewFakeGateway(declineAboveMinor)} }

// Port returns the gateway other modules consume.
func (m *Module) Port() paymentscontracts.Gateway { return m.gateway }
