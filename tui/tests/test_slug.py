import unittest

from mdview_tui.slug import SlugRegistry, slugify


class SlugTest(unittest.TestCase):
    def test_ascii(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_symbols(self):
        self.assertEqual(slugify("What's new? (v1.0)"), "whats-new-v10")

    def test_keeps_hyphen_and_underscore(self):
        self.assertEqual(slugify("a-b_c"), "a-b_c")

    def test_japanese(self):
        self.assertEqual(slugify("セクション 2"), "セクション-2")
        self.assertEqual(slugify("使いかた（概要）"), "使いかた概要")

    def test_duplicates(self):
        reg = SlugRegistry()
        self.assertEqual([reg.make("Foo"), reg.make("Foo"), reg.make("Foo")], ["foo", "foo-1", "foo-2"])

    def test_duplicate_collides_with_existing(self):
        reg = SlugRegistry()
        self.assertEqual([reg.make("a-1"), reg.make("a"), reg.make("a")], ["a-1", "a", "a-2"])


if __name__ == "__main__":
    unittest.main()
