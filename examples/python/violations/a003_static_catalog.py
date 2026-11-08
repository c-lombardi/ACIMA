# acima-unit: catalog
"""Violation A003 (declaration): module-level mutable state other modules can reach."""
PRODUCT_CACHE: dict[str, str] = {}
