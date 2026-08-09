"""Tests for the floating context toolbar."""

import unittest
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QMainWindow, QPushButton
from PyQt6.QtGui import QTextCursor

from beernotes.ui.floating_toolbar import FloatingToolbar


class DummyI18n:
    def t(self, key, **kwargs):
        return key


class FloatingToolbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = QMainWindow()
        self.editor = QPlainTextEdit(self.window)
        self.window.setCentralWidget(self.editor)
        self.editor.setPlainText("Hello World. This is a test.")

    def tearDown(self) -> None:
        self.window.close()

    def test_floating_toolbar_shows_on_selection(self) -> None:
        callbacks = []

        def wrap_selection(prefix, suffix, placeholder):
            callbacks.append((prefix, suffix, placeholder))

        toolbar = FloatingToolbar(self.editor, wrap_selection, DummyI18n(), self.window)

        self.assertTrue(toolbar.isHidden())

        # Select text
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        # Selection changed signal should have fired
        self.assertFalse(toolbar.isHidden())

        # Clear selection
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)

        self.assertTrue(toolbar.isHidden())

    def test_floating_toolbar_actions(self) -> None:
        callbacks = []

        def wrap_selection(prefix, suffix, placeholder):
            callbacks.append((prefix, suffix, placeholder))

        toolbar = FloatingToolbar(self.editor, wrap_selection, DummyI18n(), self.window)

        # Select text
        cursor = self.editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)

        self.assertFalse(toolbar.isHidden())

        # Get the bold button
        buttons = toolbar.findChildren(QPushButton)
        bold_btn = next((b for b in buttons if b.toolTip() == "bold"), None)

        self.assertIsNotNone(bold_btn)
        # Simulate a click
        bold_btn.clicked.emit(False)

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(callbacks[0], ("**", "**", "bold"))

        # Toolbar should hide after action
        self.assertTrue(toolbar.isHidden())


if __name__ == "__main__":
    unittest.main()
