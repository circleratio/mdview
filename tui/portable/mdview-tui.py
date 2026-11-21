#!/usr/bin/env python3
# mdview-tui 0.1.0 -- portable single-file version.
#
# GENERATED FILE: do not edit. The source of truth is tui/src/mdview_tui/;
# regenerate with `python3 tools/bundle.py` in the tui/ directory.
#
# Requires Python 3.10+ and: textual>=2.0, markdown-it-py[linkify]>=3.0, PyYAML>=6.0
# Usage: python3 mdview-tui.py [OPTIONS] [FILE]
"""mdview-tui: a TUI viewer for Markdown files (portable single-file version)."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import re
import sys


# ---- mdview_tui/deps.py ----

# (distribution name, import name, minimum version); keep in sync with pyproject.toml
REQUIREMENTS = (
    ("textual", "textual", "2.0"),
    ("markdown-it-py", "markdown_it", "3.0"),
    ("PyYAML", "yaml", "6.0"),
)


def version_tuple(version: str) -> tuple[int, ...]:
    """Return the leading numeric release part of `version`, e.g. "2.1.2-1" -> (2, 1, 2)."""
    m = re.match(r"\d+(?:\.\d+)*", version.strip())
    return tuple(int(p) for p in m.group(0).split(".")) if m else ()


def _installed_version(dist: str, module: str) -> str | None:
    """Return the installed version, "" if importable but unknown, or None if missing."""
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return "" if importlib.util.find_spec(module) is not None else None


def dependency_error() -> str | None:
    """Return a message describing missing or too old libraries, or None if all are usable."""
    problems = []
    for dist, module, minimum in REQUIREMENTS:
        found = _installed_version(dist, module)
        if found is None:
            problems.append(f"{dist}>={minimum} is required (not installed)")
        elif found and version_tuple(found) < version_tuple(minimum):
            problems.append(f"{dist}>={minimum} is required (found {found})")
    return "; ".join(problems) or None


if dependency_error() is not None:
    sys.exit(f"mdview-tui: {dependency_error()}")


import argparse
from collections.abc import Mapping
from dataclasses import dataclass, field
import io
import os
from pathlib import Path
import shlex
import subprocess
from typing import Literal
from urllib.parse import unquote, urlsplit
import webbrowser

from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound
from rich import box
from rich.cells import cell_len
from rich.console import Console, RenderableType
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.geometry import Size
from textual.message import Message
from textual.screen import ModalScreen
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.timer import Timer
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option
import yaml


# ---- mdview_tui/__init__.py ----

__version__ = "0.1.0"


# ---- mdview_tui/editor.py ----

def editor_command(
    path: Path, env: Mapping[str, str] | None = None, platform: str | None = None
) -> list[str]:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    windows = platform.startswith("win")
    value = (env.get("VISUAL") or "").strip() or (env.get("EDITOR") or "").strip()
    if value:
        parts = shlex.split(value, posix=not windows)
        if windows:
            parts = [p.strip('"') for p in parts]
    else:
        parts = ["notepad" if windows else "vi"]
    return [*parts, str(path)]


# ---- mdview_tui/errors.py ----

class MdviewError(Exception):
    """A user-facing error with a message and an exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


# ---- mdview_tui/frontmatter.py ----

OPEN_FENCE = re.compile(r"---[ \t]*")
CLOSE_FENCE = re.compile(r"(---|\.\.\.)[ \t]*")
NOT_A_MAPPING = "フロントマターがキーと値の形式ではありません"
ERROR_PREFIX = "フロントマターを解釈できませんでした: "


@dataclass(frozen=True)
class FrontMatter:
    raw: str  # text between the fences
    data: dict[str, object] | None  # parsed mapping, None on error
    error: str | None  # one-line reason when it could not be parsed


@dataclass(frozen=True)
class FrontMatterView:
    title: str | None
    byline: list[str]  # author, then date (only non-empty ones)
    others: list[tuple[str, str]]  # every other key, in the order written

    @property
    def is_empty(self) -> bool:
        return self.title is None and not self.byline and not self.others


def split_front_matter(text: str) -> tuple[FrontMatter | None, str]:
    """Split a leading front matter block off `text` (BOM removed, LF line endings).

    The block is replaced with the same number of empty lines, so line numbers in the
    returned body still match the file.
    """
    lines = text.split("\n")
    if not OPEN_FENCE.fullmatch(lines[0]):
        return None, text
    close = next((i for i in range(1, len(lines)) if CLOSE_FENCE.fullmatch(lines[i])), None)
    if close is None:
        # No closing fence: just a document that starts with a horizontal rule.
        return None, text
    raw = "\n".join(lines[1:close])
    body = "\n".join([""] * (close + 1) + lines[close + 1:])
    return _parse(raw), body


