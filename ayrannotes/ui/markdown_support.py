"""Markdown syntax highlighting and HTML preview helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from pygments import lex
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.util import ClassNotFound
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)

_OPENING_FENCE = re.compile(
    r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*([^ \t`~]+)?(?:[ \t].*)?$"
)
_CLOSING_FENCE = re.compile(r"^[ \t]{0,3}([`~]+)[ \t]*$")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def pygments_style_for_theme(theme: str) -> str:
    """Return a stable Pygments style for an application theme."""
    return "friendly" if theme == "light" else "native"


@dataclass(frozen=True)
class _Fence:
    marker: str
    minimum_length: int
    language: str


class MarkdownSyntaxHighlighter(QSyntaxHighlighter):
    """Highlight Pygments tokens only inside Markdown fenced code blocks."""

    def __init__(
        self,
        document: QTextDocument,
        theme: str = "dark",
    ) -> None:
        super().__init__(document)
        self._theme = "light" if theme == "light" else "dark"
        self._highlighting_enabled = True
        self._state_for_fence: dict[_Fence, int] = {}
        self._fence_for_state: dict[int, _Fence] = {}
        self._next_state = 1
        self._lexer_cache: dict[str, object] = {}
        self._format_cache: dict[object, QTextCharFormat] = {}
        fixed_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )
        self._fixed_font_family = fixed_font.family()
        self._configure_formats()

    @property
    def theme(self) -> str:
        return self._theme

    @property
    def highlighting_enabled(self) -> bool:
        return self._highlighting_enabled

    def set_theme(self, theme: str) -> None:
        """Update token colors and rehighlight the attached document."""
        normalized = "light" if theme == "light" else "dark"
        if normalized == self._theme:
            return
        self._theme = normalized
        self._configure_formats()
        self.rehighlight()

    def set_highlighting_enabled(self, enabled: bool) -> None:
        """Enable fenced-code highlighting for Markdown notes only."""
        enabled = bool(enabled)
        if enabled == self._highlighting_enabled:
            return
        self._highlighting_enabled = enabled
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not self._highlighting_enabled:
            self.setCurrentBlockState(0)
            return

        previous_state = self.previousBlockState()
        fence = self._fence_for_state.get(previous_state)
        if fence is not None:
            if self._is_closing_fence(text, fence):
                self.setFormat(0, len(text), self._fence_format)
                self.setCurrentBlockState(0)
            else:
                self._highlight_code(text, fence.language)
                self.setCurrentBlockState(previous_state)
            return

        opening = _OPENING_FENCE.match(text)
        if opening is None:
            self.setCurrentBlockState(0)
            return

        marker = opening.group(1)
        fence = _Fence(
            marker=marker[0],
            minimum_length=len(marker),
            language=self._normalize_language(opening.group(2) or ""),
        )
        self.setFormat(0, len(text), self._fence_format)
        self.setCurrentBlockState(self._state_for(fence))

    def _configure_formats(self) -> None:
        self._style = get_style_by_name(pygments_style_for_theme(self._theme))
        self._format_cache.clear()

        self._base_code_format = QTextCharFormat()
        self._base_code_format.setFontFamily(self._fixed_font_family)
        default = "#F8F8F2" if self._theme == "dark" else "#333333"
        self._base_code_format.setForeground(QColor(default))

        self._fence_format = QTextCharFormat(self._base_code_format)
        fence_color = "#8E8E93" if self._theme == "dark" else "#6E6E73"
        self._fence_format.setForeground(QColor(fence_color))

    def _state_for(self, fence: _Fence) -> int:
        state = self._state_for_fence.get(fence)
        if state is not None:
            return state
        state = self._next_state
        self._next_state += 1
        self._state_for_fence[fence] = state
        self._fence_for_state[state] = fence
        return state

    @staticmethod
    def _normalize_language(info: str) -> str:
        language = info.strip()
        if language.startswith("{."):
            language = language[2:].split()[0].rstrip("}")
        elif language.startswith("."):
            language = language[1:]
        return language.lower()

    @staticmethod
    def _is_closing_fence(text: str, fence: _Fence) -> bool:
        match = _CLOSING_FENCE.match(text)
        if match is None:
            return False
        marker = match.group(1)
        return (
            marker[0] == fence.marker
            and len(marker) >= fence.minimum_length
            and set(marker) == {fence.marker}
        )

    def _lexer_for(self, language: str):
        cache_key = language or "__text__"
        lexer = self._lexer_cache.get(cache_key)
        if lexer is not None:
            return lexer
        try:
            lexer = (
                get_lexer_by_name(
                    language,
                    stripnl=False,
                    ensurenl=False,
                )
                if language
                else TextLexer(stripnl=False, ensurenl=False)
            )
        except ClassNotFound:
            lexer = TextLexer(stripnl=False, ensurenl=False)
        self._lexer_cache[cache_key] = lexer
        return lexer

    def _format_for_token(self, token) -> QTextCharFormat:
        cached = self._format_cache.get(token)
        if cached is not None:
            return cached

        token_style = self._style.style_for_token(token)
        text_format = QTextCharFormat(self._base_code_format)
        color = token_style.get("color")
        if color:
            text_format.setForeground(QColor("#" + color))
        if token_style.get("bold"):
            text_format.setFontWeight(QFont.Weight.Bold)
        if token_style.get("italic"):
            text_format.setFontItalic(True)
        if token_style.get("underline"):
            text_format.setFontUnderline(True)
        self._format_cache[token] = text_format
        return text_format

    def _highlight_code(self, text: str, language: str) -> None:
        if not text:
            return
        self.setFormat(0, len(text), self._base_code_format)
        offset = 0
        for token, value in lex(text, self._lexer_for(language)):
            if offset >= len(text):
                break
            length = min(len(value), len(text) - offset)
            if length:
                self.setFormat(offset, length, self._format_for_token(token))
            offset += len(value)


def render_markdown_html(
    text: str,
    *,
    theme: str = "dark",
    accent: str = "#F59E0B",
    font_family: str = "Inter",
    font_size: int = 14,
) -> str:
    """Render Markdown with Pygments code colors and Ayran Notes styling."""
    normalized_theme = "light" if theme == "light" else "dark"
    style_name = pygments_style_for_theme(normalized_theme)
    body = markdown.markdown(
        text,
        extensions=[
            "fenced_code",
            CodeHiliteExtension(
                css_class="highlight",
                guess_lang=False,
                pygments_style=style_name,
            ),
            "tables",
            "nl2br",
        ],
    )
    body = re.sub(
        r"<li>\s*\[([ xX])\]\s*",
        lambda match: (
            '<li class="task-item"><span class="task-box">'
            + ("☑" if match.group(1).lower() == "x" else "☐")
            + "</span> "
        ),
        body,
    )

    safe_accent = accent if _HEX_COLOR.fullmatch(accent) else "#F59E0B"
    safe_font = font_family.replace("\\", "\\\\").replace('"', '\\"')
    size = max(8, min(int(font_size), 32))
    if normalized_theme == "light":
        foreground = "#1D1D1F"
        background = "#FAFAFC"
        code_background = "#F0F0F4"
        code_color = "#24292F"
        code_border = "#E1E4E8"
        secondary = "#6E6E73"
        border = "#D7D7DC"
    else:
        foreground = "#F5F5F7"
        background = "#1F1F21"
        code_background = "#2A2A2D"
        code_color = "#F5F5F7"
        code_border = "#3A3A3C"
        secondary = "#AEAEB2"
        border = "#3A3A3C"

    pygments_css = HtmlFormatter(style=style_name).get_style_defs(".highlight")
    return f"""
    <style>
        {pygments_css}
        body {{ color: {foreground}; background: {background}; font-family: "{safe_font}", sans-serif; font-size: {size}px; line-height: 1.7; padding: 8px; }}
        h1, h2, h3 {{ color: {safe_accent}; margin-top: 16px; }}
        a {{ color: {safe_accent}; }}
        code {{ color: {code_color}; background-color: {code_background}; border: 1px solid {code_border}; padding: 2px 6px; border-radius: 4px; font-family: "Fira Code", monospace; font-size: {max(8, size - 1)}px; }}
        .highlight {{ background-color: {code_background}; border: 1px solid {code_border}; border-radius: 8px; }}
        .highlight pre {{ background-color: transparent; padding: 12px; margin: 0; white-space: pre-wrap; }}
        .highlight code {{ color: inherit; background-color: transparent; border: none; padding: 0; }}
        blockquote {{ border-left: 3px solid {safe_accent}; padding-left: 12px; color: {secondary}; margin: 8px 0; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid {border}; padding: 8px; text-align: left; }}
        th {{ background-color: {code_background}; }}
        li.task-item {{ list-style: none; margin-left: -20px; }}
        span.task-box {{ color: {safe_accent}; margin-right: 7px; }}
        hr {{ border: none; border-top: 1px solid {border}; margin: 16px 0; }}
    </style>
    {body}
    """

