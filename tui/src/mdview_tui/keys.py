"""Single source of truth for key bindings (used for BINDINGS and help)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from textual.binding import Binding


@dataclass(frozen=True)
class KeySpec:
    keys: tuple[str, ...]  # Textual key names
    label: str  # shown in the help screen
    action: str
    description: str
    scope: Literal["view", "app"]
    priority: bool = False


KEYSPECS: tuple[KeySpec, ...] = (
    KeySpec(("j", "down"), "j / ↓", "line_down", "1行下へ", "view"),
    KeySpec(("k", "up"), "k / ↑", "line_up", "1行上へ", "view"),
    KeySpec(("space", "f", "pagedown"), "Space / f / PgDn", "page_down", "1画面下へ", "view"),
    KeySpec(("b", "pageup"), "b / PgUp", "page_up", "1画面上へ", "view"),
    KeySpec(("d",), "d", "half_down", "半画面下へ", "view"),
    KeySpec(("u",), "u", "half_up", "半画面上へ", "view"),
    KeySpec(("g", "home"), "g / Home", "top", "先頭へ", "view"),
    KeySpec(("G", "end"), "G / End", "bottom", "末尾へ", "view"),
    KeySpec(("slash",), "/", "search", "検索", "app"),
    KeySpec(("n",), "n", "next_match", "次の一致へ", "view"),
    KeySpec(("N",), "N", "prev_match", "前の一致へ", "view"),
    KeySpec(("t",), "t", "toggle_toc", "目次パネルの表示切替", "app"),
    KeySpec(("tab",), "Tab", "next_link", "次のリンクを選択", "view"),
    KeySpec(("shift+tab",), "Shift+Tab", "prev_link", "前のリンクを選択", "view"),
    KeySpec(("enter",), "Enter", "open_link", "選択中のリンクを開く", "view"),
    KeySpec(("backspace", "H"), "Backspace / H", "back", "履歴を戻る", "app"),
    KeySpec(("L",), "L", "forward", "履歴を進む", "app"),
    KeySpec(("e",), "e", "edit", "外部エディタで開く", "app"),
    KeySpec(("r",), "r", "reload", "手動再読込", "app"),
    KeySpec(("T",), "T", "toggle_theme", "テーマ切替", "app"),
    KeySpec(("question_mark",), "?", "help", "ヘルプ表示", "app"),
    KeySpec(("q", "ctrl+c"), "q / Ctrl+C", "quit", "終了", "app", priority=True),
)


def bindings(scope: str) -> list[Binding]:
    return [
        Binding(",".join(spec.keys), spec.action, spec.description, show=False, priority=spec.priority)
        for spec in KEYSPECS
        if spec.scope == scope
    ]
