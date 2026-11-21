import tempfile
import unittest
from pathlib import Path

from mdview_tui.errors import MdviewError
from mdview_tui.source import load_file
from tests.helpers import FIXTURES


class LoadFileTest(unittest.TestCase):
    def test_utf8(self):
        src = load_file(FIXTURES / "sample.md")
        self.assertTrue(src.text.startswith("# mdview サンプル"))
        self.assertEqual(src.path, FIXTURES / "sample.md")

    def test_bom_and_crlf(self):
        src = load_file(FIXTURES / "bom_crlf.md")
        self.assertEqual(src.text, "# BOM\n\nline\n")

    def test_display_name(self):
        src = load_file(FIXTURES / "sample.md", "x.md")
        self.assertEqual(src.display_name, "x.md")

    def assertError(self, path, name, message):
        with self.assertRaises(MdviewError) as cm:
            load_file(path, name)
        self.assertEqual(cm.exception.message, message)
        self.assertEqual(cm.exception.exit_code, 1)

    def test_missing(self):
        self.assertError(Path("nofile.md"), "nofile.md", "nofile.md: No such file or directory")

    def test_directory(self):
        self.assertError(FIXTURES, "fixtures", "fixtures: Is a directory")

    def test_not_utf8(self):
        self.assertError(FIXTURES / "sjis.md", "sjis.md", "sjis.md: not valid UTF-8")

    def test_cr_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cr.md"
            path.write_bytes(b"a\rb\r")
            self.assertEqual(load_file(path).text, "a\nb\n")


if __name__ == "__main__":
    unittest.main()
