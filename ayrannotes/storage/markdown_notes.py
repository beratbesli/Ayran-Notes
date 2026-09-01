"""Serialize Ayran Notes as readable Markdown with YAML front matter."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import yaml

from ayrannotes.storage.models import Note


def serialize_note(note: Note) -> str:
    """Return a portable Markdown representation of *note*."""
    metadata = {
        "title": note.title,
        "created": note.created_at,
        "updated": note.updated_at,
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
