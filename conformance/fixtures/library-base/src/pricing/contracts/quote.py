"""Public contract owned by the pricing module; no implementation dependency."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    amount: int
