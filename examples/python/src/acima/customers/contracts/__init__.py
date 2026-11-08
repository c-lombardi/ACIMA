"""Customers' complete public surface: a view, a provided port and a local id.

Callers map their own customer identifier into this project at the boundary. They do
not import Customers' implementation or use another module's customer type.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .values import CustomerId

__all__ = [
    "CustomerId",
    "CustomerNotFound",
    "CustomerReader",
    "CustomerView",
]


class CustomerNotFound(Exception):
    """Raised when a customer id is unknown to Customers."""


@dataclass(frozen=True, slots=True)
class CustomerView:
    """A customer as other modules may see them. The email is a display value, not a login."""

    id: CustomerId
    name: str
    email: str


class CustomerReader(Protocol):
    """The capability Customers promises: resolve a customer id to its view."""

    def get(self, customer_id: CustomerId) -> CustomerView:
        """Return the customer, or raise CustomerNotFound."""
        ...
