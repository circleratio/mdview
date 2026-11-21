# mdview-tui 設計

`doc/requirement.md` の要求仕様を実装するための設計を定める。

## 1. 全体方針

- Markdown の解析は **markdown-it-py**（`gfm-like` 相当の設定）で行い、トークン列から **独自レンダラ** で Rich の描画行（`Strip` のリスト）を生成する。
- 表示は Textual の **Line API**（`ScrollView` を継承し `render_line()` を実装）で行う。
  - Textual 標準の `Markdown` / `MarkdownViewer` ウィジェットは使わない。ブロック単位のウィジェット構成のため、行単位の検索ハイライト、Tab によるリンク選択、行番号ベースのスクロール位置の維持を実現しにくいため。
- レンダリング結果は「描画行 + メタデータ（見出し位置・リンク位置・行ごとのプレーンテキスト）」をまとめた `RenderedDoc` として扱う。検索・目次・リンク選択はすべて `RenderedDoc` 上で行い、UI から切り離して単体テストできるようにする。
- 端末幅の変更・テーマ切替・ファイル再読込のたびに `RenderedDoc` を作り直す（Markdown の解析結果 `tokens` はファイル内容が変わらない限り再利用する）。

```
 FILE / stdin ──► source.load() ──► Source(text, path)
                                        │
                         parser.parse() ▼
                                    tokens
                                        │  render(tokens, width, theme)
                                        ▼
                                  RenderedDoc ──► MarkdownView (render_line)
                                   │   │   │
                         headings ─┘   │   └─ links ──► links.resolve() ──► History
                                 plain_lines ──► search.find()
```

## 2. ディレクトリ構成

リポジトリ `mdview` の `tui/` ディレクトリに置く。GUI 版（`gui/` ディレクトリ）とは独立しており、互いに依存しない。

```
mdview/                  # repository root
├── gui/                 # GUI version (Tauri), not covered here
└── tui/
    ├── .gitignore
    ├── pyproject.toml
    ├── README.md
    ├── doc/
    │   ├── requirement.md
    │   ├── spec.md
    │   └── plan.md
    ├── src/mdview_tui/
    │   ├── __init__.py      # __version__
    │   ├── __main__.py      # python -m mdview_tui
    │   ├── cli.py           # argument parsing, entry point, exit codes
    │   ├── errors.py        # MdviewError
    │   ├── source.py        # loading file / stdin, re-attaching TTY
    │   ├── parser.py        # markdown-it-py setup
    │   ├── document.py      # RenderedDoc, Heading, LinkRegion data classes
    │   ├── render.py        # tokens -> RenderedDoc
    │   ├── slug.py          # GitHub-style heading anchors
    │   ├── search.py        # text search over plain lines
    │   ├── links.py         # link target resolution
    │   ├── history.py       # back / forward history
    │   ├── watcher.py       # file change detection (polling)
    │   ├── editor.py        # external editor command resolution
    │   ├── themes.py        # dark / light style definitions
    │   ├── keys.py          # key binding definitions (BINDINGS and help)
    │   ├── app.py           # Textual App (MdviewApp)
    │   └── widgets/
    │       ├── __init__.py
    │       ├── view.py      # MarkdownView (ScrollView + Line API)
    │       ├── toc.py       # TocPanel
    │       ├── search_bar.py# SearchInput
    │       ├── status.py    # StatusBar
    │       └── help.py      # HelpScreen (key binding list)
    └── tests/
        ├── fixtures/        # sample Markdown files
        ├── helpers.py
        ├── test_cli.py
        ├── test_source.py
        ├── test_render.py
        ├── test_slug.py
        ├── test_search.py
        ├── test_links.py
        ├── test_history.py
        ├── test_watcher.py
        ├── test_editor.py
        └── test_app.py      # Textual Pilot based
```

## 3. モジュールごとの責務と主要シグネチャ

### 3.1 `errors.py`

```python
class MdviewError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None: ...
    message: str
    exit_code: int
```

