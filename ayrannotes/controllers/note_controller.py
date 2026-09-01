"""Ayran Notes — Note controller.

Bridges the UI layer and the storage engine, managing note
lifecycle operations and search/filter logic.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from ayrannotes.storage.database import StorageEngine
from ayrannotes.storage.models import Note


class NoteController(QObject):
    """Handles all note CRUD operations and emits signals for UI updates."""

    notes_changed = pyqtSignal()          # list was modified
    note_saved = pyqtSignal(str)          # note_id
    note_deleted = pyqtSignal(str)        # note_id

    def __init__(self, storage: StorageEngine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage = storage

    @property
    def notes_directory(self) -> Path:
        """Return the directory that is currently the note source of truth."""
        return self._storage.notes_dir

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_notes(self) -> list[Note]:
        """Return every Markdown note, newest first."""
        return self._storage.list_notes()

    def get_note(self, note_id: str) -> Note | None:
        """Load a single note."""
        return self._storage.get_note(note_id)

    def search(self, query: str) -> list[Note]:
        """Full-text search across title and content."""
        q = query.lower().strip()
        if not q:
            return self.list_notes()
        return [
            n for n in self.list_notes()
            if (
                q in n.title.lower()
                or q in n.content.lower()
            )
        ]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_note(
        self,
        title: str = "Untitled",
    ) -> Note:
        """Create and persist a new empty note."""
        note = Note(title=title)
        self._storage.save_note(note)
        self.notes_changed.emit()
        self.note_saved.emit(note.id)
        return note

    def save_note(self, note: Note) -> None:
        """Save changes to an existing note."""
        self._storage.save_note(note)
        self.notes_changed.emit()
        self.note_saved.emit(note.id)

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by its ID."""
        ok = self._storage.delete_note(note_id)
        if ok:
            self.note_deleted.emit(note_id)
            self.notes_changed.emit()
        return ok
