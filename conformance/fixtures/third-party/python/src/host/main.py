"""Composition root: the only place that names the adapter."""
from editor.monaco import MonacoEditor
from notes.impl.service import NoteService


def build() -> NoteService:
    """Wire the service to the adapter; nothing else knows the vendor."""
    return NoteService(MonacoEditor())
