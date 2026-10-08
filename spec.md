# mdview 設計書

`requirements.md`（要求仕様）に対する実装設計をまとめる。対象は現在のソースツリー（`src/` / `src-tauri/`）の実装内容。

## 1. アーキテクチャ概要

- **Tauri v2**（Rust製バックエンド + OS純正Webview）上に**React 19 + TypeScript + Vite**のフロントエンドを載せる構成。
- フロントエンドはMarkdownの読み込み・レンダリング・UI操作・Word形式へのエクスポート（requirements.md 3.10、6章参照）をほぼすべて担当し、Rust側は「CLI引数取得」「ファイル監視」「外部エディタ起動」という薄い役割のみを持つ。
- ファイルの読み書きはフロントエンドから`@tauri-apps/plugin-fs`を直接呼び出す方式とし、独自のRustコマンドは作らない（読み取り専用のcapabilitiesで権限を絞ることでセキュリティを担保）。プロセス起動が必要な「外部エディタで開く」だけは、任意コマンド実行の穴にしないよう専用のRustコマンドとして実装する。
- 複数ファイルを同時に開く「タブ機能」（requirements.md 3.2）はフロントエンド側の状態管理・UI構成の拡張として実現する。Rust側で変わるのは「ファイル監視」だけで、単一ファイルの監視から**タブごとに独立した複数ファイルの同時監視**に拡張する（3.1参照）。

```
┌─────────────────────────────┐        ┌───────────────────────────┐
│         React (Webview)       │◄──IPC──►│        Rust (Tauri)         │
│  ・タブ状態管理 / UI            │        │  ・CLI引数取得コマンド        │
│  ・Markdownレンダリング         │        │  ・ファイル監視 (notify)     │
│  ・fs/dialog/store/opener呼出  │        │    （タブごとに複数同時）     │
│                                │        │  ・file-changedイベント発火  │
│                                │        │  ・外部エディタプロセス起動   │
└─────────────────────────────┘        └───────────────────────────┘
```

## 2. ディレクトリ構成

```
src-tauri/
  src/
    lib.rs         # プラグイン登録・コマンド登録のエントリポイント
    commands.rs     # initial_file_path（CLI引数取得）・open_in_editor・finish_startup
    watcher.rs        # start_watching / stop_watching（タブごとに複数ファイルを同時監視）
    main.rs
  capabilities/
    default.json      # 権限定義（読み取り専用）
  tauri.conf.json

src/
  main.tsx
  App.tsx                     # 全体レイアウト（Toolbar + TabBar + タブぶんのTabPane）の配線
  App.css
  state/
    TabsContext.tsx             # 開いている全タブの配列・アクティブタブ・タブ非依存の一時エラーを持つ唯一のグローバル状態
    TabDocumentContext.tsx        # 1タブぶんの{path, dir}を配下（MarkdownLink等）へ渡す読み取り専用コンテキスト
    ZoomContext.tsx                 # 全タブ共通の本文ズーム倍率・永続化・キーボードショートカット（11章参照）
  hooks/
    useFileOpener.ts            # openTab（新規タブ作成/既存タブへの切替）・reloadTab（監視からの再読込）
    useFileWatcher.ts             # 開いている全タブぶんのfile-changedイベントを購読し該当タブをreloadTab
    useRecentFiles.ts               # 最近使ったファイルの永続化
    useHeadings.ts                    # 見出し抽出＋アクティブ見出し追跡（TabPaneごとに1インスタンス）
    useSearch.ts                        # mark.js制御。状態自体はTabsContextのtab.searchに保持（4.4参照）
    useOsTheme.ts                         # OSライト/ダーク設定の監視
    useExternalEditor.ts                    # アクティブタブに対するエディタコマンドの永続化・起動・Ctrl+E
    useWordExport.ts                          # アクティブタブをWord形式(.docx)へ変換・保存（6章参照）
    usePaneZoom.ts                              # TabPaneごと: Ctrl+ホイール受付・倍率の適用・スクロール位置の保持（11章参照）
  components/
    Toolbar.tsx           # 開く・最近使ったファイル・エディタ・Word形式で保存・検索欄（アイコンボタン、常にアクティブタブに対して操作）
    TabBar.tsx               # タブ一覧（横スクロール、×またはCtrl+Wで閉じる）
    TabPane.tsx                # タブ1枚ぶんの2ペイン（Sidebar+MarkdownView）とロード状態表示
    icons.tsx                     # ツールバー用SVGラインアイコン（Folder/History/Pencil）
    DropZoneOverlay.tsx             # ドラッグ&ドロップ受付
    Sidebar.tsx / TocTree.tsx         # 左ペイン目次
    MarkdownView.tsx                    # 右ペイン本体（react-markdown配線）
    FrontMatterHeader.tsx                 # 本文先頭のフロントマター表示（12章参照）
    MermaidBlock.tsx                      # Mermaid個別描画
    MarkdownLink.tsx                        # 相対リンク/外部リンクの振り分け
  lib/
    markdown.tsx      # remark/rehypeプラグイン構成・componentsマップ
    headings.ts          # 見出しツリー構築（純粋関数、テスト対象）
    paths.ts                # 相対パス解決（純粋関数、テスト対象）
    assetSrc.ts                # img src解決（convertFileSrc）
    markdownFiles.ts              # .md/.markdown判定
    displayPath.ts                   # UI表示用のファイル名抽出
    docxExport.ts                       # Markdown AST → docxパッケージのドキュメントツリーへの変換（6章参照）
    settingsStore.ts                      # settings.jsonストアの共有ローダー（エディタ設定・ズーム倍率で共用）
    zoom.ts                                 # ズーム倍率の計算（純粋関数、テスト対象、11章参照）
    frontMatter.ts                            # フロントマターの切り出し・表示用データへの変換（純粋関数、テスト対象、12章参照）
```

## 3. Rust側（バックエンド）設計

### 3.1 コマンド一覧

| コマンド | 役割 |
| --- | --- |
| `initial_file_path()` | `std::env::args().nth(1)` を返すだけ。起動時にCLI引数で渡されたパスをフロントエンドへ渡す（起動時の最初のタブとして開かれる）。 |
| `start_watching(path)` | 指定ファイルの**親ディレクトリ**を`notify`で監視し、対象ファイルへの変更イベントを検知したら`file-changed`イベント（payload=path）をフロントエンドへemitする。タブごとに呼ばれるため、`WatcherState`は単一の監視ではなく**パスをキーにした`HashMap<String, RecommendedWatcher>`**として複数ファイルを同時に監視できるようにする。同じpathで再度呼んだ場合はそのエントリを新しい値で置き換える（＝再読込のたびに呼んでも安全な冪等操作）。 |
| `stop_watching(path)` | **新規**。`HashMap`から該当pathのエントリを削除する（`RecommendedWatcher`がdropされ監視が止まる）。タブを閉じたときにフロントエンドから呼ばれ、閉じたタブの監視をリークさせないためのクリーンアップ用コマンド。 |
| `open_in_editor(command, path)` | `std::process::Command::new(command).arg(path).spawn()`を実行するだけの薄いラッパー。`spawn`は起動確認のみで完了を待たない（fire-and-forget）。`command`はフロントエンドの`useExternalEditor`が保持する**ユーザー設定値**（デフォルト`emacs`）のみを渡す設計とし、Markdown本文など信頼できない入力を渡す経路は無い。`path`は常にアクティブタブのpathを渡す。起動失敗（コマンドが見つからない等）は`Err(String)`にして呼び出し元でエラーバナー表示する。 |
| `finish_startup(app)` | 起動直後に1回だけフロントエンドから呼ばれる。ウィンドウの`inner_size()`を取得し、+1px→元のサイズに戻す形で`set_size()`を2回呼ぶだけの処理。8.1「既知の落とし穴」参照。 |

