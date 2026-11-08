"""Payments' composition function."""
from __future__ import annotations

from decimal import Decimal

from acima.payments.contracts import PaymentAuthorized, PaymentRequest
from acima.shared_kernel import Currency, Money

from .gateway import FakeGateway


class PaymentsModule:
    """Owns the gateway instance; the gateway is injected, not discovered."""

    def __init__(self, gateway: FakeGateway | None = None) -> None:
        self._gateway = gateway or FakeGateway(Money(Decimal("1000.00"), Currency.EUR))

    def gateway(self) -> FakeGateway:
        return self._gateway

    def authorize(self, request: PaymentRequest) -> PaymentAuthorized:
        return self._gateway.authorize(request)
