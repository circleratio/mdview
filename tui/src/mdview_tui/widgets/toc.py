"""Table of contents panel."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from mdview_tui.document import Heading


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
