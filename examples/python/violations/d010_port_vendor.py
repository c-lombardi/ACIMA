# acima-unit: editor.port
"""Violation D010: a port that leaks the vendor's shape."""
from monaco_editor import IEditor


class EditorPort(Protocol):
    """Open a note in a code editor."""

    def open(self, note: str) -> IEditor:
        ...
