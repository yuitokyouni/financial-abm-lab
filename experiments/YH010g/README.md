# YH010-g — 議決権行使ガバナンス

実験固有のインストール可能パッケージ `yh010g`、テスト、仕様、文書、検証入力をここに集約する。
**Pythonのimport名 `yh010g` は変更しない。** 共有エンジンだけを [`agora_engine`](../../packages/agora_engine/) から使う。

## 構成

```text
YH010g/
  pyproject.toml       # root uv workspaceに明示登録
  yh010g/              # この実験固有の実装
  tests/               # parser / policy / simulation 等
  specs/HANDOFF.md     # 仕様
  docs/                # 先行研究・方法・作業記録
  data/fixtures/       # Git管理する検証入力
  data/raw/            # ローカル原本（Git管理外）
  data/processed/      # 実行生成物（Git管理外）
```

## 実行

```sh
# リポジトリルートから
uv sync --extra dev
uv run pytest experiments/YH010g/tests
uv run python -m yh010g.validate_policy
```

検証コマンドは同梱の手動フラグ付き検証CSVを読む。APIキーがないまま財務属性を推測することはしない。
データ・出力の既定パスは `yh010g.paths` に集約し、カレントディレクトリに依存させない。
ローカルの旧 `data/raw/yh010g/` と `data/processed/yh010g/` は、それぞれ本ディレクトリの
`data/raw/` と `data/processed/` へ移す。Git管理外の原本は今回のリモート作業では移動していない。
新パスに原本がない場合、実データを使う16件のparserテストは従来どおりスキップする。

[HANDOFF](specs/HANDOFF.md) / [調査・作業記録](docs/) / [配置台帳](experiment.toml) / [実験一覧](../README.md)
