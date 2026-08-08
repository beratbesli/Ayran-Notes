#!/usr/bin/env python3
"""Beer Notes — Application entry point.

Initializes the storage engine, controllers, i18n system, and launches
the main window.
"""

import sys
from importlib.resources import files

from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from beernotes import __version__
from beernotes.controllers.note_controller import NoteController
from beernotes.controllers.settings_controller import SettingsController
from beernotes.localization.i18n import I18n
from beernotes.storage.database import StorageEngine
from beernotes.ui.main_window import MainWindow


def main() -> None:
    """Launch the Beer Notes application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Beer Notes")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(
        QIcon(str(files("beernotes").joinpath("assets", "beernotes.png")))
    )

    # --- Core services ---
    try:
        storage = StorageEngine()
    except (OSError, ValueError) as error:
        QMessageBox.critical(
            None,
            "Beer Notes",
            "The configured notes directory is unavailable.\n\n"
            f"{error}",
        )
        return
    settings_ctrl = SettingsController(storage)
    note_ctrl = NoteController(storage)
    i18n = I18n(language=settings_ctrl.settings.language)

    # --- Default font ---
    font = QFont(settings_ctrl.settings.font_family, settings_ctrl.settings.font_size)
    app.setFont(font)

    # --- Main window ---
    window = MainWindow(note_ctrl, settings_ctrl, i18n)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
