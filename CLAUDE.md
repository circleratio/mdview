# mdview

GUI版（`gui/`）と TUI版（`tui/`）は互いに独立している。両版の共通の決まりは `doc/common.md`、各版の詳細は各ディレクトリの README と `doc/` を参照。

## TUI版のポータブル版

- `tui/portable/mdview-tui.py` は `tui/src/mdview_tui/` から生成した1ファイル版。**直接編集しない**
- `tui/src/mdview_tui/`、`tui/pyproject.toml` の `dependencies`、`__version__` のいずれかを変更したら、`tui/` で `python3 tools/bundle.py` を実行してポータブル版を作り直し、ソースの変更と同じコミットに含める
- 作り直したあとは `tui/` でテストを実行する: `PYTHONPATH=src python3 -m unittest discover -s tests -t .`（ポータブル版が古いと `tests/test_portable.py` が失敗する）
- モジュールをまたいで同じ最上位の名前を定義したり、パッケージ内の import に `as` の別名を付けたりすると生成が失敗する。その場合は名前を変えて解消する
- 手順の詳細は `tui/README.md`「src を変更したときの手順」、生成の規則は `tui/doc/spec.md` 6.1
