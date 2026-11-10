"""A second composition boundary over the same orders module."""

from orders.service import InMemoryRepository, OrdersService


def build_worker() -> OrdersService:
    return OrdersService(InMemoryRepository())
