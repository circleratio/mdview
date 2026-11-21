"""Search input line."""

from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


class SearchInput(Input):
    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    class Cancelled(Message):
        pass

    def action_cancel(self) -> None:
        self.post_message(self.Cancelled())
