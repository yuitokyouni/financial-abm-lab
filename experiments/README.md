# 実験一覧

**実験は問い・条件・実行手順・評価・その証拠を所有し、共通パッケージは再利用する実装を所有する。**
「独立」は共通コードの複製を意味しない。YHごとの文書・コードをここからたどれるようにする。

| ディレクトリ | 内容 | 配置上の区分 |
|---|---|---|
| [YH001](YH001/README.md) | Cont–Bouchaud | `simulation` |
| [YH002](YH002/README.md) | Lux–Marchesi | `simulation` |
| [YH003](YH003/README.md) | Minority Game | `simulation` |
| [YH004](YH004/README.md) | Grand Canonical Minority Game | `simulation` |
| [YH005](YH005/README.md) | Speculation Game / YH005_1 | `simulation` |
| [YH006](YH006/README.md) | SG on LOB（旧実装の保存） | `archive` |
| [YH007](YH007/README.md) | 共有予測・注文板・較正／介入 | `simulation` |
| [YH008](YH008/README.md) | LLM内部活性への介入 | `archive` |
| [YH009](YH009/README.md) | unwind-tape / 政策保有株解消 | `empirical` |
| [YH010](YH010/README.md) | agent-agora / 協調とモノカルチャー | `design` |
| [YH010g](YH010g/README.md) | 議決権行使ガバナンス | `empirical` |
| [YH012](YH012/README.md) | LOBcore単一注文インパクト | `simulation` |
| [fingerprint_atlas](fingerprint_atlas/README.md) | モデル比較・研究探索の実行記録 | `workflow` |

YH005_1はYH005の旧実験リンク、旧YH007はYH006_3のリンクで区別する。
YH011・YH013はこの整理の対象となったmainに実体がなかったため、新しい実験を捏造していない。
`archive` は現在のコードが `imported/` 側に保存されていること、`design` はこの場所に実験ドライバがないことを表す。
**この区分は研究成果の合否や完成度の評価ではない。**

## 新規実験

[`_template/README.md`](_template/README.md)に従い、まず固有ディレクトリとREADME、`experiment.toml`を作る。
必要に応じて `configs/`, `docs/`, `specs/`, `tests/`, `data/`, `reports/` を追加する。
空フォルダを一律に作る必要はない。生成物は `runs/<run_id>/`、採用した証拠は来歴付きで `reports/` に置く。

## 互換性

`classical/baseline.py` と `speculation_game/baseline.py` は旧コマンドの小さな互換入口。
実装の正本ではなく、新しい実験コードを置かない。ルート `unwind-tape` もYH009への互換リンクのみ。

[配置の設計](../docs/architecture/repository-layout.md) / [移動対応表](../docs/architecture/migration-2026-09-19.md)
