# 実装計画: 表示の拡大・縮小（ズーム）

対象: requirements.md 3.11 ／ 設計: spec.md 11章

各ステップの終わりで `npm run build`（型チェックを含む）と `npm run test` が通る状態を保つ。ステップごとに1コミットを目安とする。

## ステップ1: 倍率計算の純粋関数とテスト

**ファイル**: `src/lib/zoom.ts`（新規）、`src/lib/zoom.test.ts`（新規）

- 定数 `ZOOM_MIN = 50` / `ZOOM_MAX = 300` / `ZOOM_STEP = 10` / `ZOOM_DEFAULT = 100`
- `stepZoom(current, direction: 1 | -1)`: 10%増減し、50〜300の範囲に収める
- `normalizeZoom(value: unknown)`: 数値でなければ100にする。範囲外は範囲内に収め、10の倍数に丸める
- テストケース
  - 100→110→…→300で止まる（300で拡大しても300のまま）
  - 50で縮小しても50のまま
  - `normalizeZoom`: `undefined`・文字列・`NaN` → 100、`1000` → 300、`20` → 50、`123` → 120

**確認**: `npm run test`

## ステップ2: 設定ストアの共有化

**ファイル**: `src/lib/settingsStore.ts`（新規）、`src/hooks/useExternalEditor.ts`（変更）

- `useExternalEditor.ts` の `STORE_FILE` と `getStore()` を `settingsStore.ts` に移して export する
- `useExternalEditor.ts` は移した `getStore` を import して使う。動作は変えない

**確認**: `npm run build`。動作は変わらないので、実機確認はステップ7でまとめて行う

## ステップ3: ZoomContext（状態・永続化・キーボード）

**ファイル**: `src/state/ZoomContext.tsx`（新規）、`src/App.tsx`（変更）

- `ZoomProvider` と `useZoom()` を作る
  - state: `zoomPercent`（初期値100）
  - ref: `pendingAnchor: { x: number; y: number } | null`（再描画のきっかけにしない）
  - 公開する操作: `zoomIn()` / `zoomOut()` / `resetZoom()` / `zoomBy(direction, anchor)` / `consumeAnchor()`
- 起動時に `getStore()` から `contentZoom` を読み、`normalizeZoom` を通して state に入れる
  - アンマウント後に結果が届いた場合は捨てる。`useExternalEditor` と同じ `cancelled` フラグ方式を使う
- 保存: `zoomPercent` が変わってから300ms後に `store.set("contentZoom", value)` を呼ぶ（デバウンス）
  - 起動時に読み込んだ値をそのまま書き戻さないよう、読み込みが終わるまでは保存しない
- キーボード: `window` の `keydown` を購読する。`useTabs().activeTabPath` が `null` のときは何もしない
  - 拡大: `key` が `+` / `=` / `;` のいずれか、または `code === "NumpadAdd"`
  - 縮小: `key === "-"` または `code === "NumpadSubtract"`
  - リセット: `key === "0"` または `code === "Numpad0"`
  - `ctrlKey`（または `metaKey`）のときだけ判定し、該当したときだけ `preventDefault()`
- `App.tsx`: `<TabsProvider><ZoomProvider><AppShell/></ZoomProvider></TabsProvider>` の構成にする

**確認**: `npm run build`

## ステップ4: CSSと本文ペインへの倍率の適用

**ファイル**: `src/hooks/usePaneZoom.ts`（新規）、`src/components/TabPane.tsx`（変更）、`src/App.css`（変更）

- `App.css`: `.markdown-body` に `zoom: var(--content-zoom, 1);` を追加する
- `usePaneZoom(containerRef, isActive, hasContent)`
  - ref `appliedZoom`: このコンテナに最後に適用した倍率。未適用なら `null`
  - `useLayoutEffect`（依存: `zoomPercent`, `isActive`, `hasContent`）
    - `!isActive || !hasContent || !container` なら何もしない（非アクティブのタブには後で適用する。spec.md 11.4）
    - `appliedZoom === zoomPercent` なら、溜まっている基準点を `consumeAnchor()` で消して終わる
    - `appliedZoom === null`（初回）: 倍率を適用するだけで、スクロールは補正しない
    - それ以外: 基準点（`consumeAnchor()` の値、無ければ本文ペインの上端・横方向は中央）を使い、spec.md 11.4 の手順1〜3（基準要素の測定 → `--content-zoom` の設定 → `scrollTop` の補正）を行う
    - 最後に `appliedZoom = zoomPercent` とする
  - 基準要素の取得と `scrollTop` の補正は、小さな内部関数 `captureAnchor` / `restoreAnchor` に分ける（DOMに依存するのでテスト対象外）
- `TabPane.tsx`: `usePaneZoom(containerRef, isActive, !tab.loading && tab.content !== null)` を呼ぶ

**確認**: `npm run build`。倍率を手で変える手段はまだないので、ステップ5の後にまとめて確認する

## ステップ5: Ctrl+ホイールの受付

**ファイル**: `src/hooks/usePaneZoom.ts`（変更）

