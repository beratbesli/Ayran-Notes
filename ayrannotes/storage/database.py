"""Ayran Notes — Markdown-file-based storage engine.

Settings remain XDG compliant while notes can live in any user-selected folder.
Each note is a plain Markdown file with YAML front matter.

Directory layout:
    ~/.local/share/ayrannotes/
        settings.json
        notes/
            <note_id>.md
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from ayrannotes.storage.git_versioning import git_manager
from ayrannotes.storage.markdown_notes import deserialize_note, serialize_note
from ayrannotes.storage.models import AppSettings, Note

_NOTE_ID = re.compile(r"^[0-9a-f]{12}$")
_NOTES_DIRECTORY_MARKER = ".ayrannotes-directory"
_UNSUPPORTED_FSYNC_ERRORS = {
    errno.EBADF,
    errno.EINVAL,
    errno.ENOTSUP,
    getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
}


class StorageConflictError(OSError):
    """Raised when a note changed outside Ayran Notes after it was loaded."""


def _atomic_write(path: Path, content: str) -> None:
    """Write text durably, replacing the destination only after a complete write."""
    _atomic_write_bytes(path, content.encode("utf-8"))


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically write exact bytes next to their destination."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _fsync_directory(directory: Path) -> None:
    """Persist a rename where supported, tolerating filesystems without it."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as error:
        if error.errno in _UNSUPPORTED_FSYNC_ERRORS:
            return
        raise
    try:
        os.fsync(descriptor)
    except OSError as error:
        if error.errno not in _UNSUPPORTED_FSYNC_ERRORS:
            raise
    finally:
        os.close(descriptor)


def _data_dir() -> Path:
    """Return the XDG-compliant data directory for Ayran Notes."""
    xdg = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(xdg) / "ayrannotes"


