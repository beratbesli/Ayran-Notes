"""Beer Notes — Tab manager for multi-note editing.

Manages a QTabWidget where each tab represents an open note.
Provides per-tab autosave, dirty-state indicators, duplicate
prevention, and safe close semantics.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QTabWidget, QWidget


class _TabData:
    """Per-tab bookkeeping."""

    __slots__ = ("note_id", "title", "content", "is_dirty", "timer")

    def __init__(self, note_id: str, title: str, content: str) -> None:
        self.note_id = note_id
        self.title = title
        self.content = content
        self.is_dirty = False
        self.timer: Optional[QTimer] = None


class TabManager(QWidget):
    """Manages multiple open notes as tabs.

    Signals
    -------
    tab_switched(str)
        Emitted with *note_id* when the active tab changes.
    tab_close_requested(str)
        Emitted with *note_id* when a tab's close button is clicked.
    autosave_requested(str, str)
        Emitted with *(note_id, content)* when the per-tab autosave
        timer fires.
    """

    tab_switched = pyqtSignal(str)
    tab_close_requested = pyqtSignal(str)
    autosave_requested = pyqtSignal(str, str)

    AUTOSAVE_MS = 2000

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)

        # note_id -> _TabData
        self._data: Dict[str, _TabData] = {}
        # tab_index -> note_id (maintained via signals)
        self._index_to_id: Dict[int, str] = {}

        self._tabs.currentChanged.connect(self._on_current_changed)
        self._tabs.tabCloseRequested.connect(self._on_close_requested)

        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tab_widget(self) -> QTabWidget:
        return self._tabs

    def open_note(self, note_id: str, title: str, content: str) -> int:
        """Open *note_id* in a tab.  Returns the tab index.

        If the note is already open, the existing tab is activated
        instead of creating a duplicate.
        """
        if note_id in self._data:
            for idx in range(self._tabs.count()):
                if self._index_to_id.get(idx) == note_id:
                    self._tabs.setCurrentIndex(idx)
                    return idx
        # Create new tab
        page = QWidget()
        idx = self._tabs.addTab(page, title)
        td = _TabData(note_id, title, content)
        td.timer = QTimer(self)
        td.timer.setSingleShot(True)
        td.timer.setInterval(self.AUTOSAVE_MS)
        td.timer.timeout.connect(lambda nid=note_id: self._fire_autosave(nid))
        self._data[note_id] = td
        self._rebuild_index()
        self._tabs.setCurrentIndex(idx)
        return idx

    def close_tab(self, index: int) -> bool:
        """Close the tab at *index*.  Returns True if closed."""
        note_id = self._index_to_id.get(index)
        if note_id is None:
            return False
        td = self._data.pop(note_id, None)
        if td and td.timer:
            td.timer.stop()
        self._tabs.removeTab(index)
        self._rebuild_index()
        return True

    def mark_dirty(self, note_id: str) -> None:
        """Mark a tab as having unsaved changes."""
        td = self._data.get(note_id)
        if td is None:
            return
        td.is_dirty = True
        self._update_tab_label(note_id)
        if td.timer:
            td.timer.start()

    def mark_clean(self, note_id: str) -> None:
        """Mark a tab as saved."""
        td = self._data.get(note_id)
        if td is None:
            return
        td.is_dirty = False
        if td.timer:
            td.timer.stop()
        self._update_tab_label(note_id)

    def update_content(self, note_id: str, content: str) -> None:
        """Update cached content for a tab."""
        td = self._data.get(note_id)
        if td:
            td.content = content

    def get_content(self, note_id: str) -> str:
        """Return cached content for *note_id*."""
        td = self._data.get(note_id)
        return td.content if td else ""

    def get_dirty_tabs(self) -> List[str]:
        """Return list of note IDs with unsaved changes."""
        return [nid for nid, td in self._data.items() if td.is_dirty]

    def save_all(self, save_callback: Callable[[str, str], bool]) -> bool:
        """Save all dirty tabs.  Returns True if all saves succeeded."""
        all_ok = True
        for nid, td in list(self._data.items()):
            if td.is_dirty:
                if save_callback(nid, td.content):
                    self.mark_clean(nid)
                else:
                    all_ok = False
        return all_ok

    def close_all(self) -> None:
        """Close every tab."""
        for td in self._data.values():
            if td.timer:
                td.timer.stop()
        self._data.clear()
        self._index_to_id.clear()
        self._tabs.clear()

    def handle_external_change(self, note_id: str, new_content: str) -> bool:
        """Handle external file modification.

        If the tab is clean, its content is silently updated.
        If the tab is dirty, returns False (caller should warn).
        """
        td = self._data.get(note_id)
        if td is None:
            return True
        if td.is_dirty:
            return False  # caller should show a conflict warning
        td.content = new_content
        return True

    def current_note_id(self) -> Optional[str]:
        """Return the note_id of the active tab, or None."""
        idx = self._tabs.currentIndex()
        return self._index_to_id.get(idx)

    def is_open(self, note_id: str) -> bool:
        """Return whether *note_id* has an open tab."""
        return note_id in self._data

    def tab_count(self) -> int:
        return self._tabs.count()

    def set_theme(self, theme: str) -> None:
        """Placeholder for theme updates — styling is handled externally."""
        pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        self._index_to_id.clear()
        # Walk existing data to find which index holds each note.
        for idx in range(self._tabs.count()):
            page = self._tabs.widget(idx)
            for nid, td in self._data.items():
                label = self._tabs.tabText(idx).lstrip("● ").strip()
                if td.title == label or f"● {td.title}" == self._tabs.tabText(idx):
                    if nid not in self._index_to_id.values():
                        self._index_to_id[idx] = nid
                        break
        # Fallback: assign in insertion order
        if len(self._index_to_id) != self._tabs.count():
            self._index_to_id.clear()
            ids = list(self._data.keys())
            for idx in range(min(self._tabs.count(), len(ids))):
                self._index_to_id[idx] = ids[idx]

    def _update_tab_label(self, note_id: str) -> None:
        td = self._data.get(note_id)
        if td is None:
            return
        for idx, nid in self._index_to_id.items():
            if nid == note_id:
                label = f"● {td.title}" if td.is_dirty else td.title
                self._tabs.setTabText(idx, label)
                break

    def _on_current_changed(self, index: int) -> None:
        nid = self._index_to_id.get(index)
        if nid:
            self.tab_switched.emit(nid)

    def _on_close_requested(self, index: int) -> None:
        nid = self._index_to_id.get(index)
        if nid:
            self.tab_close_requested.emit(nid)

    def _fire_autosave(self, note_id: str) -> None:
        td = self._data.get(note_id)
        if td and td.is_dirty:
            self.autosave_requested.emit(note_id, td.content)
