"""Ayran Notes — System Theme Integration."""

import configparser
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


class SystemThemeMonitor(QObject):
    """Monitors system theme and accent color changes."""

    system_theme_changed = pyqtSignal(str)
    system_accent_changed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app = QApplication.instance()
        self._last_theme = self.get_system_theme()
        self._last_accent = self.get_system_accent_color()

        if self._app:
            self._app.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed)
            self._app.paletteChanged.connect(self._on_palette_changed)

    def _on_color_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        new_theme = self.get_system_theme()
        if new_theme != self._last_theme:
            self._last_theme = new_theme
            self.system_theme_changed.emit(new_theme)

    def _on_palette_changed(self) -> None:
        new_accent = self.get_system_accent_color()
        if new_accent != self._last_accent:
            self._last_accent = new_accent
            self.system_accent_changed.emit(new_accent)

    def get_system_theme(self) -> str:
        """Returns 'dark' or 'light' based on the system color scheme."""
        if self._app:
            scheme = self._app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Light:
                return "light"
        return "dark"

    def get_system_accent_color(self) -> str:
        """Attempts to detect the system accent color."""
        # 1. Try KDE Plasma config first
        kde_globals = Path.home() / ".config" / "kdeglobals"
        if kde_globals.exists():
            try:
                config = configparser.ConfigParser()
                config.read(kde_globals)
                if "Colors:View" in config and "AccentColor" in config["Colors:View"]:
                    rgb_str = config["Colors:View"]["AccentColor"]
                    r, g, b = map(int, rgb_str.split(","))
                    return f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                pass

        # 2. Try Qt palette
        if self._app:
            palette = self._app.palette()
            color = palette.color(QPalette.ColorRole.Highlight)
            if color.isValid():
                return color.name()

        # 3. Fallback
        return "#F59E0B"
