"""Tests for the Ayran Notes Command Palette."""

import unittest

from PyQt6.QtWidgets import QApplication

from ayrannotes.ui.command_palette import CommandPalette


class CommandPaletteTests(unittest.TestCase):
    """Test the command palette widget."""

    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls._app = QApplication([])

    def test_palette_creates(self):
        palette = CommandPalette()
        self.assertIsNotNone(palette)

    def test_set_commands(self):
        palette = CommandPalette()
        commands = [
            ("New Note", lambda: None),
            ("Dark Mode", lambda: None),
            ("Quit", lambda: None),
        ]
        palette.set_commands(commands)
        self.assertEqual(palette._list.count(), 3)

    def test_filter_commands(self):
        palette = CommandPalette()
        commands = [
            ("New Note", lambda: None),
            ("Dark Mode", lambda: None),
            ("Delete Note", lambda: None),
        ]
        palette.set_commands(commands)
        palette._filter_commands("note")
        visible = sum(
            1
            for i in range(palette._list.count())
            if not palette._list.item(i).isHidden()
        )
        self.assertEqual(visible, 2)  # "New Note" and "Delete Note"

    def test_filter_case_insensitive(self):
        palette = CommandPalette()
        commands = [
            ("New Note", lambda: None),
            ("DARK MODE", lambda: None),
        ]
        palette.set_commands(commands)
        palette._filter_commands("dark")
        visible = sum(
            1
            for i in range(palette._list.count())
            if not palette._list.item(i).isHidden()
        )
        self.assertEqual(visible, 1)

    def test_execute_command(self):
        palette = CommandPalette()
        executed = []
        commands = [
            ("Test Cmd", lambda: executed.append(True)),
        ]
        palette.set_commands(commands)
        palette._list.setCurrentRow(0)
        palette._execute_selected()
        self.assertEqual(len(executed), 1)

    def test_theme_switch(self):
        palette = CommandPalette()
        palette.set_theme("dark")
        palette.set_theme("light")
        # Should not raise


if __name__ == "__main__":
    unittest.main()
