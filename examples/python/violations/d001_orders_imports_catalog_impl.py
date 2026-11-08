# acima-unit: orders
"""Violation D001: Orders reaches into Catalog's implementation."""
from acima.catalog.impl.repository import InMemoryProductStore

STORE_TYPE = InMemoryProductStore
