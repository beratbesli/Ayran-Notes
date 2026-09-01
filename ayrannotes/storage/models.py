"""Ayran Notes — Data models for notes and application settings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new unique note ID."""
    return uuid.uuid4().hex[:12]


@dataclass
class Note:
    """Represents a single note."""

    id: str = field(default_factory=_new_id)
    title: str = "Untitled"
    content: str = ""
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    _storage_revision: str = field(default="", repr=False, compare=False)

    def touch(self) -> None:
        """Update the `updated_at` timestamp to now."""
        self.updated_at = _utcnow()

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Note:
        """Deserialize from a dictionary."""
        return cls(
            id=data.get("id", _new_id()),
            title=data.get("title", "Untitled"),
            content=data.get("content", ""),
            created_at=data.get("created_at", _utcnow()),
            updated_at=data.get("updated_at", _utcnow()),
        )


@dataclass
class AppSettings:
    """Persisted application settings."""

    theme: str = "system"             # "system" | "dark" | "light"
    accent_color: str = ""            # empty means system accent
    font_family: str = "Inter"
    font_size: int = 14
    language: str = "en"              # "en" | "tr"
    sidebar_visible: bool = True
    preview_visible: bool = True
    window_width: int = 1000
    window_height: int = 680
    window_x: int = 100
    window_y: int = 100
    view_mode: str = "simple"
    notes_directory: str = ""
    notes_directory_id: str = ""
    compact_window_migrated: bool = False
    main_splitter_sizes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "theme": self.theme,
            "accent_color": self.accent_color,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "language": self.language,
            "sidebar_visible": self.sidebar_visible,
            "preview_visible": self.preview_visible,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "window_x": self.window_x,
            "window_y": self.window_y,
            "view_mode": self.view_mode,
            "notes_directory": self.notes_directory,
            "notes_directory_id": self.notes_directory_id,
            "compact_window_migrated": self.compact_window_migrated,
            "main_splitter_sizes": self.main_splitter_sizes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Deserialize from a dictionary."""
        s = cls()
        for key in s.to_dict():
            if key in data:
                setattr(s, key, data[key])
        if s.view_mode not in {"simple", "detailed"}:
            s.view_mode = "simple"
        if not isinstance(s.notes_directory, str):
            s.notes_directory = ""
        if not isinstance(s.notes_directory_id, str):
            s.notes_directory_id = ""
        if not isinstance(s.main_splitter_sizes, list):
            s.main_splitter_sizes = []
        return s
