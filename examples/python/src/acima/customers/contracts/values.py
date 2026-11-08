"""Customers' value types. They are owned here, not imported from a shared kernel."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustomerId:
    """A customer identity as Customers publishes it."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("customer id is required")
