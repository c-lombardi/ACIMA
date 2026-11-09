"""The capability the application needs from a code editor.

The port owns its vocabulary: no vendor type appears here, and nothing in this
package imports a third-party library (D010).
"""


class EditorPort(Protocol):
    """Open a note and read its current text."""

    def open(self, note: str) -> None:
        """Show the note in an editor."""

    def read(self) -> str:
        """Return the text currently in the editor."""
