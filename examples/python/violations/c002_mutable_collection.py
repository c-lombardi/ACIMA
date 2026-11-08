# acima-unit: orders.contracts
"""Violation C002: frozen does not make the collection immutable."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderDraft:
    """Frozen dataclass whose list can still be appended to by every receiver."""

    lines: list[str]
