"""Tests for Markdown-only import."""

import tempfile
import unittest
from pathlib import Path

from ayrannotes.importers import import_note


class ImportTests(unittest.TestCase):
    def test_imports_plain_markdown_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "release.md"
            path.write_text("# Release Plan\n\nHello **world**.", encoding="utf-8")
            imported = import_note(path)

        self.assertEqual(imported.title, "Release Plan")
        self.assertEqual(imported.content, "Hello **world**.")

    def test_imports_native_markdown_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portable.md"
            path.write_text(
                "---\ntitle: Portable\ncreated: 2024-01-01\nupdated: 2024-01-02\n---\nBody\n",
                encoding="utf-8",
            )
            imported = import_note(path)

        self.assertEqual(imported.title, "Portable")
        self.assertEqual(imported.content, "Body\n")

    def test_rejects_non_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("text", encoding="utf-8")
            with self.assertRaises(ValueError):
                import_note(path)


if __name__ == "__main__":
    unittest.main()
