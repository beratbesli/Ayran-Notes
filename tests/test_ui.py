"""Headless regression tests for critical editor behavior."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox

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

    def test_imports_multiple_files_and_opens_the_last_note(self) -> None:
        markdown_path = Path(self.temporary.name) / "first.md"
        markdown_path.write_text("# First\n\n**Tags:** work\n\nMarkdown body")
        text_path = Path(self.temporary.name) / "second.txt"
        text_path.write_text("Second\n\nPlain body")

        with patch(
            "beernotes.ui.main_window.QFileDialog.getOpenFileNames",
            return_value=([str(markdown_path), str(text_path)], ""),
        ):
            self.window._import_notes()

        imported = {note.title: note for note in self.notes.list_notes("__all__")}
        self.assertEqual(set(imported), {"First", "Second"})
        self.assertEqual(imported["First"].tags, ["work"])
        self.assertFalse(imported["Second"].is_markdown)
        self.assertEqual(self.window._current_note.title, "Second")

    def test_simple_mode_cards_search_and_safe_mode_switch(self) -> None:
        first = self.notes.create_note("Shopping", "General")
        second = self.notes.create_note("Work plan", "Work")
        self.window._refresh_simple_cards()

        self.assertIs(self.window._view_stack.currentWidget(), self.window._simple_view)
        self.assertEqual(self.window._simple_cards.count(), 2)
        self.window._simple_search.setText("work")
        self.assertEqual(self.window._simple_cards.count(), 1)
        self.assertIn("Work plan", self.window._simple_cards.item(0).text())

        self.window._load_simple_note(second.id)
        self.window._simple_content.setPlainText("edited in simple mode")
        self.window._change_view_mode("detailed")

        self.assertEqual(self.storage.get_note(second.id).content, "edited in simple mode")
        self.assertEqual(self.window._content_edit.toPlainText(), "edited in simple mode")
        self.assertIs(self.window._view_stack.currentWidget(), self.window._detailed_view)
        self.assertEqual(self.storage.load_settings().view_mode, "detailed")

    def test_simple_plus_creates_and_opens_a_note(self) -> None:
        self.window._on_simple_new_note()
        self.assertIsNotNone(self.window._current_note)
        self.assertIs(
            self.window._simple_stack.currentWidget(),
            self.window._simple_editor,
        )
        self.assertEqual(len(self.notes.list_notes("__all__")), 1)

    def test_blank_simple_note_is_deleted_when_returning_home(self) -> None:
        self.window._on_simple_new_note()
        note_id = self.window._current_note.id

        self.window._show_simple_home()

        self.assertIsNone(self.storage.get_note(note_id))
        self.assertIsNone(self.window._current_note)
        self.assertEqual(self.window._simple_cards.count(), 0)

    def test_written_simple_note_is_retained_when_returning_home(self) -> None:
        self.window._on_simple_new_note()
        note_id = self.window._current_note.id
        self.window._simple_content.setPlainText("Keep this note")

        self.window._show_simple_home()

        saved = self.storage.get_note(note_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.content, "Keep this note")

    def test_simple_manual_delete_moves_note_to_trash(self) -> None:
        note = self.notes.create_note("Temporary")
        self.window._load_simple_note(note.id)

        with patch(
            "beernotes.ui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window._on_simple_delete()

        self.assertTrue(self.storage.get_note(note.id).is_trashed)
        self.assertIsNone(self.window._current_note)


if __name__ == "__main__":
    unittest.main()
