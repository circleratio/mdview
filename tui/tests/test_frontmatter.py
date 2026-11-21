import unittest

from mdview_tui.frontmatter import (
    NOT_A_MAPPING,
    FrontMatterView,
    format_author,
    format_value,
    split_front_matter,
    to_view,
)


class SplitTest(unittest.TestCase):
    def test_no_front_matter(self):
        text = "# Title\n\nbody\n"
        self.assertEqual(split_front_matter(text), (None, text))

    def test_missing_closing_fence(self):
        text = "---\ntitle: x\n\n# Body\n"
        self.assertEqual(split_front_matter(text), (None, text))

    def test_rule_not_on_first_line(self):
        text = "\n---\ntitle: x\n---\n"
        self.assertEqual(split_front_matter(text), (None, text))

    def test_closing_fences(self):
        for close in ("---", "...", "---  ", "...\t"):
            with self.subTest(close=close):
                fm, body = split_front_matter(f"---\ntitle: x\n{close}\nbody\n")
                self.assertEqual(fm.data, {"title": "x"})
                self.assertEqual(body, "\n\n\nbody\n")

    def test_opening_fence_trailing_space(self):
        fm, _ = split_front_matter("--- \ntitle: x\n---\n")
        self.assertEqual(fm.data, {"title": "x"})

    def test_body_keeps_line_numbers(self):
        _, body = split_front_matter("---\na: 1\nb: 2\n---\n# H\n")
        self.assertEqual(body.split("\n").index("# H"), 4)

    def test_later_rule_stays_in_body(self):
        fm, body = split_front_matter("---\na: 1\n---\ntext\n\n---\n\nafter\n")
        self.assertEqual(fm.raw, "a: 1")
        self.assertIn("\n---\n", body)
        self.assertTrue(body.endswith("after\n"))

    def test_values_stay_as_written(self):
        fm, _ = split_front_matter("---\ndate: 2026-10-08\nversion: 1.10\nflag: true\nn: 007\n---\n")
        self.assertEqual(fm.data, {"date": "2026-10-08", "version": "1.10", "flag": "true", "n": "007"})

    def test_empty_front_matter(self):
        for raw in ("", "  ", "# comment only"):
            with self.subTest(raw=raw):
                fm, body = split_front_matter(f"---\n{raw}\n---\nbody\n")
                self.assertEqual(fm.data, {})
                self.assertIsNone(fm.error)
                self.assertEqual(body, "\n\n\nbody\n")
        fm, _ = split_front_matter("---\n---\nbody\n")
        self.assertEqual(fm.data, {})

    def test_syntax_error(self):
        fm, body = split_front_matter("---\ntitle: [oops\n---\n\n# Body\n")
        self.assertIsNone(fm.data)
        self.assertEqual(fm.raw, "title: [oops")
        self.assertTrue(fm.error)
        self.assertNotIn("\n", fm.error)
        self.assertTrue(body.endswith("# Body\n"))

    def test_top_level_not_a_mapping(self):
        for raw in ("- a\n- b", "just text"):
            with self.subTest(raw=raw):
                fm, _ = split_front_matter(f"---\n{raw}\n---\n")
                self.assertIsNone(fm.data)
                self.assertEqual(fm.error, NOT_A_MAPPING)


class ViewTest(unittest.TestCase):
    def test_prominent_fields(self):
        view = to_view({"title": "T", "author": "A", "date": "2026-10-08"})
        self.assertEqual(view, FrontMatterView("T", ["A", "2026-10-08"], []))

    def test_author_list(self):
        self.assertEqual(to_view({"author": ["山田", "佐藤"]}).byline, ["山田、佐藤"])
        self.assertEqual(format_author(["山田", "", "佐藤"]), "山田、佐藤")

    def test_missing_fields_are_omitted(self):
        view = to_view({"date": "2026-10-08", "title": ""})
        self.assertIsNone(view.title)
        self.assertEqual(view.byline, ["2026-10-08"])

    def test_others_keep_order(self):
        view = to_view({"z": "1", "title": "T", "a": "2", "author": "A"})
        self.assertEqual(view.others, [("z", "1"), ("a", "2")])

    def test_is_empty(self):
        self.assertTrue(to_view({}).is_empty)
        self.assertTrue(to_view({"title": "", "author": []}).is_empty)
        self.assertFalse(to_view({"key": ""}).is_empty)

    def test_format_value(self):
        self.assertEqual(format_value("x"), "x")
        self.assertEqual(format_value(""), "")
        self.assertEqual(format_value(None), "")
        self.assertEqual(format_value(["a", "b"]), "a, b")
        self.assertEqual(format_value({"k": "v", "k2": ["a", "b"]}), "k: v, k2: a, b")
        fm, _ = split_front_matter("---\nempty:\n---\n")
        self.assertEqual(to_view(fm.data).others, [("empty", "")])


if __name__ == "__main__":
    unittest.main()
