"""In-memory product store. A database would implement the same port."""
from __future__ import annotations

from typing import Dict, Protocol

from acima.catalog.contracts import ProductNotFound, ProductView
from acima.shared_kernel import ProductId


class ProductStore(Protocol):
    """Consumer-owned port: the store Catalog needs, shaped by Catalog."""

    def find(self, product_id: ProductId) -> ProductView: ...
    def all(self) -> list[ProductView]: ...
    def save(self, product: ProductView) -> None: ...


class InMemoryProductStore:
    """A trivial store. Note the table prefix `catalog_` is Catalog's own namespace."""

    _table = "catalog_products"

    def __init__(self) -> None:
        self._rows: Dict[str, ProductView] = {}

    def find(self, product_id: ProductId) -> ProductView:
        try:
            return self._rows[product_id.value]
        except KeyError:
            raise ProductNotFound(product_id.value) from None

    def all(self) -> list[ProductView]:
        return [self._rows[k] for k in sorted(self._rows)]

    def save(self, product: ProductView) -> None:
        self._rows[product.id.value] = product
