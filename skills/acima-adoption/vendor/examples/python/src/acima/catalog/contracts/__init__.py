"""Catalog's complete public surface. Zero external dependencies.

Every type here fits one of the seven contract kinds: view, provided port, value.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .values import Currency, Money, OrderId, PaymentId, ProductId

__all__ = [
    "CatalogReader",
    "Currency",
    "Money",
    "OrderId",
    "PaymentId",
    "ProductId",
    "ProductNotFound",
    "ProductView",
]


class ProductNotFound(Exception):
    """Raised when a product id is unknown to the catalog."""


@dataclass(frozen=True, slots=True)
class ProductView:
    """A purchasable product. `price` is the current list price in the product's currency."""

    id: ProductId
    name: str
    price: Money


class CatalogReader(Protocol):
    """The capability Catalog promises: read products by id."""

    def get(self, product_id: ProductId) -> ProductView:
        """Return the product, or raise ProductNotFound."""
        ...

    def list_all(self) -> Sequence[ProductView]:
        """Return every known product, ordered by id."""
        ...
