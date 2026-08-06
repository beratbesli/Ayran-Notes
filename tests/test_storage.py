"""Storage safety and compatibility tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note


class StorageEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary.name)
        self.storage = StorageEngine(self.base_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_rejects_note_id_path_traversal(self) -> None:
        self.assertIsNone(self.storage.get_note("../../outside"))
        self.assertFalse(self.storage.delete_note("../../outside"))
        with self.assertRaises(ValueError):
            self.storage.save_note(Note(id="../../outside"))

    def test_filename_is_authoritative_for_loaded_note_id(self) -> None:
        note = Note(title="Safe")
        data = note.to_dict()
        data["id"] = "../../outside"
        (self.storage.notes_dir / f"{note.id}.json").write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        loaded = self.storage.list_notes()
        self.assertEqual(loaded[0].id, note.id)

    def test_failed_atomic_replace_preserves_previous_note(self) -> None:
        note = Note(title="Original")
        self.storage.save_note(note)
        note.title = "Changed"

        with patch("beernotes.storage.database.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.storage.save_note(note)

        persisted = self.storage.get_note(note.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.title, "Original")
        self.assertEqual(list(self.storage.notes_dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
