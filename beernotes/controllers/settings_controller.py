"""Beer Notes — Settings controller.

Manages application settings lifecycle, emitting signals when
settings change so the UI can react without a restart.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import AppSettings


class SettingsController(QObject):
    """Handles loading, saving, and live-updating of application settings."""

    settings_changed = pyqtSignal(AppSettings)

    def __init__(self, storage: StorageEngine, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._settings: AppSettings = self._storage.load_settings()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def settings(self) -> AppSettings:
        """Return the current in-memory settings object."""
        return self._settings

    # ------------------------------------------------------------------
    # Mutation helpers (apply + save + notify)
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        """Persist and broadcast the current settings."""
        self._storage.save_settings(self._settings)
        self.settings_changed.emit(self._settings)

    def set_theme(self, theme: str) -> None:
        self._settings.theme = theme
        self._apply()

    def set_accent_color(self, color: str) -> None:
        self._settings.accent_color = color
        self._apply()

    def set_font_family(self, family: str) -> None:
        self._settings.font_family = family
        self._apply()

    def set_font_size(self, size: int) -> None:
        self._settings.font_size = max(8, min(size, 32))
        self._apply()

    def set_language(self, lang: str) -> None:
        self._settings.language = lang
        self._apply()

    def set_sidebar_visible(self, visible: bool) -> None:
        self._settings.sidebar_visible = visible
        self._apply()

    def set_preview_visible(self, visible: bool) -> None:
        self._settings.preview_visible = visible
        self._apply()

    def save_window_geometry(self, x: int, y: int, w: int, h: int) -> None:
        """Silently save window position and size (no broadcast)."""
        self._settings.window_x = x
        self._settings.window_y = y
        self._settings.window_width = w
        self._settings.window_height = h
        self._storage.save_settings(self._settings)

    def save_sidebar_folder_height(self, height: int) -> None:
        """Silently persist the user-selected sidebar section height."""
        self._settings.sidebar_folder_height = max(80, height)
        self._storage.save_settings(self._settings)

    def reset_defaults(self) -> None:
        """Reset all settings to factory defaults."""
        self._settings = AppSettings()
        self._apply()

    def reload(self) -> None:
        """Re-read settings from disk."""
        self._settings = self._storage.load_settings()
        self.settings_changed.emit(self._settings)
