# mdview

Markdownファイルを閲覧するためのWindowsデスクトップビューア（Tauri + React + TypeScript）。

Mermaid記法による図表描画、KaTeX形式による数式表示に対応し、左ペインに見出しの目次、右ペインに本文を表示する2ペイン構成を持つ。詳細な仕様は [`requirements.md`](./requirements.md)、設計は [`spec.md`](./spec.md) を参照。

## 前提条件

- [Node.js](https://nodejs.org/)（npm）
- [Rust](https://www.rust-lang.org/tools/install)（`cargo`）
- Windows（[Tauriの前提条件](https://tauri.app/start/prerequisites/)に従い、WebView2ランタイム・Visual Studio C++ Build Toolsが必要）

依存パッケージのインストール:

```sh
npm install
```

## 開発時の実行方法

Vite開発サーバーとTauriアプリを同時に起動する。

```sh
npm run tauri dev
```

ホットリロードが有効な状態でアプリウィンドウが立ち上がる。

## ビルド方法

Windows向けインストーラ（NSIS / MSI）を生成する。

```sh
npm run tauri build
```

成功すると以下に生成される。

- `src-tauri/target/release/bundle/nsis/mdview_<version>_x64-setup.exe`
- `src-tauri/target/release/bundle/msi/mdview_<version>_x64_en-US.msi`

## テスト・型チェック

```sh
npm run test        # Vitestによるユニットテスト（純粋関数のみ）
npx tsc --noEmit     # 型チェック
```

UI・Tauri連携部分の自動テストは無いため、`npm run tauri dev` で実機確認する（詳細は `spec.md` の「テスト方針」を参照）。

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