def _parse(raw: str) -> FrontMatter:
    try:
        # BaseLoader keeps every scalar as the string written: no dates, no 1.10 -> 1.1.
        data = yaml.load(raw, Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        return FrontMatter(raw, None, _reason(exc))
    if data is None or data == "":
        return FrontMatter(raw, {}, None)
    if not isinstance(data, dict):
        return FrontMatter(raw, None, NOT_A_MAPPING)
    return FrontMatter(raw, data, None)


def _reason(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None)
    mark = getattr(exc, "problem_mark", None)
    if problem:
        if mark is not None:
            return f"{problem} (line {mark.line + 1}, column {mark.column + 1})"
        return str(problem)
    return str(exc).split("\n", 1)[0]


def format_value(value: object) -> str:
    """Flatten a value to one line: lists as "a, b", mappings as "k: v, k2: v2"."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(format_value(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {format_value(v)}" for k, v in value.items())
    return str(value)


def format_author(value: object) -> str:
    """`author` may be one name or a list of names; a list is joined with "、"."""
    if isinstance(value, list):
        return "、".join(s for s in (format_value(v) for v in value) if s)
    return format_value(value)


def to_view(data: dict[str, object]) -> FrontMatterView:
    title = format_value(data.get("title"))
    byline = [s for s in (format_author(data.get("author")), format_value(data.get("date"))) if s]
    others = [
        (str(key), format_value(value))
        for key, value in data.items()
        if key not in ("title", "author", "date")
    ]
    return FrontMatterView(title or None, byline, others)


# ---- mdview_tui/keys.py ----

@dataclass(frozen=True)
class KeySpec:
    keys: tuple[str, ...]  # Textual key names
    label: str  # shown in the help screen
    action: str
    description: str
    scope: Literal["view", "app"]
    priority: bool = False


KEYSPECS: tuple[KeySpec, ...] = (
    KeySpec(("j", "down"), "j / ↓", "line_down", "1行下へ", "view"),
    KeySpec(("k", "up"), "k / ↑", "line_up", "1行上へ", "view"),
    KeySpec(("space", "f", "pagedown"), "Space / f / PgDn", "page_down", "1画面下へ", "view"),
    KeySpec(("b", "pageup"), "b / PgUp", "page_up", "1画面上へ", "view"),
    KeySpec(("d",), "d", "half_down", "半画面下へ", "view"),
    KeySpec(("u",), "u", "half_up", "半画面上へ", "view"),
    KeySpec(("g", "home"), "g / Home", "top", "先頭へ", "view"),
    KeySpec(("G", "end"), "G / End", "bottom", "末尾へ", "view"),
    KeySpec(("slash",), "/", "search", "検索", "app"),
    KeySpec(("n",), "n", "next_match", "次の一致へ", "view"),
    KeySpec(("N",), "N", "prev_match", "前の一致へ", "view"),
    KeySpec(("t",), "t", "toggle_toc", "目次パネルの表示切替", "app"),
    KeySpec(("tab",), "Tab", "next_link", "次のリンクを選択", "view"),
    KeySpec(("shift+tab",), "Shift+Tab", "prev_link", "前のリンクを選択", "view"),
    KeySpec(("enter",), "Enter", "open_link", "選択中のリンクを開く", "view"),
    KeySpec(("backspace", "H"), "Backspace / H", "back", "履歴を戻る", "app"),
    KeySpec(("L",), "L", "forward", "履歴を進む", "app"),
    KeySpec(("e",), "e", "edit", "外部エディタで開く", "app"),
    KeySpec(("r",), "r", "reload", "手動再読込", "app"),
    KeySpec(("T",), "T", "toggle_theme", "テーマ切替", "app"),
    KeySpec(("question_mark",), "?", "help", "ヘルプ表示", "app"),
    KeySpec(("q", "ctrl+c"), "q / Ctrl+C", "quit", "終了", "app", priority=True),
)


def bindings(scope: str) -> list[Binding]:
    return [
        Binding(",".join(spec.keys), spec.action, spec.description, show=False, priority=spec.priority)
        for spec in KEYSPECS
        if spec.scope == scope
    ]


# ---- mdview_tui/links.py ----

MARKDOWN_SUFFIXES = (".md", ".markdown")


@dataclass(frozen=True)
class Target:
    kind: Literal["anchor", "file", "external", "unsupported"]
    path: Path | None = None
    anchor: str | None = None
    url: str | None = None


def display_href(href: str) -> str:
    """Return a link target as the user wrote it, for showing on screen.

    markdown-it percent-encodes every href and image src (normalizeLink), so
    `[x](図.png)` arrives as `%E5%9B%B3.png`. Malformed escapes are left as they are.
    """
    return unquote(href)


def resolve(href: str, base: Path | None) -> Target:
    href = href.strip()
    if not href:
        return Target("unsupported")
    if href.startswith("#"):
        return Target("anchor", anchor=unquote(href[1:]))
    scheme = urlsplit(href).scheme
    # A single letter "scheme" is a Windows drive letter, not a URL.
    if scheme and len(scheme) > 1:
        if scheme.lower() == "file":
            # Local paths, never handed to the OS (doc/common.md 4).
            return _local(*_file_url(href), base)
        return Target("external", url=href)
    path_part, _, fragment = href.partition("#")
    return _local(unquote(path_part), unquote(fragment), base)


def _file_url(href: str) -> tuple[str, str]:
    """Split a `file:` URL into (local path, anchor)."""
    parts = urlsplit(href)
    path = unquote(parts.path)
    # file:///C:/x.md -> C:/x.md, only meaningful where drive letters exist.
    if os.name == "nt" and re.match(r"/[A-Za-z]:([/\\]|$)", path):
        path = path[1:]
    if parts.netloc and parts.netloc.lower() != "localhost":
        path = f"//{parts.netloc}{path}"  # UNC path: file://server/share/x.md
    return path, unquote(parts.fragment)


def _local(path_str: str, fragment: str, base: Path | None) -> Target:
    path = Path(path_str)
    if path.suffix.lower() not in MARKDOWN_SUFFIXES:
        return Target("unsupported")
    if not path.is_absolute():
        root = base.parent if base is not None else Path.cwd()
        path = root / path
    return Target("file", path=path, anchor=fragment or None)


# ---- mdview_tui/parser.py ----

@dataclass(frozen=True)
class ParsedDocument:
    tokens: list[Token]
    front_matter: FrontMatter | None  # None when the text has no front matter


def create_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"linkify": True, "html": True})
    md.enable(["table", "strikethrough", "linkify"])
    return md


_PARSER = create_parser()


def parse(text: str) -> list[Token]:
    return _PARSER.parse(text)


def parse_document(text: str) -> ParsedDocument:
    """Split off the front matter, then parse the rest as Markdown."""
    front_matter, body = split_front_matter(text)
    return ParsedDocument(parse(body), front_matter)


def to_tree(tokens: list[Token]) -> SyntaxTreeNode:
    return SyntaxTreeNode(tokens)


# ---- mdview_tui/search.py ----

@dataclass(frozen=True)
class Match:
    line: int
    start: int  # cell offset
    end: int  # cell offset


def find_all(plain_lines: list[str], query: str) -> list[Match]:
    if not query:
        return []
    needle = query.casefold()
    matches: list[Match] = []
    for line_no, line in enumerate(plain_lines):
        # casefold() may change string length (e.g. "ß"), so compare per position.
        folded = [ch.casefold() for ch in line]
        haystack = "".join(folded)
        offsets = []  # index in haystack -> index in line
        for i, part in enumerate(folded):
            offsets.extend([i] * len(part))
        offsets.append(len(line))
        pos = haystack.find(needle)
        while pos != -1:
            begin = offsets[pos]
            finish = offsets[pos + len(needle) - 1] + 1
            start = cell_len(line[:begin])
            matches.append(Match(line_no, start, start + cell_len(line[begin:finish])))
            pos = haystack.find(needle, pos + max(1, len(needle)))
    return matches


def next_match(
    matches: list[Match], current: int | None, top_line: int, forward: bool
) -> int | None:
    """Index of the next (or previous) match, wrapping around.

    If no match is current, start from the top visible line.
    """
    if not matches:
        return None
    if current is not None:
        step = 1 if forward else -1
        return (current + step) % len(matches)
    if forward:
        for i, m in enumerate(matches):
            if m.line >= top_line:
                return i
        return 0
    for i in range(len(matches) - 1, -1, -1):
        if matches[i].line < top_line:
            return i
    return len(matches) - 1


# ---- mdview_tui/slug.py ----

_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)


def slugify(text: str) -> str:
    slug = _STRIP.sub("", text.strip().lower())
    return slug.replace(" ", "-")


class SlugRegistry:
    """Generates unique slugs: foo, foo-1, foo-2, ..."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def make(self, text: str) -> str:
        base = slugify(text)
        if base not in self._counts:
            self._counts[base] = 0
            return base
        while True:
            self._counts[base] += 1
            candidate = f"{base}-{self._counts[base]}"
            if candidate not in self._counts:
                self._counts[candidate] = 0
                return candidate


# ---- mdview_tui/document.py ----

@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    anchor: str
    line: int


@dataclass(frozen=True)
class LinkRegion:
    link_id: int
    href: str
    line: int
    start: int  # cell offset (inclusive)
    end: int  # cell offset (exclusive)


@dataclass
class RenderedDoc:
    lines: list[Strip]
    plain_lines: list[str]
    headings: list[Heading] = field(default_factory=list)
    links: list[LinkRegion] = field(default_factory=list)
    width: int = 0
    # (rendered line, source line) pairs sorted by rendered line
    anchors: list[tuple[int, int]] = field(default_factory=list)

    def heading_by_anchor(self, anchor: str) -> Heading | None:
        for candidate in (anchor, anchor.lower(), slugify(anchor)):
            for heading in self.headings:
                if heading.anchor == candidate:
                    return heading
        return None

    def link_ids(self) -> list[int]:
        seen: list[int] = []
        for region in self.links:
            if not seen or seen[-1] != region.link_id:
                if region.link_id not in seen:
                    seen.append(region.link_id)
        return seen

    def regions_of(self, link_id: int) -> list[LinkRegion]:
        return [r for r in self.links if r.link_id == link_id]

    def source_position(self, line: int) -> tuple[int, int]:
        """Map a rendered line to (source line of its block, offset in block)."""
        best: tuple[int, int] | None = None
        for rendered, source in self.anchors:
            if rendered > line:
                break
            best = (rendered, source)
        if best is None:
            return (0, line)
        return (best[1], line - best[0])

    def line_for(self, source_line: int, offset: int = 0) -> int:
        """Inverse of source_position(), clamped to the document."""
        last = max(0, len(self.lines) - 1)
        for i, (rendered, source) in enumerate(self.anchors):
            if source == source_line:
                # Stay within this block when its rendered height shrank.
                limit = last
                for later, later_source in self.anchors[i + 1:]:
                    if later > rendered and later_source != source_line:
                        limit = later - 1
                        break
                return min(rendered + offset, limit)
            if source > source_line:
                return min(rendered, last)
        return min(offset, last) if not self.anchors else last


# ---- mdview_tui/source.py ----

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


# ---- mdview_tui/history.py ----

@dataclass
class Location:
    source: Source
    scroll_y: int


class History:
    def __init__(self, initial: Location) -> None:
        self._back: list[Location] = []
        self._forward: list[Location] = []
        self._current = initial

    @property
    def current(self) -> Location:
        return self._current

    def push(self, loc: Location) -> None:
        self._back.append(self._current)
        self._current = loc
        self._forward.clear()

    def update_current(self, scroll_y: int) -> None:
        self._current.scroll_y = scroll_y

    def back(self) -> Location | None:
        if not self._back:
            return None
        self._forward.append(self._current)
        self._current = self._back.pop()
        return self._current

    def forward(self) -> Location | None:
        if not self._forward:
            return None
        self._back.append(self._current)
        self._current = self._forward.pop()
        return self._current

    def can_back(self) -> bool:
        return bool(self._back)

    def can_forward(self) -> bool:
        return bool(self._forward)


# ---- mdview_tui/themes.py ----

@dataclass(frozen=True)
class MdTheme:
    name: Literal["dark", "light"]
    textual_theme: str
    pygments_style: str
    heading: tuple[Style, ...]  # H1..H6
    link: Style
    link_selected: Style
    code_inline: Style
    code_block_bg: str
    quote: Style
    html: Style
    rule: Style
    meta: Style  # front matter byline and fields
    error: Style  # front matter error line
    search_match: Style
    search_current: Style


THEMES: dict[str, MdTheme] = {
    "dark": MdTheme(
        name="dark",
        textual_theme="textual-dark",
        pygments_style="monokai",
        heading=(
            Style.parse("bold #c678dd"),
            Style.parse("bold #61afef"),
            Style.parse("bold #98c379"),
            Style.parse("bold #e5c07b"),
            Style.parse("bold #e5c07b"),
            Style.parse("bold #e5c07b"),
        ),
        link=Style.parse("underline #56b6c2"),
        link_selected=Style.parse("reverse bold"),
        code_inline=Style.parse("#e06c75 on #2c313a"),
        code_block_bg="#1e2127",
        quote=Style.parse("italic #9da5b4"),
        html=Style.parse("#7f848e"),
        rule=Style.parse("#5c6370"),
        meta=Style.parse("#9da5b4"),
        error=Style.parse("bold #e06c75"),
        search_match=Style.parse("#000000 on #e5c07b"),
        search_current=Style.parse("bold #000000 on #ff8800"),
    ),
    "light": MdTheme(
        name="light",
        textual_theme="textual-light",
        pygments_style="default",
        heading=(
            Style.parse("bold #a626a4"),
            Style.parse("bold #4078f2"),
            Style.parse("bold #50a14f"),
            Style.parse("bold #c18401"),
            Style.parse("bold #c18401"),
            Style.parse("bold #c18401"),
        ),
        link=Style.parse("underline #0184bc"),
        link_selected=Style.parse("reverse bold"),
        code_inline=Style.parse("#e45649 on #eaeaeb"),
        code_block_bg="#f0f0f0",
        quote=Style.parse("italic #696c77"),
        html=Style.parse("#a0a1a7"),
        rule=Style.parse("#a0a1a7"),
        meta=Style.parse("#696c77"),
        error=Style.parse("bold #e45649"),
        search_match=Style.parse("#000000 on #ffe066"),
        search_current=Style.parse("bold #000000 on #ff9f43"),
    ),
}


def toggle(name: str) -> str:
    return "light" if name == "dark" else "dark"


# ---- mdview_tui/render.py ----

Line = list[Segment]
BULLETS = ("•", "◦", "▪")
TASK_PREFIXES = {"[ ] ": False, "[x] ": True, "[X] ": True}
MIN_WIDTH = 10
FIELD_GAP = 2  # cells between a front matter key and its value
MIN_FIELD_VALUE = 8  # narrower than this, values go below their keys


@dataclass
class _Block:
    lines: list[Line] = field(default_factory=list)
    # (relative line, level, plain text)
    headings: list[tuple[int, int, str]] = field(default_factory=list)
    # (relative line, source line) where a source block starts
    anchors: list[tuple[int, int]] = field(default_factory=list)

    def extend(self, other: _Block) -> None:
        offset = len(self.lines)
        self.lines.extend(other.lines)
        self.headings.extend((offset + ln, lv, tx) for ln, lv, tx in other.headings)
        self.anchors.extend((offset + ln, src) for ln, src in other.anchors)


class _Renderer:
    def __init__(self, theme: MdTheme, width: int) -> None:
        self.theme = theme
        self.width = width
        self.console = Console(
            width=width,
            file=io.StringIO(),
            force_terminal=True,
            color_system="truecolor",
            legacy_windows=False,
            emoji=False,
            markup=False,
            highlight=False,
        )
        self.hrefs: list[str] = []
        self.list_depth = 0

    # ---- helpers -------------------------------------------------------

    def lines_of(self, renderable: RenderableType, width: int, pad: bool = False) -> list[Line]:
        options = self.console.options.update(width=max(1, width))
        lines = self.console.render_lines(renderable, options, pad=pad, new_lines=False)
        if not pad:
            lines = [_rstrip_line(line) for line in lines]
        return lines

    def link_style(self, href: str) -> Style:
        link_id = len(self.hrefs)
        self.hrefs.append(href)
        return self.theme.link + Style(meta={"link_id": link_id})

    # ---- inline --------------------------------------------------------

    def inline(self, node: SyntaxTreeNode | None, base: Style | None = None, skip: int = 0) -> Text:
        text = Text(overflow="fold", no_wrap=False)
        if node is not None:
            self._inline_children(node.children, text, base or Style(), [skip])
        return text

    def _inline_children(self, nodes, text: Text, style: Style, skip: list[int]) -> None:
        for node in nodes:
            kind = node.type
            if kind == "text":
                content = node.content
                if skip[0]:
                    content, skip[0] = content[skip[0]:], 0
                text.append(content, style)
            elif kind == "softbreak":
                text.append(" ", style)
            elif kind == "hardbreak":
                text.append("\n", style)
            elif kind == "code_inline":
                text.append(node.content, style + self.theme.code_inline)
            elif kind == "em":
                self._inline_children(node.children, text, style + Style(italic=True), skip)
            elif kind == "strong":
                self._inline_children(node.children, text, style + Style(bold=True), skip)
            elif kind == "s":
                self._inline_children(node.children, text, style + Style(strike=True), skip)
            elif kind == "link":
                href = str(node.attrs.get("href", ""))
                self._inline_children(node.children, text, style + self.link_style(href), skip)
            elif kind == "image":
                src = str(node.attrs.get("src", ""))
                alt = _plain(node) or str(node.attrs.get("alt", ""))
                # Show the path as written; the link itself keeps the encoded form for resolve().
                text.append(f"[image: {alt}]({display_href(src)})", style + self.link_style(src))
            elif kind == "html_inline":
                text.append(node.content, style + self.theme.html)
            elif node.children:
                self._inline_children(node.children, text, style, skip)
            else:
                text.append(node.content, style)

    # ---- blocks --------------------------------------------------------

    def children(self, nodes, width: int, tight: bool = False) -> _Block:
        block = _Block()
        for node in nodes:
            child = self.node(node, width)
            if not child.lines:
                continue
            if block.lines and not tight:
                block.lines.append([])
            block.extend(child)
        return block

    def node(self, node: SyntaxTreeNode, width: int) -> _Block:
        block = self._node(node, width)
        if node.map and block.lines:
            block.anchors.insert(0, (0, node.map[0]))
        return block

    def _node(self, node: SyntaxTreeNode, width: int) -> _Block:
        kind = node.type
        handler = getattr(self, f"_{kind}", None)
        if handler is not None:
            return handler(node, width)
        if node.children:
            return self.children(node.children, width)
        if node.content:
            return _Block(self.lines_of(Text(node.content.rstrip("\n")), width))
        return _Block()

    def _heading(self, node: SyntaxTreeNode, width: int) -> _Block:
        level = int(node.tag[1])
        style = self.theme.heading[level - 1]
        inline = node.children[0] if node.children else None
        text = self.inline(inline, style)
        plain = text.plain
        if level >= 3:
            text = Text("#" * level + " ", style, overflow="fold") + text
        lines = self.lines_of(text, width)
        if level == 1:
            lines.append([Segment("═" * width, style)])
        elif level == 2:
            lines.append([Segment("─" * width, style)])
        return _Block(lines, [(0, level, plain)])

    def _paragraph(self, node: SyntaxTreeNode, width: int, skip: int = 0) -> _Block:
        inline = node.children[0] if node.children else None
        return _Block(self.lines_of(self.inline(inline, skip=skip), width))

    def _list(self, node: SyntaxTreeNode, width: int, ordered: bool) -> _Block:
        items = node.children
        tight = any(
            child.type == "paragraph" and child.hidden
            for item in items
            for child in item.children
        )
        start = int(node.attrs.get("start", 1)) if ordered else 1
        number_width = len(f"{start + len(items) - 1}.") if ordered else 0
        bullet = BULLETS[self.list_depth % len(BULLETS)]
        self.list_depth += 1
        block = _Block()
        try:
            for index, item in enumerate(items):
                task = _task_state(item)
                if task is not None:
                    marker = ("☑" if task else "☐") + " "
                elif ordered:
                    marker = f"{start + index}.".ljust(number_width) + " "
                else:
                    marker = bullet + " "
                indent = cell_len(marker)
                body = self._item_body(item, width - indent, tight, task is not None)
                if block.lines and not tight:
                    block.lines.append([])
                lines = body.lines or [[]]
                prefixed = _Block(
                    [
                        [Segment(marker if i == 0 else " " * indent)] + line
                        for i, line in enumerate(lines)
                    ],
                    body.headings,
                    body.anchors,
                )
                block.extend(prefixed)
        finally:
            self.list_depth -= 1
        return block

    def _item_body(self, item: SyntaxTreeNode, width: int, tight: bool, task: bool) -> _Block:
        block = _Block()
        for i, child in enumerate(item.children):
            if i == 0 and task and child.type == "paragraph":
                part = self._paragraph(child, width, skip=4)
                if child.map and part.lines:
                    part.anchors.insert(0, (0, child.map[0]))
            else:
                part = self.node(child, width)
            if not part.lines:
                continue
            if block.lines and not tight:
                block.lines.append([])
            block.extend(part)
        return block

    def _bullet_list(self, node: SyntaxTreeNode, width: int) -> _Block:
        return self._list(node, width, ordered=False)

    def _ordered_list(self, node: SyntaxTreeNode, width: int) -> _Block:
        return self._list(node, width, ordered=True)

    def _blockquote(self, node: SyntaxTreeNode, width: int) -> _Block:
        inner = self.children(node.children, width - 2)
        bar = Segment("▌ ", self.theme.quote)
        lines = [[bar, *Segment.apply_style(line, self.theme.quote)] for line in inner.lines]
        return _Block(lines, inner.headings, inner.anchors)

    def _code(self, code: str, lang: str, width: int) -> _Block:
        lexer = "text"
        if lang:
            try:
                get_lexer_by_name(lang)
                lexer = lang
            except ClassNotFound:
                pass
        syntax = Syntax(
            code,
            lexer,
            theme=self.theme.pygments_style,
            background_color=self.theme.code_block_bg,
            word_wrap=False,
            padding=(0, 1),
        )
        return _Block(self.lines_of(syntax, width, pad=True))

    def _fence(self, node: SyntaxTreeNode, width: int) -> _Block:
        info = node.info.strip().split()
        return self._code(node.content.rstrip("\n"), info[0] if info else "", width)

    def _code_block(self, node: SyntaxTreeNode, width: int) -> _Block:
        return self._code(node.content.rstrip("\n"), "", width)

    def _hr(self, node: SyntaxTreeNode, width: int) -> _Block:
        return _Block([[Segment("─" * width, self.theme.rule)]])

    def _html_block(self, node: SyntaxTreeNode, width: int) -> _Block:
        text = Text(node.content.rstrip("\n"), self.theme.html, overflow="fold")
        return _Block(self.lines_of(text, width))

    def _table(self, node: SyntaxTreeNode, width: int) -> _Block:
        table = Table(
            box=box.SQUARE,
            border_style=self.theme.rule,
            show_header=True,
            header_style=Style(bold=True),
            expand=False,
        )
        header_rows: list[SyntaxTreeNode] = []
        body_rows: list[SyntaxTreeNode] = []
        for section in node.children:
            target = header_rows if section.type == "thead" else body_rows
            target.extend(section.children)
        if header_rows:
            for cell in header_rows[0].children:
                align = _align(cell)
                table.add_column(self._cell(cell), justify=align, overflow="fold")
        for row in body_rows:
            cells = [self._cell(cell) for cell in row.children]
            table.add_row(*cells)
        return _Block(self.lines_of(table, width))

    def front_matter(self, fm: FrontMatter, width: int) -> _Block:
        """The front matter header shown above the body (no headings, no links)."""
        theme = self.theme
        rule = [Segment("─" * width, theme.rule)]
        if fm.data is None:
            lines = self.lines_of(Text(ERROR_PREFIX + (fm.error or ""), theme.error, overflow="fold"), width)
            if fm.raw:
                lines += self.lines_of(Text(fm.raw, theme.meta, overflow="fold"), width)
            return _Block(lines + [rule], anchors=[(0, 0)])
        view = to_view(fm.data)
        if view.is_empty:
            return _Block()
        lines: list[Line] = []
        if view.title is not None:
            lines += self.lines_of(Text(view.title, theme.heading[0], overflow="fold"), width)
        if view.byline:
            lines += self.lines_of(Text(" ・ ".join(view.byline), theme.meta, overflow="fold"), width)
        if view.others:
            if lines:
                lines.append([Segment("┄" * width, theme.rule)])
            lines += self.fields(view.others, width)
        return _Block(lines + [rule], anchors=[(0, 0)])

    def fields(self, fields: list[tuple[str, str]], width: int) -> list[Line]:
        """Key/value rows. Values wrap with a hanging indent; when the window is too narrow
        for two columns, each value goes below its key instead (a table would drop it)."""
        style = self.theme.meta
        key_width = max(cell_len(key) for key, _ in fields)
        value_width = width - key_width - FIELD_GAP
        two_columns = value_width >= max(MIN_FIELD_VALUE, key_width)
        lines: list[Line] = []
        for key, value in fields:
            if two_columns:
                pad = " " * (key_width - cell_len(key) + FIELD_GAP)
                body = self.lines_of(Text(value, style, overflow="fold"), value_width) or [[]]
                lines.append([Segment(key + pad, style), *body[0]])
                lines.extend([Segment(" " * (key_width + FIELD_GAP)), *line] for line in body[1:])
            else:
                lines += self.lines_of(Text(key, style, overflow="fold"), width)
                if value:
                    indent = min(FIELD_GAP, width - 1)
                    body = self.lines_of(Text(value, style, overflow="fold"), width - indent)
                    lines.extend([Segment(" " * indent), *line] for line in body)
        return lines

    def _cell(self, cell: SyntaxTreeNode) -> Text:
        inline = cell.children[0] if cell.children else None
        return self.inline(inline)


def _rstrip_line(line: Line) -> Line:
    """Drop trailing unstyled padding so prefixes stay compact."""
    result = list(line)
    while result and not _has_bg(result[-1].style):
        last = result[-1]
        text = last.text.rstrip(" ")
        if text:
            result[-1] = Segment(text, last.style, last.control)
            break
        result.pop()
    return result


def _has_bg(style: Style | None) -> bool:
    return bool(style and style.bgcolor)


def _plain(node: SyntaxTreeNode) -> str:
    parts: list[str] = []
    for child in node.children:
        if child.type == "text":
            parts.append(child.content)
        else:
            parts.append(_plain(child))
    return "".join(parts)


def _task_state(item: SyntaxTreeNode) -> bool | None:
    if not item.children or item.children[0].type != "paragraph":
        return None
    para = item.children[0]
    if not para.children or not para.children[0].children:
        return None
    first = para.children[0].children[0]
    if first.type != "text":
        return None
    for prefix, state in TASK_PREFIXES.items():
        if first.content.startswith(prefix):
            return state
    return None


def _align(cell: SyntaxTreeNode) -> str:
    style = str(cell.attrs.get("style", ""))
    for name in ("left", "right", "center"):
        if f"text-align:{name}" in style:
            return name
    return "left"


def _link_regions(lines: list[Line], hrefs: list[str]) -> list[LinkRegion]:
    regions: list[LinkRegion] = []
    for line_no, line in enumerate(lines):
        x = 0
        current: list[int] | None = None  # [link_id, start, end]
        for seg in line:
            width = cell_len(seg.text)
            meta = seg.style.meta if seg.style is not None else {}
            link_id = meta.get("link_id") if meta else None
            if link_id is not None and current is not None and current[0] == link_id and current[2] == x:
                current[2] = x + width
            else:
                if current is not None:
                    regions.append(LinkRegion(current[0], hrefs[current[0]], line_no, current[1], current[2]))
                current = [link_id, x, x + width] if link_id is not None else None
            x += width
        if current is not None:
            regions.append(LinkRegion(current[0], hrefs[current[0]], line_no, current[1], current[2]))
    return [r for r in regions if r.end > r.start]


def render(
    tokens: list[Token], width: int, theme: MdTheme, front_matter: FrontMatter | None = None
) -> RenderedDoc:
    width = max(MIN_WIDTH, width)
    renderer = _Renderer(theme, width)
    tree = SyntaxTreeNode(tokens)
    block = renderer.front_matter(front_matter, width) if front_matter is not None else _Block()
    body = renderer.children(tree.children, width)
    if block.lines and body.lines:
        block.lines.append([])
    block.extend(body)
    lines = block.lines
    slugs = SlugRegistry()
    headings = [
        Heading(level, text, slugs.make(text), line) for line, level, text in block.headings
    ]
    plain_lines = ["".join(seg.text for seg in line) for line in lines]
    links = _link_regions(lines, renderer.hrefs)
    strips = [Strip(line) for line in lines]
    anchors = sorted(block.anchors, key=lambda a: a[0])
    return RenderedDoc(strips, plain_lines, headings, links, width, anchors)


# ---- mdview_tui/watcher.py ----

Status = Literal["unchanged", "modified", "deleted"]


class FileWatcher:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._sig = self._stat()

    def _stat(self) -> tuple[int, int] | None:
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def check(self) -> Status:
        """Report a change since the previous call.

        "deleted" is reported once when the file disappears; a re-created
        file is reported as "modified".
        """
        sig = self._stat()
        if sig == self._sig:
            return "unchanged"
        old, self._sig = self._sig, sig
        if sig is None:
            return "deleted"
        return "modified" if old != sig else "unchanged"


# ---- mdview_tui/widgets/help.py ----

def help_table() -> Table:
    table = Table(title="キーバインド", show_header=True, header_style="bold", expand=False)
    table.add_column("キー", no_wrap=True)
    table.add_column("動作")
    for spec in KEYSPECS:
        table.add_row(spec.label, spec.description)
    return table


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,question_mark", "dismiss", "閉じる", show=False)]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > VerticalScroll {
        width: auto;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(help_table(), id="help-table")


# ---- mdview_tui/widgets/search_bar.py ----

class SearchInput(Input):
    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    class Cancelled(Message):
        pass

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())


