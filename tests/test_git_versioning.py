"""Tests for git versioning of notes directory."""

import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch

from ayrannotes.storage.git_versioning import GitVersioning
from ayrannotes.storage.database import StorageEngine
from ayrannotes.storage.models import Note
import ayrannotes.storage.git_versioning as gv


class GitVersioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_git_init_and_is_repo(self) -> None:
        git_manager = GitVersioning()
        notes_dir = self.tmp_path / "notes"
        notes_dir.mkdir()

        self.assertFalse(git_manager.is_repo(notes_dir))
        self.assertTrue(git_manager.init_repo(notes_dir))
        self.assertTrue(git_manager.is_repo(notes_dir))

        # Second init should return True
        self.assertTrue(git_manager.init_repo(notes_dir))

    def test_commit_change_and_history(self) -> None:
        git_manager = GitVersioning()
        notes_dir = self.tmp_path / "notes"
        notes_dir.mkdir()
        git_manager.init_repo(notes_dir)

        file1 = notes_dir / "note1.md"
        file1.write_text("Hello World", encoding="utf-8")

        self.assertTrue(git_manager.commit_change(notes_dir, "Create: note1"))

        history = git_manager.get_history(notes_dir)
        self.assertEqual(len(history), 1)
        self.assertIn("Create: note1", history[0]["message"])

        # Test second commit
        file1.write_text("Hello World 2", encoding="utf-8")
        self.assertTrue(git_manager.commit_change(notes_dir, "Update: note1"))

        history = git_manager.get_history(notes_dir)
        self.assertEqual(len(history), 2)
        self.assertIn("Update: note1", history[0]["message"])

        # Test getting file version
        v1 = git_manager.get_file_version(notes_dir, file1, history[1]["hash"])
        self.assertEqual(v1.strip(), "Hello World")

    def test_commit_change_ignores_non_markdown_files(self) -> None:
        git_manager = GitVersioning()
        notes_dir = self.tmp_path / "notes"
        notes_dir.mkdir()
        git_manager.init_repo(notes_dir)

        (notes_dir / "note.md").write_text("Markdown", encoding="utf-8")
        (notes_dir / "settings.json").write_text("{}", encoding="utf-8")
        (notes_dir / "attachment.pdf").write_bytes(b"pdf")

        self.assertTrue(git_manager.commit_change(notes_dir, "Create: note"))
        tracked = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=notes_dir,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertEqual(tracked, ["note.md"])

        (notes_dir / "settings.json").write_text('{"changed": true}', encoding="utf-8")
        self.assertTrue(git_manager.commit_change(notes_dir, "Metadata change"))
        self.assertEqual(
            len(git_manager.get_history(notes_dir)),
            1,
        )

    def test_storage_engine_integration(self) -> None:
        commits = []

        def mock_schedule(notes_dir, message, delay=5.0):
            commits.append(message)
            gv.git_manager.commit_change(notes_dir, message)

        with patch.object(gv.git_manager, "schedule_commit", side_effect=mock_schedule):
            engine = StorageEngine(base_dir=self.tmp_path)
            self.assertTrue(gv.git_manager.is_repo(engine.notes_dir))

            note = Note(title="Test Note", content="Test Content")
            engine.save_note(note)

            self.assertIn("Update: Test Note", commits)

            history = gv.git_manager.get_history(engine.notes_dir)
            self.assertEqual(len(history), 1)

            engine.delete_note(note.id)
            self.assertIn("Delete: Test Note", commits)

            history = gv.git_manager.get_history(engine.notes_dir)
            self.assertEqual(len(history), 2)


if __name__ == "__main__":
    unittest.main()
