"""Regression tests for readable application themes."""

import unittest

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit

from ayrannotes.ui.themes import (
    _contrast_ratio,
    _contrast_text,
    _readable_accent,
    build_stylesheet,
)


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_accent_button_text_meets_wcag_contrast(self) -> None:
        for accent in (
            "#00AA00",
            "#CC0000",
            "#FFCC00",
            "#0066CC",
            "#777777",
            "#000000",
            "#FFFFFF",
        ):
            foreground = _contrast_text(accent)
            alternative = "#FFFFFF" if foreground == "#000000" else "#000000"
            self.assertGreaterEqual(
                _contrast_ratio(accent, foreground),
                4.5,
            )
            self.assertGreaterEqual(
                _contrast_ratio(accent, foreground),
                _contrast_ratio(accent, alternative),
            )

    def test_text_accent_is_adjusted_for_theme_surfaces(self) -> None:
        for accent, surfaces in (
            ("#F59E0B", ("#F7F7F9", "#FFFFFF", "#F2F2F4")),
            ("#103060", ("#1C1C1E", "#242426", "#171719")),
        ):
            readable = _readable_accent(accent, *surfaces)
            for surface in surfaces:
                self.assertGreaterEqual(
                    _contrast_ratio(readable, surface),
                    4.5,
                )

    def test_dialog_text_fields_follow_light_and_dark_palettes(self) -> None:
        expected = {
            "dark": ("#2a2a2d", "#f5f5f7"),
            "light": ("#ffffff", "#1d1d1f"),
        }
        for theme, (base, text) in expected.items():
            dialog = QInputDialog()
            dialog.setStyleSheet(build_stylesheet(theme))
            dialog.setInputMode(QInputDialog.InputMode.TextInput)
            dialog.ensurePolished()
            field = dialog.findChild(QLineEdit)
            field.ensurePolished()
            palette = field.palette()
            self.assertEqual(
                palette.color(QPalette.ColorRole.Base).name(),
                base,
            )
            self.assertEqual(
                palette.color(QPalette.ColorRole.Text).name(),
                text,
            )


if __name__ == "__main__":
    unittest.main()
