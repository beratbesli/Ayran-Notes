"""Import parsing and export/import round-trip tests."""

import json
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ayrannotes.exporters import export_note
from ayrannotes.importers import import_note
from ayrannotes.storage.models import Note
from ayrannotes.storage.markdown_notes import serialize_note


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_round_trips_exported_text_formats(self) -> None:
        original = Note(
            title="Release Plan",
            content="Hello **world**.",
            tags=["work", "v1"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for suffix in (".md", ".txt", ".html"):
                imported = import_note(export_note(original, directory / f"note{suffix}"))
                self.assertEqual(imported.title, original.title)
                self.assertEqual(imported.tags, original.tags)
                self.assertIn("Hello", imported.content)

    def test_imports_native_json_without_reusing_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.json"
            path.write_text(json.dumps(Note(title="Native", folder="Work").to_dict()))
            imported = import_note(path)
            self.assertEqual(imported.title, "Native")
            self.assertEqual(imported.folder, "Work")

    def test_imports_stored_markdown_front_matter(self) -> None:
        note = Note(
            title="Portable",
            content="Raw Markdown body",
            folder="Shared",
            tags=["plain", "yaml"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portable.md"
            path.write_text(serialize_note(note), encoding="utf-8")

            imported = import_note(path)

        self.assertEqual(imported.title, "Portable")
        self.assertEqual(imported.content, "Raw Markdown body")
        self.assertEqual(imported.folder, "Shared")
        self.assertEqual(imported.tags, ["plain", "yaml"])

    def test_rejects_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.pdf"
            path.write_bytes(b"%PDF")
            with self.assertRaises(ValueError):
                import_note(path)


if __name__ == "__main__":
    unittest.main()
