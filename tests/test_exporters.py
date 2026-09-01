"""Tests for portable Markdown export."""

import tempfile
import unittest
from pathlib import Path

from ayrannotes.exporters import export_note
from ayrannotes.storage.models import Note


class ExportTests(unittest.TestCase):
    def test_exports_markdown_only(self) -> None:
        note = Note(title="Release Plan", content="Hello **world**.")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = export_note(note, directory / "note.md")
            self.assertTrue(path.is_file())
            raw = path.read_text(encoding="utf-8")
            self.assertIn("title: Release Plan", raw)
            self.assertTrue(raw.endswith(note.content))

            with self.assertRaises(ValueError):
                export_note(note, directory / "note.html")


if __name__ == "__main__":
    unittest.main()
