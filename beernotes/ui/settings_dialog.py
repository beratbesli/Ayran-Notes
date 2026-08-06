"""Beer Notes — Settings dialog.

A tabbed preferences dialog for theme, font, accent color,
and language selection. All changes are applied live.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from beernotes.controllers.settings_controller import SettingsController
    from beernotes.localization.i18n import I18n


class SettingsDialog(QDialog):
    """Application settings / preferences dialog."""

    def __init__(
        self,
        settings_ctrl: SettingsController,
        i18n: I18n,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = settings_ctrl
        self._i18n = i18n
        self._setup_ui()
        self._connect_signals()
        self._retranslate()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setMinimumSize(480, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        # ── Appearance tab ──────────────────────────────────────────
        appearance = QWidget()
        form_a = QFormLayout(appearance)
        form_a.setContentsMargins(16, 16, 16, 16)
        form_a.setSpacing(14)

        # Theme
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", "dark")
        self._theme_combo.addItem("Light", "light")
        idx = self._theme_combo.findData(self._ctrl.settings.theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_label = QLabel()
        form_a.addRow(self._theme_label, self._theme_combo)

        # Accent color
        self._accent_btn = QPushButton()
        self._accent_btn.setFixedSize(80, 32)
        self._update_accent_preview()
        self._accent_label = QLabel()
        form_a.addRow(self._accent_label, self._accent_btn)

        # Font family
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        for fam in ("Inter", "Roboto", "Noto Sans", "Fira Code", "JetBrains Mono",
                     "Ubuntu", "Cantarell", "DejaVu Sans", "Liberation Sans"):
            self._font_combo.addItem(fam)
        self._font_combo.setCurrentText(self._ctrl.settings.font_family)
        self._font_label = QLabel()
        form_a.addRow(self._font_label, self._font_combo)

        # Font size
        self._size_spin = QSpinBox()
        self._size_spin.setRange(8, 32)
        self._size_spin.setValue(self._ctrl.settings.font_size)
        self._size_spin.setSuffix(" px")
        self._size_label = QLabel()
        form_a.addRow(self._size_label, self._size_spin)

        self._tabs.addTab(appearance, "")

        # ── General tab ─────────────────────────────────────────────
        general = QWidget()
        form_g = QFormLayout(general)
        form_g.setContentsMargins(16, 16, 16, 16)
        form_g.setSpacing(14)

        # Language
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("English", "en")
        self._lang_combo.addItem("Türkçe", "tr")
        idx = self._lang_combo.findData(self._ctrl.settings.language)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)
        self._lang_label = QLabel()
        form_g.addRow(self._lang_label, self._lang_combo)

        self._tabs.addTab(general, "")

        # ── Bottom buttons ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._reset_btn = QPushButton()
        btn_row.addWidget(self._reset_btn)

        self._close_btn = QPushButton()
        self._close_btn.setObjectName("accentBtn")
        btn_row.addWidget(self._close_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._theme_combo.currentIndexChanged.connect(self._on_theme)
        self._accent_btn.clicked.connect(self._on_accent_pick)
        self._font_combo.currentTextChanged.connect(self._on_font)
        self._size_spin.valueChanged.connect(self._on_font_size)
        self._lang_combo.currentIndexChanged.connect(self._on_language)
        self._reset_btn.clicked.connect(self._on_reset)
        self._close_btn.clicked.connect(self.accept)

        # Live i18n refresh
        self._i18n.language_changed.connect(lambda _: self._retranslate())

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_theme(self, _index: int) -> None:
        self._ctrl.set_theme(self._theme_combo.currentData())

    def _on_accent_pick(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._ctrl.settings.accent_color),
            self,
            self._i18n.t("accent_color"),
        )
        if color.isValid():
            self._ctrl.set_accent_color(color.name())
            self._update_accent_preview()

    def _on_font(self, family: str) -> None:
        if family:
            self._ctrl.set_font_family(family)

    def _on_font_size(self, size: int) -> None:
        self._ctrl.set_font_size(size)

    def _on_language(self, _index: int) -> None:
        lang = self._lang_combo.currentData()
        self._ctrl.set_language(lang)
        self._i18n.set_language(lang)

    def _on_reset(self) -> None:
        self._ctrl.reset_defaults()
        # Sync UI widgets with new defaults
        s = self._ctrl.settings
        self._theme_combo.setCurrentIndex(self._theme_combo.findData(s.theme))
        self._font_combo.setCurrentText(s.font_family)
        self._size_spin.setValue(s.font_size)
        self._lang_combo.setCurrentIndex(self._lang_combo.findData(s.language))
        self._update_accent_preview()
        self._i18n.set_language(s.language)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_accent_preview(self) -> None:
        c = self._ctrl.settings.accent_color
        self._accent_btn.setStyleSheet(
            f"background-color: {c}; border: none; border-radius: 6px;"
        )
        self._accent_btn.setText(c)

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("preferences"))
        self._tabs.setTabText(0, t("appearance"))
        self._tabs.setTabText(1, t("general_settings"))
        self._theme_label.setText(t("theme"))
        self._accent_label.setText(t("accent_color"))
        self._font_label.setText(t("font_family"))
        self._size_label.setText(t("font_size"))
        self._lang_label.setText(t("language"))
        self._reset_btn.setText(t("reset_defaults"))
        self._close_btn.setText(t("close"))
        # Update theme combo display names
        self._theme_combo.setItemText(0, t("dark_mode"))
        self._theme_combo.setItemText(1, t("light_mode"))
