"""Beer Notes — Settings controller.

Manages application settings lifecycle, emitting signals when
settings change so the UI can react without a restart.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import AppSettings
from beernotes.ui.system_theme import SystemThemeMonitor


class SettingsController(QObject):
    """Handles loading, saving, and live-updating of application settings."""

    settings_changed = pyqtSignal(AppSettings)

    def __init__(self, storage: StorageEngine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage = storage
        self._settings: AppSettings = self._storage.load_settings()
        self._system_theme_monitor = SystemThemeMonitor(self)
        self._system_theme_monitor.system_theme_changed.connect(self._on_system_theme_changed)
        self._system_theme_monitor.system_accent_changed.connect(self._on_system_accent_changed)
        settings_updated = False
        if not self._settings.compact_window_migrated:
            self._settings.window_width = min(self._settings.window_width, 1000)
            self._settings.window_height = min(self._settings.window_height, 680)
            self._settings.compact_window_migrated = True
            settings_updated = True
        if (
            self._storage.notes_dir != self._storage.default_notes_dir
            and not self._settings.notes_directory_id
        ):
            self._settings.notes_directory_id = (
                self._storage.ensure_notes_directory_identity()
            )
            settings_updated = True
        if settings_updated:
            self._storage.save_settings(self._settings)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def settings(self) -> AppSettings:
        """Return the current in-memory settings object."""
        return self._settings

    @property
    def resolved_theme(self) -> str:
        """Return 'dark' or 'light' resolving 'system' theme."""
        if self._settings.theme == "system":
            return self._system_theme_monitor.get_system_theme()
        return self._settings.theme

    @property
    def resolved_accent_color(self) -> str:
        """Return the hex accent color resolving system defaults."""
        if not self._settings.accent_color:
            return self._system_theme_monitor.get_system_accent_color()
        return self._settings.accent_color

    @property
    def resolved_notes_directory(self) -> Path:
        return self._storage.notes_dir

    @property
    def default_notes_directory(self) -> Path:
        return self._storage.default_notes_dir

    # ------------------------------------------------------------------
    # Mutation helpers (apply + save + notify)
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        """Persist and broadcast the current settings."""
        self._storage.save_settings(self._settings)
        self.settings_changed.emit(self._settings)

    def _on_system_theme_changed(self, theme: str) -> None:
        if self._settings.theme == "system":
            self.settings_changed.emit(self._settings)

    def _on_system_accent_changed(self, color: str) -> None:
        if not self._settings.accent_color:
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

    def set_toolbar_actions(self, actions: list[str]) -> None:
        """Persist the ordered set of tools shown above the editor."""
        self._settings.toolbar_actions = list(dict.fromkeys(actions))
        self._apply()

    def set_llm_api_url(self, url: str) -> None:
        self._settings.llm_api_url = url
        self._apply()

    def set_llm_api_key(self, key: str) -> None:
        self._settings.llm_api_key = key
        self._apply()

    def set_llm_model(self, model: str) -> None:
        self._settings.llm_model = model
        self._apply()

    def set_view_mode(self, mode: str) -> None:
        """Switch between the simple cards view and the detailed workspace."""
        if mode not in {"simple", "detailed"}:
            return
        self._settings.view_mode = mode
        self._apply()

    def set_notes_directory(self, directory: str | Path | None) -> None:
        """Use an existing folder as the shared Markdown notes directory."""
        previous_directory = self._storage.notes_dir
        previous_setting = self._settings.notes_directory
        previous_identity = self._settings.notes_directory_id
        try:
            resolved = self._storage.configure_notes_directory(directory)
            self._settings.notes_directory = (
                ""
                if resolved == self._storage.default_notes_dir
                else str(resolved)
            )
            self._settings.notes_directory_id = (
                self._storage.ensure_notes_directory_identity()
            )
            self._storage.save_settings(self._settings)
        except (OSError, ValueError):
            self._settings.notes_directory = previous_setting
            self._settings.notes_directory_id = previous_identity
            self._storage.configure_notes_directory(
                previous_directory,
                expected_identity=previous_identity,
            )
            raise
        self.settings_changed.emit(self._settings)

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

    def save_main_splitter_sizes(self, sizes: list[int]) -> None:
        """Silently persist the main splitter sizes."""
        self._settings.main_splitter_sizes = sizes
        self._storage.save_settings(self._settings)

    def reset_defaults(self) -> None:
        """Reset all settings to factory defaults."""
        previous_settings = self._settings
        previous_directory = self._storage.notes_dir
        defaults = AppSettings()
        try:
            self._storage.configure_notes_directory(None)
            self._storage.save_settings(defaults)
        except (OSError, ValueError):
            self._settings = previous_settings
            self._storage.configure_notes_directory(
                previous_directory,
                expected_identity=previous_settings.notes_directory_id,
            )
            raise
        self._settings = defaults
        self.settings_changed.emit(self._settings)

    def reload(self) -> None:
        """Re-read settings from disk."""
        loaded = self._storage.load_settings()
        previous_directory = self._storage.notes_dir
        previous_identity = self._settings.notes_directory_id
        try:
            self._storage.configure_notes_directory(
                loaded.notes_directory,
                expected_identity=loaded.notes_directory_id,
            )
            if (
                self._storage.notes_dir != self._storage.default_notes_dir
                and not loaded.notes_directory_id
            ):
                loaded.notes_directory_id = (
                    self._storage.ensure_notes_directory_identity()
                )
                self._storage.save_settings(loaded)
        except (OSError, ValueError):
            self._storage.configure_notes_directory(
                previous_directory,
                expected_identity=previous_identity,
            )
            raise
        self._settings = loaded
        self.settings_changed.emit(self._settings)
