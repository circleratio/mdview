"""The Textual application."""

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.containers import Horizontal
from textual.widgets import Input, OptionList

from mdview_tui.editor import editor_command
from mdview_tui.errors import MdviewError
from mdview_tui.history import History, Location
from mdview_tui.keys import bindings
from mdview_tui.links import resolve
from mdview_tui.parser import parse
from mdview_tui.source import Source, load_file
from mdview_tui.themes import THEMES, toggle
from mdview_tui.watcher import FileWatcher
from mdview_tui.widgets import HelpScreen, MarkdownView, SearchInput, StatusBar, TocPanel

POLL_SECONDS = 0.5


def _display_name(path: Path) -> str:
    try:
        return os.path.relpath(path)
    except ValueError:  # different drive on Windows
        return str(path)


class MdviewApp(App):
    BINDINGS = bindings("app")

    CSS = """
    #main {
        height: 1fr;
    }
    TocPanel {
        width: 32;
        height: 1fr;
        display: none;
        border: none;
        border-right: solid $primary;
    }
    TocPanel.-visible {
        display: block;
    }
    MarkdownView {
        width: 1fr;
        height: 1fr;
    }
    SearchInput {
        height: 1;
        border: none;
        padding: 0 1;
        display: none;
    }
    SearchInput.-visible {
        display: block;
    }
    StatusBar {
        height: 1;
        background: $panel;
    }
    """

    def __init__(self, source: Source, theme: str = "dark", watch: bool = True) -> None:
        super().__init__()
        self.source = source
        self.md_theme = THEMES[theme]
        self.watch_enabled = watch
        self.history = History(Location(source, 0))
        self.watcher: FileWatcher | None = None
        self._deleted_notified = False

    # ---- layout --------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            yield TocPanel(id="toc")
            yield MarkdownView(id="view")
        yield SearchInput(placeholder="検索 (Enter で確定 / Esc で取消)", id="search")
        yield StatusBar(id="status")

    @property
    def view(self) -> MarkdownView:
        return self.query_one(MarkdownView)

    @property
    def status(self) -> StatusBar:
        return self.query_one(StatusBar)

    def on_mount(self) -> None:
        self.theme = self.md_theme.textual_theme
        self.view.md_theme = self.md_theme
        self.view.focus()
        self._show(self.source, 0)
        if self.watch_enabled:
            self.set_interval(POLL_SECONDS, self._poll_file)

    # ---- document handling ---------------------------------------------------

    def _show(self, source: Source, line: int | None) -> None:
        self.source = source
        self.history.current.source = source
        self.view.set_tokens(parse(source.text), line)
        if source.path is not None and self.watch_enabled:
            if self.watcher is None or self.watcher.path != source.path:
                self.watcher = FileWatcher(source.path)
                self._deleted_notified = False
        else:
            self.watcher = None
        self._update_status()

    def message(self, text: str) -> None:
        self.status.flash(text)

    def _update_status(self) -> None:
        view = self.view
        left = ("◀ " if self.history.can_back() else "") + self.source.display_name
        parts = []
        if view.query_text:
            if view.matches:
                current = (view.current_match or 0) + 1 if view.current_match is not None else 0
                parts.append(f"[{current}/{len(view.matches)}]")
            else:
                parts.append("[0/0]")
        parts.append(view.position_label())
        self.status.set_info(left, " ".join(parts))

    def on_markdown_view_changed(self, _: MarkdownView.Changed) -> None:
        self._update_status()

    def _reload(self, quiet: bool = False) -> bool:
        if self.source.path is None:
            self.message("標準入力は再読込できません")
            return False
        try:
            source = load_file(self.source.path, self.source.display_name)
        except MdviewError as exc:
            self.message(exc.message)
            return False
        self._show(source, None)
        if not quiet:
            self.message("再読込しました")
        return True

    def _poll_file(self) -> None:
        if self.watcher is None:
            return
        state = self.watcher.check()
        if state == "modified":
            self._deleted_notified = False
            self._reload(quiet=True)
            self.message("ファイルが更新されたため再読込しました")
        elif state == "deleted" and not self._deleted_notified:
            self._deleted_notified = True
            self.message("ファイルが削除されました")

    # ---- links and history ---------------------------------------------------

    def on_markdown_view_link_activated(self, event: MarkdownView.LinkActivated) -> None:
        self.open_href(event.href)

    def open_href(self, href: str) -> None:
        target = resolve(href, self.source.path)
        if target.kind == "anchor":
            self._jump_anchor(target.anchor or "", push=True)
        elif target.kind == "file" and target.path is not None:
            try:
                source = load_file(target.path, _display_name(target.path))
            except MdviewError as exc:
                self.message(exc.message)
                return
            self.history.update_current(self.view.top_line)
            self.history.push(Location(source, 0))
            self._show(source, 0)
            if target.anchor:
                self._jump_anchor(target.anchor, push=False)
        elif target.kind == "external" and target.url:
            if not webbrowser.open(target.url):
                self.message("ブラウザを開けませんでした")
        else:
            self.message(f"サポートしていないリンク: {href}")

    def _jump_anchor(self, anchor: str, push: bool) -> None:
        doc = self.view.doc
        heading = doc.heading_by_anchor(anchor) if doc else None
        if heading is None:
            self.message(f"見出しが見つかりません: #{anchor}")
            return
        if push:
            self.history.update_current(self.view.top_line)
            self.history.push(Location(self.source, heading.line))
        self.view.scroll_to_line(heading.line)
        self.history.update_current(heading.line)
        self._update_status()

    def _restore(self, loc: Location) -> None:
        source = loc.source
        if source.path is not None:
            try:
                source = load_file(source.path, source.display_name)
            except MdviewError as exc:
                self.message(exc.message)
        self._show(source, loc.scroll_y)

    def action_back(self) -> None:
        self.history.update_current(self.view.top_line)
        loc = self.history.back()
        if loc is None:
            self.message("これ以上戻れません")
            return
        self._restore(loc)

    def action_forward(self) -> None:
        self.history.update_current(self.view.top_line)
        loc = self.history.forward()
        if loc is None:
            self.message("これ以上進めません")
            return
        self._restore(loc)

    # ---- search --------------------------------------------------------------

    def action_search(self) -> None:
        search = self.query_one(SearchInput)
        search.value = ""
        search.add_class("-visible")
        search.focus()

    def _close_search(self) -> None:
        search = self.query_one(SearchInput)
        search.remove_class("-visible")
        self.view.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not isinstance(event.input, SearchInput):
            return
        self._close_search()
        query = event.value.strip()
        count = self.view.search(query)
        if query and count == 0:
            self.message(f"見つかりません: {query}")
        self._update_status()

    def on_search_input_cancelled(self, _: SearchInput.Cancelled) -> None:
        self._close_search()

    # ---- table of contents ---------------------------------------------------

    def action_toggle_toc(self) -> None:
        toc = self.query_one(TocPanel)
        if toc.has_class("-visible"):
            self._close_toc()
            return
        doc = self.view.doc
        if doc is None or not doc.headings:
            self.message("見出しがありません")
            return
        toc.set_headings(doc.headings, self.view.top_line)
        toc.add_class("-visible")
        toc.focus()

    def _close_toc(self) -> None:
        self.query_one(TocPanel).remove_class("-visible")
        self.view.focus()

    def on_toc_panel_closed(self, _: TocPanel.Closed) -> None:
        self._close_toc()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        toc = self.query_one(TocPanel)
        index = event.option_index
        doc = self.view.doc
        if doc is not None and 0 <= index < len(toc.headings):
            # The view may have been re-rendered (narrower) since the panel opened.
            heading = doc.heading_by_anchor(toc.headings[index].anchor)
            line = heading.line if heading else toc.headings[index].line
            self.history.update_current(self.view.top_line)
            self.history.push(Location(self.source, line))
            self.view.scroll_to_line(line)
        self._close_toc()

    # ---- other actions -------------------------------------------------------

    def action_reload(self) -> None:
        self._reload()

    def action_toggle_theme(self) -> None:
        self.md_theme = THEMES[toggle(self.md_theme.name)]
        self.theme = self.md_theme.textual_theme
        self.view.set_theme(self.md_theme)
        self.message(f"テーマ: {self.md_theme.name}")

    def action_help(self) -> None:
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen())

    def action_edit(self) -> None:
        if self.source.path is None:
            self.message("標準入力の表示中はエディタを起動できません")
            return
        cmd = editor_command(self.source.path)
        try:
            with self.suspend():
                subprocess.run(cmd, check=False)
        except SuspendNotSupported:
            self.message("この環境ではエディタを起動できません")
            return
        except OSError:
            self.message(f"エディタが見つかりません: {cmd[0]}")
            return
        self._reload(quiet=True)
