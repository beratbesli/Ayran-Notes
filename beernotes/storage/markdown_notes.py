"""Serialize Beer Notes as readable Markdown with YAML front matter."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import yaml

from beernotes.storage.models import Note


def serialize_note(note: Note) -> str:
    """Return a portable Markdown representation of *note*."""
    metadata = {
        "title": note.title,
        "tags": note.tags,
        "created": note.created_at,
        "updated": note.updated_at,
        "pinned": note.is_pinned,
        "folder": note.folder,
        "favorite": note.is_favorite,
        "archived": note.is_archived,
        "trashed": note.is_trashed,
        "markdown": note.is_markdown,
        "simple_draft": note.is_simple_draft,
        "attachments": note.attachments,
    }
    front_matter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    return f"---\n{front_matter}\n---\n{note.content}"


def deserialize_note(raw: str, note_id: str) -> Note:
    """Parse a Markdown note, taking identity only from its filename."""
    metadata_text, content = _split_front_matter(raw)
    try:
        metadata = yaml.safe_load(metadata_text) or {}
    except yaml.YAMLError as error:
        raise ValueError("Note front matter is invalid YAML") from error
    if not isinstance(metadata, dict):
        raise ValueError("Note front matter must be a mapping")

    return Note.from_dict(
        {
            "id": note_id,
            "title": _text(metadata.get("title"), "Untitled"),
            "content": content,
            "folder": _text(metadata.get("folder"), "General"),
            "is_markdown": _boolean(metadata.get("markdown"), True),
            "is_pinned": _boolean(metadata.get("pinned")),
            "is_favorite": _boolean(metadata.get("favorite")),
            "is_archived": _boolean(metadata.get("archived")),
            "is_trashed": _boolean(metadata.get("trashed")),
            "is_simple_draft": _boolean(metadata.get("simple_draft")),
            "tags": _string_list(metadata.get("tags")),
            "attachments": _string_list(metadata.get("attachments")),
            "created_at": _timestamp(metadata.get("created")),
            "updated_at": _timestamp(metadata.get("updated")),
        }
    )


def _split_front_matter(raw: str) -> tuple[str, str]:
    normalized = (
        raw.removeprefix("\ufeff")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("Markdown note is missing YAML front matter")
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\n") == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1:])
    raise ValueError("Markdown note has unterminated YAML front matter")


def _text(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value)
    return text if text.strip() else default


def _timestamp(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    text = str(value).strip()
    return text or datetime.now(timezone.utc).isoformat()


def _boolean(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, list):
        values = value
    else:
        return []
    return list(
        dict.fromkeys(
            str(item).strip()
            for item in values
            if item is not None and str(item).strip()
        )
    )