起動前（TUI 起動前）の致命的エラーはすべて `MdviewError` に変換し、`cli.main()` だけが標準エラー出力への表示と終了コードを扱う。

### 3.2 `source.py`

```python
@dataclass(frozen=True)
class Source:
    text: str
    path: Path | None        # None when read from stdin
    display_name: str        # file name as given, or "<stdin>"

def load_file(path: Path, display_name: str | None = None) -> Source: ...
def load_stdin() -> Source: ...
def reattach_tty() -> None: ...
```

- 読み込みはバイト列で行い `utf-8-sig` でデコードする（BOM を除去）。改行は `\r\n` / `\r` を `\n` に正規化する。
- `load_file` の例外変換:

| 元の例外 | メッセージ |
|---|---|
| `FileNotFoundError` | `<name>: No such file or directory` |
| `IsADirectoryError` | `<name>: Is a directory` |
| `PermissionError` | `<name>: Permission denied` |
| `UnicodeDecodeError` | `<name>: not valid UTF-8` |
| その他 `OSError` | `<name>: <strerror>` |

  いずれも `MdviewError(..., exit_code=1)`。起動後の再読込・リンク遷移でも同じ関数を使い、アプリ側で `MdviewError` を捕捉してステータスバー通知に変換する。
- `reattach_tty()`: 標準入力から読み終えた後、Textual がキー入力を受け取れるよう fd 0 を端末に付け替える。
  1. POSIX: `os.open("/dev/tty", os.O_RDONLY)` → `os.dup2(fd, 0)`、`sys.stdin` を再生成
  2. Windows: `CONIN$` を開いて同様に付け替え
  3. いずれも失敗した場合は `MdviewError("cannot open terminal for input", 1)`

### 3.3 `parser.py`

```python
def create_parser() -> MarkdownIt: ...
def parse(text: str) -> list[Token]: ...
```

- `MarkdownIt("commonmark", {"linkify": True, "html": True})` に `table` / `strikethrough` / `linkify` を有効化する（`linkify` は linkify-it-py を使用）。
- HTML は「描画しないがテキストとして表示」するため、`html_block` / `html_inline` トークンとして受け取り、レンダラで生テキストとして出力する。
- タスクリストは追加プラグインを使わず、レンダラ側で `list_item` 内の先頭 inline テキストが `[ ] ` / `[x] ` / `[X] ` で始まるものを検出して処理する（依存を増やさないため）。

### 3.4 `document.py`

```python
@dataclass(frozen=True)
class Heading:
    level: int        # 1-6
    text: str         # plain text
    anchor: str       # slug (see slug.py)
    line: int         # rendered line index

@dataclass(frozen=True)
class LinkRegion:
    link_id: int      # sequential, document order
    href: str
    line: int
    start: int        # cell offset (inclusive)
    end: int          # cell offset (exclusive)

@dataclass
class RenderedDoc:
    lines: list[Strip]
    plain_lines: list[str]
    headings: list[Heading]
    links: list[LinkRegion]       # one link may span multiple regions (wrapped)
    width: int
    anchors: list[tuple[int, int]]  # (rendered line, source line) of each block start

    def heading_by_anchor(self, anchor: str) -> Heading | None: ...
    def link_ids(self) -> list[int]: ...          # unique, document order
    def regions_of(self, link_id: int) -> list[LinkRegion]: ...
    def source_position(self, line: int) -> tuple[int, int]: ...   # rendered line -> (source line, offset)
    def line_for(self, source_line: int, offset: int = 0) -> int: ...  # inverse
```

- `heading_by_anchor` は「そのまま → 小文字化 → `slugify`」の順で照合する（`#Intro` のような表記ゆれも許容する）。
- `anchors` は markdown-it のトークンが持つソース行情報（`map`）から作る。端末幅が変わって描画行がずれても、同じソース位置を表示し続けるために使う。

### 3.5 `render.py`

```python
def render(tokens: list[Token], width: int, theme: MdTheme) -> RenderedDoc: ...
```

