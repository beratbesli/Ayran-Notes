"""Beer Notes — Note controller.

Bridges the UI layer and the storage engine, managing note
lifecycle operations and search/filter logic.
"""

from __future__ import annotations

from pathlib import Path
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

    @property
    def notes_directory(self) -> Path:
        """Return the directory that is currently the note source of truth."""
        return self._storage.notes_dir

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_notes(self, folder: Optional[str] = None) -> List[Note]:
        """Return notes, optionally filtered by *folder*."""
        notes = self._storage.list_notes()
        if folder == "__trash__":
            return [note for note in notes if note.is_trashed]
        if folder == "__archive__":
            return [note for note in notes if note.is_archived and not note.is_trashed]

        notes = [note for note in notes if not note.is_archived and not note.is_trashed]
        if folder == "__favorites__":
            return [note for note in notes if note.is_favorite]
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
            if (
                q in n.title.lower()
                or q in n.content.lower()
                or any(q in tag.lower() for tag in n.tags)
            )
        ]

    def get_folders(self) -> List[str]:
        """Return sorted unique folder names."""
        folders = {
            note.folder
            for note in self._storage.list_notes()
            if not note.is_archived and not note.is_trashed
        }
        folders.add("General")
        return sorted(folders)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_note(
        self,
        title: str = "Untitled",
        folder: str = "General",
        *,
        simple_draft: bool = False,
    ) -> Note:
        """Create and persist a new empty note."""
        note = Note(
            title=title,
            folder=folder,
            is_simple_draft=simple_draft,
        )
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

    def toggle_favorite(self, note_id: str) -> Optional[Note]:
        """Toggle whether a note appears in Favorites."""
        note = self._storage.get_note(note_id)
        if note:
            note.is_favorite = not note.is_favorite
            self._storage.save_note(note)
            self.notes_changed.emit()
            return note
        return None

    def set_archived(self, note_id: str, archived: bool = True) -> Optional[Note]:
        """Archive or unarchive a note."""
        note = self._storage.get_note(note_id)
        if note:
            note.is_archived = archived
            note.is_trashed = False
            self._storage.save_note(note)
            self.notes_changed.emit()
            return note
        return None

    def move_to_trash(self, note_id: str) -> Optional[Note]:
        """Move a note to Trash without destroying it."""
        note = self._storage.get_note(note_id)
        if note:
            note.is_trashed = True
            note.is_pinned = False
            self._storage.save_note(note)
            self.notes_changed.emit()
            return note
        return None

    def restore_note(self, note_id: str) -> Optional[Note]:
        """Restore a note from Trash to its previous folder."""
        note = self._storage.get_note(note_id)
        if note:
            note.is_trashed = False
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

    def add_attachment(self, note_id: str, source: Path) -> Optional[Path]:
        """Copy an attachment into managed storage and associate it with a note."""
        note = self._storage.get_note(note_id)
        if not note:
            return None
        destination = self._storage.add_attachment(note_id, source)
        relative_path = destination.relative_to(self._storage.base_dir).as_posix()
        note.attachments.append(relative_path)
        self._storage.save_note(note)
        self.notes_changed.emit()
        return destination
