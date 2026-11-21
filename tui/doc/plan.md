# 実装計画: ポータブル版

対象: `doc/requirement.md`「ポータブル版」／設計: `doc/spec.md` 6.1（あわせて 2章・7章）

（これまでの計画（最初の実装 S1〜S10、フロントマター F1〜F6）は、git の履歴を参照）

テストは `PYTHONPATH=src python3 -m unittest discover -s tests -t .` で実行する。各ステップの終わりで全件成功する状態を保つ。

## 依存関係

```
P1 (bundle.py) ─ P2 (生成・同梱) ─ P3 (test_portable) ─ P4 (docs) ─ P5 (手動確認) ─ P6 (最終確認)
```

- P1 で生成の規則を作り、P2 でその結果をリポジトリに入れる。P3 のテストは同梱したファイルを前提にする
- P4 の README の手順は P5 で実際に試してから確定させる

## P1. 生成スクリプト（tools/bundle.py）

- やること: spec 6.1 の規則どおりに `bundle()` と `main()`（`--check` 付き）を実装する。依存関係は `ast` でパッケージ内の import を読み取って決める
- 完了条件: `python3 tools/bundle.py` が成功し、生成物が `compile()` を通る。モジュール間で名前が重なるソースを与えると失敗する

## P2. ポータブル版の生成と同梱

- やること: `portable/mdview-tui.py` を生成し、git で実行権限を付けて追加する
- 完了条件: `python3 portable/mdview-tui.py --version` が `mdview-tui 0.1.0` を出す。`python3 tools/bundle.py --check` が 0 を返す

## P3. テスト（tests/test_portable.py）

- やること: spec 7章の `portable` の項目のテストを追加する
- 完了条件: 追加したテストと既存のテストが全件成功する。`src/` のどれかのモジュールを書き換えて再生成しないと、食い違いのテストが失敗する

## P4. ドキュメント

- やること: `tui/README.md` にポータブル版の使いかたと再生成の手順（開発者向け）を書く。リポジトリ全体の `README.md` のディレクトリ構成にも載せる
- 完了条件: README の手順どおりに実行できる

## P5. 手動動作確認

```console
$ cd tui
$ unset PYTHONPATH

# 別のディレクトリから起動できること。表示・キー操作がインストール版と同じであること
$ (cd /tmp && python3 "$OLDPWD/portable/mdview-tui.py" "$OLDPWD/README.md")

# 直接実行
$ ./portable/mdview-tui.py --theme light doc/spec.md

# 標準入力
$ cat README.md | python3 portable/mdview-tui.py

# バージョン・異常系（終了コードとメッセージがインストール版と同じこと）
$ python3 portable/mdview-tui.py --version
mdview-tui 0.1.0
$ python3 portable/mdview-tui.py nofile.md; echo $?
mdview-tui: nofile.md: No such file or directory
1
$ python3 portable/mdview-tui.py </dev/tty; echo $?
usage: mdview-tui [-h] [-V] [--theme {dark,light}] [--no-watch] [FILE]
mdview-tui: error: no input (specify FILE or pipe to stdin)
2

# 再生成と食い違いの検出
$ python3 tools/bundle.py --check; echo $?
0
```

- 完了条件: 出力が `doc/requirement.md` の使用例と一致する

## P6. 最終確認

- やること: テスト全件の実行、`doc/requirement.md`「ポータブル版」の各項目と実装の突き合わせ、`__pycache__` などの副産物の削除
- 完了条件: テストが全件成功し、要求仕様に未対応の項目がない
