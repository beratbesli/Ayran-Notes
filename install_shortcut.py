#!/usr/bin/env python3
"""Install or remove the Beer Notes desktop-menu shortcut for this user."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


APP_ID = "beernotes"
PROJECT_DIR = Path(__file__).resolve().parent
LAUNCHER = PROJECT_DIR / "run.py"
SOURCE_PACKAGE = PROJECT_DIR / "beernotes"
SOURCE_ICON = PROJECT_DIR / "beernotes" / "assets" / "beernotes.png"
WRAPPER_NAME = "beernotes-repo"
LEGACY_INSTALL_DIR_NAME = "beernotes-app"


def _data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".local" / "share"


def _bin_home() -> Path:
    return Path.home() / ".local" / "bin"


def _quote_exec_arg(value: Path) -> str:
    escaped = str(value).replace("\\", "\\\\")
    for character in ('"', "`", "$"):
        escaped = escaped.replace(character, "\\" + character)
    return f'"{escaped}"'


def _refresh_desktop_database(applications_dir: Path) -> None:
    updater = shutil.which("update-desktop-database")
    if updater:
        subprocess.run(
            [updater, str(applications_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def install() -> Path:
    """Install a tiny repository launcher and desktop entry for this user."""
    if not LAUNCHER.is_file() or not SOURCE_PACKAGE.is_dir() or not SOURCE_ICON.is_file():
        raise FileNotFoundError("Beer Notes files are incomplete; clone the repository again.")

    data_home = _data_home()
    bin_home = _bin_home()
    wrapper_path = bin_home / WRAPPER_NAME
    applications_dir = data_home / "applications"
    icons_dir = data_home / "icons" / "hicolor" / "512x512" / "apps"
    desktop_path = applications_dir / f"{APP_ID}.desktop"
    icon_path = icons_dir / f"{APP_ID}.png"

    bin_home.mkdir(parents=True, exist_ok=True)
    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_ICON, icon_path)

    wrapper = f"""#!/bin/sh
PROJECT_DIR={shlex.quote(str(PROJECT_DIR))}
APP_LAUNCHER={shlex.quote(str(LAUNCHER))}

if [ ! -f "$APP_LAUNCHER" ]; then
    MESSAGE="Beer Notes project files are unavailable: $PROJECT_DIR"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "Beer Notes" "$MESSAGE"
    fi
    printf '%s\\n' "$MESSAGE" >&2
    exit 1
fi

cd "$PROJECT_DIR" || exit 1
exec {shlex.quote(sys.executable)} "$APP_LAUNCHER"
"""
    wrapper_path.write_text(wrapper, encoding="utf-8")
    wrapper_path.chmod(0o755)

    # Remove the full duplicate created by versions prior to 1.2.0.
    shutil.rmtree(data_home / LEGACY_INSTALL_DIR_NAME, ignore_errors=True)

    desktop_entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Beer Notes
GenericName=Note-Taking App
Comment=A lightweight, customizable note-taking application for Linux
Exec={_quote_exec_arg(wrapper_path)}
Icon={APP_ID}
Terminal=false
Categories=Utility;TextEditor;
Keywords=notes;markdown;editor;text;
StartupWMClass=beernotes
StartupNotify=true
"""
    desktop_path.write_text(desktop_entry, encoding="utf-8")
    desktop_path.chmod(0o755)
    _refresh_desktop_database(applications_dir)
    return desktop_path


def uninstall() -> None:
    """Remove files installed by :func:`install`."""
    data_home = _data_home()
    applications_dir = data_home / "applications"
    desktop_path = applications_dir / f"{APP_ID}.desktop"
    icon_path = data_home / "icons" / "hicolor" / "512x512" / "apps" / f"{APP_ID}.png"
    wrapper_path = _bin_home() / WRAPPER_NAME

    desktop_path.unlink(missing_ok=True)
    icon_path.unlink(missing_ok=True)
    wrapper_path.unlink(missing_ok=True)
    shutil.rmtree(data_home / LEGACY_INSTALL_DIR_NAME, ignore_errors=True)
    _refresh_desktop_database(applications_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install Beer Notes in the current user's Linux application menu."
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove the installed application-menu shortcut",
    )
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
        print("Beer Notes shortcut removed.")
    else:
        path = install()
        print(f"Beer Notes shortcut installed: {path}")


if __name__ == "__main__":
    main()
