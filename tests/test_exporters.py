"""Tests for portable note export formats."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from beernotes.exporters import export_note
from beernotes.storage.models import Note


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_exports_markdown_text_html_and_pdf(self) -> None:
        note = Note(
            title="Release <Plan>",
            content="Hello **world**.\n\n- first",
            tags=["work", "v1"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for suffix in (".md", ".txt", ".html", ".pdf"):
                path = export_note(note, directory / f"note{suffix}")
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 10)

            self.assertIn("# Release <Plan>", (directory / "note.md").read_text())
            plain = (directory / "note.txt").read_text()
            self.assertIn("Release <Plan>", plain)
            self.assertNotIn("**world**", plain)
            html_text = (directory / "note.html").read_text()
            self.assertIn("Release &lt;Plan&gt;", html_text)
            self.assertTrue((directory / "note.pdf").read_bytes().startswith(b"%PDF"))

    def test_rejects_unknown_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                export_note(Note(), Path(tmp) / "note.docx")


if __name__ == "__main__":
    unittest.main()
