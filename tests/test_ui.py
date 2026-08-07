"""Headless regression tests for critical editor behavior."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

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
        self.assertEqual(
            self.window._simple_cards.item(0).data(
                Qt.ItemDataRole.AccessibleTextRole
            ),
            "Work plan",
        )

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

    def test_simple_home_has_empty_state_and_semantic_cards(self) -> None:
        self.window._refresh_simple_cards()

        self.assertTrue(self.window._simple_cards.isHidden())
        self.assertFalse(self.window._simple_empty.isHidden())
        self.assertEqual(
            self.window._simple_empty_title.text(),
            "Your notes will appear here",
        )

        note = self.notes.create_note("Readable card", "Ideas")
        note.content = "A clean summary that is easier to scan."
        self.notes.save_note(note)
        self.window._refresh_simple_cards()

        self.assertFalse(self.window._simple_cards.isHidden())
        self.assertTrue(self.window._simple_empty.isHidden())
        item = self.window._simple_cards.item(0)
        card = self.window._simple_cards.itemWidget(item)
        self.assertEqual(
            item.data(Qt.ItemDataRole.AccessibleTextRole),
            "Readable card",
        )
        self.assertEqual(
            card.findChild(QLabel, "noteCardTitle").text(),
            "Readable card",
        )
        self.assertIn(
            "clean summary",
            card.findChild(QLabel, "noteCardSnippet").text(),
        )

    def test_simple_editor_receives_edit_commands(self) -> None:
        note = self.notes.create_note("Command routing")
        self.window._load_simple_note(note.id)
        self.window._simple_content.insertPlainText("draft")

        self.window._act_undo.trigger()
        self.assertEqual(self.window._simple_content.toPlainText(), "")
        self.window._act_redo.trigger()
        self.assertEqual(self.window._simple_content.toPlainText(), "draft")

        self.window._simple_content.setPlainText("old old")
        with patch(
            "beernotes.ui.main_window.QInputDialog.getText",
            side_effect=[("old", True), ("new", True)],
        ):
            self.window._replace_text()
        self.assertEqual(self.window._simple_content.toPlainText(), "new new")
        self.assertEqual(self.window._content_edit.toPlainText(), "")

        self.window._show_simple_home()
        self.window._simple_search.setText("new")
        with patch(
            "beernotes.ui.main_window.QInputDialog.getText"
        ) as text_prompt:
            self.window._find_text()
        text_prompt.assert_not_called()
        self.assertEqual(self.window._simple_search.selectedText(), "new")

    def test_save_failure_blocks_mode_change_and_window_close(self) -> None:
        note = self.notes.create_note("Do not lose")
        self.window._load_simple_note(note.id)
        self.window._simple_content.setPlainText("unsaved text")
        close_event = QCloseEvent()

        with (
            patch.object(self.notes, "save_note", side_effect=OSError("disk full")),
            patch("beernotes.ui.main_window.QMessageBox.critical") as critical,
        ):
            self.window._change_view_mode("detailed")
            self.assertIs(
                self.window._view_stack.currentWidget(),
                self.window._simple_view,
            )
            self.assertTrue(self.window._nav_simple.isChecked())
            self.assertTrue(self.window._simple_dirty)
            self.assertEqual(self.window._save_state_key, "save_failed")

            self.window.closeEvent(close_event)

        self.assertFalse(close_event.isAccepted())
        critical.assert_called_once()
        self.assertEqual(
            self.window._simple_content.toPlainText(),
            "unsaved text",
        )
        self.assertTrue(self.window._flush_simple_save())
        self.assertEqual(self.window._save_state_key, "saved")

    def test_metadata_actions_preserve_pending_editor_text(self) -> None:
        note = self.notes.create_note("Metadata")
        self.window._change_view_mode("detailed")
        self.window._load_note(note.id)
        self.window._content_edit.setPlainText("latest text")

        self.window._toggle_favorite(note.id)
        saved = self.storage.get_note(note.id)
        self.assertEqual(saved.content, "latest text")
        self.assertTrue(saved.is_favorite)
        self.assertTrue(self.window._current_note.is_favorite)

        self.window._content_edit.setPlainText("latest folder text")
        self.window._move_note(note.id, "Work")
        saved = self.storage.get_note(note.id)
        self.assertEqual(saved.content, "latest folder text")
        self.assertEqual(saved.folder, "Work")
        self.assertTrue(saved.is_favorite)

    def test_trashing_inactive_card_refreshes_simple_home(self) -> None:
        first = self.notes.create_note("First")
        self.notes.create_note("Second")
        self.window._refresh_simple_cards()
        self.assertEqual(self.window._simple_cards.count(), 2)

        self.window._trash_note(first.id)

        self.assertTrue(self.storage.get_note(first.id).is_trashed)
        self.assertEqual(self.window._simple_cards.count(), 1)
        self.assertEqual(
            self.window._simple_cards.item(0).data(
                Qt.ItemDataRole.AccessibleTextRole
            ),
            "Second",
        )

    def test_detailed_to_simple_transition_never_deletes_note(self) -> None:
        note = self.notes.create_note("Important")
        self.window._change_view_mode("detailed")
        self.window._load_note(note.id)
        self.window._content_edit.setPlainText("must survive")
        self.assertTrue(self.window._flush_pending_save())

        self.window._change_view_mode("simple")

        saved = self.storage.get_note(note.id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.title, "Important")
        self.assertEqual(saved.content, "must survive")
        self.assertIsNone(self.window._current_note)
        self.assertEqual(self.window._title_edit.text(), "")
        self.assertEqual(self.window._content_edit.toPlainText(), "")

        self.window._change_view_mode("detailed")
        self.assertEqual(self.window._current_note.id, note.id)
        self.assertEqual(
            self.window._content_edit.toPlainText(),
            "must survive",
        )
        self.assertTrue(self.window._content_edit.isEnabled())

    def test_abandoned_blank_draft_is_cleaned_during_refresh(self) -> None:
        abandoned = self.notes.create_note("", simple_draft=True)

        self.window._refresh_simple_cards()

        self.assertIsNone(self.storage.get_note(abandoned.id))
        self.assertEqual(self.window._simple_cards.count(), 0)
        self.assertFalse(self.window._simple_empty.isHidden())

    def test_blank_detailed_and_organized_notes_are_never_auto_deleted(
        self,
    ) -> None:
        detailed = self.notes.create_note("Untitled")
        self.notes.toggle_pin(detailed.id)
        organized_draft = self.notes.create_note(
            "",
            "Ideas",
            simple_draft=True,
        )
        favorite_draft = self.notes.create_note("", simple_draft=True)
        self.notes.toggle_favorite(favorite_draft.id)

        self.window._refresh_simple_cards()

        self.assertIsNotNone(self.storage.get_note(detailed.id))
        self.assertIsNotNone(self.storage.get_note(organized_draft.id))
        self.assertIsNotNone(self.storage.get_note(favorite_draft.id))

    def test_detailed_editor_is_disabled_without_any_note(self) -> None:
        self.window._change_view_mode("detailed")

        self.assertIsNone(self.window._current_note)
        self.assertFalse(self.window._title_edit.isEnabled())
        self.assertFalse(self.window._content_edit.isEnabled())

    def test_mode_round_trip_restores_the_same_detailed_note(self) -> None:
        pinned = self.notes.create_note("Pinned")
        self.notes.toggle_pin(pinned.id)
        active = self.notes.create_note("Active")
        self.window._change_view_mode("detailed")
        self.window._load_note(active.id)
        self.window._content_edit.setPlainText("keep this context")
        self.assertTrue(self.window._flush_pending_save())

        self.window._change_view_mode("simple")
        self.window._change_view_mode("detailed")

        self.assertEqual(self.window._current_note.id, active.id)
        self.assertEqual(
            self.window._content_edit.toPlainText(),
            "keep this context",
        )

    def test_language_change_refreshes_cards_and_empty_state(self) -> None:
        note = self.notes.create_note("Localized", "General")
        self.notes.toggle_favorite(note.id)
        self.window._refresh_simple_cards()
        card = self.window._simple_cards.itemWidget(
            self.window._simple_cards.item(0)
        )
        self.assertIn(
            "Favorite",
            card.findChild(QLabel, "noteCardMetadata").text(),
        )

        self.window._i18n.set_language("tr")

        card = self.window._simple_cards.itemWidget(
            self.window._simple_cards.item(0)
        )
        metadata = card.findChild(QLabel, "noteCardMetadata").text()
        self.assertIn("Favori", metadata)
        self.assertIn("Bugün", metadata)

        self.notes.delete_note(note.id)
        self.window._refresh_simple_cards()
        self.assertEqual(
            self.window._simple_empty_title.text(),
            "Notların burada görünecek",
        )

    def test_failed_note_switch_restores_visible_selection(self) -> None:
        first = self.notes.create_note("First")
        second = self.notes.create_note("Second")
        self.window._change_view_mode("detailed")
        self.window._load_note(first.id)
        self.window._content_edit.setPlainText("pending")
        self.window._refresh_note_list()
        second_item = next(
            self.window._note_list.item(row)
            for row in range(self.window._note_list.count())
            if self.window._note_list.item(row).data(
                Qt.ItemDataRole.UserRole
            ) == second.id
        )

        with patch.object(
            self.notes,
            "save_note",
            side_effect=OSError("disk full"),
        ):
            self.window._note_list.setCurrentItem(second_item)

        self.assertEqual(self.window._current_note.id, first.id)
        self.assertEqual(
            self.window._note_list.currentItem().data(
                Qt.ItemDataRole.UserRole
            ),
            first.id,
        )
        self.assertEqual(self.window._content_edit.toPlainText(), "pending")
        self.assertTrue(self.window._dirty)
        self.assertTrue(self.window._flush_pending_save())


if __name__ == "__main__":
    unittest.main()
