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
                parser.parse_document() ▼   (frontmatter.split_front_matter() + parse())
                          ParsedDocument(tokens, front_matter)
                                        │  render(tokens, width, theme, front_matter)
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
    ├── portable/
    │   └── mdview-tui.py    # portable single-file version (generated, do not edit)
    ├── tools/
    │   └── bundle.py        # generates portable/mdview-tui.py from src/mdview_tui/
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
    │   ├── parser.py        # markdown-it-py setup, ParsedDocument
    │   ├── frontmatter.py   # YAML front matter splitting and display values
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
        ├── test_frontmatter.py
        ├── test_slug.py
        ├── test_search.py
        ├── test_links.py
        ├── test_history.py
        ├── test_watcher.py
        ├── test_editor.py
        ├── test_app.py      # Textual Pilot based
        └── test_portable.py # portable version: up to date, starts and runs
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
@dataclass(frozen=True)
class ParsedDocument:
    tokens: list[Token]
    front_matter: FrontMatter | None   # None when the text has no front matter

def create_parser() -> MarkdownIt: ...
def parse(text: str) -> list[Token]: ...
def parse_document(text: str) -> ParsedDocument: ...
```

- `parse_document` は `frontmatter.split_front_matter()` でフロントマターを切り出してから、残りの本文を `parse()` する。アプリが文書を表示するときは常にこちらを使う（3.18）。

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
def render(tokens: list[Token], width: int, theme: MdTheme,
           front_matter: FrontMatter | None = None) -> RenderedDoc: ...
```

- `front_matter` があれば、本文より前にフロントマターのブロック（3.18 の表示）を置く。このブロックは見出し（`headings`）・リンクを持たず、`plain_lines` には含める（検索の対象）。`anchors` にはソース行 0 として記録する。

- トークン列を走査してブロックごとに Rich の renderable（`Text` / `Table` / `Syntax` / `Padding` など）を組み立て、`Console.render_lines(renderable, options.update(width=width))` で行に展開し、`Strip` に変換して連結する。
- ブロックごとの表示:

| 要素 | 表示 |
|---|---|
| 見出し H1/H2 | 太字・テーマ色、下に罫線（H1 は `═`、H2 は `─`） |
| 見出し H3〜H6 | 太字・テーマ色、先頭に `#` を level 個 |
| 段落 | 端末幅で折り返し（`Text.wrap`、全角文字幅を考慮） |
| 強調・太字・取り消し線・インラインコード | Rich の style（italic / bold / strike / 背景色） |
| リンク | 下線 + テーマ色。外部リンクは本文のみ表示（URL は付記しない） |
| 画像 | `[image: <alt>](<src>)` という文字列全体をリンク（リンク先は `src`）として表示。表示する `src` は `links.display_href()` で戻した文字列 |
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
def display_href(href: str) -> str: ...
```

- markdown-it はすべてのリンクの `href` と画像の `src` を `normalizeLink` でパーセントエンコードする（`[x](図.png)` は `%E5%9B%B3.png`、`<my image.png>` は `my%20image.png` になる）。`resolve` はパスとアンカーを `unquote` してから扱う。画面に出す文字列（画像の表示、「サポートしていないリンク」の通知）は `display_href`（`unquote`。不正な並びはそのまま残る）で書かれた通りの文字に戻す。

| href | 判定 |
|---|---|
| `#xxx` | `anchor`（同一ファイル内） |
| スキームあり（`http:`, `https:`, `mailto:` など。`file:` を除く） | `external` |
| `file:` の URL（`file:///home/x.md#a`、`file://server/share/x.md`） | パス部分と `#` 以降を `unquote` し、ローカルの絶対パスとして下の行と同じ判定をする（`file`/`unsupported`）。ホストが `localhost` 以外なら `//host/...` の UNC パスにする。Windows では `/C:/...` の先頭の `/` を取り除く。OS には渡さない（GUI 版と同じ規則、`doc/common.md` 4章） |
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
    rule: Style
    meta: Style                  # front matter byline and fields
    error: Style                 # front matter error line
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
- 公開メソッド: `set_document(parsed: ParsedDocument, line: int | None)`（`line=None` で現在の先頭行を維持）、`scroll_to_line(line)`、`select_next_link(forward)`、`set_matches(matches)`。
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
- 文書を開く処理は `open_source(source, anchor=None, push=True)` に集約する（初回表示・リンク遷移・履歴移動・再読込で共通）。表示の直前に `parse_document(source.text)` で解析し、`MarkdownView.set_document()` に渡す。
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

### 3.18 `frontmatter.py`

```python
@dataclass(frozen=True)
class FrontMatter:
    raw: str                       # text between the fences
    data: dict[str, object] | None # parsed mapping, None on error
    error: str | None              # one-line reason when it could not be parsed

@dataclass(frozen=True)
class FrontMatterView:
    title: str | None
    byline: list[str]              # author, then date (only non-empty ones)
    others: list[tuple[str, str]]  # every other key, in the order written
    is_empty: bool                 # property: nothing to show

def split_front_matter(text: str) -> tuple[FrontMatter | None, str]: ...
def format_value(value: object) -> str: ...
def format_author(value: object) -> str: ...
def to_view(data: dict[str, object]) -> FrontMatterView: ...
```

