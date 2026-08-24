"""Ayran Notes — Markdown-file-based storage engine.

Settings remain XDG compliant while notes can live in any user-selected folder.
Each note is a plain Markdown file with YAML front matter.

Directory layout:
    ~/.local/share/ayrannotes/
        settings.json
        notes/
            <note_id>.md
        legacy-json-backup/
            <note_id>.json
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
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
        self.attachments_dir = self.base_dir / "attachments"
        self.migration_backup_dir = self.base_dir / "legacy-json-backup"
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
        self._migrate_legacy_json_notes()
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
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

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
            self._migrate_legacy_json_notes()
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

    def _migrate_legacy_json_notes(self) -> int:
        """Convert legacy JSON notes once, retaining exact originals as backup."""
        converted = 0
        source_directories = {self.default_notes_dir, self.notes_dir}
        for source_directory in source_directories:
            if not source_directory.is_dir():
                continue
            backup_directory = self._migration_backup_directory(
                source_directory
            )
            for source in sorted(source_directory.glob("*.json")):
                if (
                    not _NOTE_ID.fullmatch(source.stem)
                    or not source.is_file()
                    or source.is_symlink()
                ):
                    continue
                if self._migrate_legacy_note(source, backup_directory):
                    converted += 1
        return converted

    def _migration_backup_directory(self, source_directory: Path) -> Path:
        if source_directory.resolve() == self.default_notes_dir.resolve():
            namespace = "default"
        else:
            namespace = hashlib.sha256(
                str(source_directory.resolve()).encode("utf-8")
            ).hexdigest()[:12]
        return self.migration_backup_dir / namespace

    def _migrate_legacy_note(
        self,
        source: Path,
        backup_directory: Path,
    ) -> bool:
        source_bytes = source.read_bytes()
        backup_directory.mkdir(parents=True, exist_ok=True)
        backup = backup_directory / source.name
        if backup.exists():
            if backup.read_bytes() != source_bytes:
                return False
        else:
            _atomic_write_bytes(backup, source_bytes)
            if backup.read_bytes() != source_bytes:
                return False

        try:
            data = json.loads(source_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                return False
            data["id"] = source.stem
            note = Note.from_dict(data)
        except (json.JSONDecodeError, UnicodeError, TypeError, ValueError):
            return False

        destination = source.with_suffix(".md")
        if destination.exists():
            try:
                existing = self._read_note_path(destination)
            except (OSError, TypeError, ValueError):
                return False
            if existing.to_dict() != note.to_dict():
                return False
        else:
            serialized = serialize_note(note).encode("utf-8")
            _atomic_write_bytes(destination, serialized)
            try:
                migrated = self._read_note_path(destination)
            except (OSError, TypeError, ValueError):
                return False
            if migrated.to_dict() != note.to_dict():
                return False

        source.unlink()
        return True

    @staticmethod
    def _revision(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _read_note_path(self, path: Path) -> Note:
        raw = path.read_bytes()
        note = deserialize_note(raw.decode("utf-8"), path.stem)
        note._storage_revision = self._revision(raw)
        return note

    def list_notes(self) -> list[Note]:
        """Return all saved notes, sorted: pinned first, then by updated_at descending."""
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
            shutil.rmtree(self.attachments_dir / note_id, ignore_errors=True)
            git_manager.schedule_commit(self.notes_dir, f"Delete: {title}")
            return True
        return False

    def add_attachment(self, note_id: str, source: Path) -> Path:
        """Copy a file into this note's managed attachment directory."""
        self._note_path(note_id)  # validates the ID
        self._validate_active_notes_directory()
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        note_attachments = self.attachments_dir / note_id
        note_attachments.mkdir(parents=True, exist_ok=True)
        safe_name = Path(source.name).name
        destination = note_attachments / safe_name
        if destination.exists():
            destination = note_attachments / f"{uuid.uuid4().hex[:8]}-{safe_name}"
        shutil.copy2(source, destination)
        return destination

    def get_folders(self) -> list[str]:
        """Return a sorted list of unique folder names across all notes."""
        folders = {note.folder for note in self.list_notes()}
        if "General" not in folders:
            folders.add("General")
        return sorted(folders)
