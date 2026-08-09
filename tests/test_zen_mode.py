"""Tests for Zen mode in MainWindow."""

import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from beernotes.controllers.note_controller import NoteController
from beernotes.controllers.settings_controller import SettingsController
from beernotes.localization.i18n import I18n
from beernotes.storage.database import StorageEngine
from beernotes.ui.main_window import MainWindow


class ZenModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.storage = StorageEngine(Path(self.temporary.name))
        self.settings = SettingsController(self.storage)
        self.notes = NoteController(self.storage)
        self.window = MainWindow(
            self.notes,
            self.settings,
            I18n("en"),
        )
        self.window.show()

    def tearDown(self) -> None:

        self.window.close()
        self.temporary.cleanup()

    def test_zen_mode_toggles(self) -> None:
        self.window._change_view_mode("detailed")

        self.assertTrue(self.window._sidebar.isVisible())
        self.assertTrue(self.window.menuBar().isVisible())

        self.window._enter_zen_mode()

        self.assertTrue(self.window._in_zen_mode)
        self.assertFalse(self.window._sidebar.isVisible())
        self.assertFalse(self.window.menuBar().isVisible())

        self.window._exit_zen_mode()

        self.assertFalse(self.window._in_zen_mode)
        self.assertTrue(self.window._sidebar.isVisible())
        self.assertTrue(self.window.menuBar().isVisible())

    def test_zen_mode_toggle_action(self) -> None:
        self.window._act_zen_mode.trigger()
        self.assertTrue(self.window._in_zen_mode)

        self.window._act_zen_mode.trigger()
        self.assertFalse(self.window._in_zen_mode)

    def test_zen_mode_preserves_state(self) -> None:
        self.window._change_view_mode("detailed")
        self.settings.set_sidebar_visible(False)

        self.assertFalse(self.window._sidebar.isVisible())

        self.window._enter_zen_mode()
        self.assertFalse(self.window._sidebar.isVisible())

        self.window._exit_zen_mode()
        self.assertFalse(self.window._sidebar.isVisible())


if __name__ == "__main__":
    unittest.main()
