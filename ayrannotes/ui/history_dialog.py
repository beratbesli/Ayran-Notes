"""Small, user-facing dialogs for local note history."""

from __future__ import annotations

import difflib
import html

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ayrannotes.controllers.note_controller import NoteController
from ayrannotes.localization.i18n import I18n
from ayrannotes.storage.models import Note
from ayrannotes.ui.markdown_support import render_markdown_html


def _build_diff_html(
    old: str,
    current: str,
    *,
    old_label: str,
    current_label: str,
    no_changes: str,
    text_color: str,
) -> str:
    rows = []
    for line in difflib.unified_diff(
        old.splitlines(),
        current.splitlines(),
        fromfile=old_label,
        tofile=current_label,
        lineterm="",
    ):
        escaped = html.escape(line)
        if line.startswith("+") and not line.startswith("+++"):
            css = "diff-add"
        elif line.startswith("-") and not line.startswith("---"):
            css = "diff-remove"
        elif line.startswith("@@"):
            css = "diff-header"
        else:
            css = "diff-neutral"
        rows.append(f'<div class="{css}">{escaped or " "}</div>')
    if not rows:
        rows.append(f'<div class="diff-neutral">{html.escape(no_changes)}</div>')
    return """<html><head><style>
    body { font-family: monospace; white-space: pre-wrap; }
    .diff-add { color: #77c98a; background: rgba(60, 160, 80, .16); }
    .diff-remove { color: #ef8585; background: rgba(190, 60, 60, .16); }
    .diff-header { color: #8ba9e8; }
    .diff-neutral { color: """ + text_color + """; }
    </style></head><body>""" + "".join(rows) + "</body></html>"


class _HistoryWorker(QThread):
    loaded = pyqtSignal(object)

    def __init__(self, controller: NoteController, note_id: str) -> None:
        super().__init__()
        self._controller = controller
        self._note_id = note_id

    def run(self) -> None:
        try:
            history = self._controller.get_note_history(self._note_id, limit=20)
        except (OSError, ValueError, TypeError):
            history = []
        self.loaded.emit(history)


