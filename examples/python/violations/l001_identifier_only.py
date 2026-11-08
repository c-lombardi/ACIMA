# acima-unit: orders
"""Negative L001 fixture: an identifier is not an infrastructure dependency."""


def encode(value: str, sqlalchemy_safe: bool = False) -> str:
    """Return the value; the parameter name must not trigger L001."""
    return value if sqlalchemy_safe else value
