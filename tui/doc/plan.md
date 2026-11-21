# 実装計画: フロントマター

対象: `doc/requirement.md`「フロントマター」／設計: `doc/spec.md` 3.18（あわせて 3.3・3.5・3.12・3.13・3.16）

（最初の実装（S1〜S10）の計画は、git の履歴を参照）

テストは `PYTHONPATH=src python3 -m unittest discover -s tests -t .` で実行する。各ステップの終わりで全件成功する状態を保つ。

## 依存関係

```
F1 (frontmatter) ─ F2 (parser / themes / render) ─ F3 (view / app) ─ F4 (docs) ─ F5 (手動確認) ─ F6 (最終確認)
```

- F1 は単独で実装・テストできる。F2 は F1 に、F3 は F2 に依存する
- F4 の README の更新は F1 の時点で書けるが、手順を実際に試してから確定させる

## F1. 切り出しと表示用データへの変換（frontmatter.py）

- やること: `pyproject.toml` に `PyYAML>=6.0` を追加。`split_front_matter`、`format_value`、`format_author`、`to_view` を spec 3.18 の通りに実装する。`tests/test_frontmatter.py` を追加する
- 完了条件: `tests/test_frontmatter.py`（spec 7章の `frontmatter` の項目）が成功する

## F2. 解析と描画（parser / themes / render）

- やること: `ParsedDocument` と `parse_document`、テーマに `meta` / `error` を追加（dark / light）、`render()` の `front_matter` 引数と `_front_matter()` ブロック
- 完了条件: `tests/test_render.py` に追加するフロントマターのテスト（spec 7章の `render`（フロントマター）の項目）と既存のテストが成功する

## F3. 表示への組み込み（view / app）

- やること: `MarkdownView.set_tokens` を `set_document(parsed, line)` に置き換え、`MdviewApp._show` から `parse_document` の結果を渡す
- 完了条件: `tests/test_app.py` に追加するテスト（フロントマター付きの文書を開くと題名が表示され、目次に題名が出ない／`/` で題名を検索できる／ファイルを書き換えると題名の変更が反映される）と既存のテストが成功する

## F4. ドキュメント

- やること: `README.md` の機能一覧・必要環境（PyYAML、Debian / Ubuntu の `python3-yaml`）を更新する。`doc/common.md` にフロントマターの共通の決まりを加え、7章の差異1を消す
- 完了条件: README の手順どおりに依存を入れて起動できる

## F5. 手動動作確認

```console
$ cd tui
$ export PYTHONPATH=src
$ cat > /tmp/fm.md <<'MD'
---
title: 設計メモ
author: [山田 太郎, 佐藤 花子]
date: 2026-10-08
version: 1.10
tags: [md, viewer]
---

# はじめに

本文。

---

区切りの後。
MD

# 表示例（doc/requirement.md「フロントマターの表示例」）と一致すること。t で目次に「はじめに」だけが出ること、/設計 で題名が一致すること
$ python3 -m mdview_tui /tmp/fm.md

# 別端末で title を書き換えて自動再読込で反映されること
$ sed -i 's/設計メモ/設計メモ v2/' /tmp/fm.md

# 標準入力
$ python3 -m mdview_tui < /tmp/fm.md

# 構文エラー: 「フロントマターを解釈できませんでした」と元の文字列が表示され、本文は表示されること
$ printf -- '---\ntitle: [oops\n---\n\n# Body\n' | python3 -m mdview_tui

# 閉じの行が無い: これまで通り水平線として表示されること
$ printf -- '---\ntitle: x\n\n# Body\n' | python3 -m mdview_tui
```

- 完了条件: 表示が `doc/requirement.md` の表示例・各項目と一致する。ライト／ダークの両方で読める

## F6. 最終確認

- やること: テスト全件の実行、`doc/requirement.md`「フロントマター」の各項目と実装の突き合わせ、`__pycache__` などの副産物の削除
- 完了条件: テストが全件成功し、要求仕様に未対応の項目がない
