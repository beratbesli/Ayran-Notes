import os
import subprocess
import threading
import logging
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class GitVersioning:
    """Manages Git versioning for the notes directory."""
    
    def __init__(self):
        self._commit_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def is_repo(self, notes_dir: Path) -> bool:
        """Check if the directory is a git repository."""
        if not notes_dir or not notes_dir.is_dir():
            return False
        return (notes_dir / ".git").is_dir()

    def init_repo(self, notes_dir: Path) -> bool:
        """Initialize the notes directory as a git repository."""
        if not notes_dir or not notes_dir.is_dir():
            return False
        
        if self.is_repo(notes_dir):
            return True

        try:
            subprocess.run(
                ["git", "init"],
                cwd=notes_dir,
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Beer Notes"],
                cwd=notes_dir,
                check=False,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "beernotes@local"],
                cwd=notes_dir,
                check=False,
                capture_output=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Failed to initialize git repository: {e}")
            return False


    def commit_change(self, notes_dir: Path, message: str) -> bool:
        """Commit changes in the notes directory."""
        if not self.is_repo(notes_dir):
            return False

        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=notes_dir,
                check=True,
                capture_output=True
            )
            
            # Check if there are any changes to commit
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=notes_dir,
                check=True,
                capture_output=True,
                text=True
            )
            
            if not status.stdout.strip():
                return True # Nothing to commit
                
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=notes_dir,
                check=True,
                capture_output=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Failed to commit changes: {e}")
            return False

    def get_history(self, notes_dir: Path, filepath: Optional[Path] = None, limit: int = 20) -> List[Dict]:
        """Get git commit history."""
        if not self.is_repo(notes_dir):
            return []

        cmd = ["git", "log", f"-n{limit}", "--pretty=format:%H|%an|%ad|%s", "--date=iso"]
        if filepath:
            # Need to get path relative to notes_dir
            try:
                rel_path = filepath.relative_to(notes_dir)
                cmd.extend(["--", str(rel_path)])
            except ValueError:
                cmd.extend(["--", str(filepath)])

        try:
            result = subprocess.run(
                cmd,
                cwd=notes_dir,
                check=True,
                capture_output=True,
                text=True
            )
            
            history = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) == 4:
                    history.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })
            return history
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def get_file_version(self, notes_dir: Path, filepath: Path, commit_hash: str) -> str:
        """Get the content of a file at a specific commit."""
        if not self.is_repo(notes_dir):
            return ""

        try:
            rel_path = filepath.relative_to(notes_dir)
        except ValueError:
            rel_path = filepath

        try:
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:{str(rel_path).replace(os.sep, '/')}"],
                cwd=notes_dir,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Failed to get file version: {e}")
            return ""

    def schedule_commit(self, notes_dir: Path, message: str, delay: float = 5.0):
        """Schedule a debounced commit."""
        with self._lock:
            if self._commit_timer:
                self._commit_timer.cancel()
            
            self._commit_timer = threading.Timer(
                delay, 
                self.commit_change,
                args=(notes_dir, message)
            )
            self._commit_timer.start()

# Global instance for easy use
git_manager = GitVersioning()
