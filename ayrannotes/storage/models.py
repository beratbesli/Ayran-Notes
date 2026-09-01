"""Ayran Notes — Data models for notes and application settings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re


_NOTE_ID = re.compile(r"^[0-9a-f]{12}$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


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
        raw_id = data.get("id")
        note_id = raw_id if isinstance(raw_id, str) and _NOTE_ID.fullmatch(raw_id) else _new_id()
        raw_title = data.get("title")
        title = raw_title if isinstance(raw_title, str) else "Untitled"
        raw_content = data.get("content")
        content = raw_content if isinstance(raw_content, str) else ""
        raw_created = data.get("created_at")
        created_at = raw_created if isinstance(raw_created, str) and raw_created else _utcnow()
        raw_updated = data.get("updated_at")
        updated_at = raw_updated if isinstance(raw_updated, str) and raw_updated else _utcnow()
        return cls(
            id=note_id,
            title=title,
            content=content,
            created_at=created_at,
            updated_at=updated_at,
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
        if not isinstance(data, dict):
            return s

        theme = data.get("theme")
        if theme in {"system", "dark", "light"}:
            s.theme = theme
        accent = data.get("accent_color")
        if isinstance(accent, str) and (not accent or _HEX_COLOR.fullmatch(accent)):
            s.accent_color = accent
        family = data.get("font_family")
        if isinstance(family, str) and family.strip():
            s.font_family = family.strip()
        size = data.get("font_size")
        if isinstance(size, int) and not isinstance(size, bool):
            s.font_size = max(8, min(size, 32))
        language = data.get("language")
        if language in {"en", "tr"}:
            s.language = language
        for key in ("sidebar_visible", "preview_visible", "compact_window_migrated"):
            if isinstance(data.get(key), bool):
                setattr(s, key, data[key])
        for key, minimum, maximum in (
            ("window_width", 700, 4000),
            ("window_height", 450, 3000),
            ("window_x", -10000, 10000),
            ("window_y", -10000, 10000),
        ):
            value = data.get(key)
            if (
                isinstance(value, int)
                and not isinstance(value, bool)
                and minimum <= value <= maximum
            ):
                setattr(s, key, value)
        if data.get("view_mode") in {"simple", "detailed"}:
            s.view_mode = data["view_mode"]
        if isinstance(data.get("notes_directory"), str):
            s.notes_directory = data["notes_directory"]
        if isinstance(data.get("notes_directory_id"), str):
            s.notes_directory_id = data["notes_directory_id"]
        splitter = data.get("main_splitter_sizes")
        if isinstance(splitter, list) and all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in splitter
        ):
            s.main_splitter_sizes = splitter[:3]
        return s