class StorageEngine:
    """Manages reading and writing notes and settings to disk."""

    def __init__(
        self,
        base_dir: Path | None = None,
        notes_dir: Path | None = None,
    ) -> None:
        self.base_dir = base_dir or _data_dir()
        self.default_notes_dir = self.base_dir / "notes"
        self.settings_file = self.base_dir / "settings.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        bootstrap_settings = self.load_settings()
        configured = (
            notes_dir
            if notes_dir is not None
            else bootstrap_settings.notes_directory
        )
        self._notes_directory_identity = (
            ""
            if notes_dir is not None
            else bootstrap_settings.notes_directory_id
        )
        self.notes_dir = self._resolve_notes_directory(configured)
        self._ensure_dirs()
        git_manager.init_repo(self.notes_dir)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        """Create the data directories if they don't exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if self.notes_dir == self.default_notes_dir:
            self.notes_dir.mkdir(parents=True, exist_ok=True)
        elif not self.notes_dir.is_dir():
            raise FileNotFoundError(
                f"Configured notes directory is unavailable: {self.notes_dir}"
            )
        else:
            self._validate_notes_directory_identity(
                self.notes_dir,
                self._notes_directory_identity,
            )

    def _resolve_notes_directory(self, value: object) -> Path:
        if value is None or not str(value).strip():
            return self.default_notes_dir
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = self.base_dir / path
        return path.resolve()

    def configure_notes_directory(
        self,
        directory: Path | str | None,
        *,
        expected_identity: str = "",
    ) -> Path:
        """Switch the note source to *directory* without duplicating files."""
        destination = self._resolve_notes_directory(directory)
        if destination == self.default_notes_dir:
            destination.mkdir(parents=True, exist_ok=True)
        elif not destination.is_dir():
            raise FileNotFoundError(
                f"Notes directory does not exist: {destination}"
            )
        else:
            self._validate_notes_directory_identity(
                destination,
                expected_identity,
            )
        previous_directory = self.notes_dir
        previous_identity = self._notes_directory_identity
        self.notes_dir = destination
        self._notes_directory_identity = expected_identity
        try:
            git_manager.init_repo(destination)
        except BaseException:
            self.notes_dir = previous_directory
            self._notes_directory_identity = previous_identity
            raise
        return destination

    def ensure_notes_directory_identity(self) -> str:
        """Return a stable marker used to detect an unavailable mounted disk."""
        if self.notes_dir == self.default_notes_dir:
            self._notes_directory_identity = ""
            return ""
        marker = self.notes_dir / _NOTES_DIRECTORY_MARKER
        identity = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
        if not identity:
            identity = uuid.uuid4().hex
            _atomic_write(marker, identity + "\n")
        self._notes_directory_identity = identity
        return identity

    @staticmethod
    def _validate_notes_directory_identity(
        directory: Path,
        expected_identity: str,
    ) -> None:
        if not expected_identity:
            return
        marker = directory / _NOTES_DIRECTORY_MARKER
        try:
            actual_identity = marker.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise OSError(
                f"Notes directory marker is unavailable: {directory}"
            ) from error
        if actual_identity != expected_identity:
            raise OSError(
                f"Notes directory marker does not match: {directory}"
            )

    def _validate_active_notes_directory(self) -> None:
        """Fail before I/O when a configured removable directory changed."""
        if self.notes_dir == self.default_notes_dir:
            return
        if not self.notes_dir.is_dir():
            raise FileNotFoundError(
                f"Configured notes directory is unavailable: {self.notes_dir}"
            )
        self._validate_notes_directory_identity(
            self.notes_dir,
            self._notes_directory_identity,
        )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> AppSettings:
        """Load application settings from disk, or return defaults."""
        if not self.settings_file.exists():
            return AppSettings()
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Settings file is invalid JSON: {self.settings_file}"
            ) from error
        if not isinstance(data, dict):
            raise ValueError(
                f"Settings file root must be an object: {self.settings_file}"
            )
        for key in ("notes_directory", "notes_directory_id"):
            if key in data and not isinstance(data[key], str):
                raise ValueError(
                    f"Settings field {key!r} must be a string: "
                    f"{self.settings_file}"
                )
        return AppSettings.from_dict(data)

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
        return self.notes_dir / f"{note_id}.md"

    @staticmethod
    def _revision(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _read_note_path(self, path: Path) -> Note:
        raw = path.read_bytes()
        note = deserialize_note(raw.decode("utf-8"), path.stem)
        note._storage_revision = self._revision(raw)
        return note

    def list_notes(self) -> list[Note]:
        """Return all saved Markdown notes, newest first."""
        self._validate_active_notes_directory()
        notes: list[Note] = []
        for fp in self.notes_dir.glob("*.md"):
            if (
                not _NOTE_ID.fullmatch(fp.stem)
                or not fp.is_file()
                or fp.is_symlink()
            ):
                continue
            try:
                notes.append(self._read_note_path(fp))
            except (OSError, TypeError, ValueError):
                continue
        return sorted(notes, key=lambda n: n.updated_at, reverse=True)

    def get_note(self, note_id: str) -> Note | None:
        """Load a single note by its ID."""
        try:
            path = self._note_path(note_id)
        except ValueError:
            return None
        self._validate_active_notes_directory()
        if path.exists():
            try:
                return self._read_note_path(path)
            except (OSError, TypeError, ValueError):
                return None
        return None

    def get_note_history(self, note_id: str, limit: int = 20) -> list[dict]:
        """Return only the local Git history belonging to one note."""
        self._validate_active_notes_directory()
        path = self._note_path(note_id)
        return git_manager.get_history(self.notes_dir, path, limit=limit)

    @property
    def git_history_available(self) -> bool:
        """Whether local Git history can currently be queried."""
        try:
            self._validate_active_notes_directory()
        except OSError:
            return False
        return git_manager.is_repo(self.notes_dir)

    def get_note_version(self, note_id: str, commit_hash: str) -> Note | None:
        """Read and parse a note exactly as it existed in a Git commit."""
        self._validate_active_notes_directory()
        path = self._note_path(note_id)
        if not self._is_note_history_commit(path, commit_hash):
            return None
        raw = git_manager.get_file_version(self.notes_dir, path, commit_hash)
        if not raw:
            return None
        try:
            return deserialize_note(raw, note_id)
        except (TypeError, ValueError):
            return None

    def list_deleted_notes(self, limit: int = 20) -> list[dict]:
        """Find deleted note files from local Git history only."""
        self._validate_active_notes_directory()
        deleted = git_manager.list_deleted_notes(self.notes_dir, limit=limit)
        available: list[dict] = []
        for entry in deleted:
            note_id = entry.get("note_id", "")
            commit_hash = entry.get("hash", "")
            if not isinstance(note_id, str) or not isinstance(commit_hash, str):
                continue
            path = self._note_path(note_id)
            if path.exists() or path.is_symlink():
                continue
            raw = git_manager.get_file_version(
                self.notes_dir,
                path,
                self._parent_commit(commit_hash),
            )
            try:
                entry["title"] = deserialize_note(raw, note_id).title
            except (TypeError, ValueError):
                entry["title"] = note_id
            available.append(entry)
        return available[:limit]

    def _parent_commit(self, commit_hash: str) -> str:
        """Return the first parent of a validated deletion commit."""
        return git_manager.get_parent_commit(self.notes_dir, commit_hash)

    def _is_note_history_commit(self, path: Path, commit_hash: str) -> bool:
        return any(
            entry.get("hash") == commit_hash
            for entry in git_manager.get_history(self.notes_dir, path)
        )

    def save_note(self, note: Note) -> None:
        """Create or update a note on disk."""
        self._write_note(note, touch=True)

    def _write_note(self, note: Note, *, touch: bool) -> None:
        self._validate_active_notes_directory()
        previous_updated_at = note.updated_at
        previous_revision = note._storage_revision
        path = self._note_path(note.id)
        if path.exists():
            actual_revision = self._revision(path.read_bytes())
            if (
                not note._storage_revision
                or note._storage_revision != actual_revision
            ):
                raise StorageConflictError(
                    f"Note changed outside Ayran Notes: {note.title}"
                )
        elif note._storage_revision:
            raise StorageConflictError(
                f"Note was removed outside Ayran Notes: {note.title}"
            )
        if touch:
            note.touch()
        try:
            serialized = serialize_note(note).encode("utf-8")
            _atomic_write_bytes(path, serialized)
            note._storage_revision = self._revision(serialized)
            git_manager.schedule_commit(self.notes_dir, f"Update: {note.title}")
        except BaseException:
            note.updated_at = previous_updated_at
            note._storage_revision = previous_revision
            raise

    def restore_note_version(
        self,
        note_id: str,
        commit_hash: str,
        *,
        expected_revision: str = "",
    ) -> Note:
        """Restore an existing note as a new version without rewriting history."""
        self._validate_active_notes_directory()
        path = self._note_path(note_id)
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(f"Note does not exist: {note_id}")
        previous_bytes = path.read_bytes()
        if expected_revision and self._revision(previous_bytes) != expected_revision:
            raise StorageConflictError(f"Note changed outside Ayran Notes: {note_id}")
        if not self._is_note_history_commit(path, commit_hash):
            raise ValueError("Selected version does not belong to this note")
        raw = git_manager.get_file_version(self.notes_dir, path, commit_hash)
        if not raw:
            raise ValueError("Selected note version could not be read")
        try:
            restored = deserialize_note(raw, note_id)
        except (TypeError, ValueError) as error:
            raise ValueError("Selected note version is invalid") from error
        return self._write_restored_note(
            path,
            restored,
            previous_bytes=previous_bytes,
            commit_message=f"Restore: {restored.title}",
        )

    def restore_deleted_note(
        self,
        note_id: str,
        commit_hash: str,
        *,
        new_note_id: str | None = None,
    ) -> Note:
        """Restore a deleted note from its last existing Git version."""
        self._validate_active_notes_directory()
        source_path = self._note_path(note_id)
        if source_path.exists() or source_path.is_symlink():
            if new_note_id is None:
                raise FileExistsError(f"A note with ID already exists: {note_id}")
        if not any(
            entry.get("note_id") == note_id and entry.get("hash") == commit_hash
            for entry in git_manager.list_deleted_notes(self.notes_dir)
        ):
            raise ValueError("Selected deletion does not belong to this note")
        parent = git_manager.get_parent_commit(self.notes_dir, commit_hash)
        if not parent:
            raise ValueError("Deleted note version has no readable parent")
        raw = git_manager.get_file_version(self.notes_dir, source_path, parent)
        if not raw:
            raise ValueError("Deleted note version could not be read")
        try:
            restored = deserialize_note(raw, note_id)
        except (TypeError, ValueError) as error:
            raise ValueError("Deleted note version is invalid") from error
        target_id = new_note_id or note_id
        target_path = self._note_path(target_id)
        if target_path.exists() or target_path.is_symlink():
            raise FileExistsError(f"A note with ID already exists: {target_id}")
        restored.id = target_id
        return self._write_restored_note(
            target_path,
            restored,
            previous_bytes=None,
            commit_message=f"Restore deleted note: {restored.title}",
        )

    def _write_restored_note(
        self,
        path: Path,
        note: Note,
        *,
        previous_bytes: bytes | None,
        commit_message: str,
    ) -> Note:
        """Atomically write and commit a restored note, rolling back on failure."""
        previous_updated_at = note.updated_at
        note.touch()
        serialized = serialize_note(note).encode("utf-8")
        git_manager.cancel_scheduled_commit()
        try:
            _atomic_write_bytes(path, serialized)
            if not git_manager.commit_change(self.notes_dir, commit_message):
                raise OSError("Restored note could not be committed")
        except BaseException:
            try:
                if previous_bytes is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write_bytes(path, previous_bytes)
            finally:
                note.updated_at = previous_updated_at
            raise
        note._storage_revision = self._revision(serialized)
        return note

    def delete_note(self, note_id: str) -> bool:
        """Delete a note file. Returns True if found and deleted."""
        try:
            path = self._note_path(note_id)
        except ValueError:
            return False
        self._validate_active_notes_directory()
        if path.exists():
            title = note_id
            try:
                title = self._read_note_path(path).title
            except BaseException:
                pass
            path.unlink()
            git_manager.schedule_commit(self.notes_dir, f"Delete: {title}")
            return True
        return False
