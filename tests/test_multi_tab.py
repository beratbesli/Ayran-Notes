"""Tests for the Beer Notes multi-tab system."""

import unittest

from PyQt6.QtWidgets import QApplication

from beernotes.ui.tab_manager import TabManager


class MultiTabTests(unittest.TestCase):
    """Test the TabManager component."""

    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            cls._app = QApplication([])

    def test_open_note_creates_tab(self):
        tm = TabManager()
        idx = tm.open_note("note1", "First Note", "Hello")
        self.assertEqual(tm.tab_count(), 1)
        self.assertEqual(idx, 0)

    def test_open_duplicate_switches(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        idx = tm.open_note("note1", "First", "A")
        self.assertEqual(tm.tab_count(), 2)
        self.assertEqual(tm.current_note_id(), "note1")

    def test_close_tab(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        tm.close_tab(0)
        self.assertEqual(tm.tab_count(), 1)

    def test_mark_dirty_indicator(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.mark_dirty("note1")
        label = tm.tab_widget.tabText(0)
        self.assertTrue(label.startswith("●"))

    def test_mark_clean_removes_indicator(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.mark_dirty("note1")
        tm.mark_clean("note1")
        label = tm.tab_widget.tabText(0)
        self.assertFalse(label.startswith("●"))

    def test_tab_switch_signal(self):
        tm = TabManager()
        switched = []
        tm.tab_switched.connect(switched.append)
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        # Signal should have fired with "note2"
        self.assertIn("note2", switched)

    def test_save_all_dirty_tabs(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        tm.mark_dirty("note1")
        tm.update_content("note1", "Updated A")

        saved = {}

        def save_cb(nid, content):
            saved[nid] = content
            return True

        result = tm.save_all(save_cb)
        self.assertTrue(result)
        self.assertIn("note1", saved)
        self.assertEqual(saved["note1"], "Updated A")

    def test_close_all(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        tm.close_all()
        self.assertEqual(tm.tab_count(), 0)

    def test_get_dirty_tabs(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.open_note("note2", "Second", "B")
        tm.mark_dirty("note1")
        dirty = tm.get_dirty_tabs()
        self.assertEqual(dirty, ["note1"])

    def test_handle_external_change_clean(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        result = tm.handle_external_change("note1", "New content")
        self.assertTrue(result)
        self.assertEqual(tm.get_content("note1"), "New content")

    def test_handle_external_change_dirty(self):
        tm = TabManager()
        tm.open_note("note1", "First", "A")
        tm.mark_dirty("note1")
        result = tm.handle_external_change("note1", "External change")
        self.assertFalse(result)  # Should warn, not overwrite

    def test_is_open(self):
        tm = TabManager()
        self.assertFalse(tm.is_open("note1"))
        tm.open_note("note1", "First", "A")
        self.assertTrue(tm.is_open("note1"))


if __name__ == "__main__":
    unittest.main()