- トークン列を走査してブロックごとに Rich の renderable（`Text` / `Table` / `Syntax` / `Padding` など）を組み立て、`Console.render_lines(renderable, options.update(width=width))` で行に展開し、`Strip` に変換して連結する。
- ブロックごとの表示:

| 要素 | 表示 |
|---|---|
| 見出し H1/H2 | 太字・テーマ色、下に罫線（H1 は `═`、H2 は `─`） |
| 見出し H3〜H6 | 太字・テーマ色、先頭に `#` を level 個 |
| 段落 | 端末幅で折り返し（`Text.wrap`、全角文字幅を考慮） |
| 強調・太字・取り消し線・インラインコード | Rich の style（italic / bold / strike / 背景色） |
| リンク | 下線 + テーマ色。外部リンクは本文のみ表示（URL は付記しない） |
| 画像 | `[image: <alt>](<src>)` という文字列全体をリンク（リンク先は `src`）として表示 |
| 箇条書き | `•` / `◦` / `▪`（ネスト階層で切替）、番号付きは `1.` 形式、2文字ずつインデント |
| タスクリスト | `☐` / `☑` |
| 引用 | 左に `▌` を付け、ネスト分だけ重ねる |
| コードブロック | `rich.syntax.Syntax`（Pygments、言語不明時はハイライトなし）、背景付きパネル、折り返しなし（幅超過分は切り詰め） |
| 表 | `rich.table.Table`（ヘッダ太字、列の揃えは GFM の `:---:` に従う） |
| 水平線 | 幅いっぱいの `─` |
| 生 HTML | 薄い色の生テキスト |

- ブロック間には空行を1行入れる。
- **リンク位置の抽出**: リンク文字列に `Style(meta={"link_id": n})` を付けて描画し、描画後の各行の Segment を走査して meta を持つ範囲を `LinkRegion` として記録する。折り返しや表のセル内でも正しい位置が得られる。
- **見出し位置**: 見出しブロックを描画する直前の行数を `Heading.line` とする。
- **ソース位置**: 各ブロックの先頭描画行と、そのブロックのソース行（`token.map[0]`）の組を `anchors` に記録する（ネストしたブロックも含む）。
- **プレーンテキスト**: 各行の Segment のテキストを連結したものを `plain_lines` とする（検索用）。

### 3.6 `slug.py`

```python
def slugify(text: str) -> str: ...
class SlugRegistry:
    def make(self, text: str) -> str: ...   # handles duplicates: foo, foo-1, foo-2
```

GitHub 互換: 小文字化 → 英数字・Unicode の文字（日本語含む）・`-`・`_`・空白以外を除去 → 空白を `-` に置換。重複時は `-1`, `-2` … を付与する。

### 3.7 `search.py`

```python
@dataclass(frozen=True)
class Match:
    line: int
    start: int   # cell offset
    end: int     # cell offset

def find_all(plain_lines: list[str], query: str) -> list[Match]: ...
def next_match(matches: list[Match], current: int | None, top_line: int, forward: bool) -> int | None: ...
```

- 大文字小文字を区別しない（`str.casefold()` で比較）。正規表現は扱わない。
- 位置は文字インデックスではなく **セル幅**（`rich.cells.cell_len`）で返す（全角文字に対応）。
- 一致は行単位で、折り返しをまたぐ一致は検出しない（仕様上の制限として README に記載する）。
- `next_match` は現在の一致 `current` があればその次（`forward=False` なら前）のインデックスを返す。`current` が無ければ表示先頭行 `top_line` 以降（前方向なら `top_line` より前）の最初の一致を返す。端に達したら反対側に戻る（wrap around）。

### 3.8 `links.py`

```python
@dataclass(frozen=True)
class Target:
    kind: Literal["anchor", "file", "external", "unsupported"]
    path: Path | None = None
    anchor: str | None = None
    url: str | None = None

def resolve(href: str, base: Path | None) -> Target: ...
```

