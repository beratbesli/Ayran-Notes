"""Beer Notes — Theme engine.

Provides dark and light theme stylesheets with dynamic accent color
injection. All styles use Qt StyleSheet (QSS) syntax.
"""

from __future__ import annotations


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert #RRGGBB to rgba() for QSS."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _darken(hex_color: str, factor: float = 0.7) -> str:
    """Darken a hex color by the given factor."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(hex_color: str, factor: float = 1.3) -> str:
    """Lighten a hex color by the given factor."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = min(255, int(r * factor)), min(255, int(g * factor)), min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_stylesheet(theme: str = "dark", accent: str = "#F59E0B",
                     font_family: str = "Inter", font_size: int = 14) -> str:
    """Generate the full application QSS for the given theme configuration."""
    if theme == "dark":
        return _dark_theme(accent, font_family, font_size)
    return _light_theme(accent, font_family, font_size)


def _dark_theme(accent: str, font: str, size: int) -> str:
    accent_dim = _hex_to_rgba(accent, 0.15)
    accent_mid = _hex_to_rgba(accent, 0.3)
    accent_hover = _lighten(accent, 1.15)
    accent_pressed = _darken(accent, 0.85)

    return f"""
/* ── Global ─────────────────────────────────────────── */
QWidget {{
    background-color: #0f1117;
    color: #e4e4e7;
    font-family: "{font}", "Segoe UI", "Noto Sans", sans-serif;
    font-size: {size}px;
    border: none;
}}

/* ── Main Window ────────────────────────────────────── */
QMainWindow {{
    background-color: #0f1117;
}}

/* ── Menu Bar ───────────────────────────────────────── */
QMenuBar {{
    background-color: #16181f;
    color: #a1a1aa;
    padding: 2px 4px;
    border-bottom: 1px solid #27272a;
}}
QMenuBar::item:selected {{
    background-color: {accent_dim};
    color: {accent};
    border-radius: 4px;
}}
QMenu {{
    background-color: #1c1e26;
    color: #e4e4e7;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {accent_dim};
    color: {accent};
}}
QMenu::separator {{
    height: 1px;
    background: #27272a;
    margin: 4px 8px;
}}

/* ── Sidebar ────────────────────────────────────────── */
#sidebar {{
    background-color: #13151b;
    border-right: 1px solid #1e2028;
}}
#sidebarSearch {{
    background-color: #1c1e26;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e4e4e7;
    font-size: {size - 1}px;
}}
#sidebarSearch:focus {{
    border-color: {accent};
    background-color: #1e2028;
}}

/* ── Note List ──────────────────────────────────────── */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: transparent;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 2px 6px;
    color: #a1a1aa;
}}
QListWidget::item:hover {{
    background-color: #1c1e26;
    color: #e4e4e7;
}}
QListWidget::item:selected {{
    background-color: {accent_dim};
    color: {accent};
    border-left: 3px solid {accent};
}}

/* ── Buttons ────────────────────────────────────────── */
QPushButton {{
    background-color: #1c1e26;
    color: #e4e4e7;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: #27272a;
    border-color: #3f3f46;
}}
QPushButton:pressed {{
    background-color: #3f3f46;
}}
QPushButton#accentBtn {{
    background-color: {accent};
    color: #0f1117;
    border: none;
    font-weight: 600;
}}
QPushButton#accentBtn:hover {{
    background-color: {accent_hover};
}}
QPushButton#accentBtn:pressed {{
    background-color: {accent_pressed};
}}

/* ── Editor ─────────────────────────────────────────── */
#titleEdit {{
    background-color: transparent;
    border: none;
    color: #fafafa;
    font-size: {size + 8}px;
    font-weight: 700;
    padding: 12px 0px;
}}
#contentEdit {{
    background-color: transparent;
    border: none;
    color: #d4d4d8;
    font-size: {size}px;
    line-height: 1.7;
    padding: 8px 0px;
    selection-background-color: {accent_mid};
    selection-color: #ffffff;
}}

/* ── Preview ────────────────────────────────────────── */
#previewPanel {{
    background-color: #13151b;
    border-left: 1px solid #1e2028;
    padding: 16px;
}}

/* ── Splitter ───────────────────────────────────────── */
QSplitter::handle {{
    background-color: #1e2028;
    width: 1px;
}}
QSplitter::handle:hover {{
    background-color: {accent};
}}

/* ── Scrollbar ──────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: #27272a;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #3f3f46;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background-color: #27272a;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #3f3f46;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status Bar ─────────────────────────────────────── */
QStatusBar {{
    background-color: #16181f;
    color: #71717a;
    border-top: 1px solid #1e2028;
    font-size: {size - 2}px;
    padding: 2px 8px;
}}

/* ── Labels ─────────────────────────────────────────── */
#sectionLabel {{
    color: #71717a;
    font-size: {size - 2}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 12px 4px 12px;
}}
#folderLabel {{
    color: #a1a1aa;
    padding: 6px 12px;
    border-radius: 6px;
}}
#folderLabel:hover {{
    background-color: #1c1e26;
    color: #e4e4e7;
}}

/* ── Dialog ─────────────────────────────────────────── */
QDialog {{
    background-color: #16181f;
    border: 1px solid #27272a;
    border-radius: 12px;
}}
QTabWidget::pane {{
    background-color: #16181f;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 8px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: #71717a;
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover {{
    color: #e4e4e7;
}}

/* ── ComboBox ───────────────────────────────────────── */
QComboBox {{
    background-color: #1c1e26;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e4e4e7;
    min-width: 120px;
}}
QComboBox:hover {{
    border-color: #3f3f46;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: #1c1e26;
    border: 1px solid #27272a;
    border-radius: 8px;
    color: #e4e4e7;
    selection-background-color: {accent_dim};
    selection-color: {accent};
    padding: 4px;
}}

/* ── SpinBox ────────────────────────────────────────── */
QSpinBox {{
    background-color: #1c1e26;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e4e4e7;
}}
QSpinBox:hover {{
    border-color: #3f3f46;
}}

/* ── ToolTip ────────────────────────────────────────── */
QToolTip {{
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {size - 2}px;
}}

/* ── CheckBox ───────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: #e4e4e7;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #3f3f46;
    background-color: #1c1e26;
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
"""


