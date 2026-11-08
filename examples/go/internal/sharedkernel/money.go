// Package sharedkernel holds the tiny set of value types every module may use.
// It is a leaf: it imports nothing but the standard library.
package sharedkernel

import (
	"errors"
	"fmt"
)

// Currency is the closed set of currencies the shop trades in.
type Currency string

const (
	// EUR is the euro.
	EUR Currency = "EUR"
	// USD is the US dollar.
	USD Currency = "USD"
)

// Money is an immutable amount in minor units. Zero value is zero EUR.
type Money struct {
	amount   int64
	currency Currency
}

// NewMoney builds a Money, rejecting negative or zero-currency amounts.
func NewMoney(minor int64, currency Currency) (Money, error) {
	if minor < 0 {
		return Money{}, errors.New("money cannot be negative")
	}
	if currency == "" {
		return Money{}, errors.New("money needs a currency")
	}
	return Money{amount: minor, currency: currency}, nil
}

// MustMoney panics on invalid input. Use only with compile-time constants.
func MustMoney(minor int64, currency Currency) Money {
	m, err := NewMoney(minor, currency)
	if err != nil {
		panic(err)
	}
	return m
}

// Minor returns the amount in minor units.
func (m Money) Minor() int64 { return m.amount }

// Currency returns the currency.
func (m Money) Currency() Currency { return m.currency }

// Times multiplies by a non-negative integer quantity.
func (m Money) Times(quantity int) (Money, error) {
	if quantity < 0 {
		return Money{}, errors.New("quantity cannot be negative")
	}
	return Money{amount: m.amount * int64(quantity), currency: m.currency}, nil
}

// Add sums two amounts of the same currency.
func (m Money) Add(other Money) (Money, error) {
	if m.currency != other.currency {
		return Money{}, errors.New("currency mismatch")
	}
	return Money{amount: m.amount + other.amount, currency: m.currency}, nil
}

// String renders the amount for humans.
func (m Money) String() string {
	return fmt.Sprintf("%d.%02d %s", m.amount/100, m.amount%100, m.currency)
}

// ProductID identifies a product.
type ProductID string

// OrderID identifies an order.
type OrderID string

// PaymentID identifies a payment.
type PaymentID string
