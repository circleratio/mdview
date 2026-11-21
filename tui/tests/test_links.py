import unittest
from unittest import mock
from pathlib import Path

from mdview_tui.links import Target, display_href, resolve

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


class FileUrlTest(unittest.TestCase):
    def test_file_url_is_a_local_path_with_anchor(self):
        target = resolve("file:///home/u/%E8%B3%87%E6%96%99.md#%E6%A6%82%E8%A6%81", BASE)
        self.assertEqual(target, Target("file", path=Path("/home/u/資料.md"), anchor="概要"))

    def test_localhost_and_unc(self):
        self.assertEqual(resolve("file://localhost/home/x.md", BASE).path, Path("/home/x.md"))
        self.assertEqual(resolve("file://server/share/x.md", BASE).path, Path("//server/share/x.md"))

    def test_non_markdown_file_url_is_unsupported(self):
        self.assertEqual(resolve("file:///usr/bin/calc", BASE).kind, "unsupported")

    def test_drive_letter_on_windows(self):
        with mock.patch("mdview_tui.links.os.name", "nt"):
            from mdview_tui.links import _file_url

            self.assertEqual(_file_url("file:///C:/docs/x.md#a"), ("C:/docs/x.md", "a"))


class DisplayHrefTest(unittest.TestCase):
    def test_decodes_percent_encoding(self):
        self.assertEqual(display_href("%E5%9B%B3.png"), "図.png")
        self.assertEqual(display_href("my%20image.png"), "my image.png")

    def test_keeps_malformed_escapes(self):
        self.assertEqual(display_href("100%"), "100%")
        self.assertEqual(display_href("a%zzb"), "a%zzb")


if __name__ == "__main__":
    unittest.main()