- 判定と解釈の規則は GUI 版（`gui/src/lib/frontMatter.ts`）と同じにする。入力の `text` は `source.py` で BOM の除去と改行の LF への正規化が済んでいる。
  - 1行目が `^---[ \t]*$` に一致し、2行目以降に `^(---|\.\.\.)[ \t]*$` に一致する行がある場合だけフロントマターとする。
  - 戻り値の本文は、フロントマター部分（開きの行から閉じの行まで）を**同じ行数の空行に置き換えたもの**とする。markdown-it のトークンが持つ行番号（`map`）がファイルの行番号と一致したままになり、再読込でフロントマターの行数が変わっても `source_position` / `line_for` が正しい位置を指す。先頭の空行は Markdown の表示に影響しない。
- YAML は `yaml.load(raw, Loader=yaml.BaseLoader)` で解釈する。`BaseLoader` は値をすべて書かれた通りの文字列として返すため、`2026-10-08` が日付型に、`1.10` が `1.1` になることはない（GUI 版の failsafe スキーマと同じ結果）。値の無いキー（`key:`）は空文字列になる。
  - 空のフロントマター（`None` が返る、または空白だけ）は `data={}` とする。
  - `yaml.YAMLError` は `error` に変換する。理由は例外の `problem`（あれば `problem_mark` から `(line N, column M)` を付ける。行番号はフロントマターの中での位置）とし、`problem` が無い場合は例外メッセージの1行目を使う。最上位が辞書でない場合は `フロントマターがキーと値の形式ではありません` とする（GUI 版と同じ文言）。
- `format_value`: 文字列はそのまま、配列は要素を `, ` でつなぐ、辞書は `キー: 値` を `, ` でつなぐ（再帰的に適用）。
- `format_author`: 配列なら空でない要素を「、」でつなぎ、それ以外は `format_value` と同じ。
- `to_view`: `title`・`author`・`date` を取り出し、空文字列になったものは表示しない（`title` は `None`、`byline` からは除く）。それ以外のキーは書かれた順に `others` に入れる。

表示（`render.py` の `_front_matter()`）:

| 部分 | 表示 |
|---|---|
| `title` | `theme.heading[0]`（H1 と同じ色の太字）で折り返し表示。罫線は付けない |
| `byline` | `theme.meta` で ` ・ ` でつないで1行（幅を超えたら折り返し） |
| 点線の区切り | 題名または `byline` と、`others` の両方があるときだけ、幅いっぱいの `┄`（`theme.rule`） |
| `others` | キーと値の2列（`theme.meta`）。キーの列幅は最も長いキーに合わせ、値との間を2セル空ける。値は残りの幅で折り返し、2行目以降は値の列の位置から始める。値の列の幅が8セル未満、またはキーの列より狭くなる場合（目次パネルを開いた狭い端末など）は、キーの行の下に値を2セル字下げして表示する。`rich.table.Table.grid` は幅が足りないと値の列を潰して値が消えるため使わない |
| 末尾 | 幅いっぱいの `─`（`theme.rule`）。ブロック間の空行の規則により、本文との間に空行が1行入る |
| 解釈できない場合 | `フロントマターを解釈できませんでした: <error>`（`theme.error`、GUI 版と同じ文言）、続けて元の文字列（`theme.meta`）、末尾の `─` |

表示する項目が1つも無い場合（空のフロントマター、または `title`・`author`・`date` がどれも空でその他の項目も無い場合。`FrontMatterView.is_empty`）はブロック自体を出さない。値が空のその他の項目（`key:`）は、GUI 版と同じくキーだけを表示する。

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
- 依存: `textual>=2.0`、`markdown-it-py[linkify]>=3.0`、`PyYAML>=6.0`（`rich` と `pygments` は textual 経由で入る）
- バージョンは `src/mdview_tui/__init__.py` の `__version__` を唯一の定義とし、`[tool.hatch.version] path = "src/mdview_tui/__init__.py"` で参照する
- エントリポイント: `[project.scripts] mdview-tui = "mdview_tui.cli:main"`。`python -m mdview_tui` でも起動できるようにする
- `requires-python = ">=3.10"`
- 開発環境では pip が無い場合があるため、`PYTHONPATH=src python3 -m mdview_tui` での実行も README に記載する

### 6.1 ポータブル版

依存ライブラリが入っている環境でインストールせずに動かすため、パッケージの全モジュールを1ファイルにまとめた `portable/mdview-tui.py` をリポジトリに同梱する。正本はパッケージで、ポータブル版は `tools/bundle.py` で生成する。

```console
$ python3 tools/bundle.py          # regenerate portable/mdview-tui.py
$ python3 tools/bundle.py --check  # exit 1 if portable/mdview-tui.py is out of date
```

```python
# tools/bundle.py
def bundle(package_dir: Path) -> str: ...   # returns the generated source text
def main(argv: list[str] | None = None) -> int: ...
```

生成の規則:

