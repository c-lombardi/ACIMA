# acima-unit: orders
"""Violation L007: a vendor type in an application signature."""


def open_note(editor: "monaco_editor.IEditor") -> str:
    """Return the note text from the editor handle."""
    return editor.text()