親ディレクトリ単位で監視しているのは、エディタの「一時ファイルへ保存→リネームで置き換え」という一般的な保存方式でもイベントを取りこぼさないため。タブごとに独立したエントリを持つ設計上、同じディレクトリ内の複数ファイルをそれぞれ別タブで開いた場合はディレクトリ単位で見ると監視が重複するが、実装の単純さを優先し、ディレクトリ単位の参照カウントのような重複排除はあえて行わない。

### 3.2 プラグイン構成（`lib.rs`）

`opener` / `dialog` / `fs` / `store` の4プラグインを登録。`store`は`Builder::default().build()`で初期化（最近使ったファイル一覧の永続化に使用）。

### 3.3 権限設計（`capabilities/default.json`）

- `core:default`, `opener:default`, `dialog:allow-open`, `store:default`, `fs:allow-exists`, `fs:allow-read-text-file`
- `fs:scope`に`{"path": "**/*"}`を許可し、ユーザーが選んだ任意の場所のファイルを読み取れるようにする
- **書き込み・削除系の権限は一切付与しない**（要求仕様3.7「閲覧専用」を権限レベルで担保）
- `tauri.conf.json`の`app.security.assetProtocol`を`enable:true, scope:["**"]`にし、Rust依存の`tauri` cargo featureに`protocol-asset`を追加。ローカル画像を`convertFileSrc()`経由で表示するために必要。
- `initial_file_path`/`start_watching`/`stop_watching`/`open_in_editor`/`finish_startup`はプラグインコマンドではなく自前実装のTauriコマンドのため、capabilities（ACL）の対象外で常時呼び出し可能。`open_in_editor`は代わりに「フロントエンド側でユーザー設定値以外を渡さない」という実装規約でスコープを絞っている（3.1参照）。
- Word形式エクスポート（requirements.md 3.10）のため`dialog:allow-save`・`fs:allow-write-file`を追加する。書き込み対象を保存ダイアログで選んだ1ファイルに限定する考え方は`open_in_editor`と同様に実装規約側で担保する（詳細は6.4参照）。

## 4. フロントエンド設計

### 4.1 状態管理

- `state/TabsContext.tsx`: アプリ全体でただ1つ、開いている全タブの配列`tabs: TabState[]`・`activeTabPath: string | null`・どのタブにも属さない一時的なエラー`appError: string | null`を保持するグローバル状態。
  - `TabState = { path, dir, content, loading, error, search: { query, matchCount, currentIndex } }`。**タブの識別子は連番IDではなく`path`文字列そのもの**とする。「既に同じファイルを開いていれば新規タブを作らず既存タブに切り替える」（requirements.md 3.2）を`tabs.some(t => t.path === path)`という単純な配列検索だけで実現できるための設計。パスの大文字小文字などの正規化は行わない（既存の`useFileWatcher`のpath完全一致判定と同じ前提を踏襲）。
  - 公開する操作: タブの追加（`loading:true`の仮登録）／`setTabDocument`／`setTabError`／`setTabLoading`／`removeTab`／`setActiveTab`、検索状態用の`setTabSearchQuery`・`setTabSearchMatches`・`searchGoToNext`・`searchGoToPrev`・`clearTabSearch`、および`appError`用の`setAppError`。
  - `appError`は「まだどのタブにも属していない」失敗専用のバナー状態（新規オープン試行の失敗、外部エディタ起動失敗）。既に開いているタブの再読み込み失敗は、ここではなく該当タブ自身の`error`に入る（4.4参照）。
- `state/TabDocumentContext.tsx`: `TabPane`が自分の担当する1タブぶんの`{ path, dir }`だけを配下（`MarkdownLink`）へ渡すための読み取り専用コンテキスト。旧`DocumentContext`が持っていた`setDocument`等のsetterはすべて`TabsContext`側（ファイル読み込みのオーケストレーションを行う`useFileOpener`経由）に一本化したため、こちらは値を受け渡すだけの薄いラッパーになる。

### 4.2 主要フックの役割

| フック | 役割 |
| --- | --- |
| `useFileOpener` | `openTab(path)`と`reloadTab(path)`を提供。`openTab`は既に同じpathのタブがあれば`setActiveTab`した上で`addRecentFile`を呼ぶ（新規タブを作らない場合も「開いた」扱いとして最近使ったファイル一覧の先頭に繰り上げる、requirements.md 3.1）。無ければ`loading:true`の仮タブを追加して即座にアクティブにし、`exists`確認→`readTextFile`→`dirname`取得→`setTabDocument`→`addRecentFile`→Rust`start_watching`呼び出しを行う。失敗時は`removeTab`でタブごと破棄しつつ`setAppError`＋`removeRecentFile`（新規タブが壊れたまま残ることはない）。`reloadTab`は既存タブに対してのみ動作し、失敗時はタブを消さず`setTabError`のみ行う（stale contentの上にエラーバナーを重ねる、単一ファイル版と同じ見た目）。ダイアログ経由(`openViaDialog`)・ドラッグ&ドロップ・最近使ったファイル選択・相対Markdownリンククリックは、いずれもこの`openTab`を呼ぶ薄いラッパー。 |
| `useFileWatcher` | アプリ起動時に一度だけ`file-changed`イベントを購読し、payloadのpathが現在開いているいずれかのタブのpathと一致すれば、そのタブに対して`reloadTab`を呼ぶ。`tabs`配列は常に最新を参照できるようrefで保持し、タブの増減のたびに購読を張り直したりはしない。 |
| `useRecentFiles` | `@tauri-apps/plugin-store`に`recentFiles`配列（最大10件、重複除去）を永続化する。変更なし。 |
| `useHeadings` | レンダリング後のDOMを`querySelectorAll('h1..h6')`で走査して見出しツリーを構築し、`IntersectionObserver`で画面内に入っている見出しのうち最上部のものを「アクティブ」とする。ロジックは変更なく、`TabPane`ごとに1インスタンス生成される。 |
| `useSearch` | mark.jsの実行を、タブの`search.query`（`TabsContext`）の変化に紐付ける形に変更。クエリ文字列・件数・現在位置は`TabsContext`の`tab.search`に一元化し、`Toolbar`の入力欄・件数表示・▲/▼ボタンはアクティブタブの`search`を直接読み書きする。`TabPane`側は`query`が変わるたびmark.jsで`unmark→mark`し結果件数を`setTabSearchMatches`で書き戻す副作用と、`currentIndex`が変わるたびマッチ要素へ`.search-match--current`を付け外しして`scrollIntoView`する副作用の2つを持つだけになる（詳細は4.4）。`Ctrl+F`のグローバルハンドリングは`Toolbar`が保持する`inputRef`に対して行う（変更なし）。 |
| `useOsTheme` | `matchMedia('(prefers-color-scheme: dark)')`の変化を購読。CSSの`@media`だけで済まないMermaidの配色切り替え（SVGに色が焼き込まれるため）にのみ使用。変更なし。 |
| `useExternalEditor` | `TabsContext`の`activeTabPath`を参照して起動対象を決める（`useDocument()`は使わない）。エディタコマンド（`settings.json`ストア、デフォルト`emacs`）の読み込み・保存と、`openInEditor()`（Rustの`open_in_editor`呼び出し）を提供。起動失敗は`setAppError`（特定タブの`error`ではなく前述の一時バナー）に出す。`Ctrl+E`のグローバルキーハンドリングは変更なし。 |

