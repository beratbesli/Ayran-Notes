import pytest
from PyQt6.QtCore import Qt
from beernotes.ui.main_window import MainWindow

def test_zen_mode_toggles(qtbot, note_controller, settings_controller, i18n):
    # Setup
    window = MainWindow(note_controller, settings_controller, i18n)
    qtbot.addWidget(window)
    window.show()

    # Enter detailed mode
    window._change_view_mode("detailed")

    # Verify initial state
    assert window._sidebar.isVisible()
    assert window.menuBar().isVisible()

    # Enter zen mode
    window._enter_zen_mode()
    
    assert window._in_zen_mode
    assert not window._sidebar.isVisible()
    assert not window.menuBar().isVisible()
    assert not window._navigation_bar.isVisible()
    assert not window._statusbar.isVisible()

    # Exit zen mode
    window._exit_zen_mode()

    assert not window._in_zen_mode
    assert window._sidebar.isVisible()
    assert window.menuBar().isVisible()
    assert window._navigation_bar.isVisible()
    assert window._statusbar.isVisible()

def test_zen_mode_toggle_action(qtbot, note_controller, settings_controller, i18n):
    window = MainWindow(note_controller, settings_controller, i18n)
    qtbot.addWidget(window)
    window.show()
    
    window._act_zen_mode.trigger()
    assert window._in_zen_mode
    
    window._act_zen_mode.trigger()
    assert not window._in_zen_mode

def test_zen_mode_preserves_state(qtbot, note_controller, settings_controller, i18n):
    window = MainWindow(note_controller, settings_controller, i18n)
    qtbot.addWidget(window)
    window.show()
    
    # Disable sidebar in detailed mode
    window._change_view_mode("detailed")
    settings_controller.set_sidebar_visible(False)
    
    assert not window._sidebar.isVisible()
    
    window._enter_zen_mode()
    assert not window._sidebar.isVisible()
    
    window._exit_zen_mode()
    
    # Should stay hidden after exiting zen mode
    assert not window._sidebar.isVisible()
