"""Behaviour tests for the module that owns the workflow. No architecture assertions here."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from acima.catalog.contracts import (  # noqa: E402
    Currency as CatalogCurrency,
    Money as CatalogMoney,
    ProductId as CatalogProductId,
    ProductView,
)
from acima.catalog.impl import CatalogModule  # noqa: E402
from acima.catalog.impl.repository import InMemoryProductStore  # noqa: E402
from acima.customers.contracts import (  # noqa: E402
    CustomerId as CustomersCustomerId,
    CustomerView,
)
from acima.customers.impl import CustomersModule  # noqa: E402
from acima.orders.contracts import (  # noqa: E402
    Currency,
    Money,
    OrderLine,
    PlaceOrder,
    ProductId,
)
from acima.orders.impl import OrdersModule  # noqa: E402
from acima.payments.contracts import (  # noqa: E402
    Currency as PaymentCurrency,
    Money as PaymentMoney,
)
from acima.payments.impl import PaymentsModule  # noqa: E402
from acima.payments.impl.gateway import FakeGateway  # noqa: E402


def eur(amount: str) -> Money:
    return Money(Decimal(amount), Currency.EUR)


def catalog_eur(amount: str) -> CatalogMoney:
    return CatalogMoney(Decimal(amount), CatalogCurrency.EUR)


class OrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = CatalogModule(InMemoryProductStore())
        self.customers = CustomersModule()
        self.payments = PaymentsModule(
            FakeGateway(PaymentMoney(Decimal("1000.00"), PaymentCurrency.EUR)))
        self.orders = OrdersModule(
            self.catalog.reader(), self.customers.reader(), self.payments.gateway(),
            clock=lambda: datetime.now(timezone.utc))
        self.catalog.add(ProductView(CatalogProductId("p-1"), "Beans", catalog_eur("12.50")))
        self.customers.add(CustomerView(CustomersCustomerId("c-1"), "Ada", "ada@example.test"))

    def test_places_an_order_and_publishes_one_event(self) -> None:
        result = self.orders.place(
            PlaceOrder("c-1", (OrderLine(ProductId("p-1"), eur("12.50"), 2),))
        )
        self.assertEqual(result.total, eur("25.00"))
        self.assertEqual([type(e).__name__ for e in self.orders.published_events()], ["OrderPlaced"])

    def test_unknown_product_is_rejected_not_raised(self) -> None:
        result = self.orders.place(
            PlaceOrder("c-1", (OrderLine(ProductId("missing"), eur("1.00"), 1),))
        )
        self.assertEqual(getattr(result, "reason", None), "out_of_stock")

    def test_unknown_customer_is_rejected_not_raised(self) -> None:
        result = self.orders.place(
            PlaceOrder("missing", (OrderLine(ProductId("p-1"), eur("12.50"), 1),))
        )
        self.assertEqual(getattr(result, "reason", None), "customer_not_found")

    def test_declined_payment_is_rejected(self) -> None:
        self.catalog.add(ProductView(CatalogProductId("p-2"), "Machine", catalog_eur("5000.00")))
        result = self.orders.place(
            PlaceOrder("c-1", (OrderLine(ProductId("p-2"), eur("5000.00"), 1),))
        )
        self.assertEqual(getattr(result, "reason", None), "payment_declined")

    def test_money_rejects_negative_amounts(self) -> None:
        with self.assertRaises(ValueError):
            eur("-1.00")


if __name__ == "__main__":
    unittest.main()
