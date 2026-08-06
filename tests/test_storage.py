"""Storage safety and compatibility tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note
from beernotes.controllers.settings_controller import SettingsController


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

    def test_legacy_note_gets_new_organization_defaults(self) -> None:
        note = Note(title="Legacy")
        data = note.to_dict()
        for key in ("tags", "attachments", "is_favorite", "is_archived", "is_trashed"):
            data.pop(key)
        (self.storage.notes_dir / f"{note.id}.json").write_text(
            json.dumps(data),
            encoding="utf-8",
        )

        loaded = self.storage.get_note(note.id)
        self.assertEqual(loaded.tags, [])
        self.assertFalse(loaded.is_favorite)
        self.assertFalse(loaded.is_archived)
        self.assertFalse(loaded.is_trashed)
        self.assertEqual(loaded.attachments, [])

    def test_attachment_is_copied_and_removed_with_note(self) -> None:
        note = Note(title="Attachment")
        self.storage.save_note(note)
        source = self.base_dir / "sample image.png"
        source.write_bytes(b"png-data")

        stored = self.storage.add_attachment(note.id, source)
        self.assertEqual(stored.read_bytes(), b"png-data")
        self.assertTrue(self.storage.delete_note(note.id))
        self.assertFalse(stored.exists())

    def test_existing_large_window_is_migrated_once_to_compact_size(self) -> None:
        settings = self.storage.load_settings()
        settings.window_width = 1600
        settings.window_height = 1000
        settings.compact_window_migrated = False
        self.storage.save_settings(settings)

        controller = SettingsController(self.storage)
        self.assertEqual(controller.settings.window_width, 1000)
        self.assertEqual(controller.settings.window_height, 680)
        self.assertTrue(controller.settings.compact_window_migrated)


if __name__ == "__main__":
    unittest.main()
