"""Beer Notes — JSON-file-based storage engine.

Notes and settings are stored as JSON files under
~/.local/share/beernotes/  (XDG_DATA_HOME compliant).

Directory layout:
    ~/.local/share/beernotes/
        settings.json
        notes/
            <note_id>.json
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional

from beernotes.storage.models import AppSettings, Note

_NOTE_ID = re.compile(r"^[0-9a-f]{12}$")


def _atomic_write(path: Path, content: str) -> None:
    """Write text durably, replacing the destination only after a complete write."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _data_dir() -> Path:
    """Return the XDG-compliant data directory for Beer Notes."""
    xdg = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(xdg) / "beernotes"


class StorageEngine:
    """Manages reading and writing notes and settings to disk."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _data_dir()
        self.notes_dir = self.base_dir / "notes"
        self.settings_file = self.base_dir / "settings.json"
        self._ensure_dirs()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        """Create the data directories if they don't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> AppSettings:
        """Load application settings from disk, or return defaults."""
        if self.settings_file.exists():
            try:
                data = json.loads(self.settings_file.read_text(encoding="utf-8"))
                return AppSettings.from_dict(data)
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        return AppSettings()

    def save_settings(self, settings: AppSettings) -> None:
        """Persist application settings to disk."""
        _atomic_write(
            self.settings_file,
            json.dumps(settings.to_dict(), indent=2, ensure_ascii=False),
        )

    # ------------------------------------------------------------------
    # Notes CRUD
    # ------------------------------------------------------------------

    def _note_path(self, note_id: str) -> Path:
        if not isinstance(note_id, str) or not _NOTE_ID.fullmatch(note_id):
            raise ValueError("Invalid note ID")
        return self.notes_dir / f"{note_id}.json"

    def list_notes(self) -> List[Note]:
        """Return all saved notes, sorted: pinned first, then by updated_at descending."""
        notes: List[Note] = []
        for fp in self.notes_dir.glob("*.json"):
            if not _NOTE_ID.fullmatch(fp.stem):
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                data["id"] = fp.stem
                notes.append(Note.from_dict(data))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                continue
        pinned = sorted(
            [n for n in notes if n.is_pinned],
            key=lambda n: n.updated_at,
            reverse=True,
        )
        unpinned = sorted(
            [n for n in notes if not n.is_pinned],
            key=lambda n: n.updated_at,
            reverse=True,
        )
        return pinned + unpinned

    def get_note(self, note_id: str) -> Optional[Note]:
        """Load a single note by its ID."""
        try:
            path = self._note_path(note_id)
        except ValueError:
            return None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["id"] = note_id
                return Note.from_dict(data)
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                return None
        return None

    def save_note(self, note: Note) -> None:
        """Create or update a note on disk."""
        note.touch()
        _atomic_write(
            self._note_path(note.id),
            json.dumps(note.to_dict(), indent=2, ensure_ascii=False),
        )

    def delete_note(self, note_id: str) -> bool:
        """Delete a note file. Returns True if found and deleted."""
        try:
            path = self._note_path(note_id)
        except ValueError:
            return False
        if path.exists():
            path.unlink()
            return True
        return False

    def get_folders(self) -> List[str]:
        """Return a sorted list of unique folder names across all notes."""
        folders = set()
        for fp in self.notes_dir.glob("*.json"):
            if not _NOTE_ID.fullmatch(fp.stem):
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                folders.add(data.get("folder", "General"))
            except (json.JSONDecodeError, OSError, TypeError):
                continue
        if "General" not in folders:
            folders.add("General")
        return sorted(folders)
