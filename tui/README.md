# mdview-tui

ターミナルで Markdown ファイルを整形表示する TUI ビューア `mdview-tui` です。
`gui/` ディレクトリにある GUI 版（Tauri）とは独立した Python 実装で、このディレクトリ（`tui/`）だけで完結しています。以下のコマンドはすべて `tui/` ディレクトリで実行します。

- CommonMark + GFM（表・タスクリスト・取り消し線・自動リンク）に対応し、コードブロックはシンタックスハイライトします
- less/vim 風のキー操作でスクロール・検索・目次ジャンプができます
- 相対パスの `.md` リンクをたどり、戻る/進むで行き来できます
- ファイル先頭の YAML のフロントマター（`title`・`author`・`date` など）を、本文と分けて文書の情報として表示します
- 表示中のファイルを保存すると自動で再読込します
- `e` キーで外部エディタを起動して編集できます
- ダーク／ライトのテーマを切り替えられます

## 必要環境

- Python 3.10 以上
- Linux / WSL / macOS（Windows Terminal はベストエフォート）
- 依存ライブラリ: [Textual](https://github.com/Textualize/textual) 2.0 以上、[markdown-it-py](https://github.com/executablebooks/markdown-it-py)（linkify 付き）、[PyYAML](https://pyyaml.org/) 6.0 以上

## インストール

```console
$ cd tui
$ pip install .
# または
$ uv tool install .
```

### pip が使えない環境で実行する場合

依存ライブラリ（`textual`、`markdown-it-py`、`linkify-it-py`、`PyYAML`）がシステムに入っていれば、インストールせずにソースから実行できます。

```console
$ PYTHONPATH=src python3 -m mdview_tui README.md
```

Debian / Ubuntu 系では `apt install python3-textual python3-markdown-it python3-linkify-it python3-yaml` で依存ライブラリを入れられます。

## 使いかた

```console
# ファイルを表示
$ mdview-tui README.md

# ライトテーマで、自動再読込なしで表示
$ mdview-tui --theme light --no-watch doc/spec.md

# 標準入力から表示
$ cat CHANGELOG.md | mdview-tui
$ curl -s https://example.com/doc.md | mdview-tui -

# バージョン表示
$ mdview-tui --version
mdview-tui 0.1.0
```

### オプション

| オプション | 説明 |
|---|---|
| `FILE` | 表示する Markdown ファイル。`-` で標準入力から読む。省略した場合、標準入力がパイプならそれを読む |
| `--theme {dark,light}` | 起動時のテーマ（既定: `dark`） |
| `--no-watch` | ファイル変更時の自動再読込を無効にする |
| `-h`, `--help` | ヘルプを表示する |
| `-V`, `--version` | バージョンを表示する |

### キー操作

| キー | 動作 |
|---|---|
| `j` / `↓`、`k` / `↑` | 1行下／上へ |
| `Space` / `f` / `PgDn`、`b` / `PgUp` | 1画面下／上へ |
| `d` / `u` | 半画面下／上へ |
| `g` / `Home`、`G` / `End` | 先頭／末尾へ |
| `/` | 検索（大文字小文字を区別しない） |
| `n` / `N` | 次／前の一致へ |
| `t` | 目次パネルの表示切替（`Enter` でジャンプ、`Esc` で閉じる） |
| `Tab` / `Shift+Tab` | 次／前のリンクを選択 |
| `Enter` | 選択中のリンクを開く |
| `Backspace` / `H`、`L` | 履歴を戻る／進む |
| `e` | 外部エディタで開く（`$VISUAL` → `$EDITOR` → `vi`、Windows では `notepad`） |
| `r` | 再読込 |
| `T` | テーマ切替 |
| `?` | キー操作のヘルプ |
| `q` / `Ctrl+C` | 終了 |

### リンクの扱い

- `#見出し` のリンクと相対パスの `.md` リンク（`other.md#section` のようなアンカー付きも可）はビューア内で開きます
- `http(s)://` などの外部リンクは OS 既定のブラウザで開きます
- `.md` 以外のローカルファイル（画像など）へのリンクは開けません

### フロントマター

ファイル先頭の `---` で囲まれた YAML のフロントマターは、本文の先頭に次のように表示します。目次には本文の見出しだけが出ます。

```markdown
---
title: 設計メモ
author: [山田 太郎, 佐藤 花子]
date: 2026-10-08
version: 1.10
tags: [md, viewer]
---
```

```
設計メモ
山田 太郎、佐藤 花子 ・ 2026-10-08
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
version  1.10
tags     md, viewer
────────────────────────────────────────
```

- 値は書かれた通りに表示します（`1.10` は `1.1` になりません）
- YAML として解釈できない場合は、理由と元の文字列を表示し、本文は通常どおり表示します

### 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常終了 |
| 1 | ファイルが存在しない・読み込めない・UTF-8 として解釈できない |
| 2 | 引数の誤り、または入力がない（`FILE` なしで標準入力が端末） |
| 130 | TUI 起動前に Ctrl+C で中断された |

### 制限事項

- 画像・Mermaid 図・数式は描画しません（画像は `[image: 代替テキスト](パス)` と表示します）
- 生 HTML はタグを含めてそのまま文字として表示します
- 検索は表示上の1行単位で行うため、折り返しをまたぐ語句は見つかりません
- コードブロックは折り返さず、画面幅を超える部分は切り詰めて表示します
- マウス操作には対応していません

## 開発

```console
# テストの実行（pytest があれば `PYTHONPATH=src pytest` でも可）
$ PYTHONPATH=src python3 -m unittest discover -s tests -t .
```

ソースは `src/mdview_tui/`、テストは `tests/` にあります。

## ドキュメント

- [リポジトリ全体の README](../README.md)、[GUI 版の README](../gui/README.md)
- [両版の共通仕様](../doc/common.md)

- [要求仕様](doc/requirement.md)
- [設計](doc/spec.md)
- [実装計画](doc/plan.md)
