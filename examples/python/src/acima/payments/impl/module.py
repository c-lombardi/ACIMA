"""Payments' composition function."""
from __future__ import annotations

from acima.payments.contracts import PaymentAuthorized, PaymentRequest

from .gateway import FakeGateway


class PaymentsModule:
    """Owns the gateway instance; the gateway is injected, not discovered."""

    def __init__(self, gateway: FakeGateway) -> None:
        self._gateway = gateway

    def gateway(self) -> FakeGateway:
        return self._gateway

    def authorize(self, request: PaymentRequest) -> PaymentAuthorized:
        return self._gateway.authorize(request)
