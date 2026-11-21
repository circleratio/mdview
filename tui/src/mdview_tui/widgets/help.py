"""Key binding help screen."""

from __future__ import annotations

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from mdview_tui.keys import KEYSPECS


def help_table() -> Table:
    table = Table(title="キーバインド", show_header=True, header_style="bold", expand=False)
    table.add_column("キー", no_wrap=True)
    table.add_column("動作")
    for spec in KEYSPECS:
        table.add_row(spec.label, spec.description)
    return table


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,question_mark", "dismiss", "閉じる", show=False)]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > VerticalScroll {
        width: auto;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(help_table(), id="help-table")
