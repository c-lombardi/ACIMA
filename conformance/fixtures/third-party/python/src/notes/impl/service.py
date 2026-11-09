"""Note authoring, written against the port and never the vendor."""
from editor.port import EditorPort


class NoteService:
    """Open and read notes through the editor port."""

    def __init__(self, editor: EditorPort) -> None:
        """Take the capability, not the vendor."""
        self._editor = editor

    def edit(self, note: str) -> str:
        """Open a note and report its text."""
        self._editor.open(note)
        return self._editor.read()
