"""Case-insensitive text search over rendered plain lines."""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len


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
