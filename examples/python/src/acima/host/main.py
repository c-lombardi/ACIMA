"""The composition root. The only place where every module is known.

Run: PYTHONPATH=src python3 -m acima.host.main
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from acima.catalog.contracts import (
    Currency as CatalogCurrency,
    Money as CatalogMoney,
    ProductId as CatalogProductId,
    ProductView,
)
from acima.catalog.impl import CatalogModule
from acima.catalog.impl.repository import InMemoryProductStore
from acima.customers.contracts import CustomerId as CustomersCustomerId, CustomerView
from acima.customers.impl import CustomersModule
from acima.orders.contracts import (
    Currency as OrderCurrency,
    Money as OrderMoney,
    OrderLine,
    PlaceOrder,
    ProductId as OrderProductId,
)
from acima.orders.impl import OrdersModule
from acima.payments.contracts import (
    Currency as PaymentCurrency,
    Money as PaymentMoney,
)
from acima.payments.impl import PaymentsModule
from acima.payments.impl.gateway import FakeGateway


def build() -> tuple[CatalogModule, CustomersModule, OrdersModule, PaymentsModule]:
    """Wire the object graph explicitly. No container, no globals, no discovery."""
    catalog = CatalogModule(InMemoryProductStore())
    customers = CustomersModule()
    payments = PaymentsModule(
        FakeGateway(PaymentMoney(Decimal("1000.00"), PaymentCurrency.EUR)))
    orders = OrdersModule(
        catalog=catalog.reader(),
        customers=customers.reader(),
        payments=payments.gateway(),
        clock=lambda: datetime.now(timezone.utc),
    )
    return catalog, customers, orders, payments


def main() -> None:
    catalog, customers, orders, _payments = build()
    customers.add(CustomerView(CustomersCustomerId("c-1"), "Ada Lovelace", "ada@example.test"))
    catalog.add(ProductView(
        CatalogProductId("p-1"),
        "Espresso beans",
        CatalogMoney(Decimal("12.50"), CatalogCurrency.EUR),
    ))
    catalog.add(ProductView(
        CatalogProductId("p-2"),
        "Filter papers",
        CatalogMoney(Decimal("3.20"), CatalogCurrency.EUR),
    ))

    command = PlaceOrder(
        customer_id="c-1",
        lines=(
            OrderLine(
                OrderProductId("p-1"),
                OrderMoney(Decimal("12.50"), OrderCurrency.EUR),
                2,
            ),
            OrderLine(
                OrderProductId("p-2"),
                OrderMoney(Decimal("3.20"), OrderCurrency.EUR),
                1,
            ),
        ),
    )
    result = orders.place(command)
    print(f"placed: {result}")
    print(f"events: {[type(e).__name__ for e in orders.published_events()]}")


if __name__ == "__main__":
    main()
