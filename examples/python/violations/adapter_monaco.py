# acima-unit: editor.monaco
"""The Monaco adapter: the only unit allowed to import the vendor."""


class MonacoEditor:
    """Port implementation that delegates to the vendor editor."""

    def open(self, note: str) -> str:
        """Open the note and return its text."""
        return monaco_editor.render(note)
