"""Ayran Notes — Internationalization (i18n) engine.

Provides dynamic, restart-free language switching via a simple
JSON-dictionary–based locale system.

Usage:
    from ayrannotes.localization.i18n import I18n

    i18n = I18n()            # defaults to English
    i18n.set_language("tr")  # switch to Turkish instantly
    print(i18n.t("new_note"))  # → "Yeni Not"
"""

from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

_LOCALE_DIR = Path(__file__).resolve().parent
_SUPPORTED_LANGUAGES = ("en", "tr")


class I18n(QObject):
    """Singleton-style translation provider with Qt signal support.

    Emits ``language_changed`` whenever the active language is switched
    so that connected UI widgets can refresh their labels dynamically.
    """

    language_changed = pyqtSignal(str)  # emits the new language code

    def __init__(self, language: str = "en", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._strings: dict[str, str] = {}
        self._language: str = ""
        self._cache: dict[str, dict[str, str]] = {}
        self.set_language(language)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        """Return the currently active language code."""
        return self._language

    @property
    def supported_languages(self) -> tuple:
        """Return the tuple of supported language codes."""
        return _SUPPORTED_LANGUAGES

    def set_language(self, lang: str) -> None:
        """Switch the active language.

        If the requested locale file is missing, falls back to English.
        Emits ``language_changed`` after switching.
        """
        if lang not in _SUPPORTED_LANGUAGES:
            lang = "en"
        if lang == self._language:
            return

        self._language = lang
        self._strings = self._load(lang)
        self.language_changed.emit(lang)

    def t(self, key: str, default: str | None = None, **kwargs) -> str:
        """Translate *key* into the active language.

        Supports Python-style ``str.format`` placeholders::

            i18n.t("notes_count", count=42)  # → "42 notes"

        Returns *default* or the raw key if no translation is found.
        """
        text = self._strings.get(key)
        if text is None:
            text = default if default is not None else key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, lang: str) -> dict[str, str]:
        """Load a locale JSON file, using cache when available."""
        if lang in self._cache:
            return self._cache[lang]

        path = _LOCALE_DIR / f"{lang}.json"
        if not path.exists():
            path = _LOCALE_DIR / "en.json"

        try:
            data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}

        self._cache[lang] = data
        return data
