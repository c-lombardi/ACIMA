"""Payments' public surface: a gateway port, a request, a result, an event."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from acima.shared_kernel import Money, OrderId, PaymentId

__all__ = [
    "PaymentAuthorized",
    "PaymentDeclined",
    "PaymentGateway",
    "PaymentId",
    "PaymentRequest",
]


class PaymentDeclined(Exception):
    """Raised when the gateway refuses the authorization. Expected, not exceptional."""


@dataclass(frozen=True, slots=True)
class PaymentRequest:
    """Command: authorize this amount for this order."""

    order_id: OrderId
    amount: Money
    customer_id: str


@dataclass(frozen=True, slots=True)
class PaymentAuthorized:
    """Event: money was authorized. `reference` is the gateway's id, for reconciliation."""

    payment_id: PaymentId
    order_id: OrderId
    amount: Money
    reference: str


class PaymentGateway(Protocol):
    """The capability Payments promises: authorize, and refund."""

    def authorize(self, request: PaymentRequest) -> PaymentAuthorized:
        """Authorize the amount or raise PaymentDeclined."""
        ...

    def refund(self, payment_id: PaymentId, amount: Money) -> None:
        """Refund all or part of an authorized payment."""
        ...
