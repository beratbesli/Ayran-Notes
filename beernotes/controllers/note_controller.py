"""Beer Notes — Note controller.

Bridges the UI layer and the storage engine, managing note
lifecycle operations and search/filter logic.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note


class NoteController(QObject):
    """Handles all note CRUD operations and emits signals for UI updates."""

    notes_changed = pyqtSignal()          # list was modified
    note_saved = pyqtSignal(str)          # note_id
    note_deleted = pyqtSignal(str)        # note_id

    def __init__(self, storage: StorageEngine, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._storage = storage

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_notes(self, folder: Optional[str] = None) -> List[Note]:
        """Return notes, optionally filtered by *folder*."""
        notes = self._storage.list_notes()
        if folder and folder != "__all__":
            notes = [n for n in notes if n.folder == folder]
        return notes

    def get_note(self, note_id: str) -> Optional[Note]:
        """Load a single note."""
        return self._storage.get_note(note_id)

    def search(self, query: str, folder: Optional[str] = None) -> List[Note]:
        """Full-text search across title and content."""
        q = query.lower().strip()
        if not q:
            return self.list_notes(folder)
        return [
            n for n in self.list_notes(folder)
            if q in n.title.lower() or q in n.content.lower()
        ]

    def get_folders(self) -> List[str]:
        """Return sorted unique folder names."""
        return self._storage.get_folders()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_note(self, title: str = "Untitled", folder: str = "General") -> Note:
        """Create and persist a new empty note."""
        note = Note(title=title, folder=folder)
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

    def toggle_pin(self, note_id: str) -> Optional[Note]:
        """Toggle the pinned state of a note."""
        note = self._storage.get_note(note_id)
        if note:
            note.is_pinned = not note.is_pinned
            self._storage.save_note(note)
            self.notes_changed.emit()
            return note
        return None

    def move_to_folder(self, note_id: str, folder: str) -> Optional[Note]:
        """Move a note to a different folder."""
        note = self._storage.get_note(note_id)
        if note:
            note.folder = folder
            self._storage.save_note(note)
            self.notes_changed.emit()
            return note
        return None
