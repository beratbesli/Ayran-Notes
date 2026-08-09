"""Tests for system theme and accent color integration."""

import pytest

from beernotes.storage.database import StorageEngine
from beernotes.controllers.settings_controller import SettingsController
from beernotes.ui.system_theme import SystemThemeMonitor


@pytest.fixture
def storage(tmp_path):
    """Temporary storage engine for settings tests."""
    return StorageEngine(tmp_path)


def test_system_theme_monitor_defaults(qtbot):
    """SystemThemeMonitor should provide reasonable fallback values without error."""
    monitor = SystemThemeMonitor()
    theme = monitor.get_system_theme()
    assert theme in ("dark", "light")
    
    accent = monitor.get_system_accent_color()
    assert accent.startswith("#")
    assert len(accent) == 7


def test_settings_controller_resolves_system_theme(storage, qtbot, monkeypatch):
    """SettingsController should resolve 'system' and empty strings using the monitor."""
    ctrl = SettingsController(storage)
    ctrl.settings.theme = "system"
    ctrl.settings.accent_color = ""

    # Mock the monitor methods to ensure our controller delegates correctly
    monkeypatch.setattr(
        SystemThemeMonitor, "get_system_theme", lambda self: "light"
    )
    monkeypatch.setattr(
        SystemThemeMonitor, "get_system_accent_color", lambda self: "#abcdef"
    )

    assert ctrl.resolved_theme == "light"
    assert ctrl.resolved_accent_color == "#abcdef"


def test_settings_controller_custom_theme_overrides(storage, qtbot, monkeypatch):
    """Explicitly set themes and colors should ignore system values."""
    ctrl = SettingsController(storage)
    ctrl.settings.theme = "dark"
    ctrl.settings.accent_color = "#112233"

    # Mock the monitor methods
    monkeypatch.setattr(
        SystemThemeMonitor, "get_system_theme", lambda self: "light"
    )
    monkeypatch.setattr(
        SystemThemeMonitor, "get_system_accent_color", lambda self: "#abcdef"
    )

    # Values should remain the custom ones
    assert ctrl.resolved_theme == "dark"
    assert ctrl.resolved_accent_color == "#112233"
