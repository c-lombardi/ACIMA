"""Orders' public surface: one command, one view, one provided port, two events.

The value types below are Orders' own. A caller maps its identifiers and money into
this project at the boundary; it does not pass another module's contract types through.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .values import Currency, Money, OrderId, PaymentId, ProductId

__all__ = [
    "Currency",
    "Money",
    "OrderId",
    "OrderLine",
    "OrderPlaced",
    "OrderRejected",
    "OrderRejectedReason",
    "OrderSummary",
    "OrdersReader",
    "PaymentId",
    "PlaceOrder",
    "ProductId",
]


@dataclass(frozen=True, slots=True)
class OrderLine:
    """One product in one order. The unit price is captured at placement time."""

    product_id: ProductId
    unit_price: Money
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")


@dataclass(frozen=True, slots=True)
class PlaceOrder:
    """Command: place an order for a customer with the given lines."""

    customer_id: str
    lines: tuple[OrderLine, ...]

    def __post_init__(self) -> None:
        if not self.customer_id:
            raise ValueError("customer id is required")
        if not self.lines:
            raise ValueError("an order needs at least one line")


@dataclass(frozen=True, slots=True)
class OrderSummary:
    """View: what Orders promises to return about an order."""

    id: OrderId
    customer_id: str
    total: Money
    lines: tuple[OrderLine, ...]


@dataclass(frozen=True, slots=True)
class OrderPlaced:
    """Event: an order was accepted and paid for. Carries the facts a subscriber needs."""

    order_id: OrderId
    customer_id: str
    total: Money
    lines: tuple[OrderLine, ...]


@dataclass(frozen=True, slots=True)
class OrderRejected:
    """Event: an order was refused, with the reason the business cares about."""

    order_id: OrderId
    reason: str


class OrderRejectedReason:
    """The closed set of rejection reasons. A contract, not an enum, so it can gain values safely."""

    OUT_OF_STOCK = "out_of_stock"
    CUSTOMER_NOT_FOUND = "customer_not_found"
    PAYMENT_DECLINED = "payment_declined"


class OrdersReader(Protocol):
    """The capability Orders promises: read an order by id."""

    def get(self, order_id: OrderId) -> OrderSummary:
        """Return the order, or raise OrderNotFound."""
        ...

    def recent(self, limit: int) -> Sequence[OrderSummary]:
        """Return the most recent orders, newest first."""
        ...
