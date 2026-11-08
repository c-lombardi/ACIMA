# acima-unit: orders
"""Violation L001: domain/application code reaching for the database."""
from datetime import datetime

import sqlite3


def load(connection: sqlite3.Connection, order_id: str) -> datetime:
    """Read a timestamp straight from storage, bypassing the module's ports."""
    row = connection.execute("select created_at from orders where id = ?", (order_id,)).fetchone()
    return datetime.fromisoformat(row[0])