- `useEffect`（依存: `hasContent`）で `container.addEventListener("wheel", handler, { passive: false })` を登録し、cleanup で解除する
- handler の処理
  - `!event.ctrlKey` → 何もせず return（通常のスクロール）
  - `preventDefault()` する
  - `deltaMode !== 0`（行・ページ単位）→ 1イベントで1段階変える
  - `deltaMode === 0`（ピクセル単位）→ `deltaY` を ref に積算する
    - 積算値と符号が逆のイベントが来たら、積算値を0に戻してから足す
    - 絶対値が50以上になったら1段階変え、積算値を0に戻す
  - 倍率の変更は `zoomBy(deltaY < 0 ? 1 : -1, { x: event.clientX, y: event.clientY })` で行う

**確認**: `npm run tauri dev` で起動し、次を確かめる
- Ctrl+ホイールで本文だけが拡大・縮小し、目次とツールバーは変わらない
- カーソルの下の文章がほぼ同じ位置に残る
- 50%・300%で止まる
- Ctrl を押していないホイールは普通にスクロールする

## ステップ6: ツールバーの倍率表示

**ファイル**: `src/components/Toolbar.tsx`（変更）、`src/App.css`（変更）

- 検索欄（`.toolbar__search`）の直前に、`zoomPercent !== 100` のときだけ `<button className="toolbar__zoom-reset">{zoomPercent}%</button>` を表示する
  - `title="表示倍率（クリックで100%に戻す、Ctrl+0）"`、クリックで `resetZoom()`
- CSS: 既存の `.toolbar__icon-btn` に高さを合わせ、数字の幅でボタンが動かないよう `font-variant-numeric: tabular-nums` と `min-width` を指定する

**確認**: 実機で、倍率を変えると表示が出て、クリックすると100%に戻り表示が消えることを確かめる

## ステップ7: Word出力時の倍率の一時リセット

**ファイル**: `src/hooks/useWordExport.ts`（変更）

- `findTabContainer` で見つけたタブ要素の中の `.markdown-view` について、変換の前に次を記録する
  - `style.getPropertyValue("--content-zoom")`
  - `scrollTop`
- `--content-zoom` を `"1"` にしてから `convertMarkdownToDocx` を呼ぶ
- `finally` で元の値と `scrollTop` に戻す（spec.md 11.6）
- 倍率が100%のときは何もしない（余計な再レイアウトを避ける）

**確認**: 実機で次を確かめる
- Mermaid図と数式を含む文書を、200%表示のまま Word 形式で保存する
- 100%表示で保存したファイルと、Word上の図の大きさが同じになる
- 保存後に元の倍率とスクロール位置に戻る

## ステップ8: 総合確認とドキュメント更新

**実機での確認項目**（`npm run tauri dev`）

1. キーボード操作
   - `Ctrl` + `+` / `-` / `0` が効く
   - 日本語キーボードの `Ctrl` + `;` で拡大できる
   - テンキーの `+` / `-` / `0` でも効く
   - 検索欄にフォーカスがあるときも効く
2. ファイルを開いていない状態では、キーボードでもホイールでも倍率が変わらない
3. 全タブ共通の倍率
   - タブAで150%にすると、タブBに切り替えても150%になっている
   - タブBに切り替えたとき、タブBで見ていた位置が保たれている
   - 新しく開いたタブも150%で表示される
4. アプリを再起動しても倍率が残っている
5. ほかの機能が拡大中でも正しく動く
   - 目次クリックでのジャンプ
   - 目次のアクティブハイライト
   - 検索のハイライトと `Enter` によるマッチ間移動
   - Mermaid図・数式・画像・コードブロックが本文と一緒に拡大される
6. タッチパッドのピンチ操作で拡大・縮小でき、変化が速すぎない（タッチパッドがある環境の場合）
7. ステップ7の Word 出力の確認

**ドキュメント**
- `requirements.md` 8節（検証状況）に、確認できた項目と未確認の項目を追記する
- `README.md` に機能や操作の一覧があれば、ズーム操作を追記する

## リスクと対応

| リスク | 対応 |
| --- | --- |
| WebView2 が古く、CSS `zoom` の座標計算が古い仕様のまま（Chromium 128 より前）で、`getBoundingClientRect` やスクロール補正がずれる | ステップ5の実機確認で、基準点の保持がずれないかを最初に確認する。ずれる場合は、補正の計算に倍率を掛けるかどうかを切り替えて対応する |
| `elementFromPoint` が mark.js の `<mark>` などの小さな要素を返し、補正がわずかにずれる | 実用上の差は小さいので許容する。気になる場合は、基準要素を最も近いブロック要素（`p`, `li`, `pre` など）まで親をたどって選ぶ |
| Ctrl+ホイールで WebView2 自体のズームも動いてしまう | `zoomHotkeysEnabled` の既定値（`false`）で抑止されるはず。ステップ5で目次やツールバーの上でも試し、動いてしまう場合は `tauri.conf.json` に `false` を明記する |