def _light_theme(accent: str, font: str, size: int) -> str:
    accent_dim = _hex_to_rgba(accent, 0.1)
    accent_mid = _hex_to_rgba(accent, 0.2)
    accent_hover = _darken(accent, 0.85)
    accent_pressed = _darken(accent, 0.7)

    return f"""
/* ── Global ─────────────────────────────────────────── */
QWidget {{
    background-color: #fafafa;
    color: #18181b;
    font-family: "{font}", "Segoe UI", "Noto Sans", sans-serif;
    font-size: {size}px;
    border: none;
}}

QMainWindow {{
    background-color: #fafafa;
}}

/* ── Menu Bar ───────────────────────────────────────── */
QMenuBar {{
    background-color: #ffffff;
    color: #52525b;
    padding: 2px 4px;
    border-bottom: 1px solid #e4e4e7;
}}
QMenuBar::item:selected {{
    background-color: {accent_dim};
    color: {accent};
    border-radius: 4px;
}}
QMenu {{
    background-color: #ffffff;
    color: #18181b;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {accent_dim};
    color: {accent};
}}
QMenu::separator {{
    height: 1px;
    background: #e4e4e7;
    margin: 4px 8px;
}}

/* ── Sidebar ────────────────────────────────────────── */
#sidebar {{
    background-color: #f4f4f5;
    border-right: 1px solid #e4e4e7;
}}
#sidebarSearch {{
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 8px 12px;
    color: #18181b;
    font-size: {size - 1}px;
}}
#sidebarSearch:focus {{
    border-color: {accent};
    background-color: #ffffff;
}}

/* ── Note List ──────────────────────────────────────── */
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: transparent;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 2px 6px;
    color: #52525b;
}}
QListWidget::item:hover {{
    background-color: #e4e4e7;
    color: #18181b;
}}
QListWidget::item:selected {{
    background-color: {accent_dim};
    color: {accent};
    border-left: 3px solid {accent};
}}

/* ── Buttons ────────────────────────────────────────── */
QPushButton {{
    background-color: #ffffff;
    color: #18181b;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: #f4f4f5;
    border-color: #a1a1aa;
}}
QPushButton:pressed {{
    background-color: #e4e4e7;
}}
QPushButton#accentBtn {{
    background-color: {accent};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#accentBtn:hover {{
    background-color: {accent_hover};
}}
QPushButton#accentBtn:pressed {{
    background-color: {accent_pressed};
}}

/* ── Editor ─────────────────────────────────────────── */
#titleEdit {{
    background-color: transparent;
    border: none;
    color: #09090b;
    font-size: {size + 8}px;
    font-weight: 700;
    padding: 12px 0px;
}}
#contentEdit {{
    background-color: transparent;
    border: none;
    color: #27272a;
    font-size: {size}px;
    line-height: 1.7;
    padding: 8px 0px;
    selection-background-color: {accent_mid};
    selection-color: #18181b;
}}

/* ── Preview ────────────────────────────────────────── */
#previewPanel {{
    background-color: #f4f4f5;
    border-left: 1px solid #e4e4e7;
    padding: 16px;
}}

/* ── Splitter ───────────────────────────────────────── */
QSplitter::handle {{
    background-color: #e4e4e7;
    width: 1px;
}}
QSplitter::handle:hover {{
    background-color: {accent};
}}

/* ── Scrollbar ──────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: #d4d4d8;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #a1a1aa;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background-color: #d4d4d8;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: #a1a1aa;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status Bar ─────────────────────────────────────── */
QStatusBar {{
    background-color: #ffffff;
    color: #71717a;
    border-top: 1px solid #e4e4e7;
    font-size: {size - 2}px;
    padding: 2px 8px;
}}

#sectionLabel {{
    color: #71717a;
    font-size: {size - 2}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 12px 4px 12px;
}}
#folderLabel {{
    color: #52525b;
    padding: 6px 12px;
    border-radius: 6px;
}}
#folderLabel:hover {{
    background-color: #e4e4e7;
    color: #18181b;
}}

/* ── Dialog ─────────────────────────────────────────── */
QDialog {{
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 12px;
}}
QTabWidget::pane {{
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 8px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: #71717a;
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}
QTabBar::tab:hover {{
    color: #18181b;
}}

/* ── ComboBox ───────────────────────────────────────── */
QComboBox {{
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 6px 12px;
    color: #18181b;
    min-width: 120px;
}}
QComboBox:hover {{
    border-color: #a1a1aa;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    color: #18181b;
    selection-background-color: {accent_dim};
    selection-color: {accent};
    padding: 4px;
}}

/* ── SpinBox ────────────────────────────────────────── */
QSpinBox {{
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 6px 12px;
    color: #18181b;
}}
QSpinBox:hover {{
    border-color: #a1a1aa;
}}

/* ── ToolTip ────────────────────────────────────────── */
QToolTip {{
    background-color: #18181b;
    color: #fafafa;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {size - 2}px;
}}

/* ── CheckBox ───────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: #18181b;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #d4d4d8;
    background-color: #ffffff;
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}
"""
