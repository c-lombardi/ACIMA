"""The composition root. The only place where every module is known.

Run: PYTHONPATH=src python3 -m acima.host.main
"""
from __future__ import annotations

from decimal import Decimal

from acima.catalog.contracts import ProductView
from acima.catalog.impl import CatalogModule
from acima.orders.contracts import OrderLine, PlaceOrder
from acima.orders.impl import OrdersModule
from acima.payments.impl import PaymentsModule
from acima.shared_kernel import Currency, Money, ProductId


def build() -> tuple[CatalogModule, OrdersModule, PaymentsModule]:
    """Wire the object graph explicitly. No container, no globals, no discovery."""
    catalog = CatalogModule()
    payments = PaymentsModule()
    orders = OrdersModule(catalog=catalog.reader(), payments=payments.gateway())
    return catalog, orders, payments


def main() -> None:
    catalog, orders, _payments = build()
    catalog.add(ProductView(ProductId("p-1"), "Espresso beans", Money(Decimal("12.50"), Currency.EUR)))
    catalog.add(ProductView(ProductId("p-2"), "Filter papers", Money(Decimal("3.20"), Currency.EUR)))

    command = PlaceOrder(
        customer_id="c-1",
        lines=(
            OrderLine(ProductId("p-1"), Money(Decimal("12.50"), Currency.EUR), 2),
            OrderLine(ProductId("p-2"), Money(Decimal("3.20"), Currency.EUR), 1),
        ),
    )
    result = orders.place(command)
    print(f"placed: {result}")
    print(f"events: {[type(e).__name__ for e in orders.published_events()]}")


if __name__ == "__main__":
    main()
