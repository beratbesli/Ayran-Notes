import logging
import re
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_COMMIT_HASH = re.compile(r"^[0-9a-fA-F]{7,64}$")
_NOTE_PATH = re.compile(r"^[0-9a-f]{12}\.md$")

class GitVersioning:
    """Manages Git versioning for the notes directory."""
    
    def __init__(self):
        self._commit_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def is_repo(self, notes_dir: Path) -> bool:
        """Check if the directory is a git repository."""
        if not notes_dir or not notes_dir.is_dir():
            return False
        return (notes_dir / ".git").is_dir()

    @staticmethod
    def _relative_path(notes_dir: Path, filepath: Path) -> Path | None:
        """Return a safe repository-relative path, or ``None``."""
        try:
            root = notes_dir.resolve()
            candidate = filepath.resolve(strict=False)
            relative = candidate.relative_to(root)
        except (OSError, ValueError):
            return None
        if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            return None
        return relative

    @staticmethod
    def _valid_commit_hash(commit_hash: str) -> bool:
        return isinstance(commit_hash, str) and bool(_COMMIT_HASH.fullmatch(commit_hash))

    def _commit_exists(self, notes_dir: Path, commit_hash: str) -> bool:
        if not self._valid_commit_hash(commit_hash):
            return False
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit_hash}^{{commit}}"],
                cwd=notes_dir,
                check=False,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

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
                ["git", "config", "user.name", "Ayran Notes"],
                cwd=notes_dir,
                check=False,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "ayrannotes@local"],
                cwd=notes_dir,
                check=False,
                capture_output=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"Failed to initialize git repository: {e}")
            return False


    def commit_change(self, notes_dir: Path, message: str) -> bool:
        """Commit Markdown note changes without touching other files."""
        if not self.is_repo(notes_dir):
            return False

        try:
            subprocess.run(
                ["git", "add", "-A", "--", "*.md"],
                cwd=notes_dir,
                check=True,
                capture_output=True
            )

            # Check only the staged Markdown changes. Unrelated files may
            # exist in a shared notes directory and must remain untouched.
            staged = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=notes_dir,
                check=False,
                capture_output=True,
            )

            if staged.returncode == 0:
                return True  # Nothing to commit

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=notes_dir,
                check=True,
                capture_output=True
            )
            return True
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error(f"Failed to commit changes: {e}")
            return False

    def get_history(self, notes_dir: Path, filepath: Path | None = None, limit: int = 20) -> list[dict]:
        """Get commits that changed one file, newest first.

        The returned records intentionally keep the commit hash as technical
        data while exposing whether the file existed in that version. Git
        failures are treated as an unavailable history so note editing can
        continue without versioning.
        """
        if not self.is_repo(notes_dir):
            return []

        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20
        cmd = [
            "git",
            "log",
            f"-n{limit}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
        ]
        if filepath:
            cmd.insert(3, "--follow")
            rel_path = self._relative_path(notes_dir, filepath)
            if rel_path is None:
                return []
            cmd.extend(["--", rel_path.as_posix()])

        try:
            result = subprocess.run(
                cmd,
                cwd=notes_dir,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                if result.returncode == 128 and not result.stdout.strip():
                    return []
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            
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
                        "message": parts[3],
                        "exists": True,
                    })
            if filepath:
                rel_path = self._relative_path(notes_dir, filepath)
                if rel_path is not None:
                    for entry in history:
                        entry["exists"] = self._file_exists_at_commit(
                            notes_dir,
                            entry["hash"],
                            rel_path,
                        )
            return history
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error(f"Failed to get history: {e}")
            return []

    def _file_exists_at_commit(
        self,
        notes_dir: Path,
        commit_hash: str,
        relative_path: Path,
    ) -> bool:
        if not self._commit_exists(notes_dir, commit_hash):
            return False
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit_hash}:{relative_path.as_posix()}"],
                cwd=notes_dir,
                check=False,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def list_deleted_notes(self, notes_dir: Path, limit: int = 20) -> list[dict]:
        """Return deleted note files found in local Git history."""
        if not self.is_repo(notes_dir):
            return []
        try:
            limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            limit = 20
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    f"-n{limit}",
                    "--diff-filter=D",
                    "--name-status",
                    "--pretty=format:%H|%an|%ad|%s",
                    "--date=iso",
                    "--",
                    "*.md",
                ],
                cwd=notes_dir,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                if result.returncode == 128 and not result.stdout.strip():
                    return []
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error(f"Failed to list deleted notes: {e}")
            return []

        deleted: list[dict] = []
        current: dict | None = None
        for line in result.stdout.splitlines():
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4 and self._valid_commit_hash(parts[0]):
                current = {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                }
                continue
            if current is None or not line.startswith("D\t"):
                continue
            path = line[2:]
            if not _NOTE_PATH.fullmatch(path):
                continue
            record = dict(current)
            record["path"] = path
            record["note_id"] = Path(path).stem
            deleted.append(record)
            if len(deleted) >= limit:
                return deleted
        return deleted

    def get_parent_commit(self, notes_dir: Path, commit_hash: str) -> str:
        """Return the first parent commit, or an empty string on failure."""
        if not self.is_repo(notes_dir) or not self._commit_exists(notes_dir, commit_hash):
            return ""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--parents", "-n1", commit_hash],
                cwd=notes_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error(f"Failed to get parent commit: {e}")
            return ""
        commits = result.stdout.strip().split()
        return commits[1] if len(commits) > 1 else ""

    def get_file_version(self, notes_dir: Path, filepath: Path, commit_hash: str) -> str:
        """Get the content of a file at a specific commit."""
        if not self.is_repo(notes_dir):
            return ""

        rel_path = self._relative_path(notes_dir, filepath)
        if rel_path is None or not self._valid_commit_hash(commit_hash):
            return ""
        if not self._commit_exists(notes_dir, commit_hash):
            return ""

        try:
            result = subprocess.run(
                ["git", "show", f"{commit_hash}:{rel_path.as_posix()}"],
                cwd=notes_dir,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            logger.error(f"Failed to get file version: {e}")
            return ""

    def cancel_scheduled_commit(self) -> None:
        """Cancel a pending debounced commit before an explicit operation."""
        with self._lock:
            if self._commit_timer:
                self._commit_timer.cancel()
                self._commit_timer = None

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
            self._commit_timer.daemon = True
            self._commit_timer.start()

# Global instance for easy use
git_manager = GitVersioning()
