# mdview-tui 実装計画

`doc/spec.md` の設計を以下の順で実装する。テストは `PYTHONPATH=src python3 -m unittest discover -s tests -t .` で実行する。

## 依存関係

```
S1 ─┬─ S2 (errors/source) ─────────────────────────────┐
    ├─ S3 (parser/slug/themes/document) ─ S4 (render) ─┤
    ├─ S5 (search/links/history/watcher/editor) ───────┤
    │                                                   ├─ S6 (widgets) ─ S7 (app) ─ S8 (cli) ─ S9 ─ S10
```

- S2・S3・S5 は互いに独立しており、並行して実装できる
- S4 は S3 に依存する。S6 は S4・S5 に、S7 は全モジュールに依存する
- S8（cli）は S2 だけで先に作れるが、起動確認には S7 が必要なため S7 の後に完成させる

## S1. プロジェクト雛形

- やること: `pyproject.toml`（hatchling、依存、エントリポイント、バージョン参照）、`src/mdview_tui/__init__.py`（`__version__ = "0.1.0"`）、`__main__.py`、`tests/` ディレクトリ、テスト用サンプル `tests/fixtures/`（`sample.md`、`other.md`、`bom_crlf.md`、`sjis.md`）
- 完了条件: `PYTHONPATH=src python3 -c "import mdview_tui; print(mdview_tui.__version__)"` が `0.1.0` を出力する

## S2. errors / source

- やること: `MdviewError`、`Source`、`load_file`、`load_stdin`、`reattach_tty`
- 完了条件: `tests/test_source.py`（UTF-8 / BOM / CRLF、存在しない・ディレクトリ・非 UTF-8 のメッセージと exit_code=1）が成功する

## S3. parser / slug / themes / document

- やること: markdown-it-py の設定（table / strikethrough / linkify / html）、`slugify` と `SlugRegistry`、`MdTheme` と `THEMES`（dark / light）、`RenderedDoc` などのデータクラス
- 完了条件: `tests/test_slug.py` が成功する。GFM の表・取り消し線・自動リンクを含む文書を `parse()` すると、該当トークンが得られる（`test_render.py` の前提テストとして書く）

## S4. render

- やること: 全ブロック要素・インライン要素の描画、タスクリスト検出、リンク meta 付与と `LinkRegion` 抽出、見出し行番号、`plain_lines`
- 完了条件: `tests/test_render.py`（各要素の出力、幅 40 / 80 での折り返し、全角を含む折り返し、見出し行番号、折り返し・表セル内のリンク位置）が成功する

## S5. search / links / history / watcher / editor

- やること: `doc/spec.md` 3.7〜3.11 の各モジュール
- 完了条件: `test_search.py`、`test_links.py`、`test_history.py`、`test_watcher.py`、`test_editor.py` が成功する

## S6. widgets

- やること: `keys.py`（キー定義の一元化）、`MarkdownView`（Line API、ハイライト、リンク選択、リサイズ時の再描画）、`TocPanel`、`SearchInput`、`StatusBar`、`HelpScreen`
- 完了条件: 確認用の最小アプリで `MarkdownView` に `sample.md` を表示し、スクロールとハイライトが動作する（S7 の Pilot テストで担保する）

## S7. app

- やること: `MdviewApp`、`BINDINGS`（要求仕様のキーバインド表すべて）、`open_source`、履歴操作、ポーリングによる自動再読込、エディタ起動（`suspend`）、外部リンク（`webbrowser`）、テーマ切替、エラー通知
- 完了条件: `tests/test_app.py`（`doc/spec.md` 7章の app の項目）が成功する

## S8. cli

- やること: `build_parser`、`main`（入力元の判定、`MdviewError` から終了コードへの変換、130）
- 完了条件: `tests/test_cli.py`（`--version`、未知オプション、入力なし、存在しないファイル）が成功する

## S9. 手動動作確認

`doc/requirement.md` の使いかたと突き合わせる。

```console
$ cd tui    # リポジトリルートから
$ export PYTHONPATH=src

# 正常系: 表示し、キー操作を一通り試す（j/k, Space/b, d/u, g/G, /, n/N, t, Tab/Enter, Backspace/L, e, r, T, ?, q）
$ python3 -m mdview_tui tests/fixtures/sample.md
$ python3 -m mdview_tui --theme light --no-watch doc/spec.md

# 標準入力
$ cat README.md | python3 -m mdview_tui
$ python3 -m mdview_tui - < doc/requirement.md

# 自動再読込: 別端末で表示中のファイルを書き換えて表示が更新されることを確認
$ cp tests/fixtures/sample.md /tmp/watch.md
$ python3 -m mdview_tui /tmp/watch.md               # 別端末: echo "# changed" >> /tmp/watch.md

# バージョン・ヘルプ
$ python3 -m mdview_tui --version; echo $?          # mdview-tui 0.1.0 / 0
$ python3 -m mdview_tui --help; echo $?             # usage... / 0

# 異常系
$ python3 -m mdview_tui nofile.md; echo $?          # mdview-tui: nofile.md: No such file or directory / 1
$ python3 -m mdview_tui doc; echo $?                # mdview-tui: doc: Is a directory / 1
$ python3 -m mdview_tui tests/fixtures/sjis.md; echo $?  # mdview-tui: ...: not valid UTF-8 / 1
$ python3 -m mdview_tui --bogus; echo $?            # argparse error / 2
$ python3 -m mdview_tui; echo $?                    # no input / 2
```

- 完了条件: すべての出力と終了コードが `doc/requirement.md` と一致し、TUI 上の各操作が要求どおりに動く

## S10. 最終確認

- やること: テスト全件の実行、`doc/requirement.md` の要求仕様の各項目と実装を1つずつ突き合わせる、`__pycache__` などの副産物を削除する
- 完了条件: テストが全件成功し、要求仕様に未対応の項目がない（対応できない項目があれば要求仕様側を更新してユーザーに報告する）
