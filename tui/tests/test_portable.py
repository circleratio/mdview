import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tests.helpers import FIXTURES

TUI_DIR = Path(__file__).resolve().parent.parent
PORTABLE = TUI_DIR / "portable" / "mdview-tui.py"
SIZE = (60, 20)


def load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look the module up in sys.modules
    spec.loader.exec_module(module)
    return module


bundle_tool = load_by_path("mdview_bundle_tool", TUI_DIR / "tools" / "bundle.py")


class UpToDateTest(unittest.TestCase):
    def test_portable_matches_package(self):
        expected = bundle_tool.bundle(TUI_DIR / "src" / "mdview_tui")
        self.assertTrue(
            PORTABLE.read_text(encoding="utf-8") == expected,
            "portable/mdview-tui.py is out of date; run `python3 tools/bundle.py`",
        )

    def test_check_option(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bundle_tool.main(["--check"]), 0)


class BundleRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pkg = Path(self.tmp.name) / "mdview_tui"
        self.pkg.mkdir()
        self.write("__init__.py", '__version__ = "9.9.9"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.pkg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")

    def bundle(self):
        return bundle_tool.bundle(self.pkg)

    def test_dependency_order_and_imports(self):
        self.write("b.py", '''\
            """Module b."""
            from __future__ import annotations

            import os
            from mdview_tui.a import A

            def main():
                from mdview_tui.a import A  # deferred
                return A + os.sep
        ''')
        self.write("a.py", "import os\nimport sys\n\nA = 'a'\n")
        text = self.bundle()
        self.assertTrue(text.startswith("#!/usr/bin/env python3\n"))
        self.assertIn("mdview-tui 9.9.9", text)
        self.assertEqual(text.count("from __future__ import annotations"), 1)
        self.assertEqual(text.count("import os\n"), 1)
        self.assertNotIn("from mdview_tui", text)
        self.assertNotIn("Module b.", text)
        self.assertLess(text.index("# ---- mdview_tui/a.py"), text.index("# ---- mdview_tui/b.py"))
        self.assertTrue(text.endswith('if __name__ == "__main__":\n    sys.exit(main())\n'))

    def test_name_collision(self):
        self.write("a.py", "def helper():\n    pass\n")
        self.write("b.py", "helper = 1\n")
        with self.assertRaisesRegex(bundle_tool.BundleError, "'helper'"):
            self.bundle()

    def test_collision_with_external_import(self):
        self.write("a.py", "from rich.text import Text\n")
        self.write("b.py", "class Text:\n    pass\n")
        with self.assertRaisesRegex(bundle_tool.BundleError, "'Text'"):
            self.bundle()

    def test_aliased_internal_import(self):
        self.write("a.py", "A = 1\n")
        self.write("b.py", "from mdview_tui.a import A as B\n")
        with self.assertRaisesRegex(bundle_tool.BundleError, "aliased"):
            self.bundle()

    def test_plain_internal_import(self):
        self.write("a.py", "A = 1\n")
        self.write("b.py", "import mdview_tui.a\n")
        with self.assertRaises(bundle_tool.BundleError):
            self.bundle()

    def test_circular_import(self):
        self.write("a.py", "from mdview_tui.b import B\nA = 1\n")
        self.write("b.py", "from mdview_tui.a import A\nB = 1\n")
        with self.assertRaisesRegex(bundle_tool.BundleError, "circular"):
            self.bundle()


class CommandLineTest(unittest.TestCase):
    """Run the portable file as a script, without the package on sys.path."""

    def run_portable(self, *args):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        with tempfile.TemporaryDirectory() as cwd:
            return subprocess.run(
                [sys.executable, str(PORTABLE), *args], cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
            )

    def test_version(self):
        version = bundle_tool._version(bundle_tool._load(TUI_DIR / "src" / "mdview_tui"))
        result = self.run_portable("--version")
        self.assertEqual((result.returncode, result.stdout), (0, f"mdview-tui {version}\n"))

    def test_missing_file(self):
        result = self.run_portable("nofile.md")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "mdview-tui: nofile.md: No such file or directory\n")


class PortableAppTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_by_path("mdview_tui_portable", PORTABLE)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for name in ("sample.md", "other.md"):
            shutil.copy(FIXTURES / name, self.dir / name)

    def tearDown(self):
        self.tmp.cleanup()

    async def test_basic_operations(self):
        mod = self.mod
        app = mod.MdviewApp(mod.load_file(self.dir / "sample.md", "sample.md"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            view = app.view
            self.assertEqual(view.doc.plain_lines[0], "mdview サンプル")
            await pilot.press("j", "j")
            self.assertEqual(view.top_line, 2)
            await pilot.press("g", "slash", *"タスク", "enter")
            await pilot.pause()
            self.assertEqual(len(view.matches), 2)
            await pilot.press("t")
            await pilot.pause()
            self.assertIsInstance(app.focused, mod.TocPanel)
            await pilot.press("escape", "tab", "tab", "enter")
            await pilot.pause()
            self.assertEqual(app.source.path, self.dir / "other.md")
            await pilot.press("backspace")
            await pilot.pause()
            self.assertEqual(app.source.path, self.dir / "sample.md")
