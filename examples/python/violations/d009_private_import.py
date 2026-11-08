# acima-unit: orders
"""Violation D009: importing a private type from another module."""
from acima.catalog.impl.module import _CatalogReader

READER = _CatalogReader
