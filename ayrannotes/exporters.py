"""Export notes as portable Markdown files."""

from __future__ import annotations

from pathlib import Path

from ayrannotes.storage.markdown_notes import serialize_note
from ayrannotes.storage.models import Note


def export_note(note: Note, destination: Path) -> Path:
    """Write *note* as a Markdown file and return its path."""
    destination = Path(destination)
    if destination.suffix.lower() != ".md":
        raise ValueError("Only Markdown files can be exported")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialize_note(note), encoding="utf-8")
    return destination
