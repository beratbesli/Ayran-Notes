#!/usr/bin/env python3
"""Install or remove the Beer Notes desktop-menu shortcut for this user."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_ID = "beernotes"
PROJECT_DIR = Path(__file__).resolve().parent
LAUNCHER = PROJECT_DIR / "run.py"
SOURCE_PACKAGE = PROJECT_DIR / "beernotes"
SOURCE_ICON = PROJECT_DIR / "beernotes" / "assets" / "beernotes.png"
INSTALL_DIR_NAME = "beernotes-app"


def _data_home() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".local" / "share"


def _quote_exec_arg(value: Path) -> str:
    escaped = str(value).replace("\\", "\\\\")
    for character in ('"', "`", "$"):
        escaped = escaped.replace(character, "\\" + character)
    return f'"{escaped}"'


def _desktop_value(value: Path) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


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
    """Install a self-contained app copy and desktop entry for this user."""
    if not LAUNCHER.is_file() or not SOURCE_PACKAGE.is_dir() or not SOURCE_ICON.is_file():
        raise FileNotFoundError("Beer Notes files are incomplete; clone the repository again.")

    data_home = _data_home()
    install_dir = data_home / INSTALL_DIR_NAME
    installed_package = install_dir / "beernotes"
    installed_launcher = install_dir / "run.py"
    applications_dir = data_home / "applications"
    icons_dir = data_home / "icons" / "hicolor" / "512x512" / "apps"
    desktop_path = applications_dir / f"{APP_ID}.desktop"
    icon_path = icons_dir / f"{APP_ID}.png"

    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SOURCE_PACKAGE,
        installed_package,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    shutil.copy2(LAUNCHER, installed_launcher)
    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_ICON, icon_path)

    desktop_entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Beer Notes
GenericName=Note-Taking App
Comment=A lightweight, customizable note-taking application for Linux
Exec={_quote_exec_arg(Path(sys.executable))} {_quote_exec_arg(installed_launcher)}
Path={_desktop_value(install_dir)}
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
    install_dir = data_home / INSTALL_DIR_NAME

    desktop_path.unlink(missing_ok=True)
    icon_path.unlink(missing_ok=True)
    shutil.rmtree(install_dir, ignore_errors=True)
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
