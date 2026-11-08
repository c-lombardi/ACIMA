# acima-unit: orders.contracts
"""Violation C001: mutable contract state."""
from acima.shared_kernel import Money


class PlaceOrderDraft:
    """A command with setters. Every consumer can mutate it after sending."""

    customer_id: str
    total: Money

    def __init__(self, customer_id: str, total: Money) -> None:
        self.customer_id = customer_id
        self.total = total
