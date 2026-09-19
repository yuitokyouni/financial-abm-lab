# YH005 — Speculation Game / YH005_1

このディレクトリは **実験手順**を所有する。モデル本体は
[`packages/abm_models/abm_models/sg/`](../../packages/abm_models/abm_models/sg/) を利用し、複製しない。

## 実行

リポジトリルートで依存関係を `uv sync --extra dev` により同期する。

```sh
uv run python -m experiments.YH005.baseline --seed 777
```

[`baseline.py`](baseline.py) は既存baselineのパラメータ・乱数seed・測定方法を維持した実行入口。
結果は標準出力に表示される。これは軽量smoke専用コマンドではなく、既存の実験長で動く。
新しい実行のログ・設定・seed・commit・結果表は `runs/<run_id>/` にまとめる（Git管理外）。
採用する結果は由来を添えて `reports/` に保存する。今回の整理では再実験や結果の再評価は行わない。

## 旧実験・保存済み結果

- [YH005](../../imported/speculation-game-info/experiments/YH005/) — 履歴と保存済み結果を保持。書き換えない。
- [YH005_1](../../imported/speculation-game-info/experiments/YH005_1/) — 履歴と保存済み結果を保持。書き換えない。

[モデル抽出時のparity記録](docs/backbone_parity.md)。YH005_1は旧実験を上記リンクで区別して保存する。

[配置台帳](experiment.toml) / [実験一覧](../README.md)
