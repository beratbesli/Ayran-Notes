from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from ayrannotes.localization.i18n import I18n


class FloatingToolbar(QWidget):
    """A floating toolbar that appears near the selected text in a QTextEdit."""
    
    def __init__(self, editor: QPlainTextEdit, wrap_selection_callback: Callable, i18n: I18n, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self._editor = editor
        self._wrap_selection = wrap_selection_callback
        self._i18n = i18n
        
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self._build_ui()
        self._connect_signals()
        
    def _build_ui(self):
        self.setObjectName("floatingToolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        actions = [
            ("bold", "B", "**", "**", "bold"),
            ("italic", "I", "_", "_", "italic"),
            ("inline_code", "</>", "`", "`", "code"),
            ("link", "↗", "[", "](https://)", "link text"),
        ]
        
        for key, label, prefix, suffix, placeholder in actions:
            btn = QPushButton(label)
            btn.setToolTip(self._i18n.t(key))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Need to pass default arguments in lambda so they are captured correctly
            btn.clicked.connect(lambda checked, p=prefix, s=suffix, ph=placeholder: self._on_action_clicked(p, s, ph))
            layout.addWidget(btn)
            
    def _connect_signals(self):
        self._editor.selectionChanged.connect(self._on_selection_changed)
        
    def _on_action_clicked(self, prefix: str, suffix: str, placeholder: str):
        self._wrap_selection(prefix, suffix, placeholder)
        self.hide()
        
    def _on_selection_changed(self):
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            self.hide()
            return
            
        rect = self._editor.cursorRect(cursor)
        pos = self._editor.viewport().mapToGlobal(rect.topLeft())
        
        # Calculate position (centered above the cursor)
        # Use a slight delay to get the actual geometry if we're showing it for the first time
        self.adjustSize()
        pos.setY(pos.y() - self.height() - 5)
        pos.setX(pos.x() - (self.width() // 2) + (rect.width() // 2))
        
        self.move(pos)
        self.show()
