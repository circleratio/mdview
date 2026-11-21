import os
import tempfile
import unittest
from pathlib import Path

from mdview_tui.watcher import FileWatcher


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "a.md"
        self.path.write_text("a", encoding="utf-8")
        self.watcher = FileWatcher(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def bump(self, text):
        self.path.write_text(text, encoding="utf-8")
        st = os.stat(self.path)
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

    def test_unchanged(self):
        self.assertEqual(self.watcher.check(), "unchanged")

    def test_modified(self):
        self.bump("bb")
        self.assertEqual(self.watcher.check(), "modified")
        self.assertEqual(self.watcher.check(), "unchanged")

    def test_deleted_once_then_recreated(self):
        self.path.unlink()
        self.assertEqual(self.watcher.check(), "deleted")
        self.assertEqual(self.watcher.check(), "unchanged")
        self.path.write_text("new", encoding="utf-8")
        self.assertEqual(self.watcher.check(), "modified")


if __name__ == "__main__":
    unittest.main()