### 4.3 コンポーネント構成

`App.tsx`が`TabsProvider`でラップし、`Toolbar` → `TabBar` → 開いている各タブぶんの`TabPane`という構造。`TabPane`は`tabs`配列の各要素につき1つ常にマウントされ続け、非アクティブなタブは`display:none`で見た目上隠すだけでアンマウントしない（設計判断の理由は4.4参照）。アクティブタブが1枚も無い場合の空状態メッセージ・ドラッグ&ドロップ受付（`DropZoneOverlay`）は`App.tsx`側で従来通り扱う。

各`TabPane`は`TabDocumentContext.Provider`で自タブの`{path, dir}`を配下に渡しつつ、そのタブの`loading`/`error`/`content`に応じてローディング表示・エラーバナー・2ペイン（`Sidebar`+`MarkdownView`、`react-resizable-panels`の`Group`/`Panel`/`Separator`。サイズ指定は**文字列でパーセント指定**、数値だとpx扱いになる点に注意）を描画する。`useHeadings`・`useSearch`の副作用部分は`TabPane`内でそのタブ用の`containerRef`に対して呼び出す。ペイン幅は`Group`インスタンスがタブごとに独立するため、タブごとに個別のサイズを持つ（アプリ再起動時の永続化はしない、既存の単一ファイル版と同じ方針）。

`TabBar`はタブごとにファイル名ラベル（`title`属性でフルパスをツールチップ表示）と×の閉じるボタンを横並びで表示する。コンテナに`overflow-x: auto; white-space: nowrap`を設定し、タブ数の上限なしに横スクロールで対応する（requirements.md 3.2）。タブクリックで`setActiveTab`、×クリックは`event.stopPropagation()`した上でそのタブを閉じる。閉じる処理は「`removeTab`＋Rustの`stop_watching`呼び出し」を1セットとし、閉じたのがアクティブタブだった場合は残っているタブのうち直前のタブ（無ければ次のタブ、それも無ければ`null`）をアクティブにする。`Ctrl+W`もこれと同じ「アクティブタブを閉じる」処理を呼ぶグローバルキーハンドラで、`useSearch`/`useExternalEditor`と同じ「フックが自分でキー購読する」パターンを踏襲する。閉じるボタンは新規のSVGアイコンを追加せず、既存の▲/▼ボタンと同様「×」のテキストグリフで表現する（タブの数だけ繰り返し描画されるため軽量さを優先）。

`Toolbar`は「開く」「最近使ったファイル」「エディタで開く」「検索欄」を持つ点は変わらないが、いずれの操作対象も`TabsContext`の`activeTabPath`（＝アクティブタブ）になる。ファイル未オープン時（`tabs.length === 0`）の無効化条件はすべて`activeTabPath === null`に統一される。タブごとのファイル名がタブラベルとして常時見えるようになるため、旧`.toolbar__current-path`（ツールバー右端のファイル名表示、7.1の対策対象だった要素）は廃止する。⚙ボタンによる外部エディタコマンド設定パネルは変更なし。

`MarkdownView`・`MarkdownLink`・`Sidebar`/`TocTree`・`MermaidBlock`はロジック変更なし。`MarkdownView`が受け取る`components`マップのメモ化（`dir`が変わらない限り安定した参照を保つ、8章の落とし穴参照）は、1つの`TabPane`が生涯同じ`path`/`dir`を担当し続ける（タブ切り替えで`dir`が変化することがない）ため、単一ファイル版よりもさらに安定する。

### 4.4 タブ機能の設計判断

- **タブの識別子＝ファイルパス**: 連番やUUIDを別途発行せず、開いているファイルの絶対パス文字列をそのままタブのキーとして使う。「既に開いているファイルを再度開こうとしたら既存タブに切り替える」という要求（requirements.md 3.2）を、タブ追加時の配列検索だけで満たせるため。
- **非アクティブなタブもDOMにマウントしたまま隠す**: `TabPane`をアクティブ/非アクティブに関わらず常時マウントし、`display:none`で切り替える設計とした。理由:
  1. requirements.md 3.2は自動リロード・目次・検索のハイライト状態が「タブごとに独立して保持される」ことを求めている。非表示タブでもファイル変更を検知して再読み込みする（`useFileWatcher`が全タブを対象に監視する）には、そのタブのReact状態（`content`）がタブ切り替えと無関係に生き続けている必要がある。
  2. アンマウント→再マウント方式だと、タブに戻るたびmark.jsのハイライト・Mermaid/KaTeXの再描画・スクロール位置の復元をすべて作り直す必要があり、実装・不具合の温床になる。マウントしたまま隠すだけならこれらはブラウザの描画状態としてそのまま保持される。
  - トレードオフとして、開くタブが増えるほどDOM・メモリ使用量が線形に増える。requirements.md 5節でタブ数に上限を設けない方針としたが、mdviewは少数のファイルを並べて参照する軽量ビューア用途を想定しており、実用上問題になる規模ではないと判断した。
  - **既知の落とし穴（対応済み）**: `rehype-slug`が振る見出しidは「1つの文書内」でのみ一意性を保証する。全タブを常時マウントする設計の結果、同じ見出しテキストを持つ別タブ（本プロジェクトの`requirements.md`/`spec.md`同士のように、番号付き見出しなどで衝突しやすい）が同時にDOM上へ存在しうる。このため`document.getElementById(id)`のような**文書全体を対象にしたid検索**は、非表示の別タブ側の要素を誤って返しうる。実際に「2つ目のファイルを開くと目次のハイライト・クリックジャンプが効かない」という不具合として顕在化した。対策として、目次関連の要素解決はすべて`document.getElementById`を使わず、そのタブ自身の`containerRef`配下から探す（`useHeadings`は見出し要素への参照を直接保持、`TabPane`のクリックジャンプと`MarkdownLink`の同一文書内アンカー（`#id`）は自タブのコンテナ配下を`querySelectorAll`で探す）方式に統一した。
- **検索状態は`TabsContext`に集約し、`TabPane`は片方向に反応するだけ**: `Toolbar`（検索入力欄・▲/▼ボタン）と`TabPane`（mark.jsによるDOM操作）は兄弟同士でDOM参照を共有できない。そこで`query`/`matchCount`/`currentIndex`を`TabsContext`の`tab.search`に持たせ、`Toolbar`はそこへの読み書き（`setTabSearchQuery`・`searchGoToNext`/`Prev`・`clearTabSearch`）だけを行う。`TabPane`は自タブの`search.query`/`currentIndex`の変化を`useEffect`で監視し、mark.jsの実行とスクロール・ハイライトクラスの付け替えという副作用だけを担当する。双方が相手の内部関数を直接呼び合うレジストリのような仕組みを避け、状態を介した片方向のデータフロー（Toolbarが書く→TabPaneが反応する→結果をTabPaneが書き戻す→Toolbarが表示する）に単純化した。
- **タブを跨いだエラー表示の切り分け**: 「まだタブが存在しない状態での失敗」（新規オープン試行、外部エディタ起動）は`TabsContext.appError`としてウィンドウ上部に一時バナー表示する。「既に開いているタブの再読み込み失敗」（監視中のファイルが外部で削除された等）は該当タブ自身の`error`とし、そのタブを表示したときにだけ（stale contentの上に重ねて）表示する。前者は「どのタブにも属さない一時的な通知」、後者は「特定タブの状態」という性質の違いを、そのまま状態の置き場所に反映させている。
- **タブを閉じたときのRust側クリーンアップ**: タブを閉じる操作は必ずRustの`stop_watching(path)`を呼び、そのファイルの`notify`ウォッチャーを破棄する。呼び忘れると、閉じたはずのタブのファイルを外部で変更したときに存在しないタブ宛の`file-changed`イベントが飛び続ける（実害はないが無駄なファイル監視が残り続ける）。

