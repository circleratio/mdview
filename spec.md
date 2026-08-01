# mdview 設計書

`requirements.md`（要求仕様）に対する実装設計をまとめる。対象は現在のソースツリー（`src/` / `src-tauri/`）の実装内容。

## 1. アーキテクチャ概要

- **Tauri v2**（Rust製バックエンド + OS純正Webview）上に**React 19 + TypeScript + Vite**のフロントエンドを載せる構成。
- フロントエンドはMarkdownの読み込み・レンダリング・UI操作をほぼすべて担当し、Rust側は「CLI引数取得」「ファイル監視」「外部エディタ起動」という薄い役割のみを持つ。
- ファイルの読み書きはフロントエンドから`@tauri-apps/plugin-fs`を直接呼び出す方式とし、独自のRustコマンドは作らない（読み取り専用のcapabilitiesで権限を絞ることでセキュリティを担保）。プロセス起動が必要な「外部エディタで開く」だけは、任意コマンド実行の穴にしないよう専用のRustコマンドとして実装する。

```
┌─────────────────────────────┐        ┌───────────────────────────┐
│         React (Webview)       │◄──IPC──►│        Rust (Tauri)         │
│  ・状態管理 / UI               │        │  ・CLI引数取得コマンド        │
│  ・Markdownレンダリング         │        │  ・ファイル監視 (notify)     │
│  ・fs/dialog/store/opener呼出  │        │  ・file-changedイベント発火  │
│                                │        │  ・外部エディタプロセス起動   │
└─────────────────────────────┘        └───────────────────────────┘
```

## 2. ディレクトリ構成

```
src-tauri/
  src/
    lib.rs         # プラグイン登録・コマンド登録のエントリポイント
    commands.rs     # initial_file_path（CLI引数取得）
    watcher.rs        # start_watching（ファイル監視・file-changed発火）
    main.rs
  capabilities/
    default.json      # 権限定義（読み取り専用）
  tauri.conf.json

src/
  main.tsx
  App.tsx                     # 全体レイアウトとフックの配線
  App.css
  state/
    DocumentContext.tsx        # 現在開いているドキュメントの状態
  hooks/
    useFileOpener.ts            # ファイルを開く一連の処理を集約
    useFileWatcher.ts             # file-changedイベント購読→再読込
    useRecentFiles.ts               # 最近使ったファイルの永続化
    useHeadings.ts                    # 見出し抽出＋アクティブ見出し追跡
    useSearch.ts                        # 検索状態とmark.js制御
    useOsTheme.ts                         # OSライト/ダーク設定の監視
    useExternalEditor.ts                    # 外部エディタコマンドの永続化・起動・Ctrl+E
  components/
    Toolbar.tsx           # 開く・最近使ったファイル
    DropZoneOverlay.tsx     # ドラッグ&ドロップ受付
    Sidebar.tsx / TocTree.tsx # 左ペイン目次
    MarkdownView.tsx           # 右ペイン本体（react-markdown配線）
    MermaidBlock.tsx              # Mermaid個別描画
    MarkdownLink.tsx                 # 相対リンク/外部リンクの振り分け
    SearchBar.tsx                       # 検索UI
  lib/
    markdown.tsx      # remark/rehypeプラグイン構成・componentsマップ
    headings.ts          # 見出しツリー構築（純粋関数、テスト対象）
    paths.ts                # 相対パス解決（純粋関数、テスト対象）
    assetSrc.ts                # img src解決（convertFileSrc）
    markdownFiles.ts              # .md/.markdown判定
    displayPath.ts                   # UI表示用のファイル名抽出
```

## 3. Rust側（バックエンド）設計

### 3.1 コマンド一覧

| コマンド | 役割 |
| --- | --- |
| `initial_file_path()` | `std::env::args().nth(1)` を返すだけ。起動時にCLI引数で渡されたパスをフロントエンドへ渡す。 |
| `start_watching(path)` | 指定ファイルの**親ディレクトリ**を`notify`で監視し、対象ファイルへの変更イベントを検知したら`file-changed`イベント（payload=path）をフロントエンドへemitする。既存の監視は`WatcherState`（`Mutex<Option<RecommendedWatcher>>`）を新しい値で置き換えることで自動的に停止・破棄される。 |
| `open_in_editor(command, path)` | `std::process::Command::new(command).arg(path).spawn()`を実行するだけの薄いラッパー。`spawn`は起動確認のみで完了を待たない（fire-and-forget）。`command`はフロントエンドの`useExternalEditor`が保持する**ユーザー設定値**（デフォルト`emacs`）のみを渡す設計とし、Markdown本文など信頼できない入力を渡す経路は無い。起動失敗（コマンドが見つからない等）は`Err(String)`にして呼び出し元でエラーバナー表示する。 |