| href | 判定 |
|---|---|
| `#xxx` | `anchor`（同一ファイル内） |
| スキームあり（`http:`, `https:`, `mailto:` など） | `external` |
| `*.md` / `*.markdown`（`#xxx` 付き可、URL エンコードを復号） | `file`（`base` のディレクトリからの相対パス、絶対パスはそのまま） |
| 上記以外のローカルパス | `unsupported`（「サポートしていないリンク」と通知） |
| 標準入力表示中（`base is None`）の相対ファイルリンク | カレントディレクトリ基準で解決する |

### 3.9 `history.py`

```python
@dataclass
class Location:
    source: Source
    scroll_y: int

class History:
    def __init__(self, initial: Location) -> None: ...
    @property
    def current(self) -> Location: ...
    def push(self, loc: Location) -> None: ...      # clears forward stack
    def update_current(self, scroll_y: int) -> None: ...
    def back(self) -> Location | None: ...
    def forward(self) -> Location | None: ...
    def can_back(self) -> bool: ...
    def can_forward(self) -> bool: ...
```

同一ファイル内のアンカージャンプも履歴に積む（戻るで元の位置に戻れるようにする）。戻る／進む時はファイルを読み直す（`Location.source` は再読込で置き換える）。

### 3.10 `watcher.py`

```python
class FileWatcher:
    def __init__(self, path: Path) -> None: ...
    def check(self) -> Literal["unchanged", "modified", "deleted"]: ...
```

- 追加依存（watchdog 等）を避け、**ポーリング** で実装する。`os.stat` の `(st_mtime_ns, st_size)` を前回値と比較する。
- アプリ側で `set_interval(0.5, ...)` により呼び出す。`--no-watch` 指定時、または標準入力表示時はタイマーを作らない。
- 削除から再作成された場合（エディタの保存方式による）も `modified` として扱う。

### 3.11 `editor.py`

```python
def editor_command(path: Path, env: Mapping[str, str] | None = None,
                   platform: str | None = None) -> list[str]: ...
```

- `$VISUAL` → `$EDITOR` → 既定（POSIX: `vi`、Windows: `notepad`）の順。値は `shlex.split`（Windows では `posix=False`）で分割し、末尾にファイルパスを付ける。
- 起動はアプリ側で `with self.suspend(): subprocess.run(cmd)` とする。`SuspendNotSupported` や `FileNotFoundError` はステータスバー通知に変換する。

### 3.12 `themes.py`

```python
@dataclass(frozen=True)
class MdTheme:
    name: Literal["dark", "light"]
    textual_theme: str           # "textual-dark" / "textual-light"
    pygments_style: str          # "monokai" / "default"
    heading: tuple[Style, ...]   # H1..H6
    link: Style
    link_selected: Style
    code_inline: Style
    code_block_bg: str
    quote: Style
    html: Style
    search_match: Style
    search_current: Style

THEMES: dict[str, MdTheme]
def toggle(name: str) -> str: ...
```

### 3.13 `widgets/view.py` — `MarkdownView(ScrollView)`

- 保持状態: `doc: RenderedDoc`、`matches: list[Match]`、`current_match: int | None`、`selected_link: int | None`。
- `virtual_size = Size(width, len(doc.lines))`。
- `render_line(y)`: `doc.lines[scroll_y + y]` を取り出し、該当行の検索一致・選択中リンクの範囲に `Strip.divide` / スタイル重ね合わせでハイライトを適用して返す。
- `on_resize`: 幅が変わったら再レンダリング。スクロール位置は **再描画前の先頭行に対応するソース位置**（`source_position` → `line_for`）を維持する。目次パネルの開閉でも表示幅が変わるため、割合ではなくソース位置で合わせる。
- 公開メソッド: `set_document(doc, keep_line: int | None)`、`scroll_to_line(line)`、`select_next_link(forward)`、`set_matches(matches)`。
- 選択中のリンクが画面外なら、その位置までスクロールする。Tab 選択の起点は「表示範囲内の最初のリンク」とする。
- `Enter` の処理はアプリに `LinkActivated(href)` メッセージとして通知する。

