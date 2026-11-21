"""Render markdown-it tokens into a RenderedDoc of Strips."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

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
from textual.strip import Strip

from mdview_tui.document import Heading, LinkRegion, RenderedDoc
from mdview_tui.frontmatter import ERROR_PREFIX, FrontMatter, to_view
from mdview_tui.slug import SlugRegistry
from mdview_tui.themes import MdTheme

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
                text.append(f"[image: {alt}]({src})", style + self.link_style(src))
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
