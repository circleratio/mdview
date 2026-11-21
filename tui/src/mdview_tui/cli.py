"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mdview_tui import __version__
from mdview_tui.errors import MdviewError
from mdview_tui.source import load_file, load_stdin, reattach_tty

NO_INPUT = "no input (specify FILE or pipe to stdin)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mdview-tui", description="View a Markdown file in the terminal.")
    parser.add_argument("-V", "--version", action="version", version=f"mdview-tui {__version__}")
    parser.add_argument("--theme", choices=["dark", "light"], default="dark", help="color theme (default: dark)")
    parser.add_argument("--no-watch", action="store_true", help="disable automatic reload on file change")
    parser.add_argument("file", nargs="?", metavar="FILE", help="Markdown file to view ('-' for stdin)")
    return parser


def _stdin_is_tty() -> bool:
    return sys.stdin is None or sys.stdin.isatty()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.file == "-" or (args.file is None and not _stdin_is_tty()):
            source = load_stdin()
            reattach_tty()
        elif args.file is None:
            parser.print_usage(sys.stderr)
            print(f"mdview-tui: error: {NO_INPUT}", file=sys.stderr)
            return 2
        else:
            source = load_file(Path(args.file), args.file)

        from mdview_tui.app import MdviewApp  # deferred: keeps --help/errors fast

        MdviewApp(source, theme=args.theme, watch=not args.no_watch).run()
        return 0
    except MdviewError as exc:
        print(f"mdview-tui: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
