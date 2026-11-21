"""YAML front matter: splitting it off the Markdown text and building display values."""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

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