### 3.14 `widgets/toc.py` — `TocPanel`

- 左側のドック表示パネル（幅 30 セル程度）。`OptionList` で見出しをインデント付きで表示する。
- `t` で表示切替。表示時はフォーカスをパネルに移し、`Enter` で選択した見出しの行へジャンプしてパネルを閉じ、`Esc` でジャンプせずに閉じる。`j` / `k` でも選択を移動できる。
- パネル表示で本文の幅が変わり再描画されるため、ジャンプ先の行は選択時点の `RenderedDoc` から見出しのアンカーで引き直す。

### 3.15 `widgets/search_bar.py` / `status.py` / `help.py`

- `SearchInput`: 画面下部に `/` 入力欄を出す。`Enter` で確定して検索、`Esc` で取消。
- `StatusBar`: 左に表示名（履歴で戻れる場合は `◀` を付ける）、中央に通知メッセージ（3 秒で消える）、右に検索状態 `[2/15]` と位置 `42%`（全体が画面に収まる場合は `All`）。
- `HelpScreen`: `ModalScreen` でキーバインド一覧を表示。`?` / `Esc` / `q` で閉じる。

### 3.16 `app.py` — `MdviewApp(App)`

```python
class MdviewApp(App):
    def __init__(self, source: Source, theme: str = "dark", watch: bool = True) -> None: ...
```

- 構成: `TocPanel`（非表示）| `MarkdownView` / `SearchInput`（非表示）/ `StatusBar`。
- キーバインドは `keys.py` の `KEYSPECS`（キー・表示ラベル・アクション・説明・対象 `view`/`app`）に一元定義し、`MdviewApp.BINDINGS` / `MarkdownView.BINDINGS` と `?` のヘルプ画面の両方をここから生成する（二重管理しない）。スクロール・検索移動・リンク選択は `MarkdownView` 側、それ以外はアプリ側に置く（目次パネルや検索欄にフォーカスがあるときに本文がスクロールしないようにするため）。
- 文書を開く処理は `open_source(source, anchor=None, push=True)` に集約する（初回表示・リンク遷移・履歴移動・再読込で共通）。
- 再読込（自動／`r`／エディタ復帰後）: ファイルを読み直し、`tokens` を作り直して `RenderedDoc` を再生成し、**同じ先頭行番号**（文書が短くなった場合は末尾に丸める）を維持する。検索中なら一致を再計算する。
- 起動後のエラー（再読込失敗・リンク先なし・エディタ起動失敗など）は終了せずステータスバーに通知する。

### 3.17 `cli.py`

```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> int: ...
```

処理の流れ:

1. 引数を解析（誤りは argparse により終了コード 2）
2. 入力元の決定: `FILE` が `-` または「`FILE` なし かつ stdin が TTY でない」→ `load_stdin()` + `reattach_tty()`。`FILE` なし かつ stdin が TTY → usage と `mdview-tui: error: no input (specify FILE or pipe to stdin)` を出して 2。それ以外は `load_file()`
3. `MdviewApp(...).run()` を実行し 0 を返す
4. `MdviewError` を捕捉したら `mdview-tui: <message>` を stderr に出して `exit_code` を返す。`KeyboardInterrupt` は 130

## 4. CLI 仕様

| 引数・オプション | 説明 | 既定 |
|---|---|---|
| `FILE` | 表示する Markdown ファイル。`-` で標準入力 | 省略時は標準入力（パイプ時のみ） |
| `--theme {dark,light}` | 起動時のテーマ | `dark` |
| `--no-watch` | 自動再読込を無効化 | 無効化しない |
| `-h`, `--help` | ヘルプを表示して終了 | |
| `-V`, `--version` | `mdview-tui <version>` を表示して終了 | |

| 終了コード | 条件 |
|---|---|
| 0 | 正常終了、`--help`、`--version` |
| 1 | ファイルの読み込み失敗（存在しない・ディレクトリ・権限・非 UTF-8）、端末を入力に使えない |
| 2 | 引数・オプションの誤り、入力なし |
| 130 | `KeyboardInterrupt`（TUI 外での中断） |

