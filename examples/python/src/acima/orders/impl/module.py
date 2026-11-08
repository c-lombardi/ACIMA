"""Orders' application service. Depends only on its own contracts and other modules' contracts."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Sequence

from acima.catalog.contracts import CatalogReader, ProductNotFound
from acima.orders.contracts import (
    OrderLine,
    OrderPlaced,
    OrderRejected,
    OrderRejectedReason,
    OrderSummary,
    PlaceOrder,
)
from acima.payments.contracts import PaymentDeclined, PaymentGateway, PaymentRequest
from acima.shared_kernel import Money, OrderId, ProductId

from .order import Order


class OrderNotFound(Exception):
    """Internal: the caller saw a missing order."""


class OrdersModule:
    """A module constructed from its declared dependencies. No locators, no globals."""

    def __init__(
        self,
        catalog: CatalogReader,
        payments: PaymentGateway,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._catalog = catalog
        self._payments = payments
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._orders: Dict[str, Order] = {}
        self._published: list[object] = []

    # --- command -------------------------------------------------------------
    def place(self, command: PlaceOrder) -> OrderSummary | OrderRejected:
        order_id = OrderId(str(uuid.uuid4()))
        lines: list[OrderLine] = []
        for line in command.lines:
            try:
                product = self._catalog.get(line.product_id)
            except ProductNotFound:
                return OrderRejected(order_id, OrderRejectedReason.OUT_OF_STOCK)
            lines.append(OrderLine(line.product_id, product.price, line.quantity))

        order = Order(order_id, command.customer_id)
        for line in lines:
            order.add(line)

        try:
            self._payments.authorize(
                PaymentRequest(order.id, order.total, command.customer_id)
            )
        except PaymentDeclined:
            return OrderRejected(order.id, OrderRejectedReason.PAYMENT_DECLINED)

        self._orders[order.id.value] = order
        self._published.append(
            OrderPlaced(order.id, order.customer_id, order.total, tuple(order.lines))
        )
        return order.to_summary()

    # --- query ---------------------------------------------------------------
    def get(self, order_id: OrderId) -> OrderSummary:
        try:
            return self._orders[order_id.value].to_summary()
        except KeyError:
            raise OrderNotFound(order_id.value) from None

    def recent(self, limit: int) -> Sequence[OrderSummary]:
        return [o.to_summary() for o in list(self._orders.values())[-limit:]][::-1]

    def published_events(self) -> list[object]:
        """Test seam: the host would hand these to a bus."""
        return list(self._published)
