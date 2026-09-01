"""Import external Markdown files as Ayran Notes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ayrannotes.storage.markdown_notes import deserialize_note


@dataclass(frozen=True)
class ImportedNote:
    """The user-editable fields extracted from an external Markdown file."""

    title: str
    content: str


def import_note(path: Path) -> ImportedNote:
    """Read a Markdown file and return its title and body."""
    path = Path(path)
    if path.suffix.lower() not in {".md", ".markdown"}:
        raise ValueError("Only Markdown files can be imported")
    raw = path.read_text(encoding="utf-8")
    if raw.lstrip().startswith("---"):
        note = deserialize_note(raw, "000000000000")
        return ImportedNote(note.title, note.content)

    lines = raw.splitlines()
    title = path.stem or "Untitled"
    if lines and lines[0].startswith("# "):
        title = lines.pop(0)[2:].strip() or title
        while lines and not lines[0].strip():
            lines.pop(0)
    return ImportedNote(title, "\n".join(lines).rstrip())
