"""Compliant composition boundary: every component is constructed by name."""

from orders.service import InMemoryRepository, OrdersService


def build() -> OrdersService:
    return OrdersService(InMemoryRepository())
