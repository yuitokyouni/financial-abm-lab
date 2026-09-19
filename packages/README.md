# 共通コード

ここには、特定の実験手順とは切り離して使うライブラリを置く。
「Python packageにできる」ことと「研究上の共通コードである」ことは別。
YH010-gはインストール可能なpackageのまま、実験側 `experiments/YH010g/` へ移した。

| パッケージ | 役割 |
|---|---|
| [abm_models](abm_models/) | 正準モデル・共通protocol。古典実験とatlasが同じ実装を使う |
| [stylized_facts](stylized_facts/) | リターン系列等の統計量 |
| [provenance](provenance/) | 来歴の記録 |
| [agora_engine](agora_engine/) | YH010/YH010-gで共有する意思決定行列・因子モデル・介入 |
| [fingerprint_atlas](fingerprint_atlas/) | モデル比較、文献・提案処理の再利用可能なツール |

共通コードは `experiments` をimportしない。実験固有のパラメータ、検証入力、プレレジ、図表は
該当する実験のディレクトリへ置く。共有モデルを変えたら全利用側の回帰テストを実行する。
[全体設計](../docs/architecture/repository-layout.md) / [実験一覧](../experiments/README.md)
