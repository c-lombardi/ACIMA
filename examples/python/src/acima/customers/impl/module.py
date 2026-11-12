"""Customers' implementation. The module owns its storage and exposes only its contract."""
from __future__ import annotations

from typing import Dict

from acima.customers.contracts import (
    CustomerId,
    CustomerNotFound,
    CustomerView,
)


class _CustomerReader:
    """Adapter for the provided port. Private to this module."""

    def __init__(self) -> None:
        self._rows: Dict[str, CustomerView] = {}

    def get(self, customer_id: CustomerId) -> CustomerView:
        try:
            return self._rows[customer_id.value]
        except KeyError:
            raise CustomerNotFound(customer_id.value) from None

    def save(self, customer: CustomerView) -> None:
        self._rows[customer.id.value] = customer


class CustomersModule:
    """Customers' composition surface: own the store, publish the reader."""

    def __init__(self) -> None:
        self._reader = _CustomerReader()

    def reader(self) -> _CustomerReader:
        return self._reader

    def add(self, customer: CustomerView) -> None:
        self._reader.save(customer=customer)
