"""Orders' application service. Depends only on its own contracts and other modules' contracts."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Callable, Dict, Sequence

from acima.catalog.contracts import CatalogReader, ProductId as CatalogProductId, ProductNotFound
from acima.customers.contracts import (
    CustomerId as CustomersCustomerId,
    CustomerNotFound,
    CustomerReader,
)
from acima.orders.contracts import (
    Currency,
    Money,
    OrderId,
    OrderLine,
    OrderPlaced,
    OrderRejected,
    OrderRejectedReason,
    OrderSummary,
    PlaceOrder,
)
from acima.payments.contracts import (
    Money as PaymentMoney,
    OrderId as PaymentOrderId,
    PaymentDeclined,
    PaymentGateway,
    PaymentRequest,
)

from .order import Order


class OrderNotFound(Exception):
    """Internal: the caller saw a missing order."""


class OrdersModule:
    """A module constructed from its declared dependencies. No locators, no globals."""

    def __init__(
        self,
        catalog: CatalogReader,
        customers: CustomerReader,
        payments: PaymentGateway,
        clock: Callable[[], datetime],
    ) -> None:
        self._catalog = catalog
        self._customers = customers
        self._payments = payments
        self._clock = clock
        self._orders: Dict[str, Order] = {}
        self._published: list[object] = []

    # --- command -------------------------------------------------------------
    def place(self, command: PlaceOrder) -> OrderSummary | OrderRejected:
        order_id = OrderId(str(uuid.uuid4()))
        try:
            self._customers.get(CustomersCustomerId(command.customer_id))
        except CustomerNotFound:
            return OrderRejected(order_id, OrderRejectedReason.CUSTOMER_NOT_FOUND)

        lines: list[OrderLine] = []
        for line in command.lines:
            try:
                product = self._catalog.get(CatalogProductId(line.product_id.value))
            except ProductNotFound:
                return OrderRejected(order_id, OrderRejectedReason.OUT_OF_STOCK)
            lines.append(OrderLine(
                line.product_id,
                Money(product.price.amount, Currency(product.price.currency.value)),
                line.quantity,
            ))

        order = Order(order_id, command.customer_id)
        for line in lines:
            order.add(line)

        try:
            self._payments.authorize(
                PaymentRequest(
                    PaymentOrderId(order.id.value),
                    PaymentMoney(order.total.amount, Currency(order.total.currency.value)),
                    command.customer_id,
                )
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
