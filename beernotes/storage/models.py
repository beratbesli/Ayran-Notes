"""Beer Notes — Data models for notes and application settings."""

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
    folder: str = "General"
    is_markdown: bool = True
    is_pinned: bool = False
    is_favorite: bool = False
    is_archived: bool = False
    is_trashed: bool = False
    tags: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    def touch(self) -> None:
        """Update the `updated_at` timestamp to now."""
        self.updated_at = _utcnow()

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "folder": self.folder,
            "is_markdown": self.is_markdown,
            "is_pinned": self.is_pinned,
            "is_favorite": self.is_favorite,
            "is_archived": self.is_archived,
            "is_trashed": self.is_trashed,
            "tags": self.tags,
            "attachments": self.attachments,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Note:
        """Deserialize from a dictionary."""
        raw_tags = data.get("tags", [])
        tags = []
        if isinstance(raw_tags, list):
            tags = list(dict.fromkeys(
                tag.strip() for tag in raw_tags
                if isinstance(tag, str) and tag.strip()
            ))
        raw_attachments = data.get("attachments", [])
        attachments = [
            item for item in raw_attachments
            if isinstance(item, str) and item.strip()
        ] if isinstance(raw_attachments, list) else []
        return cls(
            id=data.get("id", _new_id()),
            title=data.get("title", "Untitled"),
            content=data.get("content", ""),
            folder=data.get("folder", "General"),
            is_markdown=data.get("is_markdown", True),
            is_pinned=data.get("is_pinned", False),
            is_favorite=data.get("is_favorite", False),
            is_archived=data.get("is_archived", False),
            is_trashed=data.get("is_trashed", False),
            tags=tags,
            attachments=attachments,
            created_at=data.get("created_at", _utcnow()),
            updated_at=data.get("updated_at", _utcnow()),
        )


@dataclass
class AppSettings:
    """Persisted application settings."""

    theme: str = "dark"               # "dark" | "light"
    accent_color: str = "#F59E0B"     # amber/beer accent
    font_family: str = "Inter"
    font_size: int = 14
    language: str = "en"              # "en" | "tr"
    sidebar_visible: bool = True
    preview_visible: bool = True
    window_width: int = 1200
    window_height: int = 750
    window_x: int = 100
    window_y: int = 100
    sidebar_folder_height: int = 170

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
            "sidebar_folder_height": self.sidebar_folder_height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Deserialize from a dictionary."""
        s = cls()
        for key in s.to_dict():
            if key in data:
                setattr(s, key, data[key])
        return s