## 5. Markdownレンダリングパイプライン

`lib/markdown.tsx`で構成:

- remarkPlugins: `remark-gfm`, `remark-math`
- rehypePlugins: `rehype-slug`, `rehype-highlight`, `[rehype-katex, { throwOnError: false }]`
- componentsマップ:
  - `img`: `assetSrc.ts`の`resolveAssetSrc(src, dir)`で相対パスを`convertFileSrc()`によるURLへ変換
  - `a`: `MarkdownLink`コンポーネント（5.3参照）
  - `pre`: 子要素が`language-mermaid`のコードブロックか判定し、該当すれば`<pre>`ごと`MermaidBlock`に差し替える。それ以外は通常の`<pre>`（`rehype-highlight`が付与した`hljs-*`クラスをApp.css内の自前テーマでスタイリング）

### 5.1 Mermaid（`MermaidBlock.tsx`）

`useOsTheme()`の値が変わるたびに`mermaid.initialize({ theme, securityLevel: "strict", suppressErrorRendering: true })`→`mermaid.render()`を実行し、成功時はSVGを`innerHTML`に注入、失敗時は例外メッセージをそのままエラーボックスに表示する。

### 5.2 KaTeX

`rehype-katex`の`throwOnError: false`により、不正な数式でもアプリ全体をクラッシュさせず、KaTeX標準のインラインエラー表示（赤字でソースを表示）に委ねる。

### 5.3 相対リンク（`MarkdownLink.tsx`）

クリック時に`href`を判定する分岐:

1. `#`始まり → 何もせず標準のブラウザ内アンカー遷移に任せる（`scroll-margin-top`をCSSで見出しに設定済み）
2. `hasUriScheme(href)`（`http:`/`https:`/`mailto:`など、Windowsの絶対パスと誤認しない任意のURIスキーム）→ `event.preventDefault()`し`@tauri-apps/plugin-opener`の`openUrl()`でOS既定ブラウザ（またはスキームに関連付けられたアプリ）を起動
3. それ以外（相対/絶対パス）→ `event.preventDefault()`し`resolveRelativePath(dir, href)`で絶対パス化、`.md`/`.markdown`かつ`exists()`が真なら`openTab()`を呼ぶ。既に同じファイルが別タブで開いていればそのタブへ切り替わり、開いていなければ新規タブとして開く（4.2参照）。条件を満たさない場合は何もしない（Webviewが不正なパスへ遷移して壊れるのを防ぐ）

`dir`は自タブの`TabDocumentContext`から取得するため、リンクが含まれるタブ自身のディレクトリを基準に相対パスが解決される。

## 6. Word形式エクスポート設計（requirements.md 3.10）

requirements.md 3.10（Word形式で保存）の実装済みの設計をまとめる（実機での動作確認状況はrequirements.md 8節を参照）。

### 6.1 方針

- 変換処理はフロントエンド側で完結させ、Rust側に専用コマンドを追加しない。1章の「ファイルの読み書きはフロントエンドから`plugin-fs`を直接呼び出す」方針を、書き込みを伴うこの機能にもそのまま適用する。
- 変換元はDOM（レンダリング結果）ではなく、react-markdownが解釈するのと同じMarkdown AST（`remark-gfm`/`remark-math`適用後）とする。DOMを直接docxへ変換するのではなくASTを起点にすることで、`lib/markdown.tsx`のcomponentsマップ（画像パス解決・Mermaidブロック判定など）と処理の前提を揃えられる。
- Mermaid図・KaTeX数式は、AST上はコードブロック／数式ノードでしかなく、docx側で編集可能なテキスト・図形として変換する対象ではない（requirements.md 3.10）。そのため、これらのみ「レンダリング済みDOMを画像化」という例外経路を取る。
- コードブロックのシンタックスハイライト配色（`hljs-*`）は変換対象外とし、等幅フォントのプレーンテキストとしてのみ変換する（requirements.md 3.10）。ASTのコードノードからテキストのみを取り出せばよく、DOM側のトークン構造を参照する必要がない。
- 本文中のリンクは、外部URL（`http:`/`https:`/`mailto:`等スキームを持つもの）のみWordのハイパーリンクとして変換する。相対Markdownリンク・同一文書内アンカー（`#id`）は宛先がWord文書内で意味を持たないため、リンクテキストのみのプレーンテキストにする（`lib/paths.ts`の`hasUriScheme`と同じ判定を流用できる）。
- 見出しにはWordの見出しスタイル（Heading 1〜6、文書タイトルはTitleスタイル）を付与するが、Wordの目次フィールド（TOC）は自動生成しない（requirements.md 3.10）。
- フォントは文書タイトル・見出し・本文で固定指定する（requirements.md 3.10）。
  - 文書タイトル（文書内で最初に現れる`depth === 1`の見出しノード1つのみ）: 「游ゴシック Medium」・18pt・黒
  - 見出し（それ以外の見出し。文書タイトルを消費した後に現れる`depth === 1`の見出しがあった場合も含む）: 「游ゴシック Medium」・14pt・黒
  - 本文（見出し・コードブロックを除く段落・リスト・表・引用）: 「游明朝」・10.5pt（色は指定しない＝Word既定）
  - いずれも`Paragraph`/`TextRun`の`font`・`size`・`color`プロパティで明示指定する。Windows環境では「游ゴシック Medium」は`bold`フラグではなく独立したフォントファミリ名として存在するため、`bold: true`ではなくフォント名そのものを`"游ゴシック Medium"`と指定する。`size`はdocxパッケージの仕様上ハーフポイント単位のため、18pt→`36`、14pt→`28`、10.5pt→`21`を指定する。`color`は`"000000"`を明示指定する（Wordの既定テンプレートのTitle/Headingスタイルはテーマ色由来の色（黒以外）を持つことがあり、スタイル指定だけでは黒にならない場合があるため、ランレベルで上書きする）。コードブロックの等幅フォント（6.1既述）はこの本文フォント指定より優先される。
  - 「最初の`depth === 1`見出しだけを文書タイトルとする」判定は、AST走査全体で使い回す`docxExport.ts`内の相関用オブジェクト（Mermaid/KaTeXの画像相関に使う`mermaidIndex`/`katexIndex`と同じオブジェクト、6.2参照）に`titleConsumed: boolean`を追加し、最初の1回だけ消費されるフラグとして持たせる。
