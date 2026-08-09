"""Tests for fenced-code highlighting and Markdown preview rendering."""

import unittest

from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import QApplication

from beernotes.ui.markdown_support import (
    MarkdownSyntaxHighlighter,
    render_markdown_html,
)


class MarkdownSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _ranges(document: QTextDocument, block_number: int):
        block = document.findBlockByNumber(block_number)
        layout = block.layout()
        return layout.formats() if layout is not None else []

    @classmethod
    def _foregrounds(cls, document: QTextDocument, block_number: int) -> set[str]:
        return {
            item.format.foreground().color().name()
            for item in cls._ranges(document, block_number)
            if item.format.foreground().color().isValid()
        }

    def test_only_fenced_code_is_highlighted(self) -> None:
        document = QTextDocument()
        highlighter = MarkdownSyntaxHighlighter(document, "dark")
        document.setPlainText(
            "Before\n```python\ndef answer():\n    return 42\n```\nAfter"
        )
        highlighter.rehighlight()

        self.assertEqual(self._ranges(document, 0), [])
        self.assertGreater(document.findBlockByNumber(1).userState(), 0)
        self.assertGreater(document.findBlockByNumber(2).userState(), 0)
        self.assertGreaterEqual(len(self._foregrounds(document, 2)), 2)
        self.assertGreater(document.findBlockByNumber(3).userState(), 0)
        self.assertEqual(document.findBlockByNumber(4).userState(), 0)
        self.assertEqual(self._ranges(document, 5), [])

    def test_long_fences_and_unknown_languages_fall_back_safely(self) -> None:
        document = QTextDocument()
        highlighter = MarkdownSyntaxHighlighter(document)
        document.setPlainText(
            "````not-a-real-lexer\nvalue = 1\n```\nstill code\n````\noutside"
        )
        highlighter.rehighlight()

        self.assertGreater(document.findBlockByNumber(2).userState(), 0)
        self.assertGreater(document.findBlockByNumber(3).userState(), 0)
        self.assertEqual(document.findBlockByNumber(4).userState(), 0)
        self.assertTrue(self._ranges(document, 1))
        self.assertEqual(self._ranges(document, 5), [])

    def test_disabling_and_theme_changes_rehighlight_the_document(self) -> None:
        document = QTextDocument()
        highlighter = MarkdownSyntaxHighlighter(document, "dark")
        document.setPlainText("```python\ndef answer():\n```")
        highlighter.rehighlight()
        dark_colors = self._foregrounds(document, 1)

        highlighter.set_theme("light")
        light_colors = self._foregrounds(document, 1)
        self.assertEqual(highlighter.theme, "light")
        self.assertNotEqual(dark_colors, light_colors)

        highlighter.set_highlighting_enabled(False)
        self.assertFalse(highlighter.highlighting_enabled)
        self.assertEqual(self._ranges(document, 1), [])

    def test_preview_uses_pygments_and_keeps_task_list_markup(self) -> None:
        rendered = render_markdown_html(
            "- [x] Ship it\n\n```python\nif True:\n    print('<beer>')\n```",
            theme="dark",
        )

        self.assertIn('class="highlight"', rendered)
        self.assertRegex(rendered, r'<span class="[a-z]+">')
        self.assertIn(".highlight .k", rendered)
        self.assertIn('class="task-item"', rendered)
        self.assertIn("☑", rendered)
        self.assertIn("&lt;beer&gt;", rendered)

    def test_preview_theme_changes_pygments_style(self) -> None:
        source = "```python\nreturn True\n```"

        dark = render_markdown_html(source, theme="dark")
        light = render_markdown_html(source, theme="light")

        self.assertNotEqual(dark, light)
        self.assertIn("#2A2A2D", dark)
        self.assertIn("#F0F0F4", light)



if __name__ == "__main__":
    unittest.main()
