"""Status bar: name, transient message, search state and position."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.timer import Timer
from textual.widgets import Static

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
