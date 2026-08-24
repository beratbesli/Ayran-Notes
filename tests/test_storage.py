"""Storage safety, Markdown portability, and migration tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.storage.database import StorageConflictError, StorageEngine
from ayrannotes.storage.markdown_notes import serialize_note
from ayrannotes.storage.models import Note


class StorageEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temporary.name)
        self.storage = StorageEngine(self.base_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_note_round_trips_as_readable_markdown(self) -> None:
        note = Note(
            title="Release: Türkiye",
            content="Body\n\n---\n\n" + chr(96) + "code" + chr(96),
            folder="Work",
            is_pinned=True,
            is_favorite=True,
            is_archived=True,
            is_trashed=True,
            is_simple_draft=True,
            tags=["planning", "v1"],
            attachments=["attachments/id/report.pdf"],
        )

        self.storage.save_note(note)

        path = self.storage.notes_dir / f"{note.id}.md"
        raw = path.read_text(encoding="utf-8")
        self.assertTrue(raw.startswith("---\n"))
        self.assertIn("title: 'Release: Türkiye'", raw)
        self.assertIn("tags:", raw)
        self.assertIn("created:", raw)
        self.assertIn("updated:", raw)
        self.assertIn("pinned: true", raw)
        self.assertIn("folder: Work", raw)
        self.assertTrue(raw.endswith(note.content))
        self.assertEqual(list(self.storage.notes_dir.glob("*.json")), [])

        loaded = self.storage.get_note(note.id)
        self.assertEqual(loaded.to_dict(), note.to_dict())

    def test_external_front_matter_and_body_edits_are_source_of_truth(self) -> None:
        note = Note(title="Before")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(
            """---
title: Outside edit
tags: [shared, external]
created: 2024-01-02T03:04:05+00:00
updated: 2024-02-03
pinned: true
folder: Shared
---
Edited outside Ayran Notes.
""",
            encoding="utf-8",
        )

        loaded = self.storage.get_note(note.id)

        self.assertEqual(loaded.title, "Outside edit")
        self.assertEqual(loaded.tags, ["shared", "external"])
        self.assertEqual(loaded.folder, "Shared")
        self.assertTrue(loaded.is_pinned)
        self.assertEqual(loaded.updated_at, "2024-02-03")
        self.assertEqual(loaded.content, "Edited outside Ayran Notes.\n")

    def test_front_matter_allows_indented_yaml_delimiter_text(self) -> None:
        note = Note(title="Before")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        path.write_text(
            """---
title: |-
  line one
  ---
  line two