# ---- mdview_tui/widgets/status.py ----

MESSAGE_SECONDS = 3.0


class StatusBar(Static):
    def __init__(self, *, id: str | None = None) -> None:
        super().__init__("", id=id)
        self.left = ""
        self.right = ""
        self.message = ""
        self._timer: Timer | None = None

    def set_info(self, left: str, right: str) -> None:
        self.left, self.right = left, right
        self._redraw()

    def flash(self, message: str) -> None:
        self.message = message
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(MESSAGE_SECONDS, self._clear)
        self._redraw()

    def _clear(self) -> None:
        self.message = ""
        self._timer = None
        self._redraw()

    def _redraw(self) -> None:
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(justify="left", no_wrap=True, ratio=2)
        grid.add_column(justify="center", no_wrap=True, ratio=3)
        grid.add_column(justify="right", no_wrap=True, ratio=1)
        grid.add_row(
            Text(self.left, style="bold", overflow="ellipsis"),
            Text(self.message, overflow="ellipsis"),
            Text(self.right),
        )
        self.update(grid)


# ---- mdview_tui/widgets/toc.py ----

class TocPanel(OptionList):
    BINDINGS = [
        Binding("escape,t", "close", "閉じる", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    class Closed(Message):
        pass

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.headings: list[Heading] = []

    def set_headings(self, headings: list[Heading], current_line: int) -> None:
        self.headings = list(headings)
        self.clear_options()
        min_level = min((h.level for h in headings), default=1)
        self.add_options(
            Option("  " * (h.level - min_level) + h.text, id=str(i))
            for i, h in enumerate(self.headings)
        )
        current = None
        for i, heading in enumerate(self.headings):
            if heading.line <= current_line:
                current = i
        if self.headings:
            self.highlighted = current if current is not None else 0

    def action_close(self) -> None:
        self.post_message(self.Closed())


# ---- mdview_tui/widgets/view.py ----

MARGIN = 1  # blank cells on the left and right of the text


def highlight(segments: list[Segment], ranges: list[tuple[int, int, Style]]) -> list[Segment]:
    """Overlay styles on cell ranges [start, end)."""
    if not ranges:
        return segments
    cuts = sorted({c for start, end, _ in ranges for c in (start, end)})
    total = sum(seg.cell_length for seg in segments)
    pieces = list(Segment.divide(segments, [c for c in cuts if c < total] + [total]))
    result: list[Segment] = []
    x = 0
    for piece in pieces:
        width = sum(seg.cell_length for seg in piece)
        extra = None
        for start, end, style in ranges:
            if start <= x < end:
                extra = style if extra is None else extra + style
        for seg in piece:
            if extra is not None:
                seg = Segment(seg.text, (seg.style or Style()) + extra, seg.control)
            result.append(seg)
        x += width
    return result


class MarkdownView(ScrollView, can_focus=True):
    BINDINGS = bindings("view")

    DEFAULT_CSS = """
    MarkdownView {
        scrollbar-gutter: stable;
    }
    """

    class Changed(Message):
        """Scroll position, search state or document changed."""

    class LinkActivated(Message):
        def __init__(self, href: str) -> None:
            super().__init__()
            self.href = href

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.parsed = ParsedDocument([], None)
        self.md_theme: MdTheme = THEMES["dark"]
        self.doc: RenderedDoc | None = None
        self.query_text = ""
        self.matches: list[Match] = []
        self.current_match: int | None = None
        self.selected_link: int | None = None
        self._pending_line: int | None = 0

    # ---- document management --------------------------------------------

    @property
    def top_line(self) -> int:
        return int(self.scroll_offset.y)

    @property
    def render_width(self) -> int:
        return self.scrollable_content_region.width - MARGIN * 2

    def set_document(self, parsed: ParsedDocument, line: int | None = 0) -> None:
        """Show new content. line=None keeps the current top line."""
        self.parsed = parsed
        self._rerender(self.top_line if line is None else line)

    def set_theme(self, theme: MdTheme) -> None:
        self.md_theme = theme
        if self.doc is not None:
            self._rerender(self.top_line)

    def _rerender(self, line: int) -> None:
        width = self.render_width
        if width <= 0:
            self._pending_line = line
            return
        self._pending_line = None
        self.doc = render(self.parsed.tokens, width, self.md_theme, self.parsed.front_matter)
        self.selected_link = None
        self.virtual_size = Size(self.doc.width + MARGIN * 2, len(self.doc.lines))
        self._recompute_matches()
        self.scroll_to_line(line)
        self.refresh()
        self.post_message(self.Changed())

    def on_resize(self, event: events.Resize) -> None:
        if self.render_width <= 0:
            return
        if self.doc is not None and self.doc.width == max(MIN_WIDTH, self.render_width):
            return
        if self._pending_line is not None:
            line, self._pending_line = self._pending_line, None
            self._rerender(line)
            return
        # Keep the same source position when the width changes.
        position = self.doc.source_position(self.top_line) if self.doc else (0, 0)
        self._rerender(0)
        if self.doc is not None:
            self.scroll_to_line(self.doc.line_for(*position))

    def scroll_to_line(self, line: int) -> None:
        total = len(self.doc.lines) if self.doc else 0
        line = max(0, min(line, total))
        self.scroll_to(y=line, animate=False, immediate=True)

    def ensure_visible(self, line: int) -> None:
        height = self.scrollable_content_region.height
        top = self.top_line
        if line < top or line >= top + height:
            self.scroll_to_line(max(0, line - height // 3))

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self.post_message(self.Changed())

    # ---- drawing ---------------------------------------------------------

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        index = scroll_y + y
        width = self.scrollable_content_region.width
        base = self.rich_style
        if self.doc is None or index >= len(self.doc.lines):
            return Strip.blank(width, base)
        segments = list(self.doc.lines[index])
        ranges: list[tuple[int, int, Style]] = []
        for i, match in enumerate(self.matches):
            if match.line == index:
                style = self.md_theme.search_current if i == self.current_match else self.md_theme.search_match
                ranges.append((match.start, match.end, style))
        if self.selected_link is not None:
            for region in self.doc.regions_of(self.selected_link):
                if region.line == index:
                    ranges.append((region.start, region.end, self.md_theme.link_selected))
        segments = highlight(segments, ranges)
        strip = Strip([Segment(" " * MARGIN), *segments]).apply_style(base)
        return strip.crop_extend(scroll_x, scroll_x + width, base)

    # ---- search ------------------------------------------------------------

    def search(self, query: str) -> int:
        self.query_text = query
        self.current_match = None
        self._recompute_matches()
        if self.matches:
            self._goto_match(next_match(self.matches, None, self.top_line, True))
        self.refresh()
        self.post_message(self.Changed())
        return len(self.matches)

    def _recompute_matches(self) -> None:
        self.matches = find_all(self.doc.plain_lines, self.query_text) if self.doc else []
        if self.current_match is not None and self.current_match >= len(self.matches):
            self.current_match = None

    def _goto_match(self, index: int | None) -> None:
        self.current_match = index
        if index is not None:
            self.ensure_visible(self.matches[index].line)

    def action_next_match(self) -> None:
        self._step_match(True)

    def action_prev_match(self) -> None:
        self._step_match(False)

    def _step_match(self, forward: bool) -> None:
        if not self.matches:
            return
        self._goto_match(next_match(self.matches, self.current_match, self.top_line, forward))
        self.refresh()
        self.post_message(self.Changed())

    # ---- links -------------------------------------------------------------

    def action_next_link(self) -> None:
        self._step_link(True)

    def action_prev_link(self) -> None:
        self._step_link(False)

    def _step_link(self, forward: bool) -> None:
        if self.doc is None:
            return
        ids = self.doc.link_ids()
        if not ids:
            return
        if self.selected_link in ids:
            pos = ids.index(self.selected_link) + (1 if forward else -1)
            chosen = ids[pos % len(ids)]
        else:
            top = self.top_line
            bottom = top + self.scrollable_content_region.height
            first_line = {i: self.doc.regions_of(i)[0].line for i in ids}
            if forward:
                chosen = next((i for i in ids if first_line[i] >= top), ids[0])
            else:
                chosen = next((i for i in reversed(ids) if first_line[i] < bottom), ids[-1])
        self.selected_link = chosen
        self.ensure_visible(self.doc.regions_of(chosen)[0].line)
        self.refresh()

    def action_open_link(self) -> None:
        if self.doc is None or self.selected_link is None:
            return
        regions = self.doc.regions_of(self.selected_link)
        if regions:
            self.post_message(self.LinkActivated(regions[0].href))

    # ---- scrolling ---------------------------------------------------------

    def action_line_down(self) -> None:
        self.scroll_relative(y=1, animate=False)

    def action_line_up(self) -> None:
        self.scroll_relative(y=-1, animate=False)

    def action_page_down(self) -> None:
        self.scroll_relative(y=self.scrollable_content_region.height, animate=False)

    def action_page_up(self) -> None:
        self.scroll_relative(y=-self.scrollable_content_region.height, animate=False)

    def action_half_down(self) -> None:
        self.scroll_relative(y=max(1, self.scrollable_content_region.height // 2), animate=False)

    def action_half_up(self) -> None:
        self.scroll_relative(y=-max(1, self.scrollable_content_region.height // 2), animate=False)

    def action_top(self) -> None:
        self.scroll_home(animate=False)

    def action_bottom(self) -> None:
        self.scroll_end(animate=False)

    def position_label(self) -> str:
        if self.max_scroll_y <= 0:
            return "All"
        return f"{round(self.scroll_y / self.max_scroll_y * 100)}%"


# ---- mdview_tui/app.py ----

POLL_SECONDS = 0.5


def _display_name(path: Path) -> str:
    try:
        return os.path.relpath(path)
    except ValueError:  # different drive on Windows
        return str(path)


class MdviewApp(App):
    BINDINGS = bindings("app")

    CSS = """
    #main {
        height: 1fr;
    }
    TocPanel {
        width: 32;
        height: 1fr;
        display: none;
        border: none;
        border-right: solid $primary;
    }
    TocPanel.-visible {
        display: block;
    }
    MarkdownView {
        width: 1fr;
        height: 1fr;
    }
    SearchInput {
        height: 1;
        border: none;
        padding: 0 1;
        display: none;
    }
    SearchInput.-visible {
        display: block;
    }
    StatusBar {
        height: 1;
        background: $panel;
    }
    """

    def __init__(self, source: Source, theme: str = "dark", watch: bool = True) -> None:
        super().__init__()
        self.source = source
        self.md_theme = THEMES[theme]
        self.watch_enabled = watch
        self.history = History(Location(source, 0))
        self.watcher: FileWatcher | None = None
        self._deleted_notified = False

    # ---- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            yield TocPanel(id="toc")
            yield MarkdownView(id="view")
        yield SearchInput(placeholder="検索 (Enter で確定 / Esc で取消)", id="search")
        yield StatusBar(id="status")

    @property
    def view(self) -> MarkdownView:
        return self.query_one(MarkdownView)

    @property
    def status(self) -> StatusBar:
        return self.query_one(StatusBar)

    def on_mount(self) -> None:
        self.theme = self.md_theme.textual_theme
        self.view.md_theme = self.md_theme
        self.view.focus()
        self._show(self.source, 0)
        if self.watch_enabled:
            self.set_interval(POLL_SECONDS, self._poll_file)

    # ---- document handling ---------------------------------------------------

    def _show(self, source: Source, line: int | None) -> None:
        self.source = source
        self.history.current.source = source
        self.view.set_document(parse_document(source.text), line)
        if source.path is not None and self.watch_enabled:
            if self.watcher is None or self.watcher.path != source.path:
                self.watcher = FileWatcher(source.path)
                self._deleted_notified = False
        else:
            self.watcher = None
        self._update_status()

    def message(self, text: str) -> None:
        self.status.flash(text)

    def _update_status(self) -> None:
        view = self.view
        left = ("◀ " if self.history.can_back() else "") + self.source.display_name
        parts = []
        if view.query_text:
            if view.matches:
                current = (view.current_match or 0) + 1 if view.current_match is not None else 0
                parts.append(f"[{current}/{len(view.matches)}]")
            else:
                parts.append("[0/0]")
        parts.append(view.position_label())
        self.status.set_info(left, " ".join(parts))

    def on_markdown_view_changed(self, _: MarkdownView.Changed) -> None:
        self._update_status()

    def _reload(self, quiet: bool = False) -> bool:
        if self.source.path is None:
            self.message("標準入力は再読込できません")
            return False
        try:
            source = load_file(self.source.path, self.source.display_name)
        except MdviewError as exc:
            self.message(exc.message)
            return False
        self._show(source, None)
        if not quiet:
            self.message("再読込しました")
        return True

    def _poll_file(self) -> None:
        if self.watcher is None:
            return
        state = self.watcher.check()
        if state == "modified":
            self._deleted_notified = False
            self._reload(quiet=True)
            self.message("ファイルが更新されたため再読込しました")
        elif state == "deleted" and not self._deleted_notified:
            self._deleted_notified = True
            self.message("ファイルが削除されました")

    # ---- links and history ---------------------------------------------------

    def on_markdown_view_link_activated(self, event: MarkdownView.LinkActivated) -> None:
        self.open_href(event.href)

    def open_href(self, href: str) -> None:
        target = resolve(href, self.source.path)
        if target.kind == "anchor":
            self._jump_anchor(target.anchor or "", push=True)
        elif target.kind == "file" and target.path is not None:
            try:
                source = load_file(target.path, _display_name(target.path))
            except MdviewError as exc:
                self.message(exc.message)
                return
            self.history.update_current(self.view.top_line)
            self.history.push(Location(source, 0))
            self._show(source, 0)
            if target.anchor:
                self._jump_anchor(target.anchor, push=False)
        elif target.kind == "external" and target.url:
            if not webbrowser.open(target.url):
                self.message("ブラウザを開けませんでした")
        else:
            self.message(f"サポートしていないリンク: {display_href(href)}")

    def _jump_anchor(self, anchor: str, push: bool) -> None:
        doc = self.view.doc
        heading = doc.heading_by_anchor(anchor) if doc else None
        if heading is None:
            self.message(f"見出しが見つかりません: #{anchor}")
            return
        if push:
            self.history.update_current(self.view.top_line)
            self.history.push(Location(self.source, heading.line))
        self.view.scroll_to_line(heading.line)
        self.history.update_current(heading.line)
        self._update_status()

    def _restore(self, loc: Location) -> None:
        source = loc.source
        if source.path is not None:
            try:
                source = load_file(source.path, source.display_name)
            except MdviewError as exc:
                self.message(exc.message)
        self._show(source, loc.scroll_y)

    def action_back(self) -> None:
        self.history.update_current(self.view.top_line)
        loc = self.history.back()
        if loc is None:
            self.message("これ以上戻れません")
            return
        self._restore(loc)

    def action_forward(self) -> None:
        self.history.update_current(self.view.top_line)
        loc = self.history.forward()
        if loc is None:
            self.message("これ以上進めません")
            return
        self._restore(loc)

    # ---- search --------------------------------------------------------------

    def action_search(self) -> None:
        search = self.query_one(SearchInput)
        search.value = ""
        search.add_class("-visible")
        search.focus()

    def _close_search(self) -> None:
        search = self.query_one(SearchInput)
        search.remove_class("-visible")
        self.view.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not isinstance(event.input, SearchInput):
            return
        self._close_search()
        query = event.value.strip()
        count = self.view.search(query)
        if query and count == 0:
            self.message(f"見つかりません: {query}")
        self._update_status()

    def on_search_input_cancelled(self, _: SearchInput.Cancelled) -> None:
        self._close_search()

    # ---- table of contents ---------------------------------------------------

    def action_toggle_toc(self) -> None:
        toc = self.query_one(TocPanel)
        if toc.has_class("-visible"):
            self._close_toc()
            return
        doc = self.view.doc
        if doc is None or not doc.headings:
            self.message("見出しがありません")
            return
        toc.set_headings(doc.headings, self.view.top_line)
        toc.add_class("-visible")
        toc.focus()

    def _close_toc(self) -> None:
        self.query_one(TocPanel).remove_class("-visible")
        self.view.focus()

    def on_toc_panel_closed(self, _: TocPanel.Closed) -> None:
        self._close_toc()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        toc = self.query_one(TocPanel)
        index = event.option_index
        doc = self.view.doc
        if doc is not None and 0 <= index < len(toc.headings):
            # The view may have been re-rendered (narrower) since the panel opened.
            heading = doc.heading_by_anchor(toc.headings[index].anchor)
            line = heading.line if heading else toc.headings[index].line
            self.history.update_current(self.view.top_line)
            self.history.push(Location(self.source, line))
            self.view.scroll_to_line(line)
        self._close_toc()

    # ---- other actions -------------------------------------------------------

    def action_reload(self) -> None:
        self._reload()

    def action_toggle_theme(self) -> None:
        self.md_theme = THEMES[toggle(self.md_theme.name)]
        self.theme = self.md_theme.textual_theme
        self.view.set_theme(self.md_theme)
        self.message(f"テーマ: {self.md_theme.name}")

    def action_help(self) -> None:
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen())

    def action_edit(self) -> None:
        if self.source.path is None:
            self.message("標準入力の表示中はエディタを起動できません")
            return
        cmd = editor_command(self.source.path)
        try:
            with self.suspend():
                subprocess.run(cmd, check=False)
        except SuspendNotSupported:
            self.message("この環境ではエディタを起動できません")
            return
        except OSError:
            self.message(f"エディタが見つかりません: {cmd[0]}")
            return
        self._reload(quiet=True)


# ---- mdview_tui/cli.py ----

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
        error = dependency_error()
        if error is not None:
            raise MdviewError(error)
        if args.file == "-" or (args.file is None and not _stdin_is_tty()):
            source = load_stdin()
            reattach_tty()
        elif args.file is None:
            parser.print_usage(sys.stderr)
            print(f"mdview-tui: error: {NO_INPUT}", file=sys.stderr)
            return 2
        else:
            source = load_file(Path(args.file), args.file)


        MdviewApp(source, theme=args.theme, watch=not args.no_watch).run()
        return 0
    except MdviewError as exc:
        print(f"mdview-tui: {exc.message}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
