import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mdview_tui.app import MdviewApp
from mdview_tui.source import Source, load_file
from mdview_tui.widgets import HelpScreen, TocPanel
from tests.helpers import FIXTURES

SIZE = (60, 20)


class AppTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for name in ("sample.md", "other.md"):
            shutil.copy(FIXTURES / name, self.dir / name)
        self.sample = self.dir / "sample.md"

    def tearDown(self):
        self.tmp.cleanup()

    def make_app(self, **kwargs):
        return MdviewApp(load_file(self.sample, "sample.md"), **kwargs)


class ViewingTest(AppTestBase):
    async def test_initial_display(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.assertIsNotNone(app.view.doc)
            self.assertEqual(app.view.doc.plain_lines[0], "mdview サンプル")
            self.assertEqual(app.status.left, "sample.md")
            self.assertEqual(app.status.right, "0%")
            self.assertEqual(app.theme, "textual-dark")

    async def test_scrolling(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            view = app.view
            await pilot.press("j", "j")
            self.assertEqual(view.top_line, 2)
            await pilot.press("k")
            self.assertEqual(view.top_line, 1)
            await pilot.press("G")
            self.assertEqual(view.top_line, view.max_scroll_y)
            await pilot.pause()
            self.assertEqual(app.status.right, "100%")
            await pilot.press("g")
            self.assertEqual(view.top_line, 0)
            await pilot.press("space")
            self.assertEqual(view.top_line, view.scrollable_content_region.height)
            await pilot.press("b", "d")
            self.assertEqual(view.top_line, view.scrollable_content_region.height // 2)
            await pilot.press("u")
            self.assertEqual(view.top_line, 0)

    async def test_search(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("slash", *"タスク", "enter")
            await pilot.pause()
            view = app.view
            self.assertEqual(len(view.matches), 2)
            self.assertEqual(view.current_match, 0)
            self.assertTrue(app.status.right.startswith("[1/2]"))
            await pilot.press("n")
            await pilot.pause()
            self.assertEqual(view.current_match, 1)
            await pilot.press("N", "N")
            self.assertEqual(view.current_match, 1)
            self.assertIs(app.focused, view)

    async def test_search_not_found_and_cancel(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("slash", *"zzz", "enter")
            await pilot.pause()
            self.assertEqual(app.status.message, "見つかりません: zzz")
            await pilot.press("slash", "a", "escape")
            self.assertIs(app.focused, app.view)

    async def test_toc_jump(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("t")
            await pilot.pause()
            self.assertIsInstance(app.focused, TocPanel)
            await pilot.press("j", "j", "j", "enter")
            await pilot.pause()
            heading = app.view.doc.heading_by_anchor("小見出し")
            self.assertEqual(app.view.top_line, min(heading.line, app.view.max_scroll_y))
            self.assertIs(app.focused, app.view)
            await pilot.press("t", "escape")
            await pilot.pause()
            self.assertFalse(app.query_one(TocPanel).has_class("-visible"))

    async def test_help_and_theme(self):
        app = self.make_app(theme="light")
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.assertEqual(app.theme, "textual-light")
            await pilot.press("T")
            await pilot.pause()
            self.assertEqual(app.theme, "textual-dark")
            self.assertEqual(app.view.md_theme.name, "dark")
            await pilot.press("question_mark")
            await pilot.pause()
            self.assertIsInstance(app.screen, HelpScreen)
            await pilot.press("escape")
            await pilot.pause()
            self.assertNotIsInstance(app.screen, HelpScreen)

    async def test_resize_keeps_position(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            heading = app.view.doc.heading_by_anchor("セクション-1")
            app.view.scroll_to_line(heading.line)
            await pilot.resize_terminal(40, 20)
            await pilot.pause()
            self.assertEqual(app.view.top_line, app.view.doc.heading_by_anchor("セクション-1").line)

    async def test_quit(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
        self.assertFalse(app.is_running)


class LinkTest(AppTestBase):
    async def test_follow_relative_link_and_back(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("tab", "tab")
            self.assertEqual(app.view.selected_link, 1)
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(app.source.path, self.dir / "other.md")
            self.assertTrue(app.status.left.startswith("◀ "))
            await pilot.press("backspace")
            await pilot.pause()
            self.assertEqual(app.source.path, self.sample)
            await pilot.press("L")
            await pilot.pause()
            self.assertEqual(app.source.path, self.dir / "other.md")

    async def test_anchor_links(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.open_href("other.md#details")
            await pilot.pause()
            self.assertEqual(app.view.top_line, min(app.view.doc.heading_by_anchor("details").line, app.view.max_scroll_y))
            app.open_href("#nope")
            self.assertEqual(app.status.message, "見出しが見つかりません: #nope")
            await pilot.press("H")
            await pilot.pause()
            self.assertEqual(app.source.path, self.sample)
            app.open_href("#%E3%82%BB%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3-2")
            self.assertEqual(app.view.top_line, min(app.view.doc.heading_by_anchor("セクション-2").line, app.view.max_scroll_y))

    async def test_missing_unsupported_and_external(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.open_href("missing.md")
            self.assertIn("No such file or directory", app.status.message)
            self.assertEqual(app.source.path, self.sample)
            app.open_href("logo.png")
            self.assertEqual(app.status.message, "サポートしていないリンク: logo.png")
            with mock.patch("webbrowser.open", return_value=True) as browser:
                app.open_href("https://example.com")
            browser.assert_called_once_with("https://example.com")
            with mock.patch("webbrowser.open", return_value=False):
                app.open_href("https://example.com")
            self.assertEqual(app.status.message, "ブラウザを開けませんでした")


class ReloadTest(AppTestBase):
    def touch(self, text):
        self.sample.write_text(text, encoding="utf-8")
        st = os.stat(self.sample)
        os.utime(self.sample, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

    async def test_auto_reload(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.touch("# Changed\n")
            app._poll_file()
            await pilot.pause()
            self.assertEqual(app.view.doc.plain_lines[0], "Changed")
            self.sample.unlink()
            app._poll_file()
            self.assertEqual(app.status.message, "ファイルが削除されました")
            self.assertEqual(app.view.doc.plain_lines[0], "Changed")

    async def test_reload_keeps_line(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            await pilot.press("j", "j", "j")
            self.touch(self.sample.read_text(encoding="utf-8") + "\nappended\n")
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(app.view.top_line, 3)
            self.assertEqual(app.view.doc.plain_lines[-1], "appended")

    async def test_no_watch(self):
        app = self.make_app(watch=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.assertIsNone(app.watcher)

    async def test_editor(self):
        app = self.make_app()
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()

            def fake_run(cmd, check):
                self.touch("# Edited\n")

            with mock.patch.dict(os.environ, {"VISUAL": "myeditor"}), \
                    mock.patch("subprocess.run", side_effect=fake_run) as run, \
                    mock.patch.object(type(app), "suspend", mock.MagicMock()):
                await pilot.press("e")
                await pilot.pause()
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], ["myeditor", str(self.sample)])
            self.assertEqual(app.view.doc.plain_lines[0], "Edited")


class StdinTest(unittest.IsolatedAsyncioTestCase):
    async def test_stdin_source(self):
        app = MdviewApp(Source("# From stdin\n", None, "<stdin>"))
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            self.assertEqual(app.status.left, "<stdin>")
            self.assertIsNone(app.watcher)
            await pilot.press("e")
            self.assertEqual(app.status.message, "標準入力の表示中はエディタを起動できません")
            await pilot.press("r")
            self.assertEqual(app.status.message, "標準入力は再読込できません")


if __name__ == "__main__":
    unittest.main()
