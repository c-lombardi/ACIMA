# acima-unit: catalog
"""Violation L003 (declaration): a public implementation type other modules can reach."""
from dataclasses import dataclass


@dataclass
class PublicCatalogThing:
    """Should be internal: nothing outside Catalog may see it."""

    name: str
