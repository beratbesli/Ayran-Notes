"""Export notes to common, portable document formats."""

from __future__ import annotations

import html
from pathlib import Path

import markdown
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter

from beernotes.storage.models import Note


SUPPORTED_SUFFIXES = {".md", ".txt", ".html", ".pdf"}


def _markdown_document(note: Note) -> str:
    tags = f"**Tags:** {', '.join(note.tags)}\n\n" if note.tags else ""
    return f"# {note.title or 'Untitled'}\n\n{tags}{note.content}\n"


def _html_document(note: Note) -> str:
    tags = ""
    if note.tags:
        tags = (
            '<p class="tags">'
            + " ".join(f"<span>#{html.escape(tag)}</span>" for tag in note.tags)
            + "</p>"
        )
    body = markdown.markdown(
        note.content,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(note.title or "Untitled")}</title>
<style>
body {{ max-width: 820px; margin: 48px auto; padding: 0 28px;
       color: #1d1d1f; font: 16px/1.65 -apple-system, BlinkMacSystemFont,
       "Segoe UI", sans-serif; }}
h1 {{ font-size: 32px; line-height: 1.2; }}
.tags {{ color: #6e6e73; }}
.tags span {{ margin-right: 10px; }}
pre, code {{ background: #f2f2f7; border-radius: 6px; }}
code {{ padding: 2px 5px; }}
pre {{ padding: 14px; overflow-x: auto; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #d1d1d6; padding: 7px 10px; }}
</style>
</head>
<body>
<h1>{html.escape(note.title or "Untitled")}</h1>
{tags}
{body}
</body>
</html>
"""


def export_note(note: Note, destination: Path) -> Path:
    """Export *note* based on the destination filename suffix."""
    destination = Path(destination)
    suffix = destination.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported export format: {suffix or 'missing extension'}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".md":
        destination.write_text(_markdown_document(note), encoding="utf-8")
    elif suffix == ".html":
        destination.write_text(_html_document(note), encoding="utf-8")
    elif suffix == ".txt":
        document = QTextDocument()
        document.setHtml(_html_document(note))
        destination.write_text(document.toPlainText() + "\n", encoding="utf-8")
    else:
        document = QTextDocument()
        document.setHtml(_html_document(note))
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(destination))
        document.print(printer)
    return destination
