"""markdown-it-py setup (CommonMark + GFM subset)."""

from __future__ import annotations

from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode

from mdview_tui.frontmatter import FrontMatter, split_front_matter


@dataclass(frozen=True)
class ParsedDocument:
    tokens: list[Token]
    front_matter: FrontMatter | None  # None when the text has no front matter


def create_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"linkify": True, "html": True})
    md.enable(["table", "strikethrough", "linkify"])
    return md


_PARSER = create_parser()


def parse(text: str) -> list[Token]:
    return _PARSER.parse(text)


def parse_document(text: str) -> ParsedDocument:
    """Split off the front matter, then parse the rest as Markdown."""
    front_matter, body = split_front_matter(text)
    return ParsedDocument(parse(body), front_matter)


def to_tree(tokens: list[Token]) -> SyntaxTreeNode:
    return SyntaxTreeNode(tokens)
