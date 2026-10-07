# 実装計画: フロントマター

対象: requirements.md 3.12 ／ 設計: spec.md 12章

（前回の「表示の拡大・縮小（ズーム）」の実装計画は、git の履歴を参照）

各ステップの終わりで `npm run build`（型チェックを含む）と `npm run test` が通る状態を保つ。ステップごとに1コミットを目安とする。

## ステップ1: 切り出しと表示用データへの変換（純粋関数）とテスト

**ファイル**: `package.json`（`yaml` を追加）、`src/lib/frontMatter.ts`（新規）、`src/lib/frontMatter.test.ts`（新規）

- `npm install yaml`
- `parseFrontMatter(content)`、`toFrontMatterView(data)`、`formatValue(value)` を spec.md 12.2・12.3 の通りに実装する
- テストケース
  - フロントマター無し → `kind: "none"`、本文は元のまま
  - 1行目が `---` でも閉じの行が無い → `kind: "none"`
  - 閉じが `---` / `...` のどちらでも切り出せる
  - CRLF の改行、先頭の BOM、`---` の末尾の空白
  - 本文の途中にある `---` は本文に残る
  - `date: 2026-10-08`、`version: 1.10` が書かれた通りの文字列になる
  - 空のフロントマター → `kind: "ok"`、`data: {}`、本文から除去される
  - YAML の構文エラー → `kind: "error"`、`raw` が元の文字列
  - 最上位が配列・文字列 → `kind: "error"`
  - `toFrontMatterView`
    - title / author / date の取り出し
    - author が配列なら「、」でつなぐ
    - 書かれていない項目は含めない
    - その他の項目は書かれた順に並ぶ
    - 配列・入れ子のオブジェクト・空の値（`key:`）の文字列化

**確認**: `npm run test`

## ステップ2: 画面表示

**ファイル**: `src/components/FrontMatterHeader.tsx`（新規）、`src/components/MarkdownView.tsx`（変更）、`src/components/TabPane.tsx`（変更）、`src/App.css`（変更）

- `TabPane` で `parseFrontMatter(tab.content)` を `useMemo` で計算する
  - `MarkdownView` に `content={parsed.body}` と `frontMatter={parsed}` を渡す
  - `useHeadings`・`useTabSearchSync` は今のまま DOM を参照するので変更しない
- `FrontMatterHeader` を spec.md 12.4 の HTML 構造で実装する（`kind: "ok"` と `kind: "error"` の2通り）
  - 題名には `h1` を使わない
- `MarkdownView` の `<article>` の中、`ReactMarkdown` の前に `FrontMatterHeader` を置く
- CSS
  - 題名は `.markdown-body h1` と同じ大きさ・太さにする
  - byline は小さめで控えめな色にする
  - その他の項目は2列の grid にし、長い値は折り返す
  - エラー表示を作る
  - 区切り線を入れる
  - ダークモードの配色も用意する

**確認**: 実機で、title / author / date / その他の項目 / エラーの各パターンのファイルを開き、表示を確かめる。あわせて次も確かめる
- 目次に題名が出ない
- 検索で題名・項目の文字もハイライトされる
- ズームで一緒に拡大される

## ステップ3: Word 出力

**ファイル**: `src/lib/docxExport.ts`（変更）

- `convertMarkdownToDocx` の中で `parseFrontMatter` を呼び、本文（`body`）だけを AST の解析に渡す
- title がある場合は、文書タイトルの段落を先頭に出力し、`titleConsumed: true` で変換を始める
- byline がある場合は、その次に本文の書式で1段落出力する
- `new Document({ title, creator })` で文書のプロパティを設定する

**確認**: `convertMarkdownToDocx` を実機の WebView から直接呼び、出力された docx を確かめる
- `word/document.xml`: 先頭が Title スタイルの題名と byline になっている。本文の `#` 見出しが Heading1 になっている。フロントマターの文字列が混入していない
- `docProps/core.xml`: タイトル・作成者が入っている
- フロントマターが無いファイルは、従来通り本文最初の `#` 見出しが Title になる

## ステップ4: 総合確認とドキュメント更新

- 既存のファイル（本プロジェクトの `requirements.md`・`spec.md` など、フロントマターの無いもの）の表示が変わらないことを確かめる
- 自動リロードでフロントマターを書き換えたときに、表示が更新されることを確かめる
- `requirements.md` 8節（検証状況）に、確認できた項目と未確認の項目を追記する

## リスクと対応

| リスク | 対応 |
| --- | --- |
| 1行目に水平線 `---` を書いた既存の文書が、フロントマターとして解釈される | 一般的なツールと同じ判定のため許容する（spec.md 12.2「既知の制限」）。解釈できない場合もエラー表示になるだけで、本文は表示される |
| `yaml` パッケージの追加でバンドルが大きくなる | 数十KB程度で、Mermaid などと比べて小さいため許容する。ビルドの出力サイズを確認する |
