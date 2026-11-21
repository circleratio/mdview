# mdview

Markdownファイルを整形表示するビューア。用途に合わせて2つの版を用意している。

| 版 | ディレクトリ | 実装 | 対象環境 | 主な特徴 |
|---|---|---|---|---|
| GUI版 | [`gui/`](./gui/) | Tauri + React + TypeScript | Windows | タブ、Mermaid図・KaTeX数式の描画、Word形式での保存、ズーム、フロントマター表示 |
| TUI版 | [`tui/`](./tui/) | Python + Textual | Linux / WSL / macOS | less/vim風のキー操作、標準入力からの表示、リンクの行き来（戻る／進む）、フロントマター表示、1ファイルで動くポータブル版 |

2つの版は互いに独立しており、コードや依存関係を共有しない。対応拡張子・Markdown の対応範囲・フロントマター・見出しのアンカー・リンクの扱いなど、両版が守る共通の決まりは [`doc/common.md`](./doc/common.md) にまとめている。ビルド・実行・テストの方法は各ディレクトリの README を参照。

- GUI版: [`gui/README.md`](./gui/README.md)（要求仕様・設計・実装計画は [`gui/doc/`](./gui/doc/)）
- TUI版: [`tui/README.md`](./tui/README.md)（要求仕様・設計・実装計画は [`tui/doc/`](./tui/doc/)）

## ディレクトリ構成

```
mdview/
├── README.md     # this file
├── LICENSE
├── doc/
│   └── common.md # rules shared by both versions
├── gui/          # GUI version (Tauri); see gui/README.md
│   ├── doc/      # requirement.md / spec.md / plan.md
│   ├── src/      # React frontend
│   └── src-tauri/# Rust backend
└── tui/          # TUI version (Python + Textual); see tui/README.md
    ├── doc/      # requirement.md / spec.md / plan.md
    ├── src/mdview_tui/
    ├── portable/ # mdview-tui.py: portable single-file version (generated)
    ├── tools/    # bundle.py: generates the portable version
    └── tests/
```

## ライセンス

[LICENSE](./LICENSE) を参照。
