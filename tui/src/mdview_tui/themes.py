"""Dark / light style definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.style import Style


@dataclass(frozen=True)
class MdTheme:
    name: Literal["dark", "light"]
    textual_theme: str
    pygments_style: str
    heading: tuple[Style, ...]  # H1..H6
    link: Style
    link_selected: Style
    code_inline: Style
    code_block_bg: str
    quote: Style
    html: Style
    rule: Style
    meta: Style  # front matter byline and fields
    error: Style  # front matter error line
    search_match: Style
    search_current: Style


THEMES: dict[str, MdTheme] = {
    "dark": MdTheme(
        name="dark",
        textual_theme="textual-dark",
        pygments_style="monokai",
        heading=(
            Style.parse("bold #c678dd"),
            Style.parse("bold #61afef"),
            Style.parse("bold #98c379"),
            Style.parse("bold #e5c07b"),
            Style.parse("bold #e5c07b"),
            Style.parse("bold #e5c07b"),
        ),
        link=Style.parse("underline #56b6c2"),
        link_selected=Style.parse("reverse bold"),
        code_inline=Style.parse("#e06c75 on #2c313a"),
        code_block_bg="#1e2127",
        quote=Style.parse("italic #9da5b4"),
        html=Style.parse("#7f848e"),
        rule=Style.parse("#5c6370"),
        meta=Style.parse("#9da5b4"),
        error=Style.parse("bold #e06c75"),
        search_match=Style.parse("#000000 on #e5c07b"),
        search_current=Style.parse("bold #000000 on #ff8800"),
    ),
    "light": MdTheme(
        name="light",
        textual_theme="textual-light",
        pygments_style="default",
        heading=(
            Style.parse("bold #a626a4"),
            Style.parse("bold #4078f2"),
            Style.parse("bold #50a14f"),
            Style.parse("bold #c18401"),
            Style.parse("bold #c18401"),
            Style.parse("bold #c18401"),
        ),
        link=Style.parse("underline #0184bc"),
        link_selected=Style.parse("reverse bold"),
        code_inline=Style.parse("#e45649 on #eaeaeb"),
        code_block_bg="#f0f0f0",
        quote=Style.parse("italic #696c77"),
        html=Style.parse("#a0a1a7"),
        rule=Style.parse("#a0a1a7"),
        meta=Style.parse("#696c77"),
        error=Style.parse("bold #e45649"),
        search_match=Style.parse("#000000 on #ffe066"),
        search_current=Style.parse("bold #000000 on #ff9f43"),
    ),
}


def toggle(name: str) -> str:
    return "light" if name == "dark" else "dark"
