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
        self.home = self.data_home / "home"
        self.environment = patch.dict(
            os.environ,
            {
                "HOME": str(self.home),
                "XDG_DATA_HOME": str(self.data_home),
            },
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

    def test_install_uses_small_wrapper_that_runs_repository(self) -> None:
        legacy_copy = self.data_home / install_shortcut.LEGACY_INSTALL_DIR_NAME
        legacy_copy.mkdir()
        (legacy_copy / "stale-file").touch()

        desktop_path = install_shortcut.install()
        wrapper_path = self.home / ".local" / "bin" / install_shortcut.WRAPPER_NAME

        self.assertTrue(wrapper_path.is_file())
        self.assertFalse(legacy_copy.exists())
        wrapper = wrapper_path.read_text(encoding="utf-8")
        self.assertIn(str(install_shortcut.PROJECT_DIR), wrapper)
        self.assertIn(str(install_shortcut.LAUNCHER), wrapper)
        desktop_entry = desktop_path.read_text(encoding="utf-8")
        self.assertIn(f'"{wrapper_path}"', desktop_entry)
        self.assertNotIn("Path=", desktop_entry)
        self.assertNotIn(str(install_shortcut.PROJECT_DIR), desktop_entry)

    def test_uninstall_removes_shortcut_icon_and_wrapper(self) -> None:
        desktop_path = install_shortcut.install()
        icon_path = (
            self.data_home
            / "icons"
            / "hicolor"
            / "512x512"
            / "apps"
            / "beernotes.png"
        )
        wrapper_path = self.home / ".local" / "bin" / install_shortcut.WRAPPER_NAME

        install_shortcut.uninstall()

        self.assertFalse(desktop_path.exists())
        self.assertFalse(icon_path.exists())
        self.assertFalse(wrapper_path.exists())


if __name__ == "__main__":
    unittest.main()
