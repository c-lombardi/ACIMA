# acima-unit: catalog.contracts
"""Violation D002: a contracts unit references its own implementation."""
from acima.catalog.impl.repository import InMemoryProductStore

STORE_TYPE = InMemoryProductStore
