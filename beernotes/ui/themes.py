"""Palette-based light and dark styles for Beer Notes."""

from __future__ import annotations

import re


_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _valid_color(value: str) -> str:
    """Return a safe #RRGGBB accent color."""
    return value if _HEX_COLOR.fullmatch(value) else "#F59E0B"


def _rgba(hex_color: str, alpha: float) -> str:
    color = _valid_color(hex_color).lstrip("#")
    red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _shade(hex_color: str, factor: float) -> str:
    color = _valid_color(hex_color).lstrip("#")
    channels = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    adjusted = (max(0, min(255, round(channel * factor))) for channel in channels)
    return "#" + "".join(f"{channel:02x}" for channel in adjusted)


def build_stylesheet(
    theme: str = "dark",
    accent: str = "#F59E0B",
    font_family: str = "Inter",
    font_size: int = 14,
) -> str:
    """Build the complete application stylesheet from a compact color palette."""
    accent = _valid_color(accent)
    size = max(8, min(int(font_size), 32))

    if theme == "light":
        palette = {
            "window": "#F5F5F7",
            "surface": "#FFFFFF",
            "sidebar": "#F2F2F7",
            "raised": "#FFFFFF",
            "hover": "#E9E9ED",
            "pressed": "#DEDEE3",
            "text": "#1D1D1F",
            "secondary": "#6E6E73",
            "tertiary": "#8E8E93",
            "border": "#D8D8DC",
            "separator": "#D1D1D6",
            "scroll": "#B8B8BD",
            "preview": "#FAFAFC",
            "accent_text": "#FFFFFF",
            "accent_hover": _shade(accent, 0.90),
            "accent_pressed": _shade(accent, 0.80),
            "danger": "#FF3B30",
        }
    else:
        palette = {
            "window": "#1C1C1E",
            "surface": "#202022",
            "sidebar": "#171719",
            "raised": "#2A2A2D",
            "hover": "#323235",
            "pressed": "#3A3A3D",
            "text": "#F5F5F7",
            "secondary": "#AEAEB2",
            "tertiary": "#8E8E93",
            "border": "#3A3A3C",
            "separator": "#38383A",
            "scroll": "#555559",
            "preview": "#1F1F21",
            "accent_text": "#151515",
            "accent_hover": _shade(accent, 1.10),
            "accent_pressed": _shade(accent, 0.88),
            "danger": "#FF453A",
        }

    p = palette
    accent_soft = _rgba(accent, 0.14 if theme == "dark" else 0.11)
    accent_selection = _rgba(accent, 0.30 if theme == "dark" else 0.22)

    return f"""
/* Base */
QWidget {{
    background-color: {p["window"]};
    color: {p["text"]};
    font-family: "{font_family}", "SF Pro Text", "Segoe UI", "Noto Sans", sans-serif;
    font-size: {size}px;
    border: none;
}}
QMainWindow {{
    background-color: {p["window"]};
}}
QLabel {{
    background-color: transparent;
}}

/* Menu bar and menus */
QMenuBar {{
    background-color: {p["surface"]};
    color: {p["secondary"]};
    border-bottom: 1px solid {p["border"]};
    padding: 3px 8px;
}}
QMenuBar::item {{
    background: transparent;
    border-radius: 6px;
    padding: 5px 9px;
}}
QMenuBar::item:selected {{
    background-color: {p["hover"]};
    color: {p["text"]};
}}
QMenu {{
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{
    border-radius: 6px;
    padding: 7px 28px 7px 12px;
}}
QMenu::item:selected {{
    background-color: {accent};
    color: {p["accent_text"]};
}}
QMenu::separator {{
    height: 1px;
    background-color: {p["separator"]};
    margin: 5px 8px;
}}

/* Sidebar */
#sidebar {{
    background-color: {p["sidebar"]};
    border-right: 1px solid {p["border"]};
}}
#sidebarSearch {{
    min-height: 20px;
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 9px;
    padding: 7px 10px;
    font-size: {max(8, size - 1)}px;
    selection-background-color: {accent_selection};
}}
#sidebarSearch:hover {{
    border-color: {p["tertiary"]};
}}
#sidebarSearch:focus {{
    border: 1px solid {accent};
}}
#sectionLabel {{
    color: {p["tertiary"]};
    font-size: {max(8, size - 2)}px;
    font-weight: 600;
    padding: 7px 8px 3px 8px;
}}

/* Resizable folders / notes divider */
QSplitter#sidebarSectionSplitter {{
    background-color: transparent;
}}
QSplitter#sidebarSectionSplitter::handle:vertical {{
    height: 9px;
    background-color: transparent;
    border-top: 1px solid {p["separator"]};
    margin: 4px 8px 0 8px;
}}
QSplitter#sidebarSectionSplitter::handle:vertical:hover {{
    border-top: 2px solid {accent};
}}

/* Lists */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    color: {p["secondary"]};
    background-color: transparent;
    border-radius: 8px;
    padding: 8px 10px;
    margin: 1px 2px;
}}
QListWidget::item:hover {{
    color: {p["text"]};
    background-color: {p["hover"]};
}}
QListWidget::item:selected {{
    color: {accent};
    background-color: {accent_soft};
}}
QListWidget::item:disabled {{
    color: {p["tertiary"]};
}}

/* Simple mode */
#simpleView {{
    background-color: {p["window"]};
}}
#simpleSearch {{
    min-height: 24px;
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 12px;
    padding: 8px 14px;
    font-size: {size}px;
    selection-background-color: {accent_selection};
}}
#simpleSearch:focus {{
    border-color: {accent};
}}
QPushButton#simpleAddButton {{
    min-width: 42px;
    min-height: 42px;
    max-width: 42px;
    max-height: 42px;
    background-color: {accent};
    color: {p["accent_text"]};
    border: none;
    border-radius: 12px;
    padding: 0;
    font-size: {size + 8}px;
    font-weight: 400;
}}
QPushButton#simpleAddButton:hover {{
    background-color: {p["accent_hover"]};
}}
#simpleCards {{
    background-color: transparent;
    border: none;
    outline: none;
}}
#simpleCards::item {{
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 12px;
    padding: 14px;
    margin: 4px;
}}
#simpleCards::item:hover {{
    background-color: {p["hover"]};
    border-color: {p["tertiary"]};
}}
#simpleCards::item:selected {{
    background-color: {accent_soft};
    color: {p["text"]};
    border: 1px solid {accent};
}}
QPushButton#simpleBackButton {{
    min-width: 38px;
    min-height: 34px;
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-radius: 8px;
    padding: 0;
    font-size: {size + 6}px;
}}
QPushButton#simpleBackButton:hover {{
    background-color: {p["hover"]};
    color: {p["text"]};
}}
QPushButton#simpleDeleteButton {{
    min-width: 38px;
    min-height: 34px;
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-radius: 8px;
    padding: 0;
    font-size: {size + 1}px;
}}
QPushButton#simpleDeleteButton:hover {{
    background-color: {_rgba(p["danger"], 0.12)};
    color: {p["danger"]};
}}
#simpleTitle {{
    background-color: transparent;
    color: {p["text"]};
    border: none;
    border-bottom: 1px solid {p["separator"]};
    border-radius: 0;
    padding: 14px 2px 12px 2px;
    font-size: {size + 8}px;
    font-weight: 600;
    selection-background-color: {accent_selection};
}}
#simpleContent {{
    background-color: transparent;
    color: {p["text"]};
    border: none;
    padding: 18px 2px;
    font-size: {size + 1}px;
    selection-background-color: {accent_selection};
}}

/* Buttons */
QPushButton {{
    min-height: 18px;
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 9px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: {p["hover"]};
    border-color: {p["tertiary"]};
}}
QPushButton:pressed {{
    background-color: {p["pressed"]};
}}
QPushButton#accentBtn {{
    background-color: {accent};
    color: {p["accent_text"]};
    border: 1px solid {accent};
    font-weight: 600;
}}
QPushButton#accentBtn:hover {{
    background-color: {p["accent_hover"]};
    border-color: {p["accent_hover"]};
}}
QPushButton#accentBtn:pressed {{
    background-color: {p["accent_pressed"]};
    border-color: {p["accent_pressed"]};
}}

/* Editor and preview */
#titleEdit {{
    background-color: transparent;
    color: {p["text"]};
    border: none;
    border-bottom: 1px solid {p["separator"]};
    border-radius: 0;
    padding: 13px 2px 11px 2px;
    font-size: {size + 7}px;
    font-weight: 600;
    selection-background-color: {accent_selection};
}}
#contentEdit {{
    background-color: transparent;
    color: {p["text"]};
    border: none;
    padding: 14px 2px;
    font-size: {size}px;
    selection-background-color: {accent_selection};
}}
#tagEdit {{
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-bottom: 1px solid {p["separator"]};
    border-radius: 0;
    padding: 7px 2px;
    font-size: {max(8, size - 1)}px;
    selection-background-color: {accent_selection};
}}
QToolBar#editorToolbar {{
    background-color: transparent;
    border: none;
    border-bottom: 1px solid {p["separator"]};
    spacing: 3px;
    padding: 5px 0;
}}
QToolBar#editorToolbar QToolButton {{
    min-width: 26px;
    min-height: 24px;
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-radius: 6px;
    padding: 3px 7px;
}}
QToolBar#editorToolbar QToolButton:hover {{
    background-color: {p["hover"]};
    color: {p["text"]};
}}
QToolBar#editorToolbar QToolButton:pressed {{
    background-color: {accent_soft};
    color: {accent};
}}
#previewPanel {{
    background-color: {p["preview"]};
    color: {p["text"]};
    border: none;
    border-left: 1px solid {p["border"]};
    padding: 20px;
}}
QSplitter::handle:horizontal {{
    width: 5px;
    background-color: {p["window"]};
    border-left: 1px solid {p["separator"]};
}}
QSplitter::handle:horizontal:hover {{
    border-left: 2px solid {accent};
}}

/* Inputs */
QComboBox, QSpinBox {{
    min-height: 20px;
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {accent_selection};
}}
QComboBox:hover, QSpinBox:hover {{
    border-color: {p["tertiary"]};
}}
QComboBox:focus, QSpinBox:focus {{
    border-color: {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {accent};
    selection-color: {p["accent_text"]};
}}

/* Preferences */
QDialog {{
    background-color: {p["surface"]};
}}
QTabWidget::pane {{
    background-color: transparent;
    border: none;
    border-top: 1px solid {p["separator"]};
    padding-top: 10px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {p["secondary"]};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 14px;
}}
QTabBar::tab:hover {{
    color: {p["text"]};
}}
QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}
QCheckBox {{
    color: {p["text"]};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    background-color: {p["raised"]};
    border: 1px solid {p["border"]};
    border-radius: 5px;
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

/* Status, scrollbars and tooltips */
QStatusBar {{
    background-color: {p["surface"]};
    color: {p["tertiary"]};
    border-top: 1px solid {p["border"]};
    font-size: {max(8, size - 2)}px;
    padding: 2px 8px;
}}
QStatusBar QLabel {{
    color: {p["tertiary"]};
}}
QScrollBar:vertical {{
    width: 8px;
    margin: 2px;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    min-height: 28px;
    background-color: {p["scroll"]};
    border-radius: 4px;
}}
QScrollBar:horizontal {{
    height: 8px;
    margin: 2px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    min-width: 28px;
    background-color: {p["scroll"]};
    border-radius: 4px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QToolTip {{
    background-color: {p["raised"]};
    color: {p["text"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: {max(8, size - 2)}px;
}}
"""