class _VersionWorker(QThread):
    loaded = pyqtSignal(object, object, str)

    def __init__(
        self,
        controller: NoteController,
        note_id: str,
        commit_hash: str,
        record: dict,
        current_content: str,
        old_label: str,
        current_label: str,
        no_changes: str,
        text_color: str,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._note_id = note_id
        self._commit_hash = commit_hash
        self._record = record
        self._current_content = current_content
        self._old_label = old_label
        self._current_label = current_label
        self._no_changes = no_changes
        self._text_color = text_color

    def run(self) -> None:
        try:
            note = self._controller.get_note_version(self._note_id, self._commit_hash)
        except (OSError, ValueError, TypeError):
            note = None
        diff_html = ""
        if note is not None:
            diff_html = _build_diff_html(
                note.content,
                self._current_content,
                old_label=self._old_label,
                current_label=self._current_label,
                no_changes=self._no_changes,
                text_color=self._text_color,
            )
        self.loaded.emit(self._record, note, diff_html)


class HistoryDialog(QDialog):
    """Preview and restore versions of one existing note."""

    def __init__(
        self,
        controller: NoteController,
        note: Note,
        i18n: I18n,
        settings_controller,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._current_note = note
        self._i18n = i18n
        self._settings_controller = settings_controller
        self._history: list[dict] = []
        self._selected_record: dict | None = None
        self._selected_version: Note | None = None
        self.restored_note: Note | None = None
        self._history_worker: _HistoryWorker | None = None
        self._version_worker: _VersionWorker | None = None
        self._workers: list[QThread] = []

        self.setObjectName("historyDialog")
        self.setMinimumSize(780, 540)
        self.resize(900, 620)
        self._build_ui()
        self._i18n.language_changed.connect(lambda _: self._retranslate())
        self.finished.connect(lambda _result: self._wait_for_workers())
        self._retranslate()
        self._load_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self._heading = QLabel()
        self._heading.setObjectName("dialogHeading")
        layout.addWidget(self._heading)
        self._status = QLabel()
        self._status.setObjectName("historyStatus")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._history_list = QListWidget()
        self._history_list.setMinimumWidth(270)
        self._history_list.currentItemChanged.connect(self._on_history_selected)
        self._splitter.addWidget(self._history_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._version_heading = QLabel()
        self._version_heading.setObjectName("sectionLabel")
        right_layout.addWidget(self._version_heading)
        self._tabs = QTabWidget()
        self._preview = QTextBrowser()
        self._source = QTextBrowser()
        self._diff = QTextBrowser()
        self._tabs.addTab(self._preview, "")
        self._tabs.addTab(self._diff, "")
        self._tabs.addTab(self._source, "")
        right_layout.addWidget(self._tabs, 1)
        self._splitter.addWidget(right)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        layout.addWidget(self._splitter, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._restore_button = QPushButton()
        self._restore_button.setObjectName("accentBtn")
        self._restore_button.setEnabled(False)
        buttons.addWidget(self._restore_button)
        self._close_button = QPushButton()
        buttons.addWidget(self._close_button)
        layout.addLayout(buttons)
        self._restore_button.clicked.connect(self._restore_selected)
        self._close_button.clicked.connect(self.reject)

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("history_title"))
        self._heading.setText(t("history_for", title=self._current_note.title or t("untitled")))
        self._tabs.setTabText(0, t("preview"))
        self._tabs.setTabText(1, t("changes"))
        self._tabs.setTabText(2, t("source_markdown"))
        self._restore_button.setText(t("restore_version"))
        self._close_button.setText(t("close"))
        if not self._history:
            self._status.setText(
                t("history_unavailable")
                if not self._controller.git_history_available
                else t("history_empty")
            )
        else:
            for row, record in enumerate(self._history):
                item = self._history_list.item(row)
                if item:
                    item.setText(self._history_item_text(record, row == 0))

    def _load_history(self) -> None:
        if not self._controller.git_history_available:
            self._retranslate()
            return
        self._status.setText(self._i18n.t("history_loading"))
        self._history_worker = _HistoryWorker(self._controller, self._current_note.id)
        self._workers.append(self._history_worker)
        self._history_worker.loaded.connect(self._history_loaded)
        self._history_worker.start()

    def _history_loaded(self, history: list[dict]) -> None:
        self._history = history
        self._history_list.clear()
        if not history:
            self._retranslate()
            self._restore_button.setEnabled(False)
            return
        self._status.clear()
        for index, record in enumerate(history):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, record)
            item.setText(self._history_item_text(record, index == 0))
            self._history_list.addItem(item)
            if not record.get("exists", True):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._history_list.setCurrentRow(0)

    def _history_item_text(self, record: dict, current: bool = False) -> str:
        marker = f" · {self._i18n.t('current_version')}" if current else ""
        date = str(record.get("date", ""))
        if " " in date:
            date = date.split(" ", 1)[0]
        message = str(record.get("message", ""))
        return f"{date}{marker}\n{message}"

    def _on_history_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        record = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(record, dict) or not record.get("exists", True):
            self._restore_button.setEnabled(False)
            return
        commit_hash = record.get("hash")
        if not isinstance(commit_hash, str):
            self._restore_button.setEnabled(False)
            return
        self._selected_record = record
        self._selected_version = None
        self._restore_button.setEnabled(False)
        self._version_heading.setText(self._i18n.t("history_loading"))
        self._version_worker = _VersionWorker(
            self._controller,
            self._current_note.id,
            commit_hash,
            record,
            self._current_note.content,
            self._i18n.t("selected_version"),
            self._i18n.t("current_version"),
            self._i18n.t("no_changes"),
            "#d8dee9" if self._settings_controller.resolved_theme == "dark" else "#273142",
        )
        self._workers.append(self._version_worker)
        self._version_worker.loaded.connect(self._version_loaded)
        self._version_worker.start()

    def _version_loaded(self, record: dict, note: Note | None, diff_html: str) -> None:
        if record is not self._selected_record and record != self._selected_record:
            return
        self._selected_version = note
        if note is None:
            self._version_heading.setText(self._i18n.t("version_unavailable"))
            self._restore_button.setEnabled(False)
            self._preview.setHtml("")
            self._source.clear()
            self._diff.setHtml("")
            return
        self._version_heading.setText(
            f"{note.title or self._i18n.t('untitled')} · {record.get('date', '')}"
        )
        settings = self._settings_controller.settings
        self._preview.setHtml(
            render_markdown_html(
                note.content,
                theme=self._settings_controller.resolved_theme,
                accent=self._settings_controller.resolved_accent_color,
                font_family=settings.font_family,
                font_size=settings.font_size,
            )
        )
        self._source.setPlainText(self._serialize_for_display(note))
        self._diff.setHtml(diff_html)
        self._restore_button.setEnabled(not self._is_current_record(record))

    def _is_current_record(self, record: dict) -> bool:
        return bool(self._history and record == self._history[0])

    def _serialize_for_display(self, note: Note) -> str:
        from ayrannotes.storage.markdown_notes import serialize_note

        return serialize_note(note)

    def _build_diff(self, old: str, current: str) -> str:
        return _build_diff_html(
            old,
            current,
            old_label=self._i18n.t("selected_version"),
            current_label=self._i18n.t("current_version"),
            no_changes=self._i18n.t("no_changes"),
            text_color=(
                "#d8dee9"
                if self._settings_controller.resolved_theme == "dark"
                else "#273142"
            ),
        )

    def _restore_selected(self) -> None:
        if not self._selected_record or not self._selected_version:
            return
        reply = QMessageBox.question(
            self,
            self._i18n.t("restore_confirmation_title"),
            self._i18n.t("restore_confirmation"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.restored_note = self._controller.restore_note_version(
                self._current_note.id,
                self._selected_record["hash"],
                expected_revision=self._current_note._storage_revision,
            )
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(
                self,
                self._i18n.t("restore_failed_title"),
                self._i18n.t("restore_failed_detail", error=str(error)),
            )
            return
        self.accept()

    def closeEvent(self, event) -> None:
        self._wait_for_workers()
        event.accept()

    def _wait_for_workers(self) -> None:
        for worker in self._workers:
            if worker.isRunning():
                worker.wait()


class _DeletedNotesWorker(QThread):
    loaded = pyqtSignal(object)

    def __init__(self, controller: NoteController) -> None:
        super().__init__()
        self._controller = controller

    def run(self) -> None:
        try:
            deleted = self._controller.list_deleted_notes(limit=20)
        except (OSError, ValueError, TypeError):
            deleted = []
        self.loaded.emit(deleted)


class DeletedNotesDialog(QDialog):
    """List notes missing from disk and offer safe Git-based recovery."""

    def __init__(
        self,
        controller: NoteController,
        i18n: I18n,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._i18n = i18n
        self._records: list[dict] = []
        self._selected: dict | None = None
        self.restored_note: Note | None = None
        self._worker: _DeletedNotesWorker | None = None
        self.setMinimumSize(640, 430)
        self.resize(740, 500)
        self._build_ui()
        self._i18n.language_changed.connect(lambda _: self._retranslate())
        self.finished.connect(lambda _result: self._wait_for_worker())
        self._retranslate()
        self._load_deleted()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        self._heading = QLabel()
        self._heading.setObjectName("dialogHeading")
        layout.addWidget(self._heading)
        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selected)
        layout.addWidget(self._list, 1)
        self._detail = QLabel()
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._restore = QPushButton()
        self._restore.setObjectName("accentBtn")
        self._restore.setEnabled(False)
        self._close = QPushButton()
        buttons.addWidget(self._restore)
        buttons.addWidget(self._close)
        layout.addLayout(buttons)
        self._restore.clicked.connect(self._restore_selected)
        self._close.clicked.connect(self.reject)

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("deleted_notes"))
        self._heading.setText(t("deleted_notes"))
        self._restore.setText(t("restore_deleted_note"))
        self._close.setText(t("close"))
        if not self._records:
            self._status.setText(
                t("history_unavailable")
                if not self._controller.git_history_available
                else t("deleted_notes_empty")
            )

    def _load_deleted(self) -> None:
        if not self._controller.git_history_available:
            self._retranslate()
            return
        self._status.setText(self._i18n.t("history_loading"))
        self._worker = _DeletedNotesWorker(self._controller)
        self._worker.loaded.connect(self._loaded)
        self._worker.start()

    def _loaded(self, records: list[dict]) -> None:
        self._records = records
        self._list.clear()
        if not records:
            self._retranslate()
            return
        self._status.clear()
        for record in records:
            item = QListWidgetItem(
                f"{record.get('title', record.get('note_id', ''))}\n{record.get('date', '')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, record)
            self._list.addItem(item)
        self._list.setCurrentRow(0)

    def _on_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self._selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        if not self._selected:
            self._detail.clear()
            self._restore.setEnabled(False)
            return
        self._detail.setText(
            self._i18n.t(
                "deleted_note_detail",
                title=self._selected.get("title", self._selected.get("note_id", "")),
                date=self._selected.get("date", ""),
                message=self._selected.get("message", ""),
            )
        )
        self._restore.setEnabled(True)

    def _restore_selected(self) -> None:
        if not self._selected:
            return
        t = self._i18n.t
        reply = QMessageBox.question(
            self,
            t("restore_deleted_confirmation_title"),
            t("restore_deleted_confirmation"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.restored_note = self._controller.restore_deleted_note(
                self._selected["note_id"],
                self._selected["hash"],
            )
        except FileExistsError:
            collision = QMessageBox.question(
                self,
                t("note_id_collision_title"),
                t("note_id_collision"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if collision != QMessageBox.StandardButton.Yes:
                return
            try:
                self.restored_note = self._controller.restore_deleted_note(
                    self._selected["note_id"],
                    self._selected["hash"],
                    new_note_id=Note().id,
                )
            except (OSError, ValueError, TypeError) as error:
                self._show_failure(error)
                return
        except (OSError, ValueError, TypeError) as error:
            self._show_failure(error)
            return
        self.accept()

    def _show_failure(self, error: BaseException) -> None:
        QMessageBox.warning(
            self,
            self._i18n.t("restore_failed_title"),
            self._i18n.t("restore_failed_detail", error=str(error)),
        )

    def closeEvent(self, event) -> None:
        self._wait_for_worker()
        event.accept()

    def _wait_for_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait()