tags: []
created: 2024-01-01
updated: 2024-01-01
pinned: false
folder: General
---
Body
""",
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
        path.write_text(
            serialize_note(
                Note(
                    id=note.id,
                    title="External",
                    content="External version",
                )
            ),
            encoding="utf-8",
        )
        loaded.content = "Stale app overwrite"

        with self.assertRaises(StorageConflictError):
            self.storage.save_note(loaded)

        self.assertIn(
            "External version",
            path.read_text(encoding="utf-8"),
        )

    def test_rejects_note_id_path_traversal(self) -> None:
        self.assertIsNone(self.storage.get_note("../../outside"))
        self.assertFalse(self.storage.delete_note("../../outside"))
        with self.assertRaises(ValueError):
            self.storage.save_note(Note(id="../../outside"))

    def test_filename_is_authoritative_for_loaded_note_id(self) -> None:
        note = Note(title="Safe")
        self.storage.save_note(note)
        path = self.storage.notes_dir / f"{note.id}.md"
        raw = path.read_text(encoding="utf-8")
        path.write_text(
            raw.replace("---\n", "---\nid: ../../outside\n", 1),
            encoding="utf-8",
        )

        loaded = self.storage.list_notes()
        self.assertEqual(loaded[0].id, note.id)

    def test_failed_atomic_replace_preserves_note_and_timestamp(self) -> None:
        note = Note(title="Original")
        self.storage.save_note(note)
        persisted_timestamp = note.updated_at
        note.title = "Changed"

        with patch(
            "ayrannotes.storage.database.os.replace",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(OSError):
                self.storage.save_note(note)

        persisted = self.storage.get_note(note.id)
        self.assertEqual(persisted.title, "Original")
        self.assertEqual(note.updated_at, persisted_timestamp)
        self.assertEqual(list(self.storage.notes_dir.glob("*.tmp")), [])

    def test_legacy_json_is_migrated_once_with_exact_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            notes_dir = base / "notes"
            notes_dir.mkdir(parents=True)
            note = Note(
                title="Legacy",
                content="Preserved body",
                folder="Archive",
                is_pinned=True,
                is_favorite=True,
                tags=["old", "safe"],
            )
            original = json.dumps(
                note.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
            legacy_path = notes_dir / f"{note.id}.json"
            legacy_path.write_text(original, encoding="utf-8")

            migrated = StorageEngine(base)

            self.assertFalse(legacy_path.exists())
            self.assertTrue((notes_dir / f"{note.id}.md").is_file())
            backup = (
                migrated.migration_backup_dir
                / "default"
                / legacy_path.name
            )
            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            loaded = migrated.get_note(note.id)
            self.assertEqual(loaded.to_dict(), note.to_dict())

            reopened = StorageEngine(base)
            self.assertEqual(len(reopened.list_notes()), 1)
            self.assertEqual(
                list(reopened.migration_backup_dir.rglob("*.json")),
                [backup],
            )

    def test_legacy_migration_preserves_title_and_folder_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            notes_dir = base / "notes"
            notes_dir.mkdir(parents=True)
            note = Note(
                title="  padded title  ",
                folder="  padded folder  ",
                content="Exact metadata matters.",
            )
            legacy_path = notes_dir / f"{note.id}.json"
            legacy_path.write_text(
                json.dumps(note.to_dict(), ensure_ascii=False),
                encoding="utf-8",
            )

            migrated = StorageEngine(base)
            loaded = migrated.get_note(note.id)

            self.assertFalse(legacy_path.exists())
            self.assertEqual(loaded.title, note.title)
            self.assertEqual(loaded.folder, note.folder)

    def test_migration_does_not_overwrite_conflicting_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            notes_dir = base / "notes"
            notes_dir.mkdir(parents=True)
            legacy = Note(title="Legacy", content="JSON body")
            source = notes_dir / f"{legacy.id}.json"
            original = json.dumps(legacy.to_dict()).encode("utf-8")
            source.write_bytes(original)
            conflicting = Note(
                id=legacy.id,
                title="External",
                content="Markdown body",
            )
            destination = notes_dir / f"{legacy.id}.md"
            destination.write_text(
                serialize_note(conflicting),
                encoding="utf-8",
            )

            storage = StorageEngine(base)

            self.assertTrue(source.is_file())
            self.assertEqual(storage.get_note(legacy.id).title, "External")
            self.assertEqual(
                (
                    storage.migration_backup_dir
                    / "default"
                    / source.name
                ).read_bytes(),
                original,
            )

    def test_failed_atomic_backup_keeps_json_for_clean_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            notes_dir = base / "notes"
            notes_dir.mkdir(parents=True)
            note = Note(title="Retry")
            source = notes_dir / f"{note.id}.json"
            original = json.dumps(note.to_dict()).encode("utf-8")
            source.write_bytes(original)

            with patch(
                "ayrannotes.storage.database.os.replace",
                side_effect=OSError("backup disk full"),
            ):
                with self.assertRaises(OSError):
                    StorageEngine(base)

            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(
                list((base / "legacy-json-backup").rglob("*.json")),
                [],
            )

            retried = StorageEngine(base)
            backup = (
                retried.migration_backup_dir
                / "default"
                / source.name
            )
            self.assertFalse(source.exists())
            self.assertEqual(backup.read_bytes(), original)

    def test_malformed_legacy_json_is_backed_up_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            notes_dir = base / "notes"
            notes_dir.mkdir(parents=True)
            legacy = notes_dir / "abcdef123456.json"
            legacy.write_text("{broken", encoding="utf-8")

            storage = StorageEngine(base)

            self.assertTrue(legacy.is_file())
            self.assertEqual(
                (
                    storage.migration_backup_dir
                    / "default"
                    / legacy.name
                ).read_text(
                    encoding="utf-8"
                ),
                "{broken",
            )
            self.assertEqual(storage.list_notes(), [])

    def test_custom_notes_directory_is_shared_through_xdg_settings(self) -> None:
        shared = self.base_dir / "Shared Notes"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)

        reopened = StorageEngine(self.base_dir)
        note = Note(title="Shared")
        reopened.save_note(note)

        self.assertEqual(reopened.notes_dir, shared.resolve())
        self.assertTrue((shared / ".ayrannotes-directory").is_file())
        self.assertTrue(reopened.load_settings().notes_directory_id)
        self.assertTrue((shared / f"{note.id}.md").is_file())
        self.assertTrue((self.base_dir / "settings.json").is_file())

    def test_missing_custom_directory_is_not_silently_created(self) -> None:
        missing = self.base_dir / "missing-drive" / "Notes"
        settings = self.storage.load_settings()
        settings.notes_directory = str(missing)
        self.storage.save_settings(settings)

        with self.assertRaises(FileNotFoundError):
            StorageEngine(self.base_dir)

        self.assertFalse(missing.exists())

    def test_settings_controller_switches_and_resets_notes_directory(self) -> None:
        shared = self.base_dir / "shared"
        shared.mkdir()
        controller = SettingsController(self.storage)

        controller.set_notes_directory(shared)

        self.assertEqual(self.storage.notes_dir, shared.resolve())
        self.assertEqual(
            self.storage.load_settings().notes_directory,
            str(shared.resolve()),
        )

        controller.reset_defaults()

        self.assertEqual(self.storage.notes_dir, self.storage.default_notes_dir)
        self.assertEqual(self.storage.load_settings().notes_directory, "")
        self.assertEqual(self.storage.load_settings().notes_directory_id, "")

    def test_custom_directory_marker_detects_wrong_mount(self) -> None:
        shared = self.base_dir / "mounted-notes"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)
        marker = shared / ".ayrannotes-directory"
        marker.write_text("different-volume\n", encoding="utf-8")

        with self.assertRaises(OSError):
            StorageEngine(self.base_dir)

    def test_runtime_marker_blocks_writes_to_replaced_mountpoint(self) -> None:
        shared = self.base_dir / "mounted-notes"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)
        detached = self.base_dir / "detached-notes"
        shared.rename(detached)
        shared.mkdir()
        note = Note(title="Must not use the wrong disk")

        with self.assertRaises(OSError):
            self.storage.save_note(note)
        with self.assertRaises(OSError):
            self.storage.list_notes()

        self.assertFalse((shared / f"{note.id}.md").exists())

    def test_existing_corrupt_settings_file_is_not_silently_ignored(self) -> None:
        self.storage.settings_file.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            StorageEngine(self.base_dir)

    def test_existing_non_object_settings_file_is_rejected(self) -> None:
        self.storage.settings_file.write_text("[]", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "root must be an object"):
            StorageEngine(self.base_dir)

    def test_invalid_notes_directory_setting_type_is_rejected(self) -> None:
        self.storage.settings_file.write_text(
            json.dumps({"notes_directory": []}),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "notes_directory"):
            StorageEngine(self.base_dir)

    def test_missing_custom_directory_identity_is_upgraded(self) -> None:
        shared = self.base_dir / "shared-without-marker"
        shared.mkdir()
        settings = self.storage.load_settings()
        settings.notes_directory = str(shared)
        settings.notes_directory_id = ""
        self.storage.save_settings(settings)
        reopened = StorageEngine(self.base_dir)

        SettingsController(reopened)

        persisted = reopened.load_settings()
        marker_identity = (
            shared / ".ayrannotes-directory"
        ).read_text(encoding="utf-8").strip()
        self.assertTrue(marker_identity)
        self.assertEqual(persisted.notes_directory_id, marker_identity)

    def test_reset_defaults_rolls_back_when_settings_cannot_be_saved(self) -> None:
        shared = self.base_dir / "shared"
        shared.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(shared)
        persisted = self.storage.load_settings()

        with patch.object(
            self.storage,
            "save_settings",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(OSError):
                controller.reset_defaults()

        self.assertEqual(self.storage.notes_dir, shared.resolve())
        self.assertEqual(
            controller.settings.notes_directory,
            persisted.notes_directory,
        )
        self.assertEqual(
            self.storage.load_settings().notes_directory,
            persisted.notes_directory,
        )

    def test_reload_reconfigures_the_runtime_notes_directory(self) -> None:
        first = self.base_dir / "first"
        second = self.base_dir / "second"
        first.mkdir()
        second.mkdir()
        controller = SettingsController(self.storage)
        controller.set_notes_directory(first)
        settings = self.storage.load_settings()
        settings.notes_directory = str(second)
        settings.notes_directory_id = ""
        self.storage.save_settings(settings)

        controller.reload()

        self.assertEqual(self.storage.notes_dir, second.resolve())
        self.assertEqual(
            controller.settings.notes_directory,
            str(second),
        )
        persisted = self.storage.load_settings()
        marker_identity = (
            second / ".ayrannotes-directory"
        ).read_text(encoding="utf-8").strip()
        self.assertTrue(marker_identity)
        self.assertEqual(persisted.notes_directory_id, marker_identity)
        self.assertEqual(controller.settings.notes_directory_id, marker_identity)

    def test_legacy_note_gets_new_organization_defaults(self) -> None:
        data = Note(title="Legacy").to_dict()
        for key in (
            "tags",
            "attachments",
            "is_favorite",
            "is_archived",
            "is_trashed",
            "is_simple_draft",
        ):
            data.pop(key)
        loaded = Note.from_dict(data)
        self.assertEqual(loaded.tags, [])
        self.assertFalse(loaded.is_favorite)
        self.assertFalse(loaded.is_archived)
        self.assertFalse(loaded.is_trashed)
        self.assertFalse(loaded.is_simple_draft)
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
