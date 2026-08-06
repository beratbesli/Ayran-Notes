"""Headless regression tests for critical editor behavior."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_tags_and_trash_are_persisted(self) -> None:
        note = self.notes.create_note("Tagged")
        self.window._load_note(note.id)
        self.window._tag_edit.setText("work, urgent, work")
        self.window._flush_pending_save()

        self.assertEqual(self.storage.get_note(note.id).tags, ["work", "urgent"])
        self.window._trash_note(note.id)
        self.assertTrue(self.storage.get_note(note.id).is_trashed)
        self.assertIsNone(self.window._current_note)

    def test_markdown_tools_support_undo(self) -> None:
        note = self.notes.create_note("Formatting")
        self.window._load_note(note.id)
        self.window._content_edit.setPlainText("hello")
        self.window._content_edit.selectAll()

        self.window._wrap_selection("**", "**", "bold")
        self.assertEqual(self.window._content_edit.toPlainText(), "**hello**")
        self.window._content_edit.undo()
        self.assertEqual(self.window._content_edit.toPlainText(), "hello")

        self.window._prefix_line("- [ ] ")
        self.assertEqual(self.window._content_edit.toPlainText(), "- [ ] hello")

    def test_toolbar_can_be_customized_and_persisted(self) -> None:
        self.assertTrue(self.window._format_actions["bold"].isVisible())
        self.assertFalse(self.window._format_actions["heading"].isVisible())

        self.window._toolbar_toggle_actions["heading"].setChecked(True)
        self.window._toolbar_toggle_actions["bold"].setChecked(False)

        saved = self.storage.load_settings().toolbar_actions
        self.assertIn("heading", saved)
        self.assertNotIn("bold", saved)
        self.assertTrue(self.window._format_actions["heading"].isVisible())
        self.assertFalse(self.window._format_actions["bold"].isVisible())

    def test_export_flushes_pending_edits_and_adds_selected_suffix(self) -> None:
        note = self.notes.create_note("Export me")
        self.window._load_note(note.id)
        self.window._content_edit.setPlainText("latest content")
        destination = Path(self.temporary.name) / "exported-note"

        with patch(
            "beernotes.ui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(destination), "Markdown (*.md)"),
        ):
            self.window._export_current_note()

        exported = destination.with_name(destination.name + ".md")
        self.assertTrue(exported.is_file())
        self.assertIn("latest content", exported.read_text(encoding="utf-8"))
        self.assertEqual(self.storage.get_note(note.id).content, "latest content")


if __name__ == "__main__":
    unittest.main()
