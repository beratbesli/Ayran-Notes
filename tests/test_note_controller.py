"""Tests for the focused note controller."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ayrannotes.controllers.note_controller import NoteController
from ayrannotes.storage.database import StorageEngine


class NoteControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.controller = NoteController(StorageEngine(Path(self.temporary.name)))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_lists_all_notes_and_searches_title_and_content(self) -> None:
        first = self.controller.create_note("Roadmap")
        first.content = "Release planning"
        self.controller.save_note(first)
        second = self.controller.create_note("Personal")
        second.content = "Weekend ideas"
        self.controller.save_note(second)

        self.assertEqual(
            {note.id for note in self.controller.list_notes()},
            {first.id, second.id},
        )
        self.assertEqual([note.id for note in self.controller.search("release")], [first.id])
        self.assertEqual([note.id for note in self.controller.search("personal")], [second.id])

    def test_delete_removes_only_the_selected_markdown_note(self) -> None:
        note = self.controller.create_note("Temporary")
        other = self.controller.create_note("Keep")

        self.assertTrue(self.controller.delete_note(note.id))
        self.assertIsNone(self.controller.get_note(note.id))
        self.assertIsNotNone(self.controller.get_note(other.id))
        self.assertFalse(self.controller.delete_note(note.id))


if __name__ == "__main__":
    unittest.main()
