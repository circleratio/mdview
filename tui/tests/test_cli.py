import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from mdview_tui import __version__, cli
from tests.helpers import FIXTURES


def run(argv, tty=True):
    out, err = io.StringIO(), io.StringIO()
    code = None
    with redirect_stdout(out), redirect_stderr(err), mock.patch.object(cli, "_stdin_is_tty", return_value=tty):
        try:
            code = cli.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class CliTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(run(["--version"]), (0, f"mdview-tui {__version__}\n", ""))
        self.assertEqual(run(["-V"])[0], 0)

    def test_help(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("--no-watch", out)

    def test_unknown_option(self):
        code, _, err = run(["--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)

    def test_bad_theme(self):
        self.assertEqual(run(["--theme", "blue", "a.md"])[0], 2)

    def test_no_input(self):
        code, _, err = run([], tty=True)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("usage: mdview-tui"))
        self.assertIn("mdview-tui: error: no input (specify FILE or pipe to stdin)", err)

    def test_missing_file(self):
        self.assertEqual(run(["nofile.md"]), (1, "", "mdview-tui: nofile.md: No such file or directory\n"))

    def test_not_utf8(self):
        path = str(FIXTURES / "sjis.md")
        self.assertEqual(run([path]), (1, "", f"mdview-tui: {path}: not valid UTF-8\n"))

    def test_dependency_error(self):
        message = "textual>=2.0 is required (found 0.47.1)"
        with mock.patch.object(cli, "dependency_error", return_value=message):
            self.assertEqual(run([str(FIXTURES / "sample.md")]), (1, "", f"mdview-tui: {message}\n"))
            self.assertEqual(run(["--version"])[0], 0)

    def test_runs_app(self):
        with mock.patch("mdview_tui.app.MdviewApp") as app_cls:
            code, _, _ = run(["--theme", "light", "--no-watch", str(FIXTURES / "sample.md")])
        self.assertEqual(code, 0)
        _, kwargs = app_cls.call_args
        self.assertEqual(kwargs, {"theme": "light", "watch": False})

    def test_stdin(self):
        with mock.patch.object(cli, "load_stdin") as load, mock.patch.object(cli, "reattach_tty") as reattach, \
                mock.patch("mdview_tui.app.MdviewApp"):
            self.assertEqual(run([], tty=False)[0], 0)
            self.assertEqual(run(["-"], tty=True)[0], 0)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(reattach.call_count, 2)


if __name__ == "__main__":
    unittest.main()
