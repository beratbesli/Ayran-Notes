import pytest
import time
import subprocess
from pathlib import Path

from beernotes.storage.git_versioning import GitVersioning
from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note

def test_git_init_and_is_repo(tmp_path):
    git_manager = GitVersioning()
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    
    assert not git_manager.is_repo(notes_dir)
    assert git_manager.init_repo(notes_dir)
    assert git_manager.is_repo(notes_dir)
    
    # Second init should return True
    assert git_manager.init_repo(notes_dir)

def test_commit_change_and_history(tmp_path):
    git_manager = GitVersioning()
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    git_manager.init_repo(notes_dir)
    
    file1 = notes_dir / "note1.md"
    file1.write_text("Hello World")
    
    assert git_manager.commit_change(notes_dir, "Create: note1")
    
    history = git_manager.get_history(notes_dir)
    assert len(history) == 1
    assert "Create: note1" in history[0]["message"]
    
    # Test second commit
    file1.write_text("Hello World 2")
    assert git_manager.commit_change(notes_dir, "Update: note1")
    
    history = git_manager.get_history(notes_dir)
    assert len(history) == 2
    assert "Update: note1" in history[0]["message"]
    
    # Test getting file version
    v1 = git_manager.get_file_version(notes_dir, file1, history[1]["hash"])
    assert v1.strip() == "Hello World"

def test_storage_engine_integration(tmp_path, monkeypatch):
    # Shorten debounce delay for tests
    from beernotes.storage import database
    import beernotes.storage.git_versioning as gv
    
    original_schedule = gv.git_manager.schedule_commit
    
    commits = []
    def mock_schedule(notes_dir, message, delay=5.0):
        # execute immediately instead of timer for testing
        commits.append(message)
        gv.git_manager.commit_change(notes_dir, message)
        
    monkeypatch.setattr(gv.git_manager, "schedule_commit", mock_schedule)
    
    engine = StorageEngine(base_dir=tmp_path)
    
    assert gv.git_manager.is_repo(engine.notes_dir)
    
    note = Note(title="Test Note", content="Test Content")
    engine.save_note(note)
    
    assert "Update: Test Note" in commits
    
    # Check history
    history = gv.git_manager.get_history(engine.notes_dir)
    assert len(history) == 1
    
    engine.delete_note(note.id)
    assert "Delete: Test Note" in commits
    
    history = gv.git_manager.get_history(engine.notes_dir)
    assert len(history) == 2
