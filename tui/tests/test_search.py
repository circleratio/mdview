import unittest

from mdview_tui.search import Match, find_all, next_match


class FindAllTest(unittest.TestCase):
    def test_case_insensitive(self):
        self.assertEqual(find_all(["Foo foo FOO"], "foo"), [Match(0, 0, 3), Match(0, 4, 7), Match(0, 8, 11)])

    def test_cell_positions(self):
        self.assertEqual(find_all(["日本語のテスト"], "テスト"), [Match(0, 8, 14)])

    def test_multiple_lines(self):
        self.assertEqual(find_all(["a", "b a"], "a"), [Match(0, 0, 1), Match(1, 2, 3)])

    def test_no_match_and_empty(self):
        self.assertEqual(find_all(["abc"], "x"), [])
        self.assertEqual(find_all(["abc"], ""), [])

    def test_casefold_expansion(self):
        self.assertEqual(find_all(["Straße x"], "x"), [Match(0, 7, 8)])


class NextMatchTest(unittest.TestCase):
    matches = [Match(1, 0, 1), Match(5, 0, 1), Match(9, 0, 1)]

    def test_from_top_line(self):
        self.assertEqual(next_match(self.matches, None, 3, True), 1)
        self.assertEqual(next_match(self.matches, None, 3, False), 0)

    def test_wrap_around(self):
        self.assertEqual(next_match(self.matches, 2, 0, True), 0)
        self.assertEqual(next_match(self.matches, 0, 0, False), 2)
        self.assertEqual(next_match(self.matches, None, 10, True), 0)
        self.assertEqual(next_match(self.matches, None, 0, False), 2)

    def test_empty(self):
        self.assertIsNone(next_match([], None, 0, True))


if __name__ == "__main__":
    unittest.main()
