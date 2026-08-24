"""Ayran Notes — LLM Dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ayrannotes.localization.i18n import I18n


class LLMResultDialog(QDialog):
    """Dialog showing diff/preview of LLM output before applying."""

    def __init__(
        self,
        original_text: str,
        new_text: str,
        i18n: I18n,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._original_text = original_text
        self.new_text = new_text
        self._i18n = i18n
        self._setup_ui()
        self._retranslate()

    def _setup_ui(self) -> None:
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Original text pane
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._left_label = QLabel()
        self._left_text = QTextEdit()
        self._left_text.setReadOnly(True)
        self._left_text.setPlainText(self._original_text)
        left_layout.addWidget(self._left_label)
        left_layout.addWidget(self._left_text)
        
        # New text pane
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_label = QLabel()
        self._right_text = QTextEdit()
        self._right_text.setPlainText(self.new_text)
        right_layout.addWidget(self._right_label)
        right_layout.addWidget(self._right_text)
        
        splitter.addWidget(left_pane)
        splitter.addWidget(right_pane)
        
        root.addWidget(splitter, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._reject_btn = QPushButton()
        self._reject_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._reject_btn)

        self._accept_btn = QPushButton()
        self._accept_btn.setObjectName("accentBtn")
        self._accept_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._accept_btn)

        root.addLayout(btn_row)

    def accept(self) -> None:
        self.new_text = self._right_text.toPlainText()
        super().accept()

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("ai_result_title", "AI Result"))
        self._left_label.setText(t("original_text", "Original"))
        self._right_label.setText(t("ai_text", "AI Output"))
        self._reject_btn.setText(t("cancel"))
        self._accept_btn.setText(t("apply", "Apply"))
