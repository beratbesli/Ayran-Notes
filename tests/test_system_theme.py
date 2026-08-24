"""Tests for system theme and accent color integration."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.storage.database import StorageEngine
from ayrannotes.ui.system_theme import SystemThemeMonitor


class SystemThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = StorageEngine(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_system_theme_monitor_defaults(self) -> None:
        monitor = SystemThemeMonitor()
        theme = monitor.get_system_theme()
        self.assertIn(theme, ("dark", "light"))

        accent = monitor.get_system_accent_color()
        self.assertTrue(accent.startswith("#"))
        self.assertEqual(len(accent), 7)

    def test_settings_controller_resolves_system_theme(self) -> None:
        ctrl = SettingsController(self.storage)
        ctrl.settings.theme = "system"
        ctrl.settings.accent_color = ""

        with patch.object(SystemThemeMonitor, "get_system_theme", return_value="light"), \
             patch.object(SystemThemeMonitor, "get_system_accent_color", return_value="#abcdef"):
            self.assertEqual(ctrl.resolved_theme, "light")
            self.assertEqual(ctrl.resolved_accent_color, "#abcdef")

    def test_settings_controller_custom_theme_overrides(self) -> None:
        ctrl = SettingsController(self.storage)
        ctrl.settings.theme = "dark"
        ctrl.settings.accent_color = "#112233"

        with patch.object(SystemThemeMonitor, "get_system_theme", return_value="light"), \
             patch.object(SystemThemeMonitor, "get_system_accent_color", return_value="#abcdef"):
            self.assertEqual(ctrl.resolved_theme, "dark")
            self.assertEqual(ctrl.resolved_accent_color, "#112233")


if __name__ == "__main__":
    unittest.main()
