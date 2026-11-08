# acima-unit: orders
"""Violation A001: Orders reads Catalog's table instead of asking Catalog."""
QUERY = "select name, price from catalog_products where id = ?"
