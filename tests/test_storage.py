"""Storage safety and Markdown portability tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.storage.database import StorageConflictError, StorageEngine
from ayrannotes.storage.markdown_notes import serialize_note
from ayrannotes.storage.models import AppSettings, Note
import ayrannotes.storage.git_versioning as gv


class StorageEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary.name)
        self.storage = StorageEngine(self.base_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _immediate_commit(self, notes_dir, message, delay=5.0):
        gv.git_manager.cancel_scheduled_commit()
        return gv.git_manager.commit_change(notes_dir, message)

    def test_note_round_trips_as_clean_markdown(self) -> None:
        note = Note(title="Release: Türkiye", content="Body\n\n---\n\n`code`")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        raw = path.read_text(encoding="utf-8")

        self.assertTrue(raw.startswith("---\n"))
        self.assertIn("title: 'Release: Türkiye'", raw)
        self.assertIn("created:", raw)
        self.assertIn("updated:", raw)
        self.assertNotIn("tags:", raw)
        self.assertTrue(raw.endswith(note.content))
        self.assertEqual(self.storage.get_note(note.id).to_dict(), note.to_dict())

    def test_external_front_matter_and_body_are_source_of_truth(self) -> None:
        note = Note(title="Before")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(
            "---\ntitle: Outside edit\ncreated: 2024-01-02\nupdated: 2024-02-03\n---\nEdited outside.\n",
            encoding="utf-8",
        )

        loaded = self.storage.get_note(note.id)
        self.assertEqual(loaded.title, "Outside edit")
        self.assertEqual(loaded.updated_at, "2024-02-03")
        self.assertEqual(loaded.content, "Edited outside.\n")

    def test_front_matter_allows_indented_delimiter_text(self) -> None:
        note = Note(title="Before")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(
            "---\ntitle: |-\n  line one\n  ---\n  line two\ncreated: 2024-01-01\nupdated: 2024-01-01\n---\nBody\n",
            encoding="utf-8",
        )
        loaded = self.storage.get_note(note.id)
        self.assertEqual(loaded.title, "line one\n---\nline two")
        self.assertEqual(loaded.content, "Body\n")

    def test_external_change_is_not_overwritten_by_stale_note(self) -> None:
        note = Note(title="Original", content="App version")
        self.storage.save_note(note)
        loaded = self.storage.get_note(note.id)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(serialize_note(Note(id=note.id, title="External", content="External version")), encoding="utf-8")
        loaded.content = "Stale app overwrite"

        with self.assertRaises(StorageConflictError):
            self.storage.save_note(loaded)
        self.assertIn("External version", path.read_text(encoding="utf-8"))

    def test_rejects_note_id_path_traversal(self) -> None:
        self.assertIsNone(self.storage.get_note("../../outside"))
        self.assertFalse(self.storage.delete_note("../../outside"))
        with self.assertRaises(ValueError):
            self.storage.save_note(Note(id="../../outside"))

    def test_filename_is_authoritative_for_note_id(self) -> None:
        note = Note(title="Safe")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("---\n", "---\nid: ../../outside\n", 1),
            encoding="utf-8",
        )
        self.assertEqual(self.storage.list_notes()[0].id, note.id)

    def test_failed_atomic_replace_preserves_note_and_timestamp(self) -> None:
        note = Note(title="Original")
        self.storage.save_note(note)
        timestamp = note.updated_at
        note.title = "Changed"
        with patch("ayrannotes.storage.database.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.storage.save_note(note)
        persisted = self.storage.get_note(note.id)
        self.assertEqual(persisted.title, "Original")
        self.assertEqual(note.updated_at, timestamp)
        self.assertEqual(list(self.storage.notes_dir.glob("*.tmp")), [])

    def test_custom_notes_directory_is_shared_through_settings(self) -> None:
        shared = self.base_dir / "Shared Notes"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)
        reopened = StorageEngine(self.base_dir)
        note = Note(title="Shared")
        reopened.save_note(note)
        self.assertEqual(reopened.notes_dir, shared.resolve())
        self.assertTrue((shared / f"{note.id}.md").is_file())

    def test_missing_custom_directory_is_not_created(self) -> None:
        missing = self.base_dir / "missing-drive" / "Notes"
        settings = self.storage.load_settings()
        settings.notes_directory = str(missing)
        self.storage.save_settings(settings)
        with self.assertRaises(FileNotFoundError):
            StorageEngine(self.base_dir)
        self.assertFalse(missing.exists())

    def test_settings_directory_marker_detects_wrong_mount(self) -> None:
        shared = self.base_dir / "mounted-notes"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)
        (shared / ".ayrannotes-directory").write_text("different-volume\n", encoding="utf-8")
        with self.assertRaises(OSError):
            StorageEngine(self.base_dir)

    def test_corrupt_settings_are_not_silently_ignored(self) -> None:
        self.storage.settings_file.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            StorageEngine(self.base_dir)

    def test_non_object_settings_are_rejected(self) -> None:
        self.storage.settings_file.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "root must be an object"):
            StorageEngine(self.base_dir)

    def test_malformed_note_fields_fall_back_to_safe_values(self) -> None:
        loaded = Note.from_dict(
            {
                "id": "../../outside",
                "title": 42,
                "content": None,
                "created_at": 12,
                "updated_at": "",
            }
        )
        self.assertRegex(loaded.id, r"^[0-9a-f]{12}$")
        self.assertEqual(loaded.title, "Untitled")
        self.assertEqual(loaded.content, "")
        self.assertTrue(loaded.created_at)
        self.assertTrue(loaded.updated_at)

    def test_malformed_preferences_use_safe_defaults(self) -> None:
        settings = AppSettings.from_dict(
            {
                "theme": "neon",
                "accent_color": "not-a-color",
                "font_size": "huge",
                "language": "xx",
                "window_width": -1,
                "main_splitter_sizes": [100, "bad"],
            }
        )
        self.assertEqual(settings.theme, "system")
        self.assertEqual(settings.accent_color, "")
        self.assertEqual(settings.font_size, 14)
        self.assertEqual(settings.language, "en")
        self.assertEqual(settings.window_width, 1000)
        self.assertEqual(settings.main_splitter_sizes, [])


    def test_restore_existing_version_creates_new_commit_and_keeps_old_history(self) -> None:
        with patch.object(gv.git_manager, "schedule_commit", side_effect=self._immediate_commit):
            note = Note(title="History", content="first")
            self.storage.save_note(note)
            note.content = "second"
            self.storage.save_note(note)

            history_before = self.storage.get_note_history(note.id)
            restored = self.storage.restore_note_version(
                note.id,
                history_before[-1]["hash"],
                expected_revision=note._storage_revision,
            )

        self.assertEqual(restored.content, "first")
        self.assertEqual(self.storage.get_note(note.id).content, "first")
        history_after = self.storage.get_note_history(note.id)
        self.assertEqual(len(history_after), 3)
        self.assertEqual(history_after[0]["message"], "Restore: History")
        self.assertIn(history_before[-1]["hash"], [entry["hash"] for entry in history_after])

    def test_restore_rejects_external_change_and_invalid_version(self) -> None:
        with patch.object(gv.git_manager, "schedule_commit", side_effect=self._immediate_commit):
            note = Note(title="Safe", content="original")
            self.storage.save_note(note)
            history = self.storage.get_note_history(note.id)
            path = self.storage.notes_dir / f"{note.id}.md"
            path.write_text("external", encoding="utf-8")
            with self.assertRaises(StorageConflictError):
                self.storage.restore_note_version(
                    note.id,
                    history[0]["hash"],
                    expected_revision=note._storage_revision,
                )
            with self.assertRaises(ValueError):
                self.storage.restore_note_version(note.id, "invalid-hash")

    def test_deleted_note_can_be_found_and_restored_without_overwriting_id(self) -> None:
        with patch.object(gv.git_manager, "schedule_commit", side_effect=self._immediate_commit):
            note = Note(title="Deleted note", content="recover me")
            self.storage.save_note(note)
            self.storage.delete_note(note.id)
            deleted = self.storage.list_deleted_notes()
            restored = self.storage.restore_deleted_note(note.id, deleted[0]["hash"])

        self.assertEqual(restored.id, note.id)
        self.assertEqual(restored.title, "Deleted note")
        self.assertEqual(self.storage.get_note(note.id).content, "recover me")
        self.assertEqual(self.storage.get_note_history(note.id)[0]["message"], "Restore deleted note: Deleted note")

    def test_deleted_note_id_collision_requires_new_id_and_can_restore_with_one(self) -> None:
        with patch.object(gv.git_manager, "schedule_commit", side_effect=self._immediate_commit):
            note = Note(title="Deleted", content="old")
            self.storage.save_note(note)
            self.storage.delete_note(note.id)
            deleted = self.storage.list_deleted_notes()
            replacement = Note(id=note.id, title="Replacement", content="new")
            self.storage.save_note(replacement)
            with self.assertRaises(FileExistsError):
                self.storage.restore_deleted_note(note.id, deleted[0]["hash"])
            restored = self.storage.restore_deleted_note(
                note.id,
                deleted[0]["hash"],
                new_note_id="ffffffffffff",
            )

        self.assertEqual(restored.id, "ffffffffffff")
        self.assertEqual(self.storage.get_note(note.id).title, "Replacement")
        self.assertEqual(self.storage.get_note(restored.id).content, "old")


if __name__ == "__main__":
    unittest.main()