- 段落の行間・段落後余白も固定指定する（requirements.md 3.10）。行間の定義は「行の上端から次の行の上端までの幅がフォントサイズの1.5倍」（＝行と行の余白はフォントサイズの0.5倍）であり、Wordの行間「倍数」指定（`lineRule: LineRuleType.AUTO`。フォント固有の既定行送り値が基準で、指定フォントサイズより大きくなることが多い）はこの定義に一致しないため使わない。代わりに`lineRule: LineRuleType.AT_LEAST`を使い、`line`にフォントサイズから直接計算したtwip値（`size`（半ポイント）の値 × 15 ＝ フォントサイズ(pt) × 1.5 × 20）を指定する。文書タイトル・見出し・本文はフォントサイズが異なるため、`line`もそれぞれ計算し直す（タイトル18pt→`540`、見出し14pt→`420`、本文10.5pt→`315`）。`after`（段落後余白、6pt→`120`twip）はすべて共通。
  - `exact`ではなく`atLeast`を使うのは、本文段落中にインライン数式（KaTeXの画像化、本節既述）が挟まりフォントサイズ基準の行送りより画像が高くなる場合に、その行だけ自動的に高さが広がりクリップを防ぐため。通常のテキストのみの行では指定した行送りぴったりになり、見た目は`exact`と変わらない。
  - Mermaid/KaTeXの画像のみで構成される段落（テキストランを持たない、本節既述の「レンダリング済みDOMを画像化」した結果を挿入する段落）は、画像の高さがフォントサイズと無関係なため`line`/`lineRule`は設定せず、`after: 120`のみを指定する（Wordの既定の行高さ拡張に任せる）。
  - コードブロックの各行は既存の`spacing: { before: 0, after: 0 }`のまま据え置き、この行間・段落後余白ルールの対象外とする（詰まったコードらしい見た目を保つため、requirements.md 3.10）。

### 6.2 使用ライブラリ・処理フロー

- **docx生成**: npm `docx`パッケージ（ブラウザ上で`.docx`バイナリを組み立てられるライブラリ）を新規依存として追加する。
- **Mermaid/KaTeXの画像化**: 変換対象タブが実際にレンダリング済みのSVG（`MermaidBlock`が`innerHTML`に注入したもの）・KaTeX要素を、画面表示と等倍のサイズで一旦`<canvas>`に描画し`toBlob()`でPNG化してdocxへ画像として埋め込む（requirements.md 3.10、高解像度化は行わない）。変換のためだけにMermaid/KaTeXを再実行することはしない。
- 本文ズーム（requirements.md 3.11）が100%以外のときは、画像化の間だけ対象タブのズームを一時的に100%へ戻す（11.6参照）。これにより、出力される画像の大きさは表示倍率に左右されない。
- 処理フロー: Toolbarの「Word形式で保存」ボタン押下 → `@tauri-apps/plugin-dialog`の`save()`で保存先パスを取得（既定ファイル名は元のMarkdownファイル名の拡張子を`.docx`に変えたもの、requirements.md 3.10） → `lib/docxExport.ts`がMarkdown ASTとアクティブタブのDOM（画像化対象の取得用）を入力に`.docx`バイナリ（`Uint8Array`）を生成 → `@tauri-apps/plugin-fs`の`writeFile(path, bytes)`で書き込み → 失敗時は`setAppError`でエラーバナー表示（`useFileOpener`の新規オープン失敗時と同じ「タブに属さない一時エラー」の扱い、4.1参照）。

### 6.3 ディレクトリ構成への追加

- `hooks/useWordExport.ts`: 保存ダイアログ表示〜書き込みまでの一連の流れ（`exportActiveTabToDocx()`）を提供。対象は常に`TabsContext`の`activeTabPath`。
- `lib/docxExport.ts`: Markdown AST → `docx`パッケージのドキュメントツリー構築ロジック。DOM非依存の部分は純粋関数として実装し、`headings.ts`/`paths.ts`同様Vitestでの単体テスト対象とする（10章）。
- `components/Toolbar.tsx`: 「Word形式で保存」アイコンボタンを追加。ファイル未オープン時（`activeTabPath === null`）は無効化する（他のツールバーボタンと同じ条件、4.3参照）。

### 6.4 権限設計への追加（3.3の補足）

- `dialog:allow-save`（保存先選択ダイアログ）・`fs:allow-write-file`をcapabilitiesに追加する。
- Tauri v2の`fs`プラグインはread/writeでscopeを分離できないため、`fs:scope`の`{"path": "**/*"}`は書き込みにもそのまま適用される。requirements.md 4節が求める「保存ダイアログでユーザーが指定した保存先ファイルへの書き込み権限に限定し、任意ファイルへの書き込みの穴にしない」は、`open_in_editor`（3.1・3.3）と同じ考え方——**capabilitiesのscopeではなく実装規約でスコープを絞る**——で担保する。具体的には、`writeFile`の呼び出し箇所を`useWordExport`の1箇所のみとし、書き込み先パスには常に直前の`save()`ダイアログの戻り値だけを渡す（Markdown本文やリンク文字列など、信頼できない入力由来の値が書き込み先パスに使われる経路を作らない）。

## 7. パス解決ユーティリティ（`lib/paths.ts`）

Windows専用の同期パス処理。`@tauri-apps/api/path`の非同期APIは`img`/`a`のレンダリング関数内（同期関数）から呼べないため、自前実装とした。