親ディレクトリ単位で監視しているのは、エディタの「一時ファイルへ保存→リネームで置き換え」という一般的な保存方式でもイベントを取りこぼさないため。

### 3.2 プラグイン構成（`lib.rs`）

`opener` / `dialog` / `fs` / `store` の4プラグインを登録。`store`は`Builder::default().build()`で初期化（最近使ったファイル一覧の永続化に使用）。

### 3.3 権限設計（`capabilities/default.json`）

- `core:default`, `opener:default`, `dialog:allow-open`, `store:default`, `fs:allow-exists`, `fs:allow-read-text-file`
- `fs:scope`に`{"path": "**/*"}`を許可し、ユーザーが選んだ任意の場所のファイルを読み取れるようにする
- **書き込み・削除系の権限は一切付与しない**（要求仕様3.6「閲覧専用」を権限レベルで担保）
- `tauri.conf.json`の`app.security.assetProtocol`を`enable:true, scope:["**"]`にし、Rust依存の`tauri` cargo featureに`protocol-asset`を追加。ローカル画像を`convertFileSrc()`経由で表示するために必要。
- `initial_file_path`/`start_watching`/`open_in_editor`はプラグインコマンドではなく自前実装のTauriコマンドのため、capabilities（ACL）の対象外で常時呼び出し可能。`open_in_editor`は代わりに「フロントエンド側でユーザー設定値以外を渡さない」という実装規約でスコープを絞っている（3.1参照）。

## 4. フロントエンド設計

### 4.1 状態管理

`state/DocumentContext.tsx`が唯一のグローバル状態。`{ path, dir, content, loading, error }`を保持し、`setDocument` / `setError` / `setLoading`の3操作のみを公開する。Redux等は導入せず、React Contextのみで完結させている（状態の種類・更新パターンが単純なため）。

### 4.2 主要フックの役割

| フック | 役割 |
| --- | --- |
| `useFileOpener` | `loadFile(path)`を提供。`exists`確認→`readTextFile`→`dirname`取得→`setDocument`→`addRecentFile`→Rust`start_watching`呼び出し、を1つの関数にまとめる。途中で失敗した場合は`setError`でエラー表示しつつ`removeRecentFile`で最近使った一覧から除去する。ダイアログ経由(`openViaDialog`)もここに実装。 |
| `useFileWatcher` | 現在の`path`に対して`file-changed`イベントを購読し、一致したら`loadFile`で再読込する。 |
| `useRecentFiles` | `@tauri-apps/plugin-store`に`recentFiles`配列（最大10件、重複除去）を永続化する。 |
| `useHeadings` | レンダリング後のDOMを`querySelectorAll('h1..h6')`で走査して見出しツリーを構築し、`IntersectionObserver`で画面内に入っている見出しのうち最上部のものを「アクティブ」とする。Markdownの再パースを避け、rehype-slugが振ったidをそのままTOCのリンク先として使う設計。 |
| `useSearch` | `mark.js`のインスタンスを保持し、クエリ変更のたびに`unmark→mark`。マッチ要素に`.search-match--current`クラスを付け外ししてスクロール。`Ctrl+F`（開く）/`Escape`（閉じる）のグローバルキーハンドリングも内包し、`SearchBar`側の`Enter`/`Shift+Enter`・▲/▼ボタンで前後のマッチへ循環移動する。件数表示（`現在位置 / 総数`）も本フックの状態から算出する。 |
| `useOsTheme` | `matchMedia('(prefers-color-scheme: dark)')`の変化を購読。CSSの`@media`だけで済まないMermaidの配色切り替え（SVGに色が焼き込まれるため）にのみ使用。 |
| `useExternalEditor` | エディタコマンド（`settings.json`ストア、デフォルト`emacs`）の読み込み・保存と、`openInEditor()`（Rustの`open_in_editor`呼び出し、失敗時は`setError`）を提供。`Ctrl+E`のグローバルキーハンドリングも内包（`useSearch`と同じパターン）。 |

### 4.3 コンポーネント構成

`App.tsx`が`DocumentProvider`でラップし、`Toolbar` → `DropZoneOverlay`（内部に検索バー・2ペイン`Group/Panel/Separator`）という構造。2ペインは`react-resizable-panels`の`Group`/`Panel`/`Separator`（サイズ指定は**文字列でパーセント指定**、数値だとpx扱いになる点に注意）。

`MarkdownView`が`react-markdown`本体を描画し、`lib/markdown.tsx`の`getMarkdownComponents(dir)`で生成した`components`マップ（`img`/`a`/`pre`のオーバーライド）を渡す。

