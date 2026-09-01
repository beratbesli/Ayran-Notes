"""Ayran Notes — Main application window."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QKeyEvent,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
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
from ayrannotes.exporters import SUPPORTED_SUFFIXES, export_note
from ayrannotes.importers import import_note
from ayrannotes.localization.i18n import I18n
from ayrannotes.storage.models import AppSettings, Note
from ayrannotes.ui.floating_toolbar import FloatingToolbar
from ayrannotes.ui.markdown_support import (
    MarkdownSyntaxHighlighter,
    render_markdown_html,
)
from ayrannotes.ui.settings_dialog import SettingsDialog
from ayrannotes.ui.themes import build_stylesheet


class MainWindow(QMainWindow):
    """The primary Ayran Notes application window."""

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
        self._current_folder: str | None = None
        self._dirty = False
        self._simple_dirty = False
        self._in_zen_mode = False
        self._zen_pre_state: dict[str, bool] = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)  # auto-save 600ms after last keystroke
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
        self._change_view_mode("simple")

    # UI Construction

    def _build_ui(self) -> None:
        s = self._settings_ctrl.settings
        self.setGeometry(s.window_x, s.window_y, s.window_width, s.window_height)
        self.setMinimumSize(700, 450)

        self._view_stack = QStackedWidget()
        self.setCentralWidget(self._view_stack)

        self._detailed_view = QWidget()
        self._detailed_view.setObjectName("detailedView")
        self._view_stack.addWidget(self._detailed_view)
        main_layout = QHBoxLayout(self._detailed_view)
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

        # Sidebar shadow
        self._sidebar_shadow = QGraphicsDropShadowEffect(self._sidebar)
        self._sidebar_shadow.setBlurRadius(20)
        self._sidebar_shadow.setXOffset(3)
        self._sidebar_shadow.setYOffset(0)
        self._sidebar_shadow.setColor(QColor(0, 0, 0, 40))
        self._sidebar.setGraphicsEffect(self._sidebar_shadow)


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

        # ── Main Content Splitter (Sidebar | Editor | Preview) ────────────────────
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setObjectName("mainSplitter")
        self._main_splitter.setChildrenCollapsible(False)
        
        self._main_splitter.addWidget(self._sidebar)

        # Editor pane
        self._editor_pane = QWidget()
        self._editor_pane.setObjectName("editorPane")
        editor_main_layout = QHBoxLayout(self._editor_pane)
        editor_main_layout.setContentsMargins(0, 0, 0, 0)
        editor_main_layout.setSpacing(0)
        
        self._editor_left_stretch = QWidget()
        self._editor_right_stretch = QWidget()
        self._editor_container = QWidget()
        
        editor_layout = QVBoxLayout(self._editor_container)
        editor_layout.setContentsMargins(20, 12, 20, 12)
        editor_layout.setSpacing(0)

        self._title_edit = QLineEdit()
        self._title_edit.setObjectName("titleEdit")
        editor_layout.addWidget(self._title_edit)

        self._tag_edit = QLineEdit()
        self._tag_edit.setObjectName("tagEdit")
        editor_layout.addWidget(self._tag_edit)

        self._content_edit = QPlainTextEdit()
        self._content_edit.setObjectName("contentEdit")
        self._content_edit.setTabStopDistance(32.0)
        self._content_highlighter = MarkdownSyntaxHighlighter(
            self._content_edit.document(),
            s.theme,
        )

        self._floating_toolbar_detailed = FloatingToolbar(
            self._content_edit,
            self._wrap_selection,
            self._i18n,
            self
        )

        self._editor_toolbar = QToolBar()
        self._editor_toolbar.setObjectName("editorToolbar")
        self._editor_toolbar.setMovable(False)
        self._build_editor_toolbar()
        editor_layout.addWidget(self._editor_toolbar)
        editor_layout.addWidget(self._content_edit, 1)

        editor_main_layout.addWidget(self._editor_left_stretch, 1)
        editor_main_layout.addWidget(self._editor_container, 4)
        editor_main_layout.addWidget(self._editor_right_stretch, 1)
        self._editor_left_stretch.hide()
        self._editor_right_stretch.hide()

        self._main_splitter.addWidget(self._editor_pane)

        # Preview pane
        self._preview = QTextBrowser()
        self._preview.setObjectName("previewPanel")
        self._preview.setOpenExternalLinks(True)
        self._main_splitter.addWidget(self._preview)

        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 3)
        self._main_splitter.setStretchFactor(2, 2)
        QTimer.singleShot(0, self._restore_main_splitter)

        main_layout.addWidget(self._main_splitter, 1)

        self._build_simple_ui()
        self._build_navigation_bar()

        # ── Status bar ─────────────────────────────────────────────
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._save_state_label = QLabel()
        self._save_state_label.setObjectName("saveStateLabel")
        self._word_label = QLabel()
        self._char_label = QLabel()
        self._statusbar.addWidget(self._save_state_label)
        self._statusbar.addPermanentWidget(self._word_label)
        self._statusbar.addPermanentWidget(self._char_label)

# ── Zen mode floating exit button ─────────────────────────
        self._zen_exit_btn = QPushButton(self)
        self._zen_exit_btn.setObjectName("zenExitButton")
        self._zen_exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zen_exit_btn.clicked.connect(self._exit_zen_mode)
        self._zen_exit_btn.hide()
        
        # Zen button shadow
        self._zen_shadow = QGraphicsDropShadowEffect(self._zen_exit_btn)
        self._zen_shadow.setBlurRadius(15)
        self._zen_shadow.setOffset(0, 4)
        self._zen_shadow.setColor(QColor(0, 0, 0, 80))
        self._zen_exit_btn.setGraphicsEffect(self._zen_shadow)


    def _build_simple_ui(self) -> None:
        """Build the distraction-free cards home and plain editor."""
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
        empty_layout.addWidget(
            self._simple_empty_add,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
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
        self._simple_cards.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
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
        editor_header.setContentsMargins(0, 0, 0, 0)
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
            self._simple_content.document(),
            self._settings_ctrl.settings.theme,
        )

        self._floating_toolbar_simple = FloatingToolbar(
            self._simple_content,
            self._wrap_selection,
            self._i18n,
            self
        )
        editor_layout.addWidget(self._simple_content, 1)
        self._simple_stack.addWidget(self._simple_editor)

        self._view_stack.addWidget(self._simple_view)

    def _build_navigation_bar(self) -> None:
        """Build a persistent, uncluttered app and mode toolbar."""
        self._navigation_bar = QToolBar()
        self._navigation_bar.setObjectName("navigationBar")
        self._navigation_bar.setMovable(False)
        self._navigation_bar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._navigation_bar)

        self._nav_brand = QLabel("Ayran Notes")
        self._nav_brand.setObjectName("navigationBrand")
        self._navigation_bar.addWidget(self._nav_brand)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
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

    def _restore_main_splitter(self) -> None:
        """Restore the main splitter sizes from settings."""
        sizes = self._settings_ctrl.settings.main_splitter_sizes
        if sizes and len(sizes) == 3:
            self._main_splitter.setSizes(sizes)

    def _build_editor_toolbar(self) -> None:
        """Create compact Markdown and attachment actions."""
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
            
        self._toolbar_separator = self._editor_toolbar.addSeparator()
        self._act_sync_scroll = self._editor_toolbar.addAction("🔒")
        self._act_sync_scroll.setCheckable(True)
        self._act_sync_scroll.setChecked(False)
        
        self._toolbar_separator2 = self._editor_toolbar.addSeparator()
        self._act_attach_file = self._editor_toolbar.addAction("＋")
        self._act_attach_file.triggered.connect(lambda: self._attach_file(False))
        self._act_attach_image = self._editor_toolbar.addAction("▧")
        self._act_attach_image.triggered.connect(lambda: self._attach_file(True))
        self._toolbar_actions = {
            **self._format_actions,
            "attach_file": self._act_attach_file,
            "attach_image": self._act_attach_image,
        }

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
        self._act_file_attach = QAction(self)
        self._act_file_attach.triggered.connect(lambda: self._attach_file(False))
        self._file_menu.addAction(self._act_file_attach)
        self._act_image_attach = QAction(self)
        self._act_image_attach.triggered.connect(lambda: self._attach_file(True))
        self._file_menu.addAction(self._act_image_attach)
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

        # Edit
        self._edit_menu = mb.addMenu("")
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

        # View and mode
        self._view_menu = mb.addMenu("")
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
        self._act_sidebar.setChecked(self._settings_ctrl.settings.sidebar_visible)
        self._act_sidebar.triggered.connect(self._on_toggle_sidebar)
        self._view_menu.addAction(self._act_sidebar)

        self._act_preview = QAction(self)
        self._act_preview.setShortcut(QKeySequence("Ctrl+P"))
        self._act_preview.setCheckable(True)
        self._act_preview.setChecked(self._settings_ctrl.settings.preview_visible)
        self._act_preview.triggered.connect(self._on_toggle_preview)
        self._view_menu.addAction(self._act_preview)

        self._view_menu.addSeparator()
        self._act_zen_mode = QAction(self)
        self._act_zen_mode.setShortcuts([QKeySequence("F11"), QKeySequence("Ctrl+Shift+Z")])
        self._act_zen_mode.triggered.connect(self._toggle_zen_mode)
        self._view_menu.addAction(self._act_zen_mode)

        # Extras / customizable editor toolbar
        self._extras_menu = mb.addMenu("")
        self._customize_toolbar_menu = self._extras_menu.addMenu("")
        self._toolbar_toggle_actions = {}
        selected = set(self._settings_ctrl.settings.toolbar_actions)
        for key in self._toolbar_actions:
            toggle = QAction(self)
            toggle.setCheckable(True)
            toggle.setChecked(key in selected)
            toggle.toggled.connect(
                lambda checked, tool=key: self._set_toolbar_action_visible(tool, checked)
            )
            self._customize_toolbar_menu.addAction(toggle)
            self._toolbar_toggle_actions[key] = toggle
        self._extras_menu.addSeparator()
        self._act_reset_toolbar = QAction(self)
        self._act_reset_toolbar.triggered.connect(self._reset_toolbar)
        self._extras_menu.addAction(self._act_reset_toolbar)

        self._extras_menu.addSeparator()
        self._act_prefs = QAction(self)
        self._act_prefs.triggered.connect(self._on_open_settings)
        self._extras_menu.addAction(self._act_prefs)

        self._quick_menu = QMenu(self)
        self._quick_menu.addAction(self._act_import)
        self._quick_menu.addAction(self._act_export)
        self._quick_menu.addSeparator()
        self._quick_menu.addAction(self._act_prefs)
        self._nav_more.setMenu(self._quick_menu)

        # Help
        self._help_menu = mb.addMenu("")
        self._act_about = QAction(self)
        self._act_about.triggered.connect(self._on_about)
        self._help_menu.addAction(self._act_about)

    # Signal wiring

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
        self._tag_edit.textChanged.connect(self._schedule_save)
        self._content_edit.textChanged.connect(self._schedule_save)
        self._content_edit.textChanged.connect(self._update_preview)
        self._content_edit.textChanged.connect(self._update_status)
        self._content_edit.verticalScrollBar().valueChanged.connect(self._sync_preview_scroll)

        # Simple mode
        self._simple_search.textChanged.connect(lambda _: self._refresh_simple_cards())
        self._simple_add.clicked.connect(self._on_simple_new_note)
        self._simple_cards.itemClicked.connect(self._on_simple_card_clicked)
        self._simple_cards.customContextMenuRequested.connect(
            self._on_simple_card_context_menu
        )
        self._simple_back.clicked.connect(self._show_simple_home)
        self._simple_delete.clicked.connect(self._on_simple_delete)
        self._simple_title.textChanged.connect(self._schedule_simple_save)
        self._simple_content.textChanged.connect(self._schedule_simple_save)
        self._simple_empty_add.clicked.connect(self._on_simple_new_note)
        self._nav_simple.clicked.connect(
            lambda: self._change_view_mode("simple")
        )
        self._nav_detailed.clicked.connect(
            lambda: self._change_view_mode("detailed")
        )

        # Global shortcuts for Zen Mode (works when menuBar is hidden)
        self._shortcut_zen1 = QShortcut(QKeySequence("F11"), self)
        self._shortcut_zen1.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._shortcut_zen1.activated.connect(self._toggle_zen_mode)

        self._shortcut_zen2 = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self._shortcut_zen2.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._shortcut_zen2.activated.connect(self._toggle_zen_mode)

        self._shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._shortcut_esc.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._shortcut_esc.activated.connect(self._on_escape_key)


    # Translation

    def _retranslate(self) -> None:
        t = self._i18n.t
        self.setWindowTitle(t("app_name"))

        self._search.setPlaceholderText(t("search_placeholder"))
        self._new_btn.setText("+ " + t("new_note"))
        self._folder_label.setText(t("folders").upper())
        self._notes_label.setText(t("all_notes").upper())
        self._title_edit.setPlaceholderText(t("note_title_placeholder"))
        self._tag_edit.setPlaceholderText(t("tags_placeholder"))
        self._content_edit.setPlaceholderText(t("note_content_placeholder"))
        self._simple_search.setPlaceholderText(t("simple_search_placeholder"))
        self._simple_title.setPlaceholderText(t("note_title_placeholder"))
        self._simple_content.setPlaceholderText(t("simple_content_placeholder"))
        self._simple_add.setToolTip(t("new_note"))
        self._simple_back.setToolTip(t("back_to_notes"))
        self._simple_delete.setToolTip(t("move_to_trash"))

        self._simple_delete.setText(t("move_to_trash"))
        self._simple_heading.setText(t("notes_heading"))
        self._simple_empty_add.setText(t("new_note"))
        self._nav_simple.setText(t("simple_mode"))
        self._nav_detailed.setText(t("detailed_mode"))
        self._nav_more.setToolTip(t("more"))
        self._save_state_label.setText(t(self._save_state_key))
        # Menus
        self._file_menu.setTitle(t("file"))
        self._act_new.setText(t("new_note"))
        self._update_delete_action_text()
        self._act_file_attach.setText(t("attach_file"))
        self._act_image_attach.setText(t("attach_image"))
        self._act_import.setText(t("import"))
        self._act_export.setText(t("export"))
        self._act_quit.setText(t("close"))
        self._edit_menu.setTitle(t("edit"))
        self._act_undo.setText(t("undo"))
        self._act_redo.setText(t("redo"))
        self._act_find.setText(t("find"))
        self._act_replace.setText(t("replace"))
        self._act_simple_mode.setText(t("simple_mode"))
        self._act_detailed_mode.setText(t("detailed_mode"))
        self._view_menu.setTitle(t("view"))
        self._act_sidebar.setText(t("toggle_sidebar"))
        self._act_preview.setText(t("toggle_preview"))
        self._act_zen_mode.setText(t("zen_mode"))
        if hasattr(self, "_zen_exit_btn") and self._zen_exit_btn:
            self._zen_exit_btn.setText("✕  " + t("exit_zen_mode", "Exit Zen Mode (Esc)"))
            self._zen_exit_btn.adjustSize()
        self._extras_menu.setTitle(t("extras"))

        self._customize_toolbar_menu.setTitle(t("customize_toolbar"))
        self._act_reset_toolbar.setText(t("reset_toolbar"))
        for key, toggle in self._toolbar_toggle_actions.items():
            toggle.setText(t(key))
        self._act_prefs.setText(t("preferences"))
        self._help_menu.setTitle(t("help"))
        self._act_about.setText(t("about"))
        for key, action in self._format_actions.items():
            action.setToolTip(t(key))

        self._refresh_note_views()
        self._update_status()

    # Settings application

    def _apply_settings(self, s: AppSettings) -> None:
        theme = self._settings_ctrl.resolved_theme
        accent = self._settings_ctrl.resolved_accent_color
        qss = build_stylesheet(theme, accent, s.font_family, s.font_size)
        self.setStyleSheet(qss)
        self._content_highlighter.set_theme(theme)
        self._simple_content_highlighter.set_theme(theme)
        self._sidebar.setVisible(s.sidebar_visible)
        self._act_sidebar.setChecked(s.sidebar_visible)
        self._preview.setVisible(s.preview_visible)
        self._act_preview.setChecked(s.preview_visible)
        self._sync_toolbar_visibility(s.toolbar_actions)
        self._show_view_mode(s.view_mode)
        self._update_preview()
        
    def _set_toolbar_action_visible(self, key: str, visible: bool) -> None:
        """Add or remove a tool from the compact editor toolbar."""
        selected = [
            tool for tool in self._toolbar_actions
            if self._toolbar_toggle_actions[tool].isChecked()
        ]
        self._settings_ctrl.set_toolbar_actions(selected)

    def _sync_toolbar_visibility(self, selected_actions: list[str]) -> None:
        selected = {
            key for key in selected_actions
            if key in self._toolbar_actions
        }
        for key, action in self._toolbar_actions.items():
            action.setVisible(key in selected)
            toggle = self._toolbar_toggle_actions[key]
            toggle.blockSignals(True)
            toggle.setChecked(key in selected)
            toggle.blockSignals(False)
        has_formatting = bool(selected.intersection(self._format_actions))
        has_attachments = bool(selected.intersection({"attach_file", "attach_image"}))
        self._toolbar_separator.setVisible(has_formatting and has_attachments)
        self._editor_toolbar.setVisible(bool(selected))

    def _reset_toolbar(self) -> None:
        defaults = ["bold", "italic", "checklist"]
        self._settings_ctrl.set_toolbar_actions(defaults)

    # Simple / detailed mode

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
        
        new_widget = self._simple_view if simple else self._detailed_view
        if previous and previous is not new_widget:
            # Fade transition
            self._opacity_effect = QGraphicsOpacityEffect(self._view_stack)
            self._view_stack.setGraphicsEffect(self._opacity_effect)
            self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            self._anim.setDuration(250)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._anim.finished.connect(lambda: self._view_stack.setGraphicsEffect(None))
            
            self._view_stack.setCurrentWidget(new_widget)
            self._anim.start()
        else:
            self._view_stack.setCurrentWidget(new_widget)

        if simple:
            self._refresh_simple_cards()
        elif previous is not self._detailed_view:
            self._refresh_note_list()
            self._restore_detailed_context()
        elif not self._current_note:
            self._restore_detailed_context()

        self._update_statusbar_visibility()

    def _restore_detailed_context(self) -> None:
        """Open the selected note, or the first note, when detail mode appears."""
        preferred_id = (
            self._current_note.id
            if self._current_note else self._last_detailed_note_id
        )
        candidate = None
        note_id = None
        if preferred_id:
            candidate = next(
                (
                    self._note_list.item(row)
                    for row in range(self._note_list.count())
                    if self._note_list.item(row).data(
                        Qt.ItemDataRole.UserRole
                    ) == preferred_id
                ),
                None,
            )
            if candidate is not None:
                note_id = preferred_id
        if not note_id:
            candidate = self._note_list.currentItem()
        if not note_id and candidate is not None:
            note_id = candidate.data(Qt.ItemDataRole.UserRole)
        if not note_id:
            candidate = next(
                (
                    self._note_list.item(row)
                    for row in range(self._note_list.count())
                    if self._note_list.item(row).data(
                        Qt.ItemDataRole.UserRole
                    )
                ),
                None,
            )
            note_id = (
                candidate.data(Qt.ItemDataRole.UserRole)
                if candidate is not None else None
            )
        if note_id:
            self._note_list.blockSignals(True)
            self._note_list.setCurrentItem(candidate)
            self._note_list.blockSignals(False)
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

    def _remove_abandoned_empty_notes(self) -> None:
        active_id = self._current_note.id if self._current_note else None
        for note in self._note_ctrl.list_notes("__all__"):
            if (
                note.id != active_id
                and note.is_simple_draft
                and self._is_empty_simple_note(note)
            ):
                self._note_ctrl.delete_note(note.id)

    def _refresh_simple_cards(self) -> None:
        self._remove_abandoned_empty_notes()
        query = self._simple_search.text().strip()
        notes = (
            self._note_ctrl.search(query, "__all__")
            if query else self._note_ctrl.list_notes("__all__")
        )
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
            labels = []
            if note.is_favorite:
                labels.append(self._i18n.t("favorite"))
            if note.is_pinned:
                labels.append(self._i18n.t("pinned"))
            labels.extend(
                [note.folder, self._format_note_date(note.updated_at)]
            )
            metadata = "  ·  ".join(filter(None, labels))

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
            snippet_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            card_layout.addWidget(snippet_label, 1)

            metadata_label = QLabel(metadata)
            metadata_label.setObjectName("noteCardMetadata")
            card_layout.addWidget(metadata_label)
            self._simple_cards.setItemWidget(item, card)

    def _on_simple_card_clicked(self, item: QListWidgetItem) -> None:
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if note_id:
            self._load_simple_note(note_id)

    def _on_simple_card_context_menu(self, pos) -> None:
        item = self._simple_cards.itemAt(pos)
        if not item:
            return
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if not note_id:
            return
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return
        t = self._i18n.t
        menu = QMenu(self)

        favorite_action = menu.addAction(
            t("remove_from_favorites")
            if note.is_favorite else t("add_to_favorites")
        )
        favorite_action.triggered.connect(
            lambda checked=False: self._toggle_favorite(note_id)
        )
        pin_action = menu.addAction(
            t("unpin_note") if note.is_pinned else t("pin_note")
        )
        pin_action.triggered.connect(
            lambda checked=False: self._toggle_pin(note_id)
        )
        archive_action = menu.addAction(t("archive_note"))
        archive_action.triggered.connect(
            lambda checked=False: self._set_archived(note_id, True)
        )

        menu.addSeparator()
        delete_action = menu.addAction(t("move_to_trash"))
        delete_action.triggered.connect(
            lambda checked=False: self._confirm_simple_trash(note_id)
        )
        menu.exec(self._simple_cards.mapToGlobal(pos))

    def _load_simple_note(self, note_id: str) -> None:
        if self._current_note and self._current_note.id != note_id:
            if not self._flush_all_edits():
                return
            self._discard_empty_simple_note()
        note = self._note_ctrl.get_note(note_id)
        if not note:
            return
        self._current_note = note
        self._simple_content_highlighter.set_highlighting_enabled(
            note.is_markdown
        )
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
        if self._simple_editor_is_active():
            self._discard_empty_simple_note()
        note = self._note_ctrl.create_note(
            "",
            "General",
            simple_draft=True,
        )
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

    @staticmethod
    def _is_empty_simple_note(
        note: Note,
        title: str | None = None,
        content: str | None = None,
    ) -> bool:
        """Return whether a simple-mode draft contains no useful information."""
        visible_title = note.title if title is None else title
        visible_content = note.content if content is None else content
        empty_titles = {"", "Untitled", "Başlıksız"}
        return (
            visible_title.strip() in empty_titles
            and not note.is_pinned
            and not note.is_favorite
            and note.folder == "General"
            and not visible_content.strip()
            and not note.tags
            and not note.attachments
        )

    def _discard_empty_simple_note(self) -> bool:
        """Permanently remove the active blank draft without filling Trash."""
        if not self._simple_editor_is_active():
            return False
        note = self._current_note
        if not note or not self._is_empty_simple_note(
            note,
            self._simple_title.text(),
            self._simple_content.toPlainText(),
        ):
            return False
        note_id = note.id
        if not self._note_ctrl.delete_note(note_id):
            return False
        self._clear_current_note(note_id)
        return True

    def _on_simple_delete(self) -> None:
        if self._current_note:
            self._confirm_simple_trash(self._current_note.id)

    def _confirm_simple_trash(self, note_id: str) -> None:
        reply = QMessageBox.question(
            self,
            self._i18n.t("move_to_trash"),
            self._i18n.t("confirm_trash"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._trash_note(note_id)

    def _schedule_simple_save(self) -> None:
        if self._current_note:
            self._simple_dirty = True
            self._simple_save_timer.start()
            self._set_save_state("saving")
            self._update_status()

    def _flush_simple_save(self) -> bool:
        if self._simple_save_timer.isActive():
            self._simple_save_timer.stop()
        if self._simple_dirty:
            return self._auto_save_simple()
        return True

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
        return True

    def _flush_all_edits(self) -> bool:
        if not self._flush_pending_save():
            return False
        return self._flush_simple_save()

    # Sidebar handlers

    def _refresh_folder_list(self) -> None:
        self._folder_list.blockSignals(True)
        self._folder_list.clear()
        all_item = QListWidgetItem(self._i18n.t("all_notes"))
        all_item.setData(Qt.ItemDataRole.UserRole, "__all__")
        self._folder_list.addItem(all_item)
        for label_key, value in (
            ("favorites", "__favorites__"),
            ("archive", "__archive__"),
            ("trash", "__trash__"),
        ):
            item = QListWidgetItem(self._i18n.t(label_key))
            item.setData(Qt.ItemDataRole.UserRole, value)
            self._folder_list.addItem(item)
        for folder in self._note_ctrl.get_folders():
            item = QListWidgetItem(folder)
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
                prefix = (
                    ("★ " if note.is_favorite else "")
                    + ("● " if note.is_pinned else "")
                )
                display = prefix + (note.title or self._i18n.t("untitled"))
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, note.id)
                self._note_list.addItem(item)
                # Auto-select the current note
                if self._current_note and note.id == self._current_note.id:
                    self._note_list.setCurrentItem(item)

        self._note_list.blockSignals(False)
        if (
            self._view_stack.currentWidget() is self._detailed_view
            and not self._current_note
        ):
            self._restore_detailed_context()

    def _on_folder_selected(self, row: int) -> None:
        item = self._folder_list.item(row)
        if item:
            self._current_folder = item.data(Qt.ItemDataRole.UserRole)
            self._update_delete_action_text()
            self._refresh_note_list()

    def _update_delete_action_text(self) -> None:
        key = (
            "delete_permanently"
            if self._current_folder == "__trash__" else "move_to_trash"
        )
        self._act_delete.setText(self._i18n.t(key))

    def _on_note_selected(self, row: int) -> None:
        item = self._note_list.item(row)
        if item:
            note_id = item.data(Qt.ItemDataRole.UserRole)
            if note_id:
                self._load_note(note_id)

    def _on_search(self, _text: str) -> None:
        self._refresh_note_list()

    # Note CRUD

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
        self._content_highlighter.set_highlighting_enabled(note.is_markdown)
        self._title_edit.blockSignals(True)
        self._tag_edit.blockSignals(True)
        self._content_edit.blockSignals(True)
        self._title_edit.setText(note.title)
        self._tag_edit.setText(", ".join(note.tags))
        self._content_edit.setPlainText(note.content)
        self._title_edit.blockSignals(False)
        self._tag_edit.blockSignals(False)
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
        folder = self._current_folder if self._current_folder and self._current_folder != "__all__" else "General"
        if folder.startswith("__"):
            folder = "General"
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
        if self._current_folder == "__trash__":
            self._delete_specific_note(self._current_note.id)
        else:
            self._trash_note(self._current_note.id)

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

        if note.is_trashed:
            restore_action = menu.addAction(t("restore_note"))
            restore_action.triggered.connect(lambda: self._restore_note(note_id))
            menu.addSeparator()
            delete_action = menu.addAction(t("delete_permanently"))
            delete_action.triggered.connect(lambda: self._delete_specific_note(note_id))
            menu.exec(self._note_list.mapToGlobal(pos))
            return

        favorite_text = (
            t("remove_from_favorites") if note.is_favorite else t("add_to_favorites")
        )
        favorite_action = menu.addAction(favorite_text)
        favorite_action.triggered.connect(lambda: self._toggle_favorite(note_id))

        # Pin / Unpin
        pin_text = t("unpin_note") if note.is_pinned else t("pin_note")
        pin_action = menu.addAction(pin_text)
        pin_action.triggered.connect(lambda: self._toggle_pin(note_id))

        archive_text = t("unarchive_note") if note.is_archived else t("archive_note")
        archive_action = menu.addAction(archive_text)
        archive_action.triggered.connect(
            lambda: self._set_archived(note_id, not note.is_archived)
        )

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
        trash_action = menu.addAction(t("move_to_trash"))
        trash_action.triggered.connect(lambda: self._trash_note(note_id))

        menu.exec(self._note_list.mapToGlobal(pos))

    def _refresh_note_views(self) -> None:
        self._refresh_note_list()
        self._refresh_simple_cards()

    def _toggle_pin(self, note_id: str) -> None:
        if not self._flush_all_edits():
            return
        updated = self._note_ctrl.toggle_pin(note_id)
        if updated and self._current_note and self._current_note.id == note_id:
            self._current_note = updated
        self._refresh_note_views()

    def _toggle_favorite(self, note_id: str) -> None:
        if not self._flush_all_edits():
            return
        updated = self._note_ctrl.toggle_favorite(note_id)
        if updated and self._current_note and self._current_note.id == note_id:
            self._current_note = updated
        self._refresh_note_views()

    def _set_archived(self, note_id: str, archived: bool) -> None:
        if not self._flush_all_edits():
            return
        self._note_ctrl.set_archived(note_id, archived)
        self._clear_current_note(note_id)
        self._refresh_note_views()

    def _trash_note(self, note_id: str) -> None:
        if not self._flush_all_edits():
            return
        self._note_ctrl.move_to_trash(note_id)
        self._clear_current_note(note_id)
        self._refresh_note_views()

    def _restore_note(self, note_id: str) -> None:
        if not self._flush_all_edits():
            return
        self._note_ctrl.restore_note(note_id)
        self._clear_current_note(note_id)
        self._refresh_note_views()

    def _clear_editor_fields(self) -> None:
        for editor in (self._title_edit, self._tag_edit, self._content_edit):
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        for editor in (self._simple_title, self._simple_content):
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        self._content_highlighter.set_highlighting_enabled(False)
        self._simple_content_highlighter.set_highlighting_enabled(False)
        self._preview.clear()
        self._set_detailed_editor_enabled(False)

    def _set_detailed_editor_enabled(self, enabled: bool) -> None:
        """Prevent text entry when no detailed note can receive it."""
        for widget in (
            self._title_edit,
            self._tag_edit,
            self._content_edit,
            self._editor_toolbar,
        ):
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
        self._refresh_simple_cards()
        self._update_status()

    def _move_note(self, note_id: str, folder: str) -> None:
        if not self._flush_all_edits():
            return
        updated = self._note_ctrl.move_to_folder(note_id, folder)
        if updated and self._current_note and self._current_note.id == note_id:
            self._current_note = updated
        self._refresh_note_views()

    def _create_folder_and_move(self, note_id: str) -> None:
        name, ok = QInputDialog.getText(
            self, self._i18n.t("new_folder"), self._i18n.t("new_folder") + ":"
        )
        if ok and name.strip():
            self._move_note(note_id, name.strip())

    def _delete_specific_note(self, note_id: str) -> None:
        reply = QMessageBox.question(
            self,
            self._i18n.t("confirm_delete_title"),
            self._i18n.t("confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._note_ctrl.delete_note(note_id)
            self._clear_current_note(note_id)
            self._refresh_note_views()

    # Editor tools

    def _active_content_editor(self) -> QPlainTextEdit:
        """Return the editor that is actually visible to the user."""
        if (
            self._view_stack.currentWidget() is self._simple_view
            and self._simple_stack.currentWidget() is self._simple_editor
        ):
            return self._simple_content
        return self._content_edit

    def _simple_home_is_active(self) -> bool:
        return (
            self._view_stack.currentWidget() is self._simple_view
            and self._simple_stack.currentWidget() is self._simple_home
        )

    def _simple_editor_is_active(self) -> bool:
        return (
            self._view_stack.currentWidget() is self._simple_view
            and self._simple_stack.currentWidget() is self._simple_editor
        )

    def _undo_active(self) -> None:
        if not self._simple_home_is_active():
            self._active_content_editor().undo()

    def _redo_active(self) -> None:
        if not self._simple_home_is_active():
            self._active_content_editor().redo()

    def _wrap_selection(self, prefix: str, suffix: str, placeholder: str) -> None:
        """Wrap selected editor text with Markdown tokens."""
        if not self._current_note:
            return
        editor = self._active_content_editor()
        cursor = editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        cursor.insertText(f"{prefix}{selected or placeholder}{suffix}")
        editor.setTextCursor(cursor)
        editor.setFocus()

    def _prefix_line(self, prefix: str) -> None:
        """Insert a Markdown prefix at the beginning of the current line."""
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
        query, accepted = QInputDialog.getText(
            self, self._i18n.t("find"), self._i18n.t("find") + ":"
        )
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
        old, accepted = QInputDialog.getText(
            self, self._i18n.t("replace"), self._i18n.t("find") + ":"
        )
        if not accepted or not old:
            return
        new, accepted = QInputDialog.getText(
            self, self._i18n.t("replace"), self._i18n.t("replace_with") + ":"
        )
        if not accepted:
            return
        editor = self._active_content_editor()
        content = editor.toPlainText()
        count = content.count(old)
        if count:
            editor.setPlainText(content.replace(old, new))
            self._statusbar.showMessage(
                self._i18n.t("replacements_count", count=count),
                3000,
            )
        else:
            self._statusbar.showMessage(self._i18n.t("text_not_found"), 3000)

    def _attach_file(self, image: bool) -> None:
        if not self._current_note:
            return
        file_filter = (
            self._i18n.t("image_files") + " (*.png *.jpg *.jpeg *.gif *.webp *.svg)"
            if image else self._i18n.t("all_files") + " (*)"
        )
        source, _ = QFileDialog.getOpenFileName(
            self,
            self._i18n.t("attach_image") if image else self._i18n.t("attach_file"),
            "",
            file_filter,
        )
        if not source:
            return
        if not self._flush_all_edits():
            return
        try:
            destination = self._note_ctrl.add_attachment(
                self._current_note.id,
                Path(source),
            )
        except OSError as error:
            self._statusbar.showMessage(f"Attachment failed: {error}", 5000)
            return
        if not destination:
            return
        persisted = self._note_ctrl.get_note(self._current_note.id)
        if persisted:
            self._current_note.attachments = persisted.attachments
        label = destination.name
        markdown_link = (
            f"![{label}]({destination.as_uri()})"
            if image else f"[{label}]({destination.as_uri()})"
        )
        target = (
            self._simple_content
            if (
                self._view_stack.currentWidget() is self._simple_view
                and self._simple_stack.currentWidget() is self._simple_editor
            )
            else self._content_edit
        )
        target.textCursor().insertText(markdown_link)

    def _export_current_note(self) -> None:
        """Export the active note to a user-selected portable format."""
        if not self._current_note:
            self._statusbar.showMessage(self._i18n.t("select_note_to_export"), 3000)
            return
        if not self._flush_all_edits():
            return
        safe_title = re.sub(r"[^\w .-]+", "_", self._current_note.title).strip(" .")
        safe_title = safe_title or "note"
        t = self._i18n.t
        filters = ";;".join((
            f"{t('markdown_files')} (*.md)",
            f"{t('text_files')} (*.txt)",
            f"{t('html_files')} (*.html)",
            f"{t('pdf_files')} (*.pdf)",
        ))
        destination, selected_filter = QFileDialog.getSaveFileName(
            self,
            t("export"),
            str(Path.home() / f"{safe_title}.md"),
            filters,
        )
        if not destination:
            return
        path = Path(destination)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            suffix_by_filter = {
                t("markdown_files"): ".md",
                t("text_files"): ".txt",
                t("html_files"): ".html",
                t("pdf_files"): ".pdf",
            }
            suffix = next(
                (value for label, value in suffix_by_filter.items() if selected_filter.startswith(label)),
                ".md",
            )
            path = path.with_name(path.name + suffix)
        try:
            export_note(self._current_note, path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self,
                t("export_failed"),
                t("export_failed_detail", error=str(error)),
            )
            return
        self._statusbar.showMessage(t("export_success", path=str(path)), 5000)

    def _import_notes(self) -> None:
        """Import one or more external files as new notes."""
        t = self._i18n.t
        filters = ";;".join((
            f"{t('supported_note_files')} (*.md *.markdown *.txt *.html *.htm *.json)",
            f"{t('markdown_files')} (*.md *.markdown)",
            f"{t('text_files')} (*.txt)",
            f"{t('html_files')} (*.html *.htm)",
            f"{t('json_files')} (*.json)",
        ))
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            t("import"),
            str(Path.home()),
            filters,
        )
        if not filenames:
            return
        if not self._flush_all_edits():
            return
        current_folder = self._current_folder or "General"
        if current_folder.startswith("__"):
            current_folder = "General"

        imported_notes = []
        failures = []
        for filename in filenames:
            try:
                imported = import_note(Path(filename))
                note = self._note_ctrl.create_note(
                    imported.title,
                    imported.folder or current_folder,
                )
                note.content = imported.content
                note.tags = imported.tags
                note.is_markdown = imported.is_markdown
                self._note_ctrl.save_note(note)
                imported_notes.append(note)
            except (OSError, ValueError, TypeError) as error:
                failures.append(f"{Path(filename).name}: {error}")

        if imported_notes:
            last_note = imported_notes[-1]
            self._current_folder = (
                last_note.folder if last_note.folder in self._note_ctrl.get_folders()
                else "__all__"
            )
            self._refresh_note_list()
            if self._view_stack.currentWidget() is self._simple_view:
                self._refresh_simple_cards()
                self._load_simple_note(last_note.id)
            else:
                self._load_note(last_note.id)
            self._statusbar.showMessage(
                t("import_success", count=len(imported_notes)),
                5000,
            )
        if failures:
            QMessageBox.warning(
                self,
                t("import_failed"),
                t("import_failed_detail", errors="\n".join(failures)),
            )

    # Auto-save

    def _schedule_save(self) -> None:
        if self._current_note:
            self._dirty = True
            self._save_timer.start()

            self._set_save_state("saving")

    def _flush_pending_save(self) -> bool:
        """Synchronously save the active note before changing editor context."""
        if self._save_timer.isActive():
            self._save_timer.stop()
        if self._dirty:
            return self._auto_save()
        return True

    def _auto_save(self) -> bool:
        if not self._current_note or not self._dirty:
            return True
        self._current_note.title = self._title_edit.text()
        self._current_note.tags = list(dict.fromkeys(
            tag.strip()
            for tag in self._tag_edit.text().split(",")
            if tag.strip()
        ))
        self._current_note.content = self._content_edit.toPlainText()
        try:
            self._note_ctrl.save_note(self._current_note)
        except (OSError, ValueError) as error:
            self._statusbar.showMessage(str(error), 5000)
            self._set_save_state("save_failed")
            return False
        self._dirty = False
        # Refresh list to show updated title
        self._set_save_state("saved")
        self._refresh_note_list()

        return True

    # Preview & Status

    def _update_preview(self, reset_scroll: bool = False) -> None:
        if not hasattr(self, "_preview") or not self._preview.isVisible():
            return


        sync = hasattr(self, "_act_sync_scroll") and self._act_sync_scroll.isChecked()
        v_bar = self._preview.verticalScrollBar()
        h_bar = self._preview.horizontalScrollBar()
        v_pos = 0 if reset_scroll else v_bar.value()
        h_pos = 0 if reset_scroll else h_bar.value()

        text = self._content_edit.toPlainText()
        
        sync_marker = "SYNC_MARK_1234567890"
        if sync and not reset_scroll:
            cursor = self._content_edit.textCursor()
            pos = cursor.position()
            text = text[:pos] + sync_marker + text[pos:]

        if self._current_note and self._current_note.is_markdown:
            settings = self._settings_ctrl.settings
            html = render_markdown_html(
                text,
                theme=settings.theme,
                accent=settings.accent_color,
                font_family=settings.font_family,
                font_size=settings.font_size,
            )
            self._preview.setHtml(html)
        else:
            self._preview.setPlainText(text)

        if sync and not reset_scroll:
            doc = self._preview.document()
            found_cursor = doc.find(sync_marker)
            if not found_cursor.isNull():
                found_cursor.removeSelectedText()
                self._preview.setTextCursor(found_cursor)
                self._preview.ensureCursorVisible()
        elif not reset_scroll:
            v_bar.setValue(v_pos)
            h_bar.setValue(h_pos)
            QTimer.singleShot(0, lambda: (v_bar.setValue(v_pos), h_bar.setValue(h_pos)))

    def _sync_preview_scroll(self) -> None:
        if not hasattr(self, "_act_sync_scroll") or not self._act_sync_scroll.isChecked():
            return
        if not hasattr(self, "_preview") or not self._preview.isVisible():
            return
            
        e_sb = self._content_edit.verticalScrollBar()
        p_sb = self._preview.verticalScrollBar()
        
        if e_sb.maximum() > 0:
            ratio = e_sb.value() / e_sb.maximum()
            p_sb.setValue(int(ratio * p_sb.maximum()))


    def _set_save_state(self, key: str) -> None:
        self._save_state_key = key
        self._save_state_label.setText(self._i18n.t(key))
        state = "error" if key == "save_failed" else "normal"
        self._save_state_label.setProperty("state", state)
        self._save_state_label.style().unpolish(self._save_state_label)
        self._save_state_label.style().polish(self._save_state_label)

    def _update_statusbar_visibility(self) -> None:
        simple_home = (
            self._view_stack.currentWidget() is self._simple_view
            and self._simple_stack.currentWidget() is self._simple_home
        )
        self._statusbar.setVisible(not simple_home)

    def _update_status(self) -> None:
        simple_mode = self._view_stack.currentWidget() is self._simple_view
        if simple_mode:
            text = (
                self._simple_content.toPlainText()
                if self._simple_stack.currentWidget() is self._simple_editor else ""
            )
        else:
            text = self._content_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        self._word_label.setText(self._i18n.t("word_count", count=words))
        self._char_label.setText("  ·  " + self._i18n.t("char_count", count=chars))

    # View toggles

    def _on_toggle_sidebar(self, checked: bool) -> None:
        self._settings_ctrl.set_sidebar_visible(checked)

    def _on_toggle_preview(self, checked: bool) -> None:
        self._settings_ctrl.set_preview_visible(checked)

    def _on_escape_key(self) -> None:
        if self._in_zen_mode:
            self._exit_zen_mode()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._in_zen_mode and event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F11):
            self._exit_zen_mode()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_zen_exit_btn") and self._zen_exit_btn and self._zen_exit_btn.isVisible():
            self._zen_exit_btn.move(max(10, self.width() - self._zen_exit_btn.width() - 25), 18)

    def _toggle_zen_mode(self) -> None:
        if self._in_zen_mode:
            self._exit_zen_mode()
        else:
            self._enter_zen_mode()

    def _enter_zen_mode(self) -> None:
        if self._view_stack.currentWidget() is not self._detailed_view:
            self._change_view_mode("detailed")
            
        self._in_zen_mode = True
        self._zen_pre_state = {
            "sidebar": self._settings_ctrl.settings.sidebar_visible,
            "toolbar": self._settings_ctrl.settings.toolbar_actions,
            "preview": self._settings_ctrl.settings.preview_visible,
            "fullscreen": self.isFullScreen(),
            "maximized": self.isMaximized(),
        }
        
        self._sidebar.setVisible(False)
        self._editor_toolbar.setVisible(False)
        self._preview.setVisible(False)
        self.menuBar().setVisible(False)
        self._navigation_bar.setVisible(False)
        self._statusbar.setVisible(False)
        
        self._editor_container.setMaximumWidth(800)
        self._editor_left_stretch.show()
        self._editor_right_stretch.show()
        
        if hasattr(self, "_zen_exit_btn") and self._zen_exit_btn:
            t = self._i18n.t
            self._zen_exit_btn.setText("✕  " + t("exit_zen_mode", "Exit Zen Mode (Esc)"))
            self._zen_exit_btn.adjustSize()
            self._zen_exit_btn.move(max(10, self.width() - self._zen_exit_btn.width() - 25), 18)
            self._zen_exit_btn.show()
            self._zen_exit_btn.raise_()

        if not self.isFullScreen():
            self.showFullScreen()

    def _exit_zen_mode(self) -> None:
        self._in_zen_mode = False

        if hasattr(self, "_zen_exit_btn") and self._zen_exit_btn:
            self._zen_exit_btn.hide()
        
        # Restore widgets
        self._sidebar.setVisible(self._zen_pre_state.get("sidebar", True))
        self._sync_toolbar_visibility(self._zen_pre_state.get("toolbar", []))
        self._preview.setVisible(self._zen_pre_state.get("preview", True))
        self.menuBar().setVisible(True)
        self._navigation_bar.setVisible(True)
        self._statusbar.setVisible(True)
        
        self._editor_container.setMaximumWidth(16777215) # Default max size
        self._editor_left_stretch.hide()
        self._editor_right_stretch.hide()
        
        if not self._zen_pre_state.get("fullscreen", False):
            if self._zen_pre_state.get("maximized", False):
                self.showMaximized()
            else:
                self.showNormal()


    # Settings / About dialogs

    def _on_open_settings(self) -> None:
        if not self._flush_all_edits():
            return
        previous_notes_directory = self._note_ctrl.notes_directory
        dlg = SettingsDialog(self._settings_ctrl, self._i18n, self)
        dlg.exec()
        if self._note_ctrl.notes_directory != previous_notes_directory:
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

    # Window lifecycle

    def closeEvent(self, event) -> None:
        # Save any pending edits
        if not self._flush_all_edits():
            QMessageBox.critical(
                self,
                self._i18n.t("save_failed_title"),
                self._i18n.t("save_failed_close"),
            )
            event.ignore()
            return
        if self._simple_stack.currentWidget() is self._simple_editor:
            self._discard_empty_simple_note()
        # Save window geometry
        g = (
            self.normalGeometry()
            if self.isMaximized() or self.isFullScreen()
            else self.geometry()
        )
        self._settings_ctrl.save_window_geometry(g.x(), g.y(), g.width(), g.height())
        self._settings_ctrl.save_sidebar_folder_height(self._sidebar_splitter.sizes()[0])
        self._settings_ctrl.save_main_splitter_sizes(self._main_splitter.sizes())
        super().closeEvent(event)
