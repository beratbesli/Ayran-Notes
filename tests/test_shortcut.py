"""Tests for portable per-user desktop shortcut installation."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import install_shortcut


class ShortcutInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_home = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {"XDG_DATA_HOME": str(self.data_home)},
        )
        self.environment.start()
        self.no_database_refresh = patch(
            "install_shortcut.shutil.which",
            return_value=None,
        )
        self.no_database_refresh.start()

    def tearDown(self) -> None:
        self.no_database_refresh.stop()
        self.environment.stop()
        self.temporary.cleanup()

    def test_install_uses_stable_local_copy_instead_of_repository(self) -> None:
        desktop_path = install_shortcut.install()
        install_dir = self.data_home / install_shortcut.INSTALL_DIR_NAME
        installed_launcher = install_dir / "run.py"
        installed_package = install_dir / "beernotes"

        self.assertTrue(installed_launcher.is_file())
        self.assertTrue((installed_package / "main.py").is_file())
        desktop_entry = desktop_path.read_text(encoding="utf-8")
        self.assertIn(f'"{installed_launcher}"', desktop_entry)
        self.assertIn(f"Path={install_dir}", desktop_entry)
        self.assertNotIn(str(install_shortcut.PROJECT_DIR), desktop_entry)

    def test_uninstall_removes_shortcut_icon_and_local_copy(self) -> None:
        desktop_path = install_shortcut.install()
        icon_path = (
            self.data_home
            / "icons"
            / "hicolor"
            / "512x512"
            / "apps"
            / "beernotes.png"
        )
        install_dir = self.data_home / install_shortcut.INSTALL_DIR_NAME

        install_shortcut.uninstall()

        self.assertFalse(desktop_path.exists())
        self.assertFalse(icon_path.exists())
        self.assertFalse(install_dir.exists())


if __name__ == "__main__":
    unittest.main()
