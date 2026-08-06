"""Beer Notes — Main application window."""

from __future__ import annotations

from typing import Optional

import markdown

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from beernotes.controllers.note_controller import NoteController
from beernotes.controllers.settings_controller import SettingsController
from beernotes.localization.i18n import I18n
from beernotes.storage.models import AppSettings, Note
from beernotes.ui.settings_dialog import SettingsDialog
from beernotes.ui.themes import build_stylesheet


class MainWindow(QMainWindow):
    """The primary Beer Notes application window."""

    def __init__(
        self,
        note_ctrl: NoteController,
        settings_ctrl: SettingsController,
        i18n: I18n,
    ) -> None:
        super().__init__()
        self._note_ctrl = note_ctrl
        self._settings_ctrl = settings_ctrl
        self._i18n = i18n
        self._current_note: Optional[Note] = None
        self._current_folder: Optional[str] = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)  # auto-save 600ms after last keystroke
        self._save_timer.timeout.connect(self._auto_save)

        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._apply_settings(self._settings_ctrl.settings)
        self._refresh_note_list()
        self._retranslate()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        s = self._settings_ctrl.settings
        self.setGeometry(s.window_x, s.window_y, s.window_width, s.window_height)
        self.setMinimumSize(700, 450)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(6)

        # Search
        self._search = QLineEdit()
        self._search.setObjectName("sidebarSearch")
        self._search.setClearButtonEnabled(True)
        sidebar_layout.addWidget(self._search)

        # New note button
        self._new_btn = QPushButton()
        self._new_btn.setObjectName("accentBtn")
        sidebar_layout.addWidget(self._new_btn)

        # Resizable sidebar sections (folders | notes)
        self._sidebar_splitter = QSplitter(Qt.Orientation.Vertical)
        self._sidebar_splitter.setObjectName("sidebarSectionSplitter")
        self._sidebar_splitter.setChildrenCollapsible(False)
        self._sidebar_splitter.setHandleWidth(9)

        folder_panel = QWidget()
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(0, 4, 0, 0)
        folder_layout.setSpacing(2)

        # Folder section label
        self._folder_label = QLabel()
        self._folder_label.setObjectName("sectionLabel")
        folder_layout.addWidget(self._folder_label)

        # Folder list
        self._folder_list = QListWidget()
        folder_layout.addWidget(self._folder_list, 1)
        self._sidebar_splitter.addWidget(folder_panel)

        notes_panel = QWidget()
        notes_layout = QVBoxLayout(notes_panel)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(2)

        # Notes section label
        self._notes_label = QLabel()
        self._notes_label.setObjectName("sectionLabel")
        notes_layout.addWidget(self._notes_label)

        # Note list
        self._note_list = QListWidget()
        notes_layout.addWidget(self._note_list, 1)
        self._sidebar_splitter.addWidget(notes_panel)

        self._sidebar_splitter.setStretchFactor(0, 1)
        self._sidebar_splitter.setStretchFactor(1, 3)
        self._initial_sidebar_folder_height = s.sidebar_folder_height
        QTimer.singleShot(0, self._restore_sidebar_splitter)
        sidebar_layout.addWidget(self._sidebar_splitter, 1)

        main_layout.addWidget(self._sidebar)

        # ── Content splitter (editor | preview) ────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Editor pane
        editor_pane = QWidget()
        editor_layout = QVBoxLayout(editor_pane)
        editor_layout.setContentsMargins(20, 12, 20, 12)
        editor_layout.setSpacing(0)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("titleEdit")
        editor_layout.addWidget(self._title_edit)

        self._content_edit = QPlainTextEdit()
        self._content_edit.setObjectName("contentEdit")
        self._content_edit.setTabStopDistance(32.0)
        editor_layout.addWidget(self._content_edit, 1)

        self._splitter.addWidget(editor_pane)

        # Preview pane
        self._preview = QTextBrowser()
        self._preview.setObjectName("previewPanel")
        self._preview.setOpenExternalLinks(True)
        self._splitter.addWidget(self._preview)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)

        main_layout.addWidget(self._splitter, 1)

        # ── Status bar ─────────────────────────────────────────────
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._word_label = QLabel()
        self._char_label = QLabel()
        self._statusbar.addPermanentWidget(self._word_label)
        self._statusbar.addPermanentWidget(self._char_label)

    def _restore_sidebar_splitter(self) -> None:
        """Restore the folder panel in pixels after Qt has completed layout."""
        sizes = self._sidebar_splitter.sizes()
        available = sum(sizes)
        if available <= 0:
            return
        folder_height = min(
            max(80, self._initial_sidebar_folder_height),
            max(80, available - 100),
        )
        self._sidebar_splitter.setSizes([folder_height, available - folder_height])

    def _build_menus(self) -> None:
        mb = self.menuBar()

        # File
        self._file_menu = mb.addMenu("")
        self._act_new = QAction(self)
        self._act_new.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new.triggered.connect(self._on_new_note)
        self._file_menu.addAction(self._act_new)

        self._act_delete = QAction(self)
        self._act_delete.setShortcut(QKeySequence("Ctrl+Delete"))
        self._act_delete.triggered.connect(self._on_delete_note)
        self._file_menu.addAction(self._act_delete)

        self._file_menu.addSeparator()

        self._act_quit = QAction(self)
        self._act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._act_quit.triggered.connect(self.close)
        self._file_menu.addAction(self._act_quit)

        # View
        self._view_menu = mb.addMenu("")
        self._act_sidebar = QAction(self)
        self._act_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        self._act_sidebar.setCheckable(True)
        self._act_sidebar.setChecked(self._settings_ctrl.settings.sidebar_visible)
        self._act_sidebar.triggered.connect(self._on_toggle_sidebar)
        self._view_menu.addAction(self._act_sidebar)

        self._act_preview = QAction(self)
        self._act_preview.setShortcut(QKeySequence("Ctrl+P"))
        self._act_preview.setCheckable(True)
        self._act_preview.setChecked(self._settings_ctrl.settings.preview_visible)
        self._act_preview.triggered.connect(self._on_toggle_preview)
        self._view_menu.addAction(self._act_preview)

        # Settings
        self._settings_menu = mb.addMenu("")
        self._act_prefs = QAction(self)
        self._act_prefs.triggered.connect(self._on_open_settings)
        self._settings_menu.addAction(self._act_prefs)

        # Help
        self._help_menu = mb.addMenu("")
        self._act_about = QAction(self)
        self._act_about.triggered.connect(self._on_about)
        self._help_menu.addAction(self._act_about)

    # ==================================================================
    # Signal wiring
    # ==================================================================

    def _connect_signals(self) -> None:
        # i18n
        self._i18n.language_changed.connect(lambda _: self._retranslate())

        # Settings
        self._settings_ctrl.settings_changed.connect(self._apply_settings)

        # Sidebar
        self._search.textChanged.connect(self._on_search)
        self._new_btn.clicked.connect(self._on_new_note)
        self._folder_list.currentRowChanged.connect(self._on_folder_selected)
        self._note_list.currentRowChanged.connect(self._on_note_selected)
        self._note_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._note_list.customContextMenuRequested.connect(self._on_note_context_menu)

        # Editor → auto-save
        self._title_edit.textChanged.connect(self._schedule_save)
        self._content_edit.textChanged.connect(self._schedule_save)
        self._content_edit.textChanged.connect(self._update_preview)
        self._content_edit.textChanged.connect(self._update_status)

    # ==================================================================
    # Translation
    # ==================================================================

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("app_name"))

        self._search.setPlaceholderText(t("search_placeholder"))
        self._new_btn.setText("+ " + t("new_note"))
        self._folder_label.setText(t("folders").upper())
        self._notes_label.setText(t("all_notes").upper())
        self._title_edit.setPlaceholderText(t("note_title_placeholder"))
        self._content_edit.setPlaceholderText(t("note_content_placeholder"))

        # Menus
        self._file_menu.setTitle(t("file"))
        self._act_new.setText(t("new_note"))
        self._act_delete.setText(t("delete_note"))
        self._act_quit.setText(t("close"))
        self._view_menu.setTitle(t("view"))
        self._act_sidebar.setText(t("toggle_sidebar"))
        self._act_preview.setText(t("toggle_preview"))
        self._settings_menu.setTitle(t("settings"))
        self._act_prefs.setText(t("preferences"))
        self._help_menu.setTitle(t("help"))
        self._act_about.setText(t("about"))

        self._update_status()

    # ==================================================================
    # Settings application
    # ==================================================================

    def _apply_settings(self, s: AppSettings) -> None:
        qss = build_stylesheet(s.theme, s.accent_color, s.font_family, s.font_size)
        self.setStyleSheet(qss)
        self._sidebar.setVisible(s.sidebar_visible)
        self._act_sidebar.setChecked(s.sidebar_visible)
        self._preview.setVisible(s.preview_visible)
        self._act_preview.setChecked(s.preview_visible)
        self._update_preview()

    # ==================================================================
    # Sidebar handlers
    # ==================================================================

    def _refresh_folder_list(self) -> None:
        self._folder_list.blockSignals(True)
        self._folder_list.clear()
        # "All Notes" virtual folder
        all_item = QListWidgetItem("📋 " + self._i18n.t("all_notes"))
        all_item.setData(Qt.ItemDataRole.UserRole, "__all__")
        self._folder_list.addItem(all_item)
        for folder in self._note_ctrl.get_folders():
            item = QListWidgetItem("📁 " + folder)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            self._folder_list.addItem(item)
        selected_folder = self._current_folder or "__all__"
        selected_row = 0
        for row in range(self._folder_list.count()):
            if self._folder_list.item(row).data(Qt.ItemDataRole.UserRole) == selected_folder:
                selected_row = row
                break
        self._folder_list.setCurrentRow(selected_row)
        self._folder_list.blockSignals(False)

    def _refresh_note_list(self) -> None:
        self._refresh_folder_list()
        query = self._search.text().strip()
        if query:
            notes = self._note_ctrl.search(query, self._current_folder)
        else:
            notes = self._note_ctrl.list_notes(self._current_folder)

        self._note_list.blockSignals(True)
        self._note_list.clear()

        if not notes:
            empty = QListWidgetItem(self._i18n.t("no_notes"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._note_list.addItem(empty)
        else:
            for note in notes:
                prefix = "📌 " if note.is_pinned else ""
                display = prefix + (note.title or self._i18n.t("untitled"))
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                self._note_list.addItem(item)
                # Auto-select the current note
                if self._current_note and note.id == self._current_note.id:
                    self._note_list.setCurrentItem(item)

        self._note_list.blockSignals(False)

    def _on_folder_selected(self, row: int) -> None:
        item = self._folder_list.item(row)
        if item:
            self._current_folder = item.data(Qt.ItemDataRole.UserRole)
            self._refresh_note_list()

    def _on_note_selected(self, row: int) -> None:
        item = self._note_list.item(row)
        if item:
            note_id = item.data(Qt.ItemDataRole.UserRole)
            if note_id:
                self._load_note(note_id)

    def _on_search(self, _text: str) -> None:
        self._refresh_note_list()

    # ==================================================================
    # Note CRUD
    # ==================================================================

    def _load_note(self, note_id: str) -> None:
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return
        self._current_note = note
        self._title_edit.blockSignals(True)
        self._content_edit.blockSignals(True)
        self._title_edit.setText(note.title)
        self._content_edit.setPlainText(note.content)
        self._title_edit.blockSignals(False)
        self._content_edit.blockSignals(False)
        self._update_preview()
        self._update_status()

    def _on_new_note(self) -> None:
        folder = self._current_folder if self._current_folder and self._current_folder != "__all__" else "General"
        note = self._note_ctrl.create_note(
            title=self._i18n.t("untitled"),
            folder=folder,
        )
        self._current_note = note
        self._refresh_note_list()
        self._load_note(note.id)
        self._title_edit.setFocus()
        self._title_edit.selectAll()

    def _on_delete_note(self) -> None:
        if not self._current_note:
            return
        reply = QMessageBox.question(
            self,
            self._i18n.t("confirm_delete_title"),
            self._i18n.t("confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._note_ctrl.delete_note(self._current_note.id)
            self._current_note = None
            self._title_edit.clear()
            self._content_edit.clear()
            self._preview.clear()
            self._refresh_note_list()

    def _on_note_context_menu(self, pos) -> None:
        item = self._note_list.itemAt(pos)
        if not item:
            return
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if not note_id:
            return
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return

        menu = QMenu(self)
        t = self._i18n.t

        # Pin / Unpin
        pin_text = t("unpin_note") if note.is_pinned else t("pin_note")
        pin_action = menu.addAction(pin_text)
        pin_action.triggered.connect(lambda: self._toggle_pin(note_id))

        # Move to folder
        move_menu = menu.addMenu(t("move_to_folder"))
        for folder in self._note_ctrl.get_folders():
            act = move_menu.addAction(folder)
            act.triggered.connect(lambda checked, f=folder: self._move_note(note_id, f))

        # New folder
        menu.addSeparator()
        new_folder_action = menu.addAction(t("new_folder"))
        new_folder_action.triggered.connect(lambda: self._create_folder_and_move(note_id))

        menu.addSeparator()
        del_action = menu.addAction(t("delete_note"))
        del_action.triggered.connect(lambda: self._delete_specific_note(note_id))

        menu.exec(self._note_list.mapToGlobal(pos))

    def _toggle_pin(self, note_id: str) -> None:
        self._note_ctrl.toggle_pin(note_id)
        self._refresh_note_list()

    def _move_note(self, note_id: str, folder: str) -> None:
        self._note_ctrl.move_to_folder(note_id, folder)
        self._refresh_note_list()

    def _create_folder_and_move(self, note_id: str) -> None:
        name, ok = QInputDialog.getText(
            self, self._i18n.t("new_folder"), self._i18n.t("new_folder") + ":"
        )
        if ok and name.strip():
            self._note_ctrl.move_to_folder(note_id, name.strip())
            self._refresh_note_list()

    def _delete_specific_note(self, note_id: str) -> None:
        reply = QMessageBox.question(
            self,
            self._i18n.t("confirm_delete_title"),
            self._i18n.t("confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._note_ctrl.delete_note(note_id)
            if self._current_note and self._current_note.id == note_id:
                self._current_note = None
                self._title_edit.clear()
                self._content_edit.clear()
                self._preview.clear()
            self._refresh_note_list()

    # ==================================================================
    # Auto-save
    # ==================================================================

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _auto_save(self) -> None:
        if not self._current_note:
            return
        self._current_note.title = self._title_edit.text()
        self._current_note.content = self._content_edit.toPlainText()
        self._note_ctrl.save_note(self._current_note)
        # Refresh list to show updated title
        self._refresh_note_list()

    # ==================================================================
    # Preview & Status
    # ==================================================================

    def _update_preview(self) -> None:
        text = self._content_edit.toPlainText()
        if self._current_note and self._current_note.is_markdown:
            html = markdown.markdown(
                text,
                extensions=["fenced_code", "tables", "nl2br"],
            )
            # Inject preview styling
            accent = self._settings_ctrl.settings.accent_color
            theme = self._settings_ctrl.settings.theme
            fg = "#F5F5F7" if theme == "dark" else "#1D1D1F"
            bg = "#1F1F21" if theme == "dark" else "#FAFAFC"
            code_bg = "#2A2A2D" if theme == "dark" else "#EFEFF2"
            font = self._settings_ctrl.settings.font_family
            size = self._settings_ctrl.settings.font_size
            styled = f"""
            <style>
                body {{ color: {fg}; background: {bg}; font-family: "{font}", sans-serif; font-size: {size}px; line-height: 1.7; padding: 8px; }}
                h1, h2, h3 {{ color: {accent}; margin-top: 16px; }}
                a {{ color: {accent}; }}
                code {{ background: {code_bg}; padding: 2px 6px; border-radius: 4px; font-family: "Fira Code", monospace; font-size: {size - 1}px; }}
                pre {{ background: {code_bg}; padding: 12px; border-radius: 8px; overflow-x: auto; }}
                pre code {{ padding: 0; }}
                blockquote {{ border-left: 3px solid {accent}; padding-left: 12px; color: #71717a; margin: 8px 0; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #3f3f46; padding: 8px; text-align: left; }}
                th {{ background: {code_bg}; }}
                hr {{ border: none; border-top: 1px solid #27272a; margin: 16px 0; }}
            </style>
            {html}
            """
            self._preview.setHtml(styled)
        else:
            self._preview.setPlainText(text)

    def _update_status(self) -> None:
        text = self._content_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        self._word_label.setText(self._i18n.t("word_count", count=words))
        self._char_label.setText("  ·  " + self._i18n.t("char_count", count=chars))

    # ==================================================================
    # View toggles
    # ==================================================================

    def _on_toggle_sidebar(self, checked: bool) -> None:
        self._settings_ctrl.set_sidebar_visible(checked)

    def _on_toggle_preview(self, checked: bool) -> None:
        self._settings_ctrl.set_preview_visible(checked)

    # ==================================================================
    # Settings / About dialogs
    # ==================================================================

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(self._settings_ctrl, self._i18n, self)
        dlg.exec()

    def _on_about(self) -> None:
        QMessageBox.about(self, self._i18n.t("about"), self._i18n.t("about_text"))

    # ==================================================================
    # Window lifecycle
    # ==================================================================

    def closeEvent(self, event) -> None:
        # Save any pending edits
        self._auto_save()
        # Save window geometry
        g = self.geometry()
        self._settings_ctrl.save_window_geometry(g.x(), g.y(), g.width(), g.height())
        self._settings_ctrl.save_sidebar_folder_height(self._sidebar_splitter.sizes()[0])
        super().closeEvent(event)
