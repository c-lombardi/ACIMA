# acima-unit: orders.contracts
"""Violation C005: a persistence type in a contract."""
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderQuery:
    """Hands the caller a live database connection."""

    connection: sqlite3.Connection
