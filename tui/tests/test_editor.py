import unittest
from pathlib import Path

from mdview_tui.editor import editor_command

P = Path("a.md")


class EditorTest(unittest.TestCase):
    def test_visual_first(self):
        self.assertEqual(editor_command(P, {"VISUAL": "code -w", "EDITOR": "nano"}, "linux"), ["code", "-w", "a.md"])

    def test_editor(self):
        self.assertEqual(editor_command(P, {"EDITOR": "nano"}, "linux"), ["nano", "a.md"])

    def test_empty_visual_falls_back(self):
        self.assertEqual(editor_command(P, {"VISUAL": " ", "EDITOR": "nano"}, "linux"), ["nano", "a.md"])

    def test_defaults(self):
        self.assertEqual(editor_command(P, {}, "linux"), ["vi", "a.md"])
        self.assertEqual(editor_command(P, {}, "darwin"), ["vi", "a.md"])
        self.assertEqual(editor_command(P, {}, "win32"), ["notepad", "a.md"])

    def test_quoted(self):
        self.assertEqual(editor_command(P, {"EDITOR": "'my editor' --wait"}, "linux"), ["my editor", "--wait", "a.md"])
        self.assertEqual(
            editor_command(P, {"EDITOR": '"C:\\Program Files\\ed.exe" -w'}, "win32"),
            ["C:\\Program Files\\ed.exe", "-w", "a.md"],
        )


if __name__ == "__main__":
    unittest.main()
