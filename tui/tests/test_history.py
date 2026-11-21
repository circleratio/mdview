import unittest

from mdview_tui.history import History, Location
from mdview_tui.source import Source


def loc(name, y=0):
    return Location(Source("", None, name), y)


class HistoryTest(unittest.TestCase):
    def test_empty(self):
        h = History(loc("a"))
        self.assertIsNone(h.back())
        self.assertIsNone(h.forward())
        self.assertFalse(h.can_back())
        self.assertEqual(h.current.source.display_name, "a")

    def test_back_forward(self):
        h = History(loc("a"))
        h.update_current(5)
        h.push(loc("b"))
        self.assertTrue(h.can_back())
        back = h.back()
        self.assertEqual((back.source.display_name, back.scroll_y), ("a", 5))
        self.assertTrue(h.can_forward())
        self.assertEqual(h.forward().source.display_name, "b")
        self.assertFalse(h.can_forward())

    def test_push_clears_forward(self):
        h = History(loc("a"))
        h.push(loc("b"))
        h.back()
        h.push(loc("c"))
        self.assertIsNone(h.forward())
        self.assertEqual(h.back().source.display_name, "a")


if __name__ == "__main__":
    unittest.main()
