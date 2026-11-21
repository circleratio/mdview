import unittest
from pathlib import Path

from mdview_tui.links import Target, resolve

BASE = Path("/docs/guide/index.md")


class ResolveTest(unittest.TestCase):
    def test_anchor(self):
        self.assertEqual(resolve("#intro", BASE), Target("anchor", anchor="intro"))

    def test_anchor_url_encoded(self):
        self.assertEqual(resolve("#%E3%81%82", BASE).anchor, "あ")

    def test_external(self):
        for href in ("https://example.com", "http://x", "mailto:a@b.c"):
            self.assertEqual(resolve(href, BASE), Target("external", url=href))

    def test_relative_md(self):
        self.assertEqual(resolve("../other.md", BASE), Target("file", path=Path("/docs/guide/../other.md")))

    def test_md_with_anchor_and_encoding(self):
        target = resolve("%E8%A8%AD%E8%A8%88.markdown#Part%201", BASE)
        self.assertEqual(target, Target("file", path=Path("/docs/guide/設計.markdown"), anchor="Part 1"))

    def test_absolute(self):
        self.assertEqual(resolve("/tmp/x.MD", BASE).path, Path("/tmp/x.MD"))

    def test_unsupported(self):
        for href in ("image.png", "dir/", "", "file.txt#x"):
            self.assertEqual(resolve(href, BASE).kind, "unsupported")

    def test_stdin_uses_cwd(self):
        self.assertEqual(resolve("a.md", None).path, Path.cwd() / "a.md")


if __name__ == "__main__":
    unittest.main()
