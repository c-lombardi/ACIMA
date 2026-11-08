"""A fake gateway. A real one would call a provider; the module would not change."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Dict, Set

from acima.payments.contracts import (
    PaymentAuthorized,
    PaymentDeclined,
    PaymentId,
    PaymentRequest,
)
from acima.shared_kernel import Money


class FakeGateway:
    """Authorizes everything up to a limit; declines above it. Deterministic, testable."""

    def __init__(self, decline_above: Money) -> None:
        self._decline_above = decline_above
        self._authorized: Dict[str, PaymentAuthorized] = {}
        self._refunded: Set[str] = set()

    def authorize(self, request: PaymentRequest) -> PaymentAuthorized:
        if request.amount.amount > self._decline_above.amount:
            raise PaymentDeclined(str(request.amount))
        authorized = PaymentAuthorized(
            payment_id=PaymentId(str(uuid.uuid4())),
            order_id=request.order_id,
            amount=request.amount,
            reference=f"ref-{uuid.uuid4().hex[:8]}",
        )
        self._authorized[authorized.payment_id.value] = authorized
        return authorized

    def refund(self, payment_id: PaymentId, amount: Money) -> None:
        if amount.amount > self._authorized[payment_id.value].amount.amount:
            raise ValueError("cannot refund more than authorized")
        self._refunded.add(payment_id.value)