- 対象は `src/mdview_tui/` 以下の `.py`。`__main__.py` と `widgets/__init__.py`（再エクスポートだけ）は含めない
- 並び順はパッケージ内の import の依存関係から決める（依存される側を先に置く）。同じ依存段のものはパス名の順。関数の中に書いた遅延 import（`cli.py` の `app` の import）も依存として扱う。循環があれば生成を失敗させる
- パッケージ内の import（`from mdview_tui... import ...`）は消す。関数の中のものも消す
- 最上位の外部ライブラリ・標準ライブラリの import は先頭にまとめ、同じ文は1つにする。`from __future__ import annotations` は全体の先頭に1つだけ置く
- 各モジュールの docstring は消し、代わりに `# ---- mdview_tui/<path> ----` の区切りのコメントを入れる
- 先頭にシバン `#!/usr/bin/env python3`、生成物であること・バージョン・必要な依存ライブラリ・再生成のコマンドを書いたコメントを入れ、末尾に `if __name__ == "__main__": sys.exit(main())` を置く
- 次の場合は1ファイルにすると意味が変わるので、生成を失敗させる（理由を stderr に出し終了コード 1）
  - モジュールの最上位で定義される名前（関数・クラス・代入）が、別のモジュールと重なる
  - パッケージ内の import に `as` の別名や `import mdview_tui.xxx` の形がある
- 生成結果を `compile()` で構文チェックしてから書き出す。改行は LF、文字コードは UTF-8
- `--check` では書き出さずに、既存のファイルと生成結果が一致するかだけを調べる（一致すれば 0、違えば理由を出して 1）

## 7. テスト方針

- テストは標準ライブラリの `unittest` で書く（pytest でもそのまま実行可能な形にする）。実行: `PYTHONPATH=src python3 -m unittest discover -s tests -t .`
- UI 以外のロジックは単体テストで網羅し、UI は Textual の `App.run_test()`（Pilot）で主要操作のみ確認する。

| 対象 | 確認内容 |
|---|---|
| `cli` | `--version` 出力と終了コード 0、未知オプションで 2、入力なし（TTY）で 2 とメッセージ、存在しないファイルで 1 とメッセージ |
| `source` | UTF-8 / BOM 付き / CRLF の読み込み、非 UTF-8・ディレクトリ・存在しないファイルのエラーメッセージ |
| `render` | 各要素（見出し・リスト・タスクリスト・引用・コード・表・水平線・HTML・画像）の出力文字列、幅による折り返し、全角文字を含む折り返し、見出し行番号、リンク位置（折り返し・表セル内を含む）、幅を変えてもソース位置で見出しが対応すること |
| `frontmatter` | フロントマター無し・閉じの行が無い（`none`）、閉じが `---` / `...`、末尾の空白、本文が同じ行数の空行で始まること、本文の途中の `---` は残ること、値が書かれた通りの文字列になる（`2026-10-08`・`1.10`）、空のフロントマター、構文エラー・最上位が配列/文字列のエラー、`to_view`（title/author/date の取り出し、author の配列、書かれていない項目、その他の項目の順序、配列・入れ子・空の値の文字列化） |
| `render`（フロントマター） | 題名・作成者・日付・その他の項目・区切りの出力、点線の区切りの有無、目次（`headings`）に題名が入らないこと、`plain_lines` に含まれること、エラー表示、空のフロントマターで何も出ないこと、フロントマターがあっても本文の見出しの `anchors` のソース行がファイルの行番号と一致すること |
| `slug` | 英字・記号・日本語・重複見出し |
| `search` | 大文字小文字無視、全角文字のセル位置、0件、wrap around |
| `links` | アンカー・外部・相対 `.md`・`#` 付き・URL エンコード・非対応ファイル・stdin 時、`file:` の URL（アンカー・`localhost`・UNC・Windows のドライブ名・Markdown 以外）、`display_href`（復元・不正な並び） |
| `history` | push で forward がクリアされる、back/forward の境界（空のとき None） |
| `watcher` | 変更なし・更新・削除・再作成（一時ディレクトリで検証） |
| `editor` | `VISUAL` 優先、`EDITOR`、未設定時の OS 別既定、引数付きコマンドの分割 |
| `portable` | 同梱の `portable/mdview-tui.py` が `bundle()` の結果と一致すること（食い違いの検出）、`PYTHONPATH` を付けずに別ディレクトリから `--version`・存在しないファイル（終了コード 1）が動くこと、モジュールとして読み込み Pilot で起動・スクロール・検索・目次・リンク遷移が動くこと、名前の重なり・別名 import で `bundle()` が失敗すること |
| `app` | 起動して本文表示、各スクロールキー、`/` 検索で一致数表示と `n`/`N`、`t` から見出しジャンプ、Tab+Enter で相対リンク遷移と Backspace / `L` で戻る・進む、アンカー・存在しないリンク・非対応リンク・外部リンク、ファイル書き換えで自動再読込・削除通知、`r` 再読込で行維持、フロントマターの表示と検索・自動再読込での更新、エディタ起動後の再読込、`T` でテーマ切替、`?` ヘルプ、リサイズで位置維持、標準入力時の制限 |
