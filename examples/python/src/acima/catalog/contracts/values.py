"""Value types owned by this contracts project. No imports outside the language core.

The same file is duplicated in each module's contracts package on purpose: value types
belong to the boundary that publishes them, not to a shared kernel.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Currency(str, Enum):
    """The currencies this module accepts at its boundary."""

    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount in one currency, quantised to cents."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError("amount must be a Decimal")
        if self.amount < 0:
            raise ValueError("money cannot be negative")
        if self.amount != self.amount.quantize(Decimal("0.01")):
            raise ValueError("money must be quantised to 2 decimal places")

    def times(self, quantity: int) -> Money:
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        return Money(self.amount * quantity, self.currency)

    def plus(self, other: Money) -> Money:
        if other.currency is not self.currency:
            raise ValueError("cannot add money in different currencies")
        return Money(self.amount + other.amount, self.currency)

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency.value}"


@dataclass(frozen=True, slots=True)
class ProductId:
    """Identifies a product in this module's vocabulary."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("product id cannot be empty")


@dataclass(frozen=True, slots=True)
class OrderId:
    """Identifies an order in this module's vocabulary."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("order id cannot be empty")


@dataclass(frozen=True, slots=True)
class PaymentId:
    """Identifies a payment in this module's vocabulary."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("payment id cannot be empty")
