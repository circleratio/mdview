"""markdown-it-py setup (CommonMark + GFM subset)."""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode


def create_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"linkify": True, "html": True})
    md.enable(["table", "strikethrough", "linkify"])
    return md


_PARSER = create_parser()


def parse(text: str) -> list[Token]:
    return _PARSER.parse(text)


def to_tree(tokens: list[Token]) -> SyntaxTreeNode:
    return SyntaxTreeNode(tokens)
