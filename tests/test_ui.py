"""Headless regression tests for critical editor behavior."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from beernotes.controllers.note_controller import NoteController
from beernotes.controllers.settings_controller import SettingsController
from beernotes.localization.i18n import I18n
from beernotes.storage.database import StorageEngine
from beernotes.ui.main_window import MainWindow


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = StorageEngine(Path(self.temporary.name))
        self.notes = NoteController(self.storage)
        self.window = MainWindow(
            self.notes,
            SettingsController(self.storage),
            I18n("en"),
        )

    def tearDown(self) -> None:
        self.window.close()
        self.temporary.cleanup()

    def test_switching_notes_flushes_pending_edit(self) -> None:
        first = self.notes.create_note("First")
        second = self.notes.create_note("Second")
        self.window._load_note(first.id)
        self.window._content_edit.setPlainText("must survive")

        self.window._load_note(second.id)

        self.assertEqual(self.storage.get_note(first.id).content, "must survive")
        self.assertEqual(self.storage.get_note(second.id).content, "")


if __name__ == "__main__":
    unittest.main()
