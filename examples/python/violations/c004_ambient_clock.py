# acima-unit: orders.contracts
"""Violation C004: the contract reads the clock."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class OrderStamped:
    """Non-deterministic: two constructions of the same message differ."""

    placed_at: datetime = field(default_factory=datetime.now)
