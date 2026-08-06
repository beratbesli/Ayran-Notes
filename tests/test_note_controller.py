"""Tests for note organization and filtering."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from beernotes.controllers.note_controller import NoteController
from beernotes.storage.database import StorageEngine


class NoteControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.controller = NoteController(StorageEngine(Path(self.temporary.name)))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_favorites_archive_trash_and_restore_filters(self) -> None:
        note = self.controller.create_note("Roadmap", "Work")
        note.tags = ["planning", "release"]
        self.controller.save_note(note)

        self.controller.toggle_favorite(note.id)
        self.assertEqual([item.id for item in self.controller.list_notes("__favorites__")], [note.id])
        self.assertEqual([item.id for item in self.controller.search("release")], [note.id])

        self.controller.set_archived(note.id)
        self.assertEqual(self.controller.list_notes("__all__"), [])
        self.assertEqual([item.id for item in self.controller.list_notes("__archive__")], [note.id])

        self.controller.move_to_trash(note.id)
        self.assertEqual(self.controller.list_notes("__archive__"), [])
        self.assertEqual([item.id for item in self.controller.list_notes("__trash__")], [note.id])

        self.controller.restore_note(note.id)
        self.assertEqual([item.id for item in self.controller.list_notes("__archive__")], [note.id])

    def test_attachment_is_tracked_on_note(self) -> None:
        note = self.controller.create_note("Files")
        source = Path(self.temporary.name) / "report.txt"
        source.write_text("content", encoding="utf-8")

        destination = self.controller.add_attachment(note.id, source)

        self.assertTrue(destination.is_file())
        loaded = self.controller.get_note(note.id)
        self.assertEqual(len(loaded.attachments), 1)
        self.assertTrue(loaded.attachments[0].endswith("/report.txt"))


if __name__ == "__main__":
    unittest.main()
