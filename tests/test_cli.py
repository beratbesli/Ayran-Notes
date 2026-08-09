"""Tests for the Beer Notes CLI."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note


class CLITests(unittest.TestCase):
    """Test the beernotes-cli command-line interface."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._base = Path(self._tmpdir.name)
        self._env_patch = mock.patch.dict(os.environ, {
            "XDG_DATA_HOME": str(self._base),
        })
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmpdir.cleanup()

    def _engine(self) -> StorageEngine:
        return StorageEngine(base_dir=self._base / "beernotes")

    def test_add_note(self):
        from beernotes.cli import main
        engine = self._engine()
        rc = main(["add", "Test Note"])
        self.assertEqual(rc, 0)
        # Verify note was created
        engine2 = self._engine()
        notes = engine2.list_notes()
        titles = [n.title for n in notes]
        self.assertIn("Test Note", titles)

    def test_add_note_with_content_and_folder(self):
        from beernotes.cli import main
        main(["add", "Work Note", "--content", "Some content", "--folder", "Work"])
        engine = self._engine()
        notes = engine.list_notes()
        found = [n for n in notes if n.title == "Work Note"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].content, "Some content")
        self.assertEqual(found[0].folder, "Work")

    def test_add_note_with_tags(self):
        from beernotes.cli import main
        main(["add", "Tagged Note", "--tags", "python,coding"])
        engine = self._engine()
        notes = engine.list_notes()
        found = [n for n in notes if n.title == "Tagged Note"]
        self.assertEqual(len(found), 1)
        self.assertIn("python", found[0].tags)
        self.assertIn("coding", found[0].tags)

    def test_list_notes(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Listed Note")
        engine.save_note(note)
        rc = main(["list"])
        self.assertEqual(rc, 0)

    def test_list_notes_by_folder(self):
        from beernotes.cli import main
        engine = self._engine()
        n1 = Note(title="Note A", folder="Work")
        n2 = Note(title="Note B", folder="Personal")
        engine.save_note(n1)
        engine.save_note(n2)
        rc = main(["list", "--folder", "Work"])
        self.assertEqual(rc, 0)

    def test_list_notes_by_tag(self):
        from beernotes.cli import main
        engine = self._engine()
        n1 = Note(title="Tagged A", tags=["python"])
        n2 = Note(title="Tagged B", tags=["rust"])
        engine.save_note(n1)
        engine.save_note(n2)
        rc = main(["list", "--tag", "python"])
        self.assertEqual(rc, 0)

    def test_search_notes(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Searchable", content="unique search term here")
        engine.save_note(note)
        rc = main(["search", "unique search"])
        self.assertEqual(rc, 0)

    def test_show_note(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Show Me", content="Hello World")
        engine.save_note(note)
        rc = main(["show", note.id])
        self.assertEqual(rc, 0)

    def test_show_note_with_meta(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Meta Note", content="Content")
        engine.save_note(note)
        rc = main(["show", note.id, "--meta"])
        self.assertEqual(rc, 0)

    def test_show_note_not_found(self):
        from beernotes.cli import main
        rc = main(["show", "nonexistent123"])
        self.assertEqual(rc, 1)

    def test_delete_note_to_trash(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Trash Me")
        engine.save_note(note)
        rc = main(["delete", note.id])
        self.assertEqual(rc, 0)
        engine2 = self._engine()
        reloaded = engine2.get_note(note.id)
        self.assertTrue(reloaded.is_trashed)

    def test_delete_note_permanent(self):
        from beernotes.cli import main
        engine = self._engine()
        note = Note(title="Delete Me")
        engine.save_note(note)
        rc = main(["delete", note.id, "--permanent", "--yes"])
        self.assertEqual(rc, 0)
        engine2 = self._engine()
        reloaded = engine2.get_note(note.id)
        self.assertIsNone(reloaded)

    def test_list_folders(self):
        from beernotes.cli import main
        engine = self._engine()
        engine.save_note(Note(title="A", folder="Work"))
        engine.save_note(Note(title="B", folder="Personal"))
        rc = main(["folders"])
        self.assertEqual(rc, 0)

    def test_list_tags(self):
        from beernotes.cli import main
        engine = self._engine()
        engine.save_note(Note(title="A", tags=["python"]))
        engine.save_note(Note(title="B", tags=["python", "rust"]))
        rc = main(["tags"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
