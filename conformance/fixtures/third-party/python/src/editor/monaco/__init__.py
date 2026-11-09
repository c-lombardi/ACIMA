"""The Monaco adapter: the only unit that imports the vendor."""
import monaco_editor


class MonacoEditor:
    """Port implementation backed by the vendor editor."""

    def open(self, note: str) -> None:
        """Open the note in the vendor editor."""
        self._editor = monaco_editor.open(note)

    def read(self) -> str:
        """Return the vendor editor's current text."""
        return self._editor.text()
