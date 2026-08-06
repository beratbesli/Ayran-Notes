"""Import external note files into a normalized representation."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtGui import QTextDocument

from beernotes.storage.models import Note


SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm", ".json"}


@dataclass
class ImportedNote:
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    folder: str | None = None
    is_markdown: bool = True


def _consume_metadata(lines: list[str], fallback_title: str) -> tuple[str, list[str], list[str]]:
    while lines and not lines[0].strip():
        lines.pop(0)
    title = fallback_title
    if lines and lines[0].startswith("# "):
        title = lines.pop(0)[2:].strip() or fallback_title
    elif lines:
        title = lines.pop(0).strip() or fallback_title
    while lines and not lines[0].strip():
        lines.pop(0)

    tags: list[str] = []
    if lines and lines[0].startswith("**Tags:**"):
        tags = [tag.strip() for tag in lines.pop(0)[9:].split(",") if tag.strip()]
    elif lines and all(part.startswith("#") for part in lines[0].split()):
        tags = [part[1:] for part in lines.pop(0).split() if len(part) > 1]
    while lines and not lines[0].strip():
        lines.pop(0)
    return title, tags, lines


def import_note(path: Path) -> ImportedNote:
    """Read a supported file and return data ready for creating a new note."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported import format: {suffix or 'missing extension'}")

    raw = path.read_text(encoding="utf-8")
    fallback_title = path.stem or "Imported Note"

    if suffix == ".json":
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("The JSON root must be an object")
        note = Note.from_dict(data)
        return ImportedNote(
            title=note.title,
            content=note.content,
            tags=note.tags,
            folder=note.folder,
            is_markdown=note.is_markdown,
        )

    if suffix in {".md", ".markdown"}:
        title, tags, lines = _consume_metadata(raw.splitlines(), fallback_title)
        return ImportedNote(title, "\n".join(lines).rstrip(), tags, is_markdown=True)

    if suffix == ".txt":
        title, tags, lines = _consume_metadata(raw.splitlines(), fallback_title)
        return ImportedNote(title, "\n".join(lines).rstrip(), tags, is_markdown=False)

    title_match = re.search(r"<title\b[^>]*>(.*?)</title>", raw, re.I | re.S)
    title = (
        html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
        if title_match else fallback_title
    )
    document = QTextDocument()
    document.setHtml(raw)
    lines = document.toPlainText().splitlines()
    parsed_title, tags, content_lines = _consume_metadata(lines, title)
    if title_match:
        parsed_title = title
    return ImportedNote(
        parsed_title,
        "\n".join(content_lines).rstrip(),
        tags,
        is_markdown=False,
    )