## 5. エラーハンドリング方針

| 発生箇所 | 扱い |
|---|---|
| 起動前（引数・初回読み込み・TTY 付け替え） | `MdviewError` → `cli.main()` が `mdview-tui: <理由>` を stderr に出し、終了コードを返す。TUI は起動しない |
| 起動後の読み込み失敗（再読込・リンク遷移・履歴移動） | `MdviewError` を捕捉 → ステータスバー通知。現在の表示は維持する |
| 表示中ファイルの削除 | 「file deleted」と通知し、最後の内容を表示し続ける。ポーリングは継続し、再作成されたら再読込する |
| 外部リンクを開けない（`webbrowser.open` が False） | 「cannot open browser」と通知 |
| アンカー先の見出しなし | 「anchor not found: #xxx」と通知（ファイル遷移自体は行う） |
| エディタ起動失敗 | 「editor not found: <cmd>」などを通知 |
| 想定外の例外 | 捕捉せず Textual の標準処理に任せる（トレースバックを表示して終了） |

## 6. パッケージング方針

- `pyproject.toml`（ビルドバックエンドは `hatchling`、src レイアウト）
- 依存: `textual>=2.0`、`markdown-it-py[linkify]>=3.0`（`rich` と `pygments` は textual 経由で入る）
- バージョンは `src/mdview_tui/__init__.py` の `__version__` を唯一の定義とし、`[tool.hatch.version] path = "src/mdview_tui/__init__.py"` で参照する
- エントリポイント: `[project.scripts] mdview-tui = "mdview_tui.cli:main"`。`python -m mdview_tui` でも起動できるようにする
- `requires-python = ">=3.10"`
- 開発環境では pip が無い場合があるため、`PYTHONPATH=src python3 -m mdview_tui` での実行も README に記載する

## 7. テスト方針

- テストは標準ライブラリの `unittest` で書く（pytest でもそのまま実行可能な形にする）。実行: `PYTHONPATH=src python3 -m unittest discover -s tests -t .`
- UI 以外のロジックは単体テストで網羅し、UI は Textual の `App.run_test()`（Pilot）で主要操作のみ確認する。

| 対象 | 確認内容 |
|---|---|
| `cli` | `--version` 出力と終了コード 0、未知オプションで 2、入力なし（TTY）で 2 とメッセージ、存在しないファイルで 1 とメッセージ |
| `source` | UTF-8 / BOM 付き / CRLF の読み込み、非 UTF-8・ディレクトリ・存在しないファイルのエラーメッセージ |
| `render` | 各要素（見出し・リスト・タスクリスト・引用・コード・表・水平線・HTML・画像）の出力文字列、幅による折り返し、全角文字を含む折り返し、見出し行番号、リンク位置（折り返し・表セル内を含む）、幅を変えてもソース位置で見出しが対応すること |
| `slug` | 英字・記号・日本語・重複見出し |
| `search` | 大文字小文字無視、全角文字のセル位置、0件、wrap around |
| `links` | アンカー・外部・相対 `.md`・`#` 付き・URL エンコード・非対応ファイル・stdin 時 |
| `history` | push で forward がクリアされる、back/forward の境界（空のとき None） |
| `watcher` | 変更なし・更新・削除・再作成（一時ディレクトリで検証） |
| `editor` | `VISUAL` 優先、`EDITOR`、未設定時の OS 別既定、引数付きコマンドの分割 |
| `app` | 起動して本文表示、各スクロールキー、`/` 検索で一致数表示と `n`/`N`、`t` から見出しジャンプ、Tab+Enter で相対リンク遷移と Backspace / `L` で戻る・進む、アンカー・存在しないリンク・非対応リンク・外部リンク、ファイル書き換えで自動再読込・削除通知、`r` 再読込で行維持、エディタ起動後の再読込、`T` でテーマ切替、`?` ヘルプ、リサイズで位置維持、標準入力時の制限 |
