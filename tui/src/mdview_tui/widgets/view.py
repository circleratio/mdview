"""MarkdownView: a ScrollView rendering a RenderedDoc via the Line API."""

from __future__ import annotations

from markdown_it.token import Token
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from mdview_tui.document import RenderedDoc
from mdview_tui.keys import bindings
from mdview_tui.render import MIN_WIDTH, render
from mdview_tui.search import Match, find_all, next_match
from mdview_tui.themes import THEMES, MdTheme

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
        self.tokens: list[Token] = []
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

    def set_tokens(self, tokens: list[Token], line: int | None = 0) -> None:
        """Show new content. line=None keeps the current top line."""
        self.tokens = tokens
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
        self.doc = render(self.tokens, width, self.md_theme)
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
