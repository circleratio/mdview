# mdview（GUI版）

Markdownファイルを閲覧するためのWindowsデスクトップビューア（Tauri + React + TypeScript）。

Mermaid記法による図表描画、KaTeX形式による数式表示に対応し、左ペインに見出しの目次、右ペインに本文を表示する2ペイン構成を持つ。詳細な仕様は [`doc/requirement.md`](./doc/requirement.md)、設計は [`doc/spec.md`](./doc/spec.md) を参照。

このディレクトリ（`gui/`）だけで完結しており、以下のコマンドはすべて `gui/` ディレクトリで実行する。ターミナルで使うTUI版は [`../tui/`](../tui/) を参照。

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

UI・Tauri連携部分の自動テストは無いため、`npm run tauri dev` で実機確認する（詳細は `doc/spec.md` の「テスト方針」を参照）。

## アプリのアイコン

アイコンの元データは [`app-icon.svg`](./app-icon.svg)（1024×1024 の SVG）。これを編集した後、次のコマンドで `src-tauri/icons/` の各サイズの画像（Windows の `icon.ico` を含む）を作り直す。

```sh
npm run tauri icon app-icon.svg
```

コマンドは Android・iOS 用の画像（`src-tauri/icons/android/`、`src-tauri/icons/ios/`）も作るが、このアプリでは使わないので削除する。ウィンドウ内で使うファビコン（`public/icon.png`）は `src-tauri/icons/icon.png` をコピーして更新する。

タイトルバーのアイコンはビルド時に実行ファイルへ埋め込まれる。`src-tauri/build.rs` で `icons/` を変更の監視対象にしているため、アイコンを作り直した後の `npm run tauri dev` / `npm run tauri build` では自動的に再ビルドされる。

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
