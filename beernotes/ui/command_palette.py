from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class CommandPalette(QDialog):
    """A searchable command palette for quick actions."""

    def __init__(
        self,
        commands: list[tuple[str, Callable[[], None]]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setModal(True)
        self.setObjectName("commandPalette")
        self.resize(500, 350)

        self._all_commands = commands or []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("commandPaletteSearch")
        self.search_input.textChanged.connect(self._filter_commands)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("commandPaletteList")
        self.list_widget.itemClicked.connect(self._execute_selected)
        self._list = self.list_widget
        layout.addWidget(self.list_widget)

        self._populate_list(self._all_commands)

    def set_commands(self, commands: list[tuple[str, Callable[[], None]]]) -> None:
        self._all_commands = commands
        self._populate_list(commands)

    def set_theme(self, theme: str) -> None:
        pass


    def set_placeholder(self, text: str) -> None:
        """Set the placeholder text for the search input."""
        self.search_input.setPlaceholderText(text)

    def _filter_commands(self, query: str) -> None:
        query = query.lower().strip()
        if not query:
            filtered = self._all_commands
        else:
            filtered = [
                cmd for cmd in self._all_commands
                if query in cmd[0].lower()
            ]
        self._populate_list(filtered)

    def _populate_list(self, commands: list[tuple[str, Callable[[], None]]]) -> None:
        self.list_widget.clear()
        for name, callback in commands:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, callback)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _execute_selected(self, item: QListWidgetItem = None) -> None:
        if item is None:
            item = self.list_widget.currentItem()
        if item is not None:
            callback = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
            if callback:
                callback()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_selected()
        elif event.key() == Qt.Key.Key_Up:
            current = self.list_widget.currentRow()
            if current > 0:
                self.list_widget.setCurrentRow(current - 1)
        elif event.key() == Qt.Key.Key_Down:
            current = self.list_widget.currentRow()
            if current < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(current + 1)
        else:
            super().keyPressEvent(event)
