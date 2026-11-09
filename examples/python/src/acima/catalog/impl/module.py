"""Catalog's composition function: builds its own graph, exposes only contracts types."""
from __future__ import annotations

from typing import Sequence

from acima.catalog.contracts import ProductId, ProductView

from .repository import ProductStore


class _CatalogReader:
    """Adapter that implements the provided port. Private: `_` prefix and not in contracts."""

    def __init__(self, store: ProductStore) -> None:
        self._store = store

    def get(self, product_id: ProductId) -> ProductView:
        return self._store.find(product_id)

    def list_all(self) -> Sequence[ProductView]:
        return self._store.all()


class CatalogModule:
    """The module. Constructed with its dependencies, never discovering them."""

    def __init__(self, store: ProductStore) -> None:
        self._store = store
        self._reader = _CatalogReader(self._store)

    def reader(self) -> _CatalogReader:
        return self._reader

    def add(self, product: ProductView) -> None:
        self._store.save(product)
