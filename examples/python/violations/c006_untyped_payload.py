# acima-unit: orders.contracts
"""Violation C006: an untyped payload."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IntegrationEvent:
    """No type, no contract: every consumer must validate at runtime."""

    event_type: str
    payload: dict[str, Any]
