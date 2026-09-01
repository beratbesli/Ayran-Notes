"""Headless regression tests for the focused editor UI."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from ayrannotes.controllers.note_controller import NoteController
from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.localization.i18n import I18n
from ayrannotes.storage.database import StorageEngine
from ayrannotes.ui.main_window import MainWindow


class MainWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = StorageEngine(Path(self.temporary.name))
        self.notes = NoteController(self.storage)
        self.window = MainWindow(self.notes, SettingsController(self.storage), I18n("en"))

    def tearDown(self) -> None:
        self.window.close()
        self.temporary.cleanup()

    def test_startup_view_is_simple(self) -> None:
        self.assertIs(self.window._view_stack.currentWidget(), self.window._simple_view)
        self.assertTrue(self.window._nav_simple.isChecked())

    def test_simple_note_saves_and_survives_return_home(self) -> None:
        self.window._on_simple_new_note()
        self.window._simple_title.setText("Keep this note")
        self.window._simple_content.setPlainText("Markdown body")
        self.assertTrue(self.window._flush_simple_save())
        note_id = self.window._current_note.id

        self.window._show_simple_home()

        saved = self.storage.get_note(note_id)
        self.assertEqual(saved.title, "Keep this note")
        self.assertEqual(saved.content, "Markdown body")

    def test_blank_simple_draft_is_removed_when_returning_home(self) -> None:
        self.window._on_simple_new_note()
        note_id = self.window._current_note.id
        self.window._show_simple_home()
        self.assertIsNone(self.storage.get_note(note_id))

    def test_simple_search_filters_cards(self) -> None:
        first = self.notes.create_note("Work")
        first.content = "Release planning"
        self.notes.save_note(first)
        self.notes.create_note("Personal")
        self.window._refresh_simple_cards()
        self.window._simple_search.setText("release")
        self.assertEqual(self.window._simple_cards.count(), 1)
        self.assertEqual(
            self.window._simple_cards.item(0).data(0x0100),
            first.id,
        )

    def test_detailed_editor_flushes_pending_text(self) -> None:
        first = self.notes.create_note("First")
        second = self.notes.create_note("Second")
        self.window._change_view_mode("detailed")
        self.window._load_note(first.id)
        self.window._content_edit.setPlainText("must survive")
        self.window._load_note(second.id)
        self.assertEqual(self.storage.get_note(first.id).content, "must survive")

    def test_markdown_tools_support_undo(self) -> None:
        note = self.notes.create_note("Formatting")
        self.window._change_view_mode("detailed")
        self.window._load_note(note.id)
        self.window._content_edit.setPlainText("hello")
        self.window._content_edit.selectAll()
        self.window._wrap_selection("**", "**", "bold")
        self.assertEqual(self.window._content_edit.toPlainText(), "**hello**")
        self.window._content_edit.undo()
        self.assertEqual(self.window._content_edit.toPlainText(), "hello")

    def test_delete_requires_confirmation_and_removes_note(self) -> None:
        note = self.notes.create_note("Temporary")
        self.window._load_simple_note(note.id)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window._on_simple_delete()
        self.assertIsNone(self.storage.get_note(note.id))

    def test_import_accepts_markdown_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "imported.md"
            path.write_text("# Imported\n\nBody", encoding="utf-8")
            with patch(
                "ayrannotes.ui.main_window.QFileDialog.getOpenFileNames",
                return_value=([str(path)], ""),
            ):
                self.window._import_notes()
        imported = self.notes.list_notes()[0]
        self.assertEqual(imported.title, "Imported")
        self.assertEqual(imported.content, "Body")

    def test_export_always_writes_markdown(self) -> None:
        note = self.notes.create_note("Export")
        self.window._load_simple_note(note.id)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "exported"
            with patch(
                "ayrannotes.ui.main_window.QFileDialog.getSaveFileName",
                return_value=(str(target), ""),
            ):
                self.window._export_current_note()
            self.assertTrue((Path(tmp) / "exported.md").is_file())


if __name__ == "__main__":
    unittest.main()
