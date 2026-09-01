"""Ayran Notes — focused Markdown writing window."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QColor, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ayrannotes.controllers.note_controller import NoteController
from ayrannotes.controllers.settings_controller import SettingsController
from ayrannotes.exporters import export_note
from ayrannotes.importers import import_note
from ayrannotes.localization.i18n import I18n
from ayrannotes.storage.models import AppSettings, Note
from ayrannotes.ui.floating_toolbar import FloatingToolbar
from ayrannotes.ui.markdown_support import MarkdownSyntaxHighlighter, render_markdown_html
from ayrannotes.ui.settings_dialog import SettingsDialog
from ayrannotes.ui.themes import build_stylesheet


class MainWindow(QMainWindow):
    """The primary Ayran Notes window."""

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
        self._save_state_key = "saved"
        self._current_note: Note | None = None
        self._last_detailed_note_id: str | None = None
        self._dirty = False
        self._simple_dirty = False
        self._simple_draft_ids: set[str] = set()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self._auto_save)
        self._simple_save_timer = QTimer(self)
        self._simple_save_timer.setSingleShot(True)
        self._simple_save_timer.setInterval(600)
        self._simple_save_timer.timeout.connect(self._auto_save_simple)

        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._apply_settings(self._settings_ctrl.settings)
        self._refresh_note_list()
        self._retranslate()
        # Preserve the existing product decision: Simple is the opening view.
        self._change_view_mode("simple")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        settings = self._settings_ctrl.settings
        self.setGeometry(
            settings.window_x,
            settings.window_y,
            settings.window_width,
            settings.window_height,
        )
        self.setMinimumSize(700, 450)

        self._view_stack = QStackedWidget()
        self.setCentralWidget(self._view_stack)

        self._detailed_view = QWidget()
        self._detailed_view.setObjectName("detailedView")
        self._view_stack.addWidget(self._detailed_view)
        detailed_layout = QHBoxLayout(self._detailed_view)
        detailed_layout.setContentsMargins(0, 0, 0, 0)
        detailed_layout.setSpacing(0)

        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(6)
        self._search = QLineEdit()
        self._search.setObjectName("sidebarSearch")
        self._search.setClearButtonEnabled(True)
        sidebar_layout.addWidget(self._search)
        self._new_btn = QPushButton()
        self._new_btn.setObjectName("accentBtn")
        sidebar_layout.addWidget(self._new_btn)
        self._notes_label = QLabel()
        self._notes_label.setObjectName("sectionLabel")
        sidebar_layout.addWidget(self._notes_label)
        self._note_list = QListWidget()
        sidebar_layout.addWidget(self._note_list, 1)

        sidebar_shadow = QGraphicsDropShadowEffect(self._sidebar)
        sidebar_shadow.setBlurRadius(20)
        sidebar_shadow.setXOffset(3)
        sidebar_shadow.setYOffset(0)
        sidebar_shadow.setColor(QColor(0, 0, 0, 40))
        self._sidebar.setGraphicsEffect(sidebar_shadow)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setObjectName("mainSplitter")
        self._main_splitter.setChildrenCollapsible(False)
        self._main_splitter.addWidget(self._sidebar)

        editor_pane = QWidget()
        editor_pane.setObjectName("editorPane")
        editor_layout = QVBoxLayout(editor_pane)
        editor_layout.setContentsMargins(20, 12, 20, 12)
        editor_layout.setSpacing(0)
        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("titleEdit")
        editor_layout.addWidget(self._title_edit)
        self._content_edit = QPlainTextEdit()
        self._content_edit.setObjectName("contentEdit")
        self._content_edit.setTabStopDistance(32.0)
        self._content_highlighter = MarkdownSyntaxHighlighter(
            self._content_edit.document(), settings.theme
        )
        FloatingToolbar(self._content_edit, self._wrap_selection, self._i18n, self)
        self._editor_toolbar = QToolBar()
        self._editor_toolbar.setObjectName("editorToolbar")
        self._editor_toolbar.setMovable(False)
        self._build_editor_toolbar()
        editor_layout.addWidget(self._editor_toolbar)
        editor_layout.addWidget(self._content_edit, 1)
        self._main_splitter.addWidget(editor_pane)

        self._preview = QTextBrowser()
        self._preview.setObjectName("previewPanel")
        self._preview.setOpenExternalLinks(True)
        self._main_splitter.addWidget(self._preview)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setStretchFactor(2, 2)
        QTimer.singleShot(0, self._restore_main_splitter)
        detailed_layout.addWidget(self._main_splitter, 1)

        self._build_simple_ui()
        self._build_navigation_bar()
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._save_state_label = QLabel()
        self._save_state_label.setObjectName("saveStateLabel")
        self._word_label = QLabel()
        self._char_label = QLabel()
        self._statusbar.addWidget(self._save_state_label)
        self._statusbar.addPermanentWidget(self._word_label)
        self._statusbar.addPermanentWidget(self._char_label)

    def _build_simple_ui(self) -> None:
        self._simple_view = QWidget()
        self._simple_view.setObjectName("simpleView")
        simple_layout = QVBoxLayout(self._simple_view)
        simple_layout.setContentsMargins(24, 18, 24, 20)
        simple_layout.setSpacing(16)
        self._simple_stack = QStackedWidget()
        simple_layout.addWidget(self._simple_stack)

        self._simple_home = QWidget()
        home_layout = QVBoxLayout(self._simple_home)
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(18)
        self._simple_heading = QLabel()
        self._simple_heading.setObjectName("simpleHeading")
        home_layout.addWidget(self._simple_heading)
        search_row = QHBoxLayout()
        search_row.addStretch(1)
        self._simple_search = QLineEdit()
        self._simple_search.setObjectName("simpleSearch")
        self._simple_search.setClearButtonEnabled(True)
        self._simple_search.setMaximumWidth(620)
        search_row.addWidget(self._simple_search, 4)
        self._simple_add = QPushButton("+")
        self._simple_add.setObjectName("simpleAddButton")
        self._simple_add.setFixedSize(42, 42)
        search_row.addWidget(self._simple_add)
        search_row.addStretch(1)
        home_layout.addLayout(search_row)

        self._simple_empty = QWidget()
        self._simple_empty.setObjectName("simpleEmptyState")
        empty_layout = QVBoxLayout(self._simple_empty)
        empty_layout.setContentsMargins(24, 52, 24, 52)
        empty_layout.setSpacing(10)
        empty_layout.addStretch(1)
        self._simple_empty_title = QLabel()
        self._simple_empty_title.setObjectName("emptyStateTitle")
        self._simple_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._simple_empty_title)
        self._simple_empty_body = QLabel()
        self._simple_empty_body.setObjectName("emptyStateBody")
        self._simple_empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._simple_empty_body.setWordWrap(True)
        empty_layout.addWidget(self._simple_empty_body)
        self._simple_empty_add = QPushButton()
        self._simple_empty_add.setObjectName("emptyStateButton")
        self._simple_empty_add.setMaximumWidth(180)
        empty_layout.addWidget(self._simple_empty_add, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(2)
        self._simple_empty.setVisible(False)
        home_layout.addWidget(self._simple_empty, 1)

        self._simple_cards = QListWidget()
        self._simple_cards.setObjectName("simpleCards")
        self._simple_cards.setViewMode(QListView.ViewMode.IconMode)
        self._simple_cards.setResizeMode(QListView.ResizeMode.Adjust)
        self._simple_cards.setMovement(QListView.Movement.Static)
        self._simple_cards.setWordWrap(True)
        self._simple_cards.setSpacing(12)
        self._simple_cards.setMaximumWidth(980)
        self._simple_cards.setGridSize(QSize(230, 150))
        home_layout.addWidget(self._simple_cards, 1)
        self._simple_stack.addWidget(self._simple_home)

        self._simple_editor = QWidget()
        editor_layout = QVBoxLayout(self._simple_editor)
        editor_layout.setContentsMargins(72, 18, 72, 30)
        editor_layout.setSpacing(0)
        self._simple_back = QPushButton("←")
        self._simple_back.setObjectName("simpleBackButton")
        self._simple_back.setFixedSize(38, 34)
        editor_header = QHBoxLayout()
        editor_header.addWidget(self._simple_back)
        editor_header.addStretch(1)
        self._simple_delete = QPushButton()
        self._simple_delete.setObjectName("simpleDeleteButton")
        self._simple_delete.setFixedHeight(34)
        editor_header.addWidget(self._simple_delete)
        editor_layout.addLayout(editor_header)
        self._simple_title = QLineEdit()
        self._simple_title.setObjectName("simpleTitle")
        editor_layout.addWidget(self._simple_title)
        self._simple_content = QPlainTextEdit()
        self._simple_content.setObjectName("simpleContent")
        self._simple_content_highlighter = MarkdownSyntaxHighlighter(
            self._simple_content.document(), self._settings_ctrl.settings.theme
        )
        FloatingToolbar(self._simple_content, self._wrap_selection, self._i18n, self)
        editor_layout.addWidget(self._simple_content, 1)
        self._simple_stack.addWidget(self._simple_editor)
        self._view_stack.addWidget(self._simple_view)

    def _build_navigation_bar(self) -> None:
        self._navigation_bar = QToolBar()
        self._navigation_bar.setObjectName("navigationBar")
        self._navigation_bar.setMovable(False)
        self._navigation_bar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._navigation_bar)
        self._nav_brand = QLabel("Ayran Notes")
        self._nav_brand.setObjectName("navigationBrand")
        self._navigation_bar.addWidget(self._nav_brand)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._navigation_bar.addWidget(spacer)
        mode_segment = QWidget()
        mode_segment.setObjectName("modeSegment")
        mode_layout = QHBoxLayout(mode_segment)
        mode_layout.setContentsMargins(3, 3, 3, 3)
        mode_layout.setSpacing(2)
        self._nav_simple = QPushButton()
        self._nav_simple.setObjectName("modeSegmentButton")
        self._nav_simple.setCheckable(True)
        self._nav_detailed = QPushButton()
        self._nav_detailed.setObjectName("modeSegmentButton")
        self._nav_detailed.setCheckable(True)
        self._nav_mode_group = QButtonGroup(self)
        self._nav_mode_group.setExclusive(True)
        self._nav_mode_group.addButton(self._nav_simple)
        self._nav_mode_group.addButton(self._nav_detailed)
        mode_layout.addWidget(self._nav_simple)
        mode_layout.addWidget(self._nav_detailed)
        self._navigation_bar.addWidget(mode_segment)
        self._nav_more = QPushButton("•••")
        self._nav_more.setObjectName("navigationMoreButton")
        self._nav_more.setFixedSize(38, 32)
        self._navigation_bar.addWidget(self._nav_more)

    def _restore_main_splitter(self) -> None:
        sizes = self._settings_ctrl.settings.main_splitter_sizes
        if sizes and len(sizes) == 3:
            self._main_splitter.setSizes(sizes)

    def _build_editor_toolbar(self) -> None:
        self._format_actions = {}
        actions = (
            ("bold", "B", lambda: self._wrap_selection("**", "**", "bold"), "Ctrl+B"),
            ("italic", "I", lambda: self._wrap_selection("_", "_", "italic"), "Ctrl+I"),
            ("heading", "H", lambda: self._prefix_line("## "), None),
            ("checklist", "☑", lambda: self._prefix_line("- [ ] "), None),
            ("inline_code", "</>", lambda: self._wrap_selection("`", "`", "code"), None),
            ("code_block", "{ }", lambda: self._wrap_selection("\n```\n", "\n```\n", "code"), None),
            ("link", "↗", lambda: self._wrap_selection("[", "](https://)", "link text"), None),
        )
        for key, label, callback, shortcut in actions:
            action = self._editor_toolbar.addAction(label)
            action.triggered.connect(callback)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            self._format_actions[key] = action
        self._editor_toolbar.addSeparator()
        self._act_sync_scroll = self._editor_toolbar.addAction("🔒")
        self._act_sync_scroll.setCheckable(True)
        self._act_sync_scroll.setChecked(False)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()
        self._file_menu = menu_bar.addMenu("")
        self._act_new = QAction(self)
        self._act_new.setShortcut(QKeySequence("Ctrl+N"))
        self._act_new.triggered.connect(self._on_new_note)
        self._file_menu.addAction(self._act_new)
        self._act_delete = QAction(self)
        self._act_delete.setShortcut(QKeySequence("Ctrl+Delete"))
        self._act_delete.triggered.connect(self._on_delete_note)
        self._file_menu.addAction(self._act_delete)
        self._file_menu.addSeparator()
        self._act_import = QAction(self)
        self._act_import.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self._act_import.triggered.connect(self._import_notes)
        self._file_menu.addAction(self._act_import)
        self._act_export = QAction(self)
        self._act_export.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self._act_export.triggered.connect(self._export_current_note)
        self._file_menu.addAction(self._act_export)
        self._file_menu.addSeparator()
        self._act_quit = QAction(self)
        self._act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._act_quit.triggered.connect(self.close)
        self._file_menu.addAction(self._act_quit)

        self._edit_menu = menu_bar.addMenu("")
        self._act_undo = QAction(self)
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.triggered.connect(self._undo_active)
        self._edit_menu.addAction(self._act_undo)
        self._act_redo = QAction(self)
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.triggered.connect(self._redo_active)
        self._edit_menu.addAction(self._act_redo)
        self._edit_menu.addSeparator()
        self._act_find = QAction(self)
        self._act_find.setShortcut(QKeySequence.StandardKey.Find)
        self._act_find.triggered.connect(self._find_text)
        self._edit_menu.addAction(self._act_find)
        self._act_replace = QAction(self)
        self._act_replace.setShortcut(QKeySequence("Ctrl+H"))
        self._act_replace.triggered.connect(self._replace_text)
        self._edit_menu.addAction(self._act_replace)

        self._view_menu = menu_bar.addMenu("")
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)
        self._act_simple_mode = QAction(self)
        self._act_simple_mode.setCheckable(True)
        self._act_simple_mode.triggered.connect(
            lambda checked: checked and self._change_view_mode("simple")
        )
        self._mode_group.addAction(self._act_simple_mode)
        self._view_menu.addAction(self._act_simple_mode)
        self._act_detailed_mode = QAction(self)
        self._act_detailed_mode.setCheckable(True)
        self._act_detailed_mode.triggered.connect(
            lambda checked: checked and self._change_view_mode("detailed")
        )
        self._mode_group.addAction(self._act_detailed_mode)
        self._view_menu.addAction(self._act_detailed_mode)
        self._view_menu.addSeparator()
        self._act_sidebar = QAction(self)
        self._act_sidebar.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self._act_sidebar.setCheckable(True)
        self._act_sidebar.triggered.connect(self._on_toggle_sidebar)
        self._view_menu.addAction(self._act_sidebar)
        self._act_preview = QAction(self)
        self._act_preview.setShortcut(QKeySequence("Ctrl+P"))
        self._act_preview.setCheckable(True)
        self._act_preview.triggered.connect(self._on_toggle_preview)
        self._view_menu.addAction(self._act_preview)

        self._help_menu = menu_bar.addMenu("")
        self._act_prefs = QAction(self)
        self._act_prefs.triggered.connect(self._on_open_settings)
        self._help_menu.addAction(self._act_prefs)
        self._act_about = QAction(self)
        self._act_about.triggered.connect(self._on_about)
        self._help_menu.addAction(self._act_about)

        self._quick_menu = QMenu(self)
        self._quick_menu.addAction(self._act_import)
        self._quick_menu.addAction(self._act_export)
        self._quick_menu.addSeparator()
        self._quick_menu.addAction(self._act_prefs)
        self._nav_more.setMenu(self._quick_menu)

    def _connect_signals(self) -> None:
        self._i18n.language_changed.connect(lambda _: self._retranslate())
        self._settings_ctrl.settings_changed.connect(self._apply_settings)
        self._search.textChanged.connect(self._on_search)
        self._new_btn.clicked.connect(self._on_new_note)
        self._note_list.currentRowChanged.connect(self._on_note_selected)
        self._content_edit.textChanged.connect(self._schedule_save)
        self._content_edit.textChanged.connect(self._update_preview)
        self._content_edit.textChanged.connect(self._update_status)
        self._content_edit.verticalScrollBar().valueChanged.connect(self._sync_preview_scroll)
        self._title_edit.textChanged.connect(self._schedule_save)
        self._simple_search.textChanged.connect(lambda _: self._refresh_simple_cards())
        self._simple_add.clicked.connect(self._on_simple_new_note)
        self._simple_cards.itemClicked.connect(self._on_simple_card_clicked)
        self._simple_back.clicked.connect(self._show_simple_home)
        self._simple_delete.clicked.connect(self._on_simple_delete)
        self._simple_title.textChanged.connect(self._schedule_simple_save)
        self._simple_content.textChanged.connect(self._schedule_simple_save)
        self._simple_empty_add.clicked.connect(self._on_simple_new_note)
        self._nav_simple.clicked.connect(lambda: self._change_view_mode("simple"))
        self._nav_detailed.clicked.connect(lambda: self._change_view_mode("detailed"))

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("app_name"))
        self._search.setPlaceholderText(t("search_placeholder"))
        self._new_btn.setText("+ " + t("new_note"))
        self._notes_label.setText(t("all_notes").upper())
        self._title_edit.setPlaceholderText(t("note_title_placeholder"))
        self._content_edit.setPlaceholderText(t("note_content_placeholder"))
        self._simple_search.setPlaceholderText(t("simple_search_placeholder"))
        self._simple_title.setPlaceholderText(t("note_title_placeholder"))
        self._simple_content.setPlaceholderText(t("simple_content_placeholder"))
        self._simple_add.setToolTip(t("new_note"))
        self._simple_back.setToolTip(t("back_to_notes"))
        self._simple_delete.setToolTip(t("delete_note"))
        self._simple_delete.setText(t("delete_note"))
        self._simple_heading.setText(t("notes_heading"))
        self._simple_empty_add.setText(t("new_note"))
        self._nav_simple.setText(t("simple_mode"))
        self._nav_detailed.setText(t("detailed_mode"))
        self._nav_more.setToolTip(t("more"))
        self._save_state_label.setText(t(self._save_state_key))
        self._file_menu.setTitle(t("file"))
        self._act_new.setText(t("new_note"))
        self._act_delete.setText(t("delete_note"))
        self._act_import.setText(t("import"))
        self._act_export.setText(t("export"))
        self._act_quit.setText(t("close"))
        self._edit_menu.setTitle(t("edit"))
        self._act_undo.setText(t("undo"))
        self._act_redo.setText(t("redo"))
        self._act_find.setText(t("find"))
        self._act_replace.setText(t("replace"))
        self._view_menu.setTitle(t("view"))
        self._act_simple_mode.setText(t("simple_mode"))
        self._act_detailed_mode.setText(t("detailed_mode"))
        self._act_sidebar.setText(t("toggle_sidebar"))
        self._act_preview.setText(t("toggle_preview"))
        self._help_menu.setTitle(t("help"))
        self._act_prefs.setText(t("preferences"))
        self._act_about.setText(t("about"))
        for key, action in self._format_actions.items():
            action.setToolTip(t(key))
        self._refresh_note_views()
        self._update_status()

    def _apply_settings(self, settings: AppSettings) -> None:
        theme = self._settings_ctrl.resolved_theme
        accent = self._settings_ctrl.resolved_accent_color
        self.setStyleSheet(build_stylesheet(theme, accent, settings.font_family, settings.font_size))
        self._content_highlighter.set_theme(theme)
        self._simple_content_highlighter.set_theme(theme)
        self._sidebar.setVisible(settings.sidebar_visible)
        self._act_sidebar.setChecked(settings.sidebar_visible)
        self._preview.setVisible(settings.preview_visible)
        self._act_preview.setChecked(settings.preview_visible)
        self._show_view_mode(settings.view_mode)
        self._update_preview()

    # ------------------------------------------------------------------
    # View modes and simple mode
    # ------------------------------------------------------------------

    def _change_view_mode(self, mode: str) -> None:
        if not self._flush_all_edits():
            self._show_view_mode(self._settings_ctrl.settings.view_mode)
            return
        if self._simple_editor_is_active():
            self._discard_empty_simple_note()
        if mode == "simple":
            self._show_simple_home()
        self._settings_ctrl.set_view_mode(mode)

    def _show_view_mode(self, mode: str) -> None:
        simple = mode == "simple"
        previous = self._view_stack.currentWidget()
        self._act_simple_mode.setChecked(simple)
        self._act_detailed_mode.setChecked(not simple)
        self._nav_simple.setChecked(simple)
        self._nav_detailed.setChecked(not simple)
        current = self._simple_view if simple else self._detailed_view
        if previous is not None and previous is not current:
            effect = QGraphicsOpacityEffect(self._view_stack)
            self._view_stack.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b"opacity")
            animation.setDuration(180)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.Type.InOutSine)
            animation.finished.connect(lambda: self._view_stack.setGraphicsEffect(None))
            self._view_stack.setCurrentWidget(current)
            self._view_animation = animation
            animation.start()
        else:
            self._view_stack.setCurrentWidget(current)
        if simple:
            self._refresh_simple_cards()
        elif previous is not self._detailed_view:
            self._refresh_note_list()
            self._restore_detailed_context()
        elif not self._current_note:
            self._restore_detailed_context()
        self._update_statusbar_visibility()

    def _restore_detailed_context(self) -> None:
        preferred_id = self._current_note.id if self._current_note else self._last_detailed_note_id
        note_id = preferred_id
        if note_id and not any(
            self._note_list.item(row).data(Qt.ItemDataRole.UserRole) == note_id
            for row in range(self._note_list.count())
        ):
            note_id = None
        if not note_id and self._note_list.currentItem():
            note_id = self._note_list.currentItem().data(Qt.ItemDataRole.UserRole)
        if not note_id:
            for row in range(self._note_list.count()):
                candidate = self._note_list.item(row).data(Qt.ItemDataRole.UserRole)
                if candidate:
                    note_id = candidate
                    break
        if note_id:
            self._load_note(note_id)
        else:
            self._set_detailed_editor_enabled(False)

    def _format_note_date(self, value: str) -> str:
        try:
            updated = datetime.fromisoformat(value).astimezone()
        except (TypeError, ValueError):
            return ""
        today = datetime.now().astimezone().date()
        if updated.date() == today:
            return self._i18n.t("today")
        if updated.date() == today - timedelta(days=1):
            return self._i18n.t("yesterday")
        return updated.strftime("%d.%m.%Y")

    def _refresh_simple_cards(self) -> None:
        query = self._simple_search.text().strip()
        notes = self._note_ctrl.search(query) if query else self._note_ctrl.list_notes()
        self._simple_cards.clear()
        has_notes = bool(notes)
        self._simple_cards.setVisible(has_notes)
        self._simple_empty.setVisible(not has_notes)
        if not has_notes:
            key = "no_results" if query else "empty_notes"
            self._simple_empty_title.setText(self._i18n.t(f"{key}_title"))
            self._simple_empty_body.setText(self._i18n.t(f"{key}_body"))
            self._simple_empty_add.setVisible(not query)
            return
        for note in notes:
            plain = re.sub(r"[#*_`>\[\]()-]+", " ", note.content)
            snippet = " ".join(plain.split())[:120]
            title = note.title or self._i18n.t("untitled")
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, title)
            item.setToolTip(title)
            item.setSizeHint(QSize(220, 142))
            self._simple_cards.addItem(item)
            card = QWidget()
            card.setObjectName("noteCard")
            card_layout = QVBoxLayout(card)
            card.setAccessibleName(title)
            card_layout.setContentsMargins(16, 14, 16, 13)
            card_layout.setSpacing(7)
            title_label = QLabel(title)
            title_label.setObjectName("noteCardTitle")
            title_label.setWordWrap(True)
            card_layout.addWidget(title_label)
            snippet_label = QLabel(snippet or self._i18n.t("empty_note_preview"))
            snippet_label.setObjectName("noteCardSnippet")
            snippet_label.setWordWrap(True)
            snippet_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            card_layout.addWidget(snippet_label, 1)
            metadata_label = QLabel(self._format_note_date(note.updated_at))
            metadata_label.setObjectName("noteCardMetadata")
            card_layout.addWidget(metadata_label)
            self._simple_cards.setItemWidget(item, card)

    def _on_simple_card_clicked(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if note_id:
            self._load_simple_note(note_id)

    def _load_simple_note(self, note_id: str) -> None:
        if self._current_note and self._current_note.id != note_id and not self._flush_all_edits():
            return
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return
        self._current_note = note
        self._simple_title.blockSignals(True)
        self._simple_content.blockSignals(True)
        self._simple_title.setText(note.title)
        self._simple_content.setPlainText(note.content)
        self._simple_title.blockSignals(False)
        self._simple_content.blockSignals(False)
        self._simple_dirty = False
        self._simple_stack.setCurrentWidget(self._simple_editor)
        self._update_statusbar_visibility()
        self._simple_content.setFocus()
        self._update_status()

    def _on_simple_new_note(self) -> None:
        if not self._flush_all_edits():
            return
        note = self._note_ctrl.create_note("")
        self._simple_draft_ids.add(note.id)
        self._current_note = note
        self._load_simple_note(note.id)
        self._simple_title.setFocus()

    def _show_simple_home(self) -> None:
        simple_editor_active = self._simple_editor_is_active()
        if not self._flush_all_edits():
            return
        if simple_editor_active:
            self._discard_empty_simple_note()
        self._current_note = None
        self._clear_editor_fields()
        self._simple_stack.setCurrentWidget(self._simple_home)
        self._update_statusbar_visibility()
        self._refresh_simple_cards()
        self._update_status()

    def _is_empty_simple_note(self, note: Note, title: str | None = None, content: str | None = None) -> bool:
        visible_title = note.title if title is None else title
        visible_content = note.content if content is None else content
        return (
            note.id in self._simple_draft_ids
            and visible_title.strip() in {"", "Untitled", "Başlıksız"}
            and not visible_content.strip()
        )

    def _discard_empty_simple_note(self) -> bool:
        if not self._simple_editor_is_active() or not self._current_note:
            return False
        if not self._is_empty_simple_note(self._current_note, self._simple_title.text(), self._simple_content.toPlainText()):
            return False
        note_id = self._current_note.id
        if not self._note_ctrl.delete_note(note_id):
            return False
        self._simple_draft_ids.discard(note_id)
        self._clear_current_note(note_id)
        return True

    def _on_simple_delete(self) -> None:
        if self._current_note:
            self._delete_specific_note(self._current_note.id)

    # ------------------------------------------------------------------
    # Sidebar and CRUD
    # ------------------------------------------------------------------

    def _refresh_note_list(self) -> None:
        query = self._search.text().strip()
        notes = self._note_ctrl.search(query) if query else self._note_ctrl.list_notes()
        self._note_list.blockSignals(True)
        self._note_list.clear()
        if not notes:
            empty = QListWidgetItem(self._i18n.t("no_notes"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._note_list.addItem(empty)
        else:
            for note in notes:
                item = QListWidgetItem(note.title or self._i18n.t("untitled"))
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                self._note_list.addItem(item)
                if self._current_note and note.id == self._current_note.id:
                    self._note_list.setCurrentItem(item)
        self._note_list.blockSignals(False)
        if self._view_stack.currentWidget() is self._detailed_view and not self._current_note:
            self._restore_detailed_context()

    def _on_note_selected(self, row: int) -> None:
        item = self._note_list.item(row)
        if item:
            note_id = item.data(Qt.ItemDataRole.UserRole)
            if note_id:
                self._load_note(note_id)

    def _on_search(self, _text: str) -> None:
        self._refresh_note_list()

    def _load_note(self, note_id: str) -> None:
        if self._current_note and self._current_note.id != note_id:
            if not self._flush_all_edits():
                self._refresh_note_list()
                return
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return
        self._current_note = note
        self._last_detailed_note_id = note.id
        self._set_detailed_editor_enabled(True)
        self._title_edit.blockSignals(True)
        self._content_edit.blockSignals(True)
        self._title_edit.setText(note.title)
        self._content_edit.setPlainText(note.content)
        self._title_edit.blockSignals(False)
        self._content_edit.blockSignals(False)
        self._dirty = False
        self._update_preview(reset_scroll=True)
        self._update_status()

    def _on_new_note(self) -> None:
        if self._view_stack.currentWidget() is self._simple_view:
            self._on_simple_new_note()
            return
        if not self._flush_all_edits():
            return
        note = self._note_ctrl.create_note(self._i18n.t("untitled"))
        self._current_note = note
        self._refresh_note_list()
        self._load_note(note.id)
        self._title_edit.setFocus()
        self._title_edit.selectAll()

    def _on_delete_note(self) -> None:
        if self._current_note:
            self._delete_specific_note(self._current_note.id)

    def _clear_editor_fields(self) -> None:
        for editor in (self._title_edit, self._content_edit, self._simple_title, self._simple_content):
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        self._content_highlighter.set_highlighting_enabled(False)
        self._simple_content_highlighter.set_highlighting_enabled(False)
        self._preview.clear()
        self._set_detailed_editor_enabled(False)

    def _set_detailed_editor_enabled(self, enabled: bool) -> None:
        for widget in (self._title_edit, self._content_edit, self._editor_toolbar):
            widget.setEnabled(enabled)

    def _clear_current_note(self, note_id: str) -> None:
        if not self._current_note or self._current_note.id != note_id:
            return
        self._save_timer.stop()
        self._simple_save_timer.stop()
        self._dirty = False
        self._simple_dirty = False
        self._current_note = None
        self._clear_editor_fields()
        self._simple_stack.setCurrentWidget(self._simple_home)
        self._update_statusbar_visibility()
        self._refresh_note_views()
        self._update_status()

    def _delete_specific_note(self, note_id: str) -> None:
        reply = QMessageBox.question(
            self,
            self._i18n.t("confirm_delete_title"),
            self._i18n.t("confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if self._flush_all_edits() and self._note_ctrl.delete_note(note_id):
            self._simple_draft_ids.discard(note_id)
            self._clear_current_note(note_id)
            self._refresh_note_views()

    def _refresh_note_views(self) -> None:
        self._refresh_note_list()
        self._refresh_simple_cards()

    # ------------------------------------------------------------------
    # Editor tools and Markdown import/export
    # ------------------------------------------------------------------

    def _active_content_editor(self) -> QPlainTextEdit:
        return self._simple_content if self._simple_editor_is_active() else self._content_edit

    def _simple_home_is_active(self) -> bool:
        return self._view_stack.currentWidget() is self._simple_view and self._simple_stack.currentWidget() is self._simple_home

    def _simple_editor_is_active(self) -> bool:
        return self._view_stack.currentWidget() is self._simple_view and self._simple_stack.currentWidget() is self._simple_editor

    def _undo_active(self) -> None:
        if not self._simple_home_is_active():
            self._active_content_editor().undo()

    def _redo_active(self) -> None:
        if not self._simple_home_is_active():
            self._active_content_editor().redo()

    def _wrap_selection(self, prefix: str, suffix: str, placeholder: str) -> None:
        if not self._current_note:
            return
        editor = self._active_content_editor()
        cursor = editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        cursor.insertText(f"{prefix}{selected or placeholder}{suffix}")
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _prefix_line(self, prefix: str) -> None:
        if not self._current_note:
            return
        editor = self._active_content_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(prefix)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _find_text(self) -> None:
        if self._simple_home_is_active():
            self._simple_search.setFocus()
            self._simple_search.selectAll()
            return
        query, accepted = QInputDialog.getText(self, self._i18n.t("find"), self._i18n.t("find") + ":")
        if not accepted or not query:
            return
        editor = self._active_content_editor()
        if not editor.find(query):
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            if not editor.find(query):
                self._statusbar.showMessage(self._i18n.t("text_not_found"), 3000)

    def _replace_text(self) -> None:
        if self._simple_home_is_active():
            return
        old, accepted = QInputDialog.getText(self, self._i18n.t("replace"), self._i18n.t("find") + ":")
        if not accepted or not old:
            return
        new, accepted = QInputDialog.getText(self, self._i18n.t("replace"), self._i18n.t("replace_with") + ":")
        if not accepted:
            return
        editor = self._active_content_editor()
        content = editor.toPlainText()
        count = content.count(old)
        if count:
            editor.setPlainText(content.replace(old, new))
            self._statusbar.showMessage(self._i18n.t("replacements_count", count=count), 3000)
        else:
            self._statusbar.showMessage(self._i18n.t("text_not_found"), 3000)

    def _export_current_note(self) -> None:
        if not self._current_note:
            self._statusbar.showMessage(self._i18n.t("select_note_to_export"), 3000)
            return
        if not self._flush_all_edits():
            return
        safe_title = re.sub(r"[^\w .-]+", "_", self._current_note.title).strip(" .") or "note"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            self._i18n.t("export"),
            str(Path.home() / f"{safe_title}.md"),
            f"{self._i18n.t('markdown_files')} (*.md)",
        )
        if not destination:
            return
        path = Path(destination)
        if path.suffix.lower() != ".md":
            path = path.with_name(path.name + ".md")
        try:
            export_note(self._current_note, path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, self._i18n.t("export_failed"), self._i18n.t("export_failed_detail", error=str(error)))
            return
        self._statusbar.showMessage(self._i18n.t("export_success", path=str(path)), 5000)

    def _import_notes(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            self._i18n.t("import"),
            str(Path.home()),
            f"{self._i18n.t('markdown_files')} (*.md *.markdown)",
        )
        if not filenames or not self._flush_all_edits():
            return
        imported_notes = []
        failures = []
        for filename in filenames:
            try:
                imported = import_note(Path(filename))
                note = self._note_ctrl.create_note(imported.title)
                note.content = imported.content
                self._note_ctrl.save_note(note)
                imported_notes.append(note)
            except (OSError, ValueError, TypeError) as error:
                failures.append(f"{Path(filename).name}: {error}")
        if imported_notes:
            last_note = imported_notes[-1]
            self._refresh_note_views()
            if self._view_stack.currentWidget() is self._simple_view:
                self._load_simple_note(last_note.id)
            else:
                self._load_note(last_note.id)
            self._statusbar.showMessage(self._i18n.t("import_success", count=len(imported_notes)), 5000)
        if failures:
            QMessageBox.warning(self, self._i18n.t("import_failed"), self._i18n.t("import_failed_detail", errors="\n".join(failures)))

    def _schedule_save(self) -> None:
        if self._current_note:
            self._dirty = True
            self._save_timer.start()
            self._set_save_state("saving")

    def _flush_pending_save(self) -> bool:
        if self._save_timer.isActive():
            self._save_timer.stop()
        return self._auto_save() if self._dirty else True

    def _auto_save(self) -> bool:
        if not self._current_note or not self._dirty:
            return True
        self._current_note.title = self._title_edit.text()
        self._current_note.content = self._content_edit.toPlainText()
        try:
            self._note_ctrl.save_note(self._current_note)
        except (OSError, ValueError) as error:
            self._statusbar.showMessage(str(error), 5000)
            self._set_save_state("save_failed")
            return False
        self._dirty = False
        self._set_save_state("saved")
        self._refresh_note_list()
        return True

    def _schedule_simple_save(self) -> None:
        if self._current_note:
            self._simple_dirty = True
            self._simple_save_timer.start()
            self._set_save_state("saving")
            self._update_status()

    def _flush_simple_save(self) -> bool:
        if self._simple_save_timer.isActive():
            self._simple_save_timer.stop()
        return self._auto_save_simple() if self._simple_dirty else True

    def _auto_save_simple(self) -> bool:
        if not self._current_note or not self._simple_dirty:
            return True
        self._current_note.title = self._simple_title.text()
        self._current_note.content = self._simple_content.toPlainText()
        try:
            self._note_ctrl.save_note(self._current_note)
        except (OSError, ValueError) as error:
            self._statusbar.showMessage(str(error), 5000)
            self._set_save_state("save_failed")
            return False
        self._simple_dirty = False
        self._set_save_state("saved")
        self._refresh_simple_cards()
        return True

    def _flush_all_edits(self) -> bool:
        return self._flush_pending_save() and self._flush_simple_save()

    def _update_preview(self, reset_scroll: bool = False) -> None:
        if not self._preview.isVisible():
            return
        v_bar = self._preview.verticalScrollBar()
        h_bar = self._preview.horizontalScrollBar()
        v_pos = 0 if reset_scroll else v_bar.value()
        h_pos = 0 if reset_scroll else h_bar.value()
        text = self._content_edit.toPlainText()
        sync = self._act_sync_scroll.isChecked()
        marker = "SYNC_MARK_1234567890"
        if sync and not reset_scroll:
            cursor = self._content_edit.textCursor()
            pos = cursor.position()
            text = text[:pos] + marker + text[pos:]
        settings = self._settings_ctrl.settings
        html = render_markdown_html(
            text,
            theme=self._settings_ctrl.resolved_theme,
            accent=self._settings_ctrl.resolved_accent_color,
            font_family=settings.font_family,
            font_size=settings.font_size,
        )
        self._preview.setHtml(html)
        if sync and not reset_scroll:
            found = self._preview.document().find(marker)
            if not found.isNull():
                found.removeSelectedText()
                self._preview.setTextCursor(found)
                self._preview.ensureCursorVisible()
        elif not reset_scroll:
            v_bar.setValue(v_pos)
            h_bar.setValue(h_pos)
            QTimer.singleShot(0, lambda: (v_bar.setValue(v_pos), h_bar.setValue(h_pos)))

    def _sync_preview_scroll(self) -> None:
        if not self._act_sync_scroll.isChecked() or not self._preview.isVisible():
            return
        editor_bar = self._content_edit.verticalScrollBar()
        preview_bar = self._preview.verticalScrollBar()
        if editor_bar.maximum() > 0:
            preview_bar.setValue(int(editor_bar.value() / editor_bar.maximum() * preview_bar.maximum()))

    def _set_save_state(self, key: str) -> None:
        self._save_state_key = key
        self._save_state_label.setText(self._i18n.t(key))
        self._save_state_label.setProperty("state", "error" if key == "save_failed" else "normal")
        self._save_state_label.style().unpolish(self._save_state_label)
        self._save_state_label.style().polish(self._save_state_label)

    def _update_statusbar_visibility(self) -> None:
        self._statusbar.setVisible(not self._simple_home_is_active())

    def _update_status(self) -> None:
        if self._view_stack.currentWidget() is self._simple_view:
            text = self._simple_content.toPlainText() if self._simple_editor_is_active() else ""
        else:
            text = self._content_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        self._word_label.setText(self._i18n.t("word_count", count=words))
        self._char_label.setText("  ·  " + self._i18n.t("char_count", count=len(text)))

    def _on_toggle_sidebar(self, checked: bool) -> None:
        self._settings_ctrl.set_sidebar_visible(checked)

    def _on_toggle_preview(self, checked: bool) -> None:
        self._settings_ctrl.set_preview_visible(checked)

    def _on_open_settings(self) -> None:
        if not self._flush_all_edits():
            return
        previous = self._note_ctrl.notes_directory
        SettingsDialog(self._settings_ctrl, self._i18n, self).exec()
        if self._note_ctrl.notes_directory != previous:
            self._save_timer.stop()
            self._simple_save_timer.stop()
            self._dirty = False
            self._simple_dirty = False
            self._current_note = None
            self._last_detailed_note_id = None
            self._clear_editor_fields()
            self._simple_stack.setCurrentWidget(self._simple_home)
            self._refresh_note_views()

    def _on_about(self) -> None:
        QMessageBox.about(self, self._i18n.t("about"), self._i18n.t("about_text"))

    def closeEvent(self, event) -> None:
        if not self._flush_all_edits():
            QMessageBox.critical(
                self,
                self._i18n.t("save_failed_title"),
                self._i18n.t("save_failed_close"),
            )
            event.ignore()
            return
        geometry = self.geometry()
        self._settings_ctrl.save_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )
        self._settings_ctrl.save_main_splitter_sizes(self._main_splitter.sizes())
        event.accept()
