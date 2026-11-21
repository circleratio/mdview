"""GitHub-compatible heading anchors."""

from __future__ import annotations

import re

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
