"""Headless regression tests for the focused editor UI."""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import PropertyMock, patch

from PyQt6.QtWidgets import QApplication, QMessageBox

from ayrannotes.controllers.note_controller import NoteController
from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.localization.i18n import I18n
from ayrannotes.storage.database import StorageEngine
from ayrannotes.ui.main_window import MainWindow
from ayrannotes.ui.history_dialog import DeletedNotesDialog, HistoryDialog
import ayrannotes.storage.git_versioning as gv


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

    def _wait_for_thread(self, thread, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while thread.isRunning() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.app.processEvents()
        self.assertFalse(thread.isRunning())

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

    def test_preview_uses_resolved_system_theme(self) -> None:
        note = self.notes.create_note("Preview")
        self.window._change_view_mode("detailed")
        self.window._load_note(note.id)
        self.window._preview.show()
        with patch.object(
            type(self.window._settings_ctrl),
            "resolved_theme",
            new_callable=PropertyMock,
            return_value="light",
        ), patch(
            "ayrannotes.ui.main_window.render_markdown_html",
            return_value="<p>preview</p>",
        ) as render, patch.object(
            self.window._preview,
            "isVisible",
            return_value=True,
        ):
            self.window._update_preview(reset_scroll=True)
        self.assertEqual(render.call_args.kwargs["theme"], "light")

    def test_history_dialog_previews_diff_and_restores_selected_version(self) -> None:
        def immediate_commit(notes_dir, message, delay=5.0):
            return gv.git_manager.commit_change(notes_dir, message)

        with patch.object(gv.git_manager, "schedule_commit", side_effect=immediate_commit):
            note = self.notes.create_note("History")
            note.content = "old body"
            self.notes.save_note(note)
            note.content = "current body"
            self.notes.save_note(note)
            dialog = HistoryDialog(
                self.notes,
                self.storage.get_note(note.id),
                self.window._i18n,
                self.window._settings_ctrl,
                self.window,
            )
            self._wait_for_thread(dialog._history_worker)
            self.assertEqual(dialog._history_list.count(), 3)
            dialog._history_list.setCurrentRow(2)
            self._wait_for_thread(dialog._version_worker)
            self.assertEqual(dialog._selected_version.content, "")
            self.assertTrue(dialog._restore_button.isEnabled())
            self.assertIn("current body", dialog._diff.toHtml())
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                dialog._restore_selected()
            self.assertEqual(dialog.restored_note.content, "")
            self.assertEqual(self.storage.get_note(note.id).content, "")
            dialog.close()

    def test_deleted_notes_dialog_recovers_note_from_local_history(self) -> None:
        def immediate_commit(notes_dir, message, delay=5.0):
            return gv.git_manager.commit_change(notes_dir, message)

        with patch.object(gv.git_manager, "schedule_commit", side_effect=immediate_commit):
            note = self.notes.create_note("Deleted")
            note.content = "recoverable"
            self.notes.save_note(note)
            self.notes.delete_note(note.id)
            dialog = DeletedNotesDialog(self.notes, self.window._i18n, self.window)
            self._wait_for_thread(dialog._worker)
            self.assertEqual(dialog._list.count(), 1)
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                dialog._restore_selected()
            self.assertEqual(dialog.restored_note.id, note.id)
            self.assertEqual(self.storage.get_note(note.id).content, "recoverable")
            dialog.close()

    def test_history_menu_is_available_without_adding_simple_controls(self) -> None:
        note = self.notes.create_note("History menu")
        self.window._load_simple_note(note.id)
        self.assertTrue(self.window._act_history.isEnabled())
        self.assertIn("History", self.window._act_history.text())
        self.window._i18n.set_language("tr")
        self.assertIn("Geçmiş", self.window._act_history.text())

    def test_history_diff_colors_follow_light_and_dark_themes(self) -> None:
        note = self.notes.create_note("Theme history")
        for theme, expected_color in (("light", "#273142"), ("dark", "#d8dee9")):
            self.window._settings_ctrl.settings.theme = theme
            dialog = HistoryDialog(
                self.notes,
                note,
                self.window._i18n,
                self.window._settings_ctrl,
                self.window,
            )
            self.assertIn(expected_color, dialog._build_diff("old", "new"))
            dialog.close()

    def test_history_items_show_date_and_time(self) -> None:
        note = self.notes.create_note("Timestamp history")
        dialog = HistoryDialog(
            self.notes,
            note,
            self.window._i18n,
            self.window._settings_ctrl,
            self.window,
        )
        text = dialog._history_item_text(
            {"date": "2024-01-02 13:45:00 +0000", "message": "Update: note"}
        )
        self.assertRegex(text, r"02\.01\.2024 \d{2}:45")
        self.assertIn("Update: note", text)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
