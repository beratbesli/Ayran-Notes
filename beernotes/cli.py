"""Beer Notes — Command-line interface.

Provides a terminal-friendly way to manage notes without launching the
graphical interface.  Reuses the same storage engine and note directory
as the GUI so every change is immediately visible in both environments.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Optional

from beernotes.storage.database import StorageEngine
from beernotes.storage.models import Note


def _make_engine() -> StorageEngine:
    """Create a StorageEngine that uses the same data dir as the GUI."""
    return StorageEngine()


# ------------------------------------------------------------------
# Subcommands
# ------------------------------------------------------------------

def _cmd_add(args: argparse.Namespace, engine: StorageEngine) -> int:
    """Create a new note."""
    content = args.content or ""
    if args.stdin:
        content = sys.stdin.read()

    note = Note(title=args.title, content=content)
    if args.folder:
        note.folder = args.folder
    if args.tags:
        note.tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    engine.save_note(note)
    print(f"Created note {note.id}: {note.title}")
    return 0


def _cmd_list(args: argparse.Namespace, engine: StorageEngine) -> int:
    """List notes with optional filters."""
    notes = engine.list_notes()

    # Apply filters
    notes = [n for n in notes if not n.is_trashed]

    if args.folder:
        notes = [n for n in notes if n.folder == args.folder]
    if args.tag:
        notes = [n for n in notes if args.tag in n.tags]

    if args.limit:
        notes = notes[: args.limit]

    if not notes:
        print("No notes found.")
        return 0

    # Header
    print(f"{'ID':<14} {'TITLE':<30} {'FOLDER':<15} {'TAGS':<20} {'UPDATED'}")
    print("-" * 100)

    for note in notes:
        title = note.title[:28] + ".." if len(note.title) > 30 else note.title
        folder = note.folder[:13] + ".." if len(note.folder) > 15 else note.folder
        tags = ", ".join(note.tags)
        tags = tags[:18] + ".." if len(tags) > 20 else tags
        updated = note.updated_at[:19] if note.updated_at else ""
        print(f"{note.id:<14} {title:<30} {folder:<15} {tags:<20} {updated}")

    print(f"\n{len(notes)} note(s)")
    return 0


def _cmd_search(args: argparse.Namespace, engine: StorageEngine) -> int:
    """Search notes by title and content."""
    query = args.query.lower()
    notes = engine.list_notes()
    results = [
        n
        for n in notes
        if not n.is_trashed
        and (query in n.title.lower() or query in n.content.lower())
    ]

    if not results:
        print(f'No notes matching "{args.query}".')
        return 0

    for note in results:
        preview = note.content[:50].replace("\n", " ")
        print(f"{note.id}  {note.title}  — {preview}")

    print(f"\n{len(results)} result(s)")
    return 0


def _cmd_show(args: argparse.Namespace, engine: StorageEngine) -> int:
    """Show full note content."""
    note = engine.get_note(args.note_id)
    if note is None:
        print(f"Note not found: {args.note_id}", file=sys.stderr)
        return 1

    if args.meta:
        print(f"ID:      {note.id}")
        print(f"Title:   {note.title}")
        print(f"Folder:  {note.folder}")
        print(f"Tags:    {', '.join(note.tags) if note.tags else '—'}")
        print(f"Pinned:  {note.is_pinned}")
        print(f"Created: {note.created_at}")
        print(f"Updated: {note.updated_at}")
        print("---")

    print(note.content)
    return 0


def _cmd_delete(args: argparse.Namespace, engine: StorageEngine) -> int:
    """Delete or trash a note."""
    note = engine.get_note(args.note_id)
    if note is None:
        print(f"Note not found: {args.note_id}", file=sys.stderr)
        return 1

    if args.permanent:
        if not args.yes:
            answer = input(f'Permanently delete "{note.title}"? [y/N] ').strip().lower()
            if answer != "y":
                print("Cancelled.")
                return 0
        engine.delete_note(args.note_id)
        print(f"Permanently deleted: {note.title}")
    else:
        note.is_trashed = True
        note.touch()
        engine.save_note(note)
        print(f"Moved to trash: {note.title}")

    return 0


def _cmd_folders(args: argparse.Namespace, engine: StorageEngine) -> int:
    """List all folders."""
    notes = engine.list_notes()
    folders: dict[str, int] = {}
    for note in notes:
        if not note.is_trashed:
            folders[note.folder] = folders.get(note.folder, 0) + 1

    if not folders:
        print("No folders found.")
        return 0

    for folder, count in sorted(folders.items()):
        print(f"  {folder} ({count})")
    return 0


def _cmd_tags(args: argparse.Namespace, engine: StorageEngine) -> int:
    """List all tags with usage count."""
    notes = engine.list_notes()
    tag_counts: dict[str, int] = {}
    for note in notes:
        if not note.is_trashed:
            for tag in note.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        print("No tags found.")
        return 0

    for tag, count in sorted(tag_counts.items()):
        print(f"  #{tag} ({count})")
    return 0


# ------------------------------------------------------------------
# Argument parser
# ------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beernotes-cli",
        description="Beer Notes — manage your notes from the terminal.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # add
    p_add = sub.add_parser("add", help="Create a new note")
    p_add.add_argument("title", help="Note title")
    p_add.add_argument("--content", "-c", default="", help="Note content")
    p_add.add_argument("--folder", "-f", default="", help="Target folder")
    p_add.add_argument("--tags", "-t", default="", help="Comma-separated tags")
    p_add.add_argument("--stdin", action="store_true", help="Read content from stdin")

    # list
    p_list = sub.add_parser("list", help="List notes")
    p_list.add_argument("--folder", "-f", default="", help="Filter by folder")
    p_list.add_argument("--tag", "-t", default="", help="Filter by tag")
    p_list.add_argument("--limit", "-n", type=int, default=0, help="Max results")

    # search
    p_search = sub.add_parser("search", help="Search notes")
    p_search.add_argument("query", help="Search query")

    # show
    p_show = sub.add_parser("show", help="Show a note's content")
    p_show.add_argument("note_id", help="Note ID")
    p_show.add_argument("--meta", "-m", action="store_true", help="Show metadata")

    # delete
    p_del = sub.add_parser("delete", help="Delete a note")
    p_del.add_argument("note_id", help="Note ID")
    p_del.add_argument("--permanent", action="store_true", help="Permanently delete")
    p_del.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    # folders
    sub.add_parser("folders", help="List all folders")

    # tags
    sub.add_parser("tags", help="List all tags")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    engine = _make_engine()

    handlers = {
        "add": _cmd_add,
        "list": _cmd_list,
        "search": _cmd_search,
        "show": _cmd_show,
        "delete": _cmd_delete,
        "folders": _cmd_folders,
        "tags": _cmd_tags,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args, engine)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
