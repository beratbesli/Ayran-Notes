"""Tests for the floating context toolbar."""

import pytest
from PyQt6.QtWidgets import QPlainTextEdit, QMainWindow, QPushButton
from PyQt6.QtGui import QTextCursor

from beernotes.ui.floating_toolbar import FloatingToolbar


class DummyI18n:
    def t(self, key, **kwargs):
        return key


@pytest.fixture
def parent_window(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def editor(parent_window):
    editor = QPlainTextEdit(parent_window)
    parent_window.setCentralWidget(editor)
    editor.setPlainText("Hello World. This is a test.")
    return editor


def test_floating_toolbar_shows_on_selection(qtbot, editor, parent_window):
    callbacks = []

    def wrap_selection(prefix, suffix, placeholder):
        callbacks.append((prefix, suffix, placeholder))

    toolbar = FloatingToolbar(editor, wrap_selection, DummyI18n(), parent_window)

    assert toolbar.isHidden()

    # Select text
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    # Selection changed signal should have fired
    assert not toolbar.isHidden()

    # Clear selection
    cursor.clearSelection()
    editor.setTextCursor(cursor)

    assert toolbar.isHidden()


def test_floating_toolbar_actions(qtbot, editor, parent_window):
    callbacks = []

    def wrap_selection(prefix, suffix, placeholder):
        callbacks.append((prefix, suffix, placeholder))

    toolbar = FloatingToolbar(editor, wrap_selection, DummyI18n(), parent_window)

    # Select text
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    assert not toolbar.isHidden()

    # Get the bold button
    buttons = toolbar.findChildren(QPushButton)
    bold_btn = next((b for b in buttons if b.toolTip() == "bold"), None)

    assert bold_btn is not None
    # Simulate a click
    bold_btn.clicked.emit(False)

    assert len(callbacks) == 1
    assert callbacks[0] == ("**", "**", "bold")

    # Toolbar should hide after action
    assert toolbar.isHidden()
