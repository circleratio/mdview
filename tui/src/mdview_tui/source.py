"""Loading Markdown text from files or stdin."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from mdview_tui.errors import MdviewError

STDIN_NAME = "<stdin>"


@dataclass(frozen=True)
class Source:
    text: str
    path: Path | None  # None when read from stdin
    display_name: str


def _decode(data: bytes, name: str) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise MdviewError(f"{name}: not valid UTF-8") from None
    # Normalize line endings to LF.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_file(path: Path, display_name: str | None = None) -> Source:
    name = display_name if display_name is not None else str(path)
    try:
        data = Path(path).read_bytes()
    except FileNotFoundError:
        raise MdviewError(f"{name}: No such file or directory") from None
    except IsADirectoryError:
        raise MdviewError(f"{name}: Is a directory") from None
    except PermissionError:
        # Windows raises PermissionError when opening a directory.
        if Path(path).is_dir():
            raise MdviewError(f"{name}: Is a directory") from None
        raise MdviewError(f"{name}: Permission denied") from None
    except OSError as exc:
        raise MdviewError(f"{name}: {exc.strerror or exc}") from None
    return Source(_decode(data, name), Path(path), name)


def load_stdin() -> Source:
    stream = sys.stdin.buffer if sys.stdin is not None else None
    if stream is None:
        raise MdviewError("no input (specify FILE or pipe to stdin)", 2)
    return Source(_decode(stream.read(), STDIN_NAME), None, STDIN_NAME)


def reattach_tty() -> None:
    """Point fd 0 back at the terminal after stdin has been consumed."""
    try:
        if os.name == "nt":
            fd = os.open("CONIN$", os.O_RDWR)
        else:
            fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        raise MdviewError("cannot open terminal for input") from None
    try:
        os.dup2(fd, 0)
    except OSError:
        raise MdviewError("cannot open terminal for input") from None
    finally:
        os.close(fd)
    sys.stdin = os.fdopen(0, "r", closefd=False)
    sys.__stdin__ = sys.stdin