`Toolbar`は「開く」「最近使ったファイル」に加えて「エディタで開く」ボタン（`path`が`null`の間は無効化）と、⚙ボタンで開閉する小さな設定パネル（`useExternalEditor`のコマンド文字列をテキスト入力で編集・保存）を持つ。専用の設定画面は設けず、既存のドロップダウン（最近使ったファイル一覧）と同じ「ツールバー直下にポップアップ」パターンを踏襲している。

## 5. Markdownレンダリングパイプライン

`lib/markdown.tsx`で構成:

- remarkPlugins: `remark-gfm`, `remark-math`
- rehypePlugins: `rehype-slug`, `rehype-highlight`, `[rehype-katex, { throwOnError: false }]`
- componentsマップ:
  - `img`: `assetSrc.ts`の`resolveAssetSrc(src, dir)`で相対パスを`convertFileSrc()`によるURLへ変換
  - `a`: `MarkdownLink`コンポーネント（4.4参照）
  - `pre`: 子要素が`language-mermaid`のコードブロックか判定し、該当すれば`<pre>`ごと`MermaidBlock`に差し替える。それ以外は通常の`<pre>`（`rehype-highlight`が付与した`hljs-*`クラスをApp.css内の自前テーマでスタイリング）

### 5.1 Mermaid（`MermaidBlock.tsx`）

`useOsTheme()`の値が変わるたびに`mermaid.initialize({ theme, securityLevel: "strict", suppressErrorRendering: true })`→`mermaid.render()`を実行し、成功時はSVGを`innerHTML`に注入、失敗時は例外メッセージをそのままエラーボックスに表示する。

### 5.2 KaTeX

`rehype-katex`の`throwOnError: false`により、不正な数式でもアプリ全体をクラッシュさせず、KaTeX標準のインラインエラー表示（赤字でソースを表示）に委ねる。

### 5.3 相対リンク（`MarkdownLink.tsx`）

クリック時に`href`を判定する分岐:

1. `#`始まり → 何もせず標準のブラウザ内アンカー遷移に任せる（`scroll-margin-top`をCSSで見出しに設定済み）
2. `hasUriScheme(href)`（`http:`/`https:`/`mailto:`など、Windowsの絶対パスと誤認しない任意のURIスキーム）→ `event.preventDefault()`し`@tauri-apps/plugin-opener`の`openUrl()`でOS既定ブラウザ（またはスキームに関連付けられたアプリ）を起動
3. それ以外（相対/絶対パス）→ `event.preventDefault()`し`resolveRelativePath(dir, href)`で絶対パス化、`.md`/`.markdown`かつ`exists()`が真なら`loadFile()`で切り替え。条件を満たさない場合は何もしない（Webviewが不正なパスへ遷移して壊れるのを防ぐ）

## 6. パス解決ユーティリティ（`lib/paths.ts`）

Windows専用の同期パス処理。`@tauri-apps/api/path`の非同期APIは`img`/`a`のレンダリング関数内（同期関数）から呼べないため、自前実装とした。

- `isAbsolutePath`: ドライブレター(`C:\`)・UNC(`\\server`)・POSIX風(`/`)を絶対パスと判定
- `resolveRelativePath(baseDir, target)`: `.`/`..`セグメントを解決してWindowsパスとして結合（ドライブルートより上には遡らない）
- `hasUriScheme`: 絶対パスと誤認しないよう除外した上で`scheme:`形式を判定

いずれも`lib/paths.test.ts`でVitestによる単体テストを持つ。

## 7. スタイリング／テーマ方針

- ベースの配色・ボタン・ツールバー等は`App.css`内の`@media (prefers-color-scheme: dark)`のみで自動切り替え（JSでのテーマ管理は行わない）
- コードハイライトは`highlight.js`のCSSを直接importせず、`.hljs-*`トークンクラスに対する自前の配色（ライト/ダーク）をApp.cssに定義。バンドルサイズと二重CSS管理を避けるため
- Mermaidだけは前述の通りSVGに色を焼き込む都合上、`useOsTheme`で明示的に再レンダリングする

## 8. ビルド・パッケージング

- `tauri.conf.json`: `productName: mdview`, ウィンドウ初期サイズ1100×750（最小480×360）, `bundle.targets: ["nsis", "msi"]`
- 開発: `npm run tauri dev`（Vite devサーバー + `cargo run`）
- 本番: `npm run tauri build` → `src-tauri/target/release/bundle/{nsis,msi}/`にインストーラ生成

## 9. テスト方針

- 純粋関数（`headings.ts`の`buildHeadingTree`、`paths.ts`の各関数）のみVitestで単体テスト化（`npm run test`）
- UIロジック・Tauri連携部分は自動テスト化せず、実機起動＋スクリーンショットによる手動/半自動確認で担保する方針とした（Tauriアプリ全体をヘッドレスでE2Eテストする標準的な仕組みがないため）