- `isAbsolutePath`: ドライブレター(`C:\`)・UNC(`\\server`)・POSIX風(`/`)を絶対パスと判定
- `resolveRelativePath(baseDir, target)`: `.`/`..`セグメントを解決してWindowsパスとして結合（ドライブルートより上には遡らない）
- `hasUriScheme`: 絶対パスと誤認しないよう除外した上で`scheme:`形式を判定

いずれも`lib/paths.test.ts`でVitestによる単体テストを持つ。

## 8. スタイリング／テーマ方針

- ベースの配色・ボタン・ツールバー等は`App.css`内の`@media (prefers-color-scheme: dark)`のみで自動切り替え（JSでのテーマ管理は行わない）。`TabBar`・タブ1つぶんのスタイルもこの方針を踏襲し、新たなテーマ切替の仕組みは導入しない。
- コードハイライトは`highlight.js`のCSSを直接importせず、`.hljs-*`トークンクラスに対する自前の配色（ライト/ダーク）をApp.cssに定義。バンドルサイズと二重CSS管理を避けるため
- Mermaidだけは前述の通りSVGに色を焼き込む都合上、`useOsTheme`で明示的に再レンダリングする

### 8.1 既知の落とし穴: WebView2の初回ペイント漏れ

ツールバーをアイコン化した際、`margin-left: auto`で右端に寄せた`.toolbar__current-path`（ファイル名表示）が、アプリ起動直後の初回描画では**一切ペイントされない**現象が発生した。`getComputedStyle`・`getBoundingClientRect`・`document.elementFromPoint()`はいずれも正しい値を返す（レイアウト自体は正常）ため、CSSの問題ではなくWebView2側の初回コンポジット漏れと判断した。

切り分けのため`margin-left: auto`／flexスペーサー／親要素の`justify-content: space-between`／`position: absolute`の4通りの右寄せ手法を試したが、いずれも同じ症状（ウィンドウをリサイズすると即座に正しく描画される）が再現した。「配置場所そのものではなく、初回レイアウト確定後に一度も再描画されていないこと」が原因と特定した。

対策として、`src-tauri/src/commands.rs`の`finish_startup`コマンドを起動直後に1回呼び出す。`App.tsx`側で初回マウントから400ms後（初回のバギーな描画が実際に発生するのを待つための遅延）に`invoke("finish_startup")`し、Rust側でウィンドウを+1px→元のサイズへ2回`set_size()`することで強制的に再コンポジットさせ、以降は正常に描画される。ウィンドウを`visible:false`で起動して見せる前に直そうとする方式も試したが、非表示中はWebView2がコンポジット自体を省略するため無効だった（表示中のウィンドウに対してのみ有効）。

> **タブ機能導入に伴う再確認事項**: 上記の不具合が発生していた`.toolbar__current-path`要素自体は4.3の通り廃止する。原因がWebView2の一般的な初回コンポジット漏れなのか、この要素固有の条件（レイアウトの位置・タイミング等）に依存していたのかは未特定のため、`finish_startup`のワークアラウンドが新しいツールバー/`TabBar`構成でも引き続き必要かどうかは実装後に実機で再確認する必要がある。

## 9. ビルド・パッケージング

- `tauri.conf.json`: `productName: mdview`, ウィンドウ初期サイズ1100×750（最小480×360）, `bundle.targets: ["nsis", "msi"]`
- 開発: `npm run tauri dev`（Vite devサーバー + `cargo run`）
- 本番: `npm run tauri build` → `src-tauri/target/release/bundle/{nsis,msi}/`にインストーラ生成

## 10. テスト方針

- 純粋関数（`headings.ts`の`buildHeadingTree`、`paths.ts`の各関数）のみVitestで単体テスト化（`npm run test`）
- ズーム倍率の計算（`lib/zoom.ts`の`stepZoom`/`normalizeZoom`、11.2参照）も純粋関数としてVitestで単体テスト化する
- フロントマターの切り出しと表示用データへの変換（`lib/frontMatter.ts`の`parseFrontMatter`/`toFrontMatterView`、12.2・12.3参照）も同様に単体テスト化する
- UIロジック・Tauri連携部分は自動テスト化せず、実機起動＋スクリーンショットによる手動/半自動確認で担保する方針とした（Tauriアプリ全体をヘッドレスでE2Eテストする標準的な仕組みがないため）。タブ機能（`TabsContext`・`TabBar`・`TabPane`・複数ファイル同時監視）もUI状態とTauri連携が主体のため、この方針を踏襲し実機確認で担保する。「既に開いているファイルは既存タブへ切り替える」判定（`path`の配列検索）のように単純な処理は、既存のvitest対象（純粋関数）ほどの複雑さがないため個別の単体テストは設けない。

## 11. 表示の拡大・縮小（ズーム）設計（requirements.md 3.11）

### 11.1 方針: 本文要素へのCSS `zoom` プロパティ

本文だけを拡大・縮小する方法として、次の3つを比べた。

| 方法 | 結果 |
| --- | --- |
| `.markdown-body`の`font-size`を変える | 文字は`em`指定なので拡大されるが、Mermaid図（SVGにpx単位の`max-width`が付く）・画像・`rem`指定の余白・`max-width: 860px`は変わらない。要求の「図や画像も同じ倍率」を満たせない |
| `transform: scale()` | 見た目だけが拡大され、レイアウト（折り返し・スクロール量）は元のまま。はみ出しやスクロール量のずれを自前で補正する必要がある |
| **CSS `zoom`（採用）** | 指定した要素の中身すべて（文字・余白・画像・SVG・KaTeX）がブラウザのページズームと同じように拡大され、折り返しも倍率に合わせて計算し直される。WebView2（Chromium）が対応している |

- `zoom`は`.markdown-body`（`<article>`）に指定し、スクロールコンテナの`.markdown-view`には指定しない。スクロールバーや本文ペインの幅は変わらず、中身だけが大きくなる。
- CSSは`.markdown-body { zoom: var(--content-zoom, 1); }`とし、倍率の値は各タブの`.markdown-view`要素にCSS変数`--content-zoom`として設定する（11.4参照）。
- WebView全体のズーム（ブラウザ標準のページズーム）は使わない。Tauri v2の`zoomHotkeysEnabled`は既定値`false`のままとし、`tauri.conf.json`には追加しない。これにより、WebView2自体がCtrl+ホイールやCtrl+`+`/`-`でページ全体を拡大することはない。
- **ピンチ操作の再有効化**: Tauri が内部で使う wry は、`zoomHotkeysEnabled`が`false`のとき`IsZoomControlEnabled`と一緒に`IsPinchZoomEnabled`も`false`にする（wry 0.55 `src/webview2/mod.rs`）。この状態では WebView2 がタッチパッドのピンチ操作を受け取った時点で捨ててしまい、ページにはイベントが一切届かない（実機で、ピンチ中のイベントが0件であることを確認した）。そこで、`src-tauri/src/webview_settings.rs`の`enable_pinch_gestures`を`Builder::setup`から呼び、各WebViewの`ICoreWebView2Settings5::SetIsPinchZoomEnabled(true)`で**ピンチ操作だけ**を有効に戻す（`IsZoomControlEnabled`は`false`のまま）。
  - これにより、タッチパッドのピンチは`ctrlKey: true`のホイールイベントとしてページに届く。
  - 一方で、ページ側がそのイベントの既定動作を止めないと、WebView2 がページ全体を見た目上拡大（ビジュアルビューポートのピンチズーム）してしまう。そのため`ZoomProvider`で`window`の`wheel`を`{ passive: false }`で購読し、`ctrlKey`付きのものはどこで発生しても`preventDefault()`する。本文ペインの`usePaneZoom`のリスナーは`preventDefault()`の後もイベントを受け取れるので、本文のズームはそのまま動く。目次・ツールバーの上でのピンチは何も起こさない。
  - タッチスクリーンでのピンチは、ホイールイベントにならず直接ページ全体を拡大してしまう。これを防ぐため、`html`に`touch-action: pan-x pan-y`を指定する。
  - 依存クレートとして`webview2-com`（0.38）と`windows`（0.61）を Windows 向けにだけ追加する。いずれも wry がすでに使っている版と同じなので、新たなクレートは増えない。

### 11.2 倍率の表現（`lib/zoom.ts`）

小数の誤差を避けるため、倍率は**整数のパーセント値**（`zoomPercent`、50〜300、既定100）で持ち、CSSに渡すときだけ`zoomPercent / 100`にする。

- `stepZoom(current, direction: 1 | -1): number` … 10%増減し、50〜300の範囲に収める
- `normalizeZoom(value: unknown): number` … ストアから読んだ値の検証用。数値でなければ100、範囲外なら範囲内に収め、10の倍数に丸める（設定ファイルを手で書き換えた場合などへの備え）
- 定数`ZOOM_MIN = 50` / `ZOOM_MAX = 300` / `ZOOM_STEP = 10` / `ZOOM_DEFAULT = 100`

いずれも純粋関数で、Vitestの単体テスト対象とする（10章）。

### 11.3 状態管理と永続化（`state/ZoomContext.tsx`）

倍率は全タブ共通なので、タブごとの状態を持つ`TabsContext`には入れず、独立した`ZoomContext`を作る。`App.tsx`で`TabsProvider`の内側に`ZoomProvider`を置く（キーボードショートカットの有効条件にアクティブタブの有無を使うため）。

- 公開する値と操作: `zoomPercent`、`zoomIn()`、`zoomOut()`、`resetZoom()`、`zoomBy(direction, anchor)`（11.5のホイール用）、`consumeAnchor()`（11.4参照）
- **永続化**: `settings.json`ストアの`contentZoom`キーに保存する。今は`useExternalEditor`がストアを開く`getStore()`を内部に持っているので、これを`lib/settingsStore.ts`に移し、エディタ設定とズームの両方から使う（同じファイルを2回`load`しないため）。
  - 起動時に読み込み、`normalizeZoom`を通して反映する。読み込みが終わるまでは100%で表示する。
  - ホイールを連続で回したときに毎回書き込まないよう、保存は最後の変更から300ms後にまとめて1回行う（デバウンス）。
- **キーボードショートカット**: 既存の`useSearchShortcut`・`useExternalEditor`と同じく、`window`の`keydown`を購読する。アクティブタブが無いときは何もしない（見えない状態で倍率だけが変わるのを防ぐ）。
  - 拡大: `Ctrl` + `+` / `=` / `;` / テンキー`+`（`;`は日本語キーボードで`+`と同じキーのため。Chromeと同じ扱い）
  - 縮小: `Ctrl` + `-` / テンキー`-`
  - 100%に戻す: `Ctrl` + `0` / テンキー`0`
  - 判定は`event.key`で行い、テンキーは`event.code`（`NumpadAdd`等）で判定する。該当したときだけ`preventDefault()`する。

### 11.4 倍率の適用とスクロール位置の保持（`hooks/usePaneZoom.ts`）

`TabPane`ごとに`usePaneZoom(containerRef, isActive, hasContent)`を呼ぶ。`containerRef`は既存の`.markdown-view`（スクロールコンテナ）への参照で、`useHeadings`・`useTabSearchSync`と共用する。

**倍率の適用は`useLayoutEffect`の中で、自分でCSS変数を書き換えて行う。** Reactの描画（`style`属性）で変数を変えてしまうと、レイアウト効果が走る時点ではすでに新しい倍率でレイアウトされており、「変更前にどこを見ていたか」を測れない。そこで、次の手順を画面に描画される前に同期的に行う。

1. 変更前の倍率のまま、基準点（11.5）にある要素と、その要素内での位置の割合を記録する
   - 基準点の要素は`document.elementFromPoint(x, y)`で取得し、`rect.top`と高さに対する割合`(y - rect.top) / rect.height`を記録する
   - 要素が取れなかった場合や、コンテナの外の要素だった場合は`.markdown-body`自体を使う（その場合は文書全体に対する割合で近似することになる）
2. `container.style.setProperty("--content-zoom", String(zoomPercent / 100))`で新しい倍率を適用する
3. 同じ要素の新しい`rect`から、記録した割合の位置がふたたび基準点の`y`に来るよう`scrollTop`を補正する

**非アクティブなタブには、その場では適用しない。** 非アクティブなタブは`display:none`なので、要素の位置を測れず、`scrollTop`も設定できない。各`usePaneZoom`は「自分のコンテナに最後に適用した倍率」をrefに持ち、`isActive`が`true`の間だけ上記の手順を実行する。非アクティブ中に倍率が変わったタブは、次にアクティブになったときの`useLayoutEffect`（タブが表示された直後、古い倍率のまま）で上記の手順を実行する。こうすると、裏で倍率が変わったタブも、表示を切り替えたときに画面上端に見えていた位置を保てる。

- 新しくファイルを開いたタブ（`hasContent`が`false`から`true`に変わったとき）は、スクロール位置が先頭なので補正はせず、倍率の適用だけを行う
- この処理は既存の`TabPane`の「非アクティブでもマウントしたまま隠す」設計（4.4）にそのまま乗る

### 11.5 ホイール操作と基準点

- `.markdown-view`要素に`wheel`イベントを`addEventListener(..., { passive: false })`で直接登録する。Reactの`onWheel`はpassiveとして登録され`preventDefault()`できないため使わない。
- `event.ctrlKey`が`false`のときは何もしない（通常のスクロール）。`true`のときは`preventDefault()`してスクロールを止め、倍率を変える。
- ホイールが効くのは本文ペインの上にカーソルがあるときだけとする。目次・ツールバーの上でCtrl+ホイールしても何も起きない（11.1の通りWebView側のズームも無効のため）。
- タッチパッドのピンチ操作も、`ctrlKey: true`のホイールイベントとして届くため（11.1の再有効化が前提）、同じく拡大・縮小になる。タッチパッドは1回の操作で細かい`deltaY`を大量に送ってくるので、`deltaY`を積算し、絶対値が50pxを超えるたびに1段階（10%）変える。マウスの1ノッチ（`deltaY`は約100）はそれ1回で1段階になる。1イベントで変えるのは最大1段階とし、向きが変わったら積算値をリセットする。`deltaMode`が行・ページ単位のときは1イベントで1段階とする。実機の記録では、ピンチ1回で`|deltaY|`が0.1〜39程度のイベントが20〜70個届き、合計は約80〜160で、1〜3段階変わった。
- **基準点**: ホイールの場合はカーソル位置`(event.clientX, event.clientY)`とし、`zoomBy(direction, anchor)`でContextに預ける。キーボード操作やツールバーの倍率表示クリックでは基準点を指定せず、そのときは本文ペインの上端（横方向は中央）を基準点とする。`usePaneZoom`は`useLayoutEffect`の中で`consumeAnchor()`を呼んで基準点を受け取る（受け取ったら消える）。基準点はrefで持ち、再描画のきっかけにはしない。

### 11.6 他機能との関係

- **目次のジャンプ・アクティブハイライト・検索のスクロール**: どれも`scrollIntoView`と、`root`を`.markdown-view`とした`IntersectionObserver`で動いている。`zoom`はスクロールコンテナの内側に掛かるだけなので、これらはそのまま正しく動く。コードの変更は不要で、実機確認のみ行う。
- **見出しの`scroll-margin-top: 1rem`**: 本文と一緒に拡大されるが、見た目への影響は小さいためそのままにする。
- **Word形式で保存（6章）**: 画像化（`rasterizeElementToImageRun`）は`getBoundingClientRect()`と`html-to-image`を使っている。`zoom`が掛かっていると、取得される大きさが表示倍率に応じて変わってしまう。そこで`useWordExport`で、変換の前に対象タブのコンテナの`--content-zoom`を一時的に`1`にし、`scrollTop`を記録しておく。変換が終わったら（失敗した場合も`finally`で）元の倍率と`scrollTop`に戻す。同じ幅・同じ倍率に戻すとレイアウトも元通りになるので、`scrollTop`をそのまま戻せばよい。
  - トレードオフ: 変換している間（画像が多い文書だと1秒程度）、本文が一時的に100%で表示される。毎回の画像化で倍率を計算して補正する方法もあるが、`html-to-image`が作る複製要素に祖先の`zoom`がどう反映されるかが実装に依存し、確実でない。そのため、確実に100%相当になるこの方法を採用する。
  - 倍率を戻すのは`useWordExport`が担当し、`usePaneZoom`が覚えている「最後に適用した倍率」は変えない（一時的な上書きなので）。

### 11.7 ツールバーの倍率表示

- 倍率が100%以外のときだけ、ツールバーの検索欄の左に`120%`のようなテキストボタン（`.toolbar__zoom-reset`）を表示する。クリックすると`resetZoom()`する。
- `title`は「表示倍率（クリックで100%に戻す、Ctrl+0）」とする。
- 新しいアイコンは追加しない（数値を表示すること自体が役割のため）。

## 12. フロントマター設計（requirements.md 3.12）

### 12.1 方針: 描画・出力の前に切り出す

フロントマターは、Markdownの解析に渡す**前**に元の文字列から切り出し、残りの本文だけを既存の処理（画面表示のreact-markdown、Word出力のremark）に渡す。

- remarkのプラグイン（`remark-frontmatter`）でASTの`yaml`ノードとして扱う方法もある。ただし、その場合もYAMLの解釈は別途必要で、画面表示とWord出力の2つのパイプラインそれぞれでノードを取り除く処理を書くことになる。最初に1回切り出せば、目次（`useHeadings`はDOM上の`h1`〜`h6`を走査する）・Word出力・本文内検索のどれにも手を入れずに「フロントマターが本文に混ざらない」状態にできる。
- 切り出しと表示用データへの変換は`lib/frontMatter.ts`に純粋関数としてまとめ、Vitestの単体テスト対象とする（10章）。

### 12.2 切り出し（`parseFrontMatter`）

`parseFrontMatter(content: string): ParsedDocument`

```ts
type FrontMatterValue = string | FrontMatterValue[] | { [key: string]: FrontMatterValue } | null;

type ParsedDocument =
  | { kind: "none"; body: string }                                      // フロントマター無し
  | { kind: "ok"; body: string; data: Record<string, FrontMatterValue> } // 解釈できた
  | { kind: "error"; body: string; raw: string; message: string };       // YAMLとして解釈できない
```

- 先頭のBOM（`﻿`）は無視する。行の区切りは`\r?\n`とする（Windowsで作られたファイルを考慮）。
- 1行目が`---`だけ（末尾の空白は許す）の行であれば、2行目以降で最初に現れる`---`または`...`だけの行までをフロントマターとする。
  - 閉じの行が見つからない場合は、フロントマターではないとみなし、`kind: "none"`で元の文字列全体を本文とする（従来通りの表示になる）。
- 本文は閉じの行の次の行から最後までとする。
- YAMLの解釈には npm `yaml` パッケージを使い、**`schema: "failsafe"`**を指定する。
  - failsafeスキーマでは、スカラー値はすべて書かれた通りの文字列になる（`date: 2026-10-08`を日付型に、`version: 1.10`を数値`1.1`に変換したりしない）。requirements.md 3.12の「`date`は書かれた文字列をそのまま表示する」を満たし、ほかの項目でも見た目が書いた内容から変わらない。
  - 配列・オブジェクトはそのまま構造として得られる。
- 次の場合は`kind: "error"`とし、`raw`（`---`の間の元の文字列）とエラー内容を返す。
  - YAMLの構文エラー（`yaml`の例外メッセージをそのまま使う）
  - 最上位がキーと値の組（マッピング）でない場合（例: 文字列や配列だけが書かれている）。メッセージは「フロントマターがキーと値の形式ではありません」とする
- `---`と`---`の間が空、または空白だけの場合は、`kind: "ok"`、`data: {}`とする（表示するものは何もないが、本文からは取り除く）。

**既知の制限**: フロントマターを持たず、1行目に水平線`---`を書き、その後にも`---`だけの行がある文書は、その間がフロントマターとして解釈される。YAMLとして解釈できなければエラー表示になる。Jekyll・Hugoなど一般的なツールと同じ判定方法であり、許容する。

### 12.3 表示用データへの変換（`toFrontMatterView`）

`toFrontMatterView(data): { title: string | null; byline: string[]; others: [string, string][] }`

- `title`: `data.title`を`formatValue`で文字列化したもの。無い・空文字なら`null`。
- `byline`: `author`と`date`をこの順に並べた配列。書かれていない・空のものは含めない。
  - `author`が配列の場合は要素を「、」でつなぐ。
- `others`: `title`・`author`・`date`以外のキーを、書かれた順に`[キー, 値の文字列]`として並べる。
- `formatValue(value)`
  - 文字列 → そのまま
  - `null`（`key:`のように値が空）→ 空文字
  - 配列 → 各要素を`formatValue`して`", "`でつなぐ
  - オブジェクト → `キー: 値`を`", "`でつなぐ（値は`formatValue`で再帰的に変換）
- キー名の大文字小文字は区別する（`Title`は`title`として扱わない）。YAMLのキーとして一般的な小文字表記に合わせる。

画面表示とWord出力の両方がこの関数を使い、`author`のつなぎ方などの扱いを揃える。

### 12.4 画面表示

- `TabPane`で`useMemo(() => parseFrontMatter(tab.content), [tab.content])`を1回だけ計算し、`MarkdownView`には本文（`body`）と解析結果を渡す。自動リロードで`content`が変わったときだけ再計算される。
- 新しいコンポーネント`components/FrontMatterHeader.tsx`を、`MarkdownView`の`<article className="markdown-body">`の中、`ReactMarkdown`の直前に置く。`.markdown-body`の中にあるため、ズーム（11章）と本文内検索（mark.jsはコンテナ全体を対象にする）がそのまま効く。
- `kind: "ok"`の場合の構造:

```html
<header class="front-matter">
  <div class="front-matter__title">設計メモ</div>          <!-- titleがあるとき -->
  <div class="front-matter__byline">藤原 ・ 2026-10-08</div> <!-- bylineが1つ以上あるとき。" ・ "でつなぐ -->
  <dl class="front-matter__fields">                         <!-- othersが1つ以上あるとき -->
    <dt>tags</dt><dd>tauri, markdown</dd>
  </dl>
</header>
```

  - `title`・`byline`・`others`がすべて空の場合は`<header>`ごと描画しない。
  - 題名に`h1`要素を**使わない**。`useHeadings`はコンテナ内の`h1`〜`h6`を目次に拾うため、`h1`にすると目次に出てしまう（requirements.md 3.12「目次には表示しない」）。見た目は`.markdown-body h1`と同じ大きさ・太さをCSSで当てる。
  - `<dl>`は`display: grid; grid-template-columns: max-content 1fr;`の2列にし、`dd`には`overflow-wrap: anywhere`を指定して長い値を折り返す。文字は`0.85em`、色は既存の控えめな文字色（`opacity`）に合わせる。`others`と題名・bylineの間に区切り線（`border-top`）を引く。
  - ヘッダー全体と本文の間は、下に区切り線と余白を設けて、本文と区別できるようにする。
  - ヘッダーの直後に来る本文の最初の要素（多くは`h1`）の上余白は0にする（`.markdown-body .front-matter + *`）。ヘッダー自身の下余白と重なって間が空きすぎるのを防ぐ。
- `kind: "error"`の場合: `<div class="front-matter front-matter--error">`に「フロントマターを解釈できませんでした: <エラー内容>」と、`raw`を`<pre>`で表示する。エラー内容は`yaml`の例外メッセージの1行目（「…at line N, column M」まで。続く該当箇所の抜粋は`raw`と重複するため使わない）とし、末尾の`:`は取り除く。配色は既存の`.mermaid-error`等のエラー表示に合わせる。
- ライト/ダークの配色は、既存方針（8章）通り`App.css`の`@media (prefers-color-scheme: dark)`で切り替える。

### 12.5 Word出力（6章への追加）

- `convertMarkdownToDocx`の中で`parseFrontMatter(content)`を呼び、ASTの解析には`body`を渡す。呼び出し側（`useWordExport`）は変更しない。
- `kind: "ok"`かつ`title`がある場合:
  - 文書の先頭に、`HeadingLevel.TITLE`・`TITLE_MARKS`・`TITLE_SPACING`（6.1の文書タイトルの書式）で題名の段落を出力する。
  - `RasterResources.titleConsumed`を最初から`true`にして変換を始める。これで本文の`#`見出しはすべて通常の見出しの書式になる（requirements.md 3.12）。
- `byline`がある場合は、その次に`BODY_MARKS`・`BODY_SPACING`の段落を1つ出力する。文字列は画面表示と同じく`" ・ "`でつなぐ。
- `others`は出力しない。
- `new Document({ title, creator, ... })`で、文書のプロパティの「タイトル」に`title`、「作成者」に`author`（`toFrontMatterView`と同じく「、」でつないだもの）を設定する。無いものは設定しない。
- `kind: "error"`・`kind: "none"`の場合は、フロントマター部分を除いた本文のみを従来通り変換する（エラー表示はWordには出力しない）。

### 12.6 依存パッケージ

- `yaml`（eemeli/yaml）を`dependencies`に追加する。依存パッケージを持たず、型定義を同梱しており、ブラウザで動く。
