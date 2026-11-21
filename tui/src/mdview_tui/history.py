"""Back / forward navigation history."""

from __future__ import annotations

from dataclasses import dataclass

from mdview_tui.source import Source


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
