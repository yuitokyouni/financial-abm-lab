# （撤回・記録）バッチオークションによるモデル弁別 —— v0、機構識別の主張は不成立

> **撤回（2026-06-13）**: 本稿 v0 の中心主張（バッチが価格を読む機構と注文流を読む機構を識別する）は
> 成立しない。本ファイルは記録として残すのみで、主張は `docs/working_paper_identification_obstacle_v0.md`
> （観測等価の観測量クラス依存性、v1）に置き換える。

## なぜ不成立か

単一資産の超過需要市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` では return = λ·ED/N で価格チャネルと注文流チャネルが
同一信号となる。価格を読むモデル A と注文流を読むモデル B は連続市場で **bit 同一**の出力を生む。これは
異なる2機構の equifinality ではなく、同一モメンタム関数の入力単位の違い（再パラメータ化）である。よって
バッチ下の「分離」は機構識別ではなく、単一モデルのパラメータ（注文流をどの時間解像度で読むか）の可識別性。
詳細は `working_paper_identification_obstacle_v0.md` §3.1。

## 残る記録（数値）

`toy/channel_band.py` + `experiments/runners/band_analyses.py` で測った数値（連続で区別不能、バッチで分離）
は、パラメータ可識別性の例としては正しい（機構識別ではない）。実装と test は残す（`channel_band` は
作用点クラスでの検証（v1 §6）の出発点として、order book 拡張の土台になる）。懸念として、バッチ強度 dose-
response の CNN 非単調（N=20 で CNN=1.00・LR=0.55）は、CNN がバッチ構造のアーティファクトを読んでいる
可能性があり、未検証（v1 でも機構識別の証拠としては用いない）。

## 関連
- 置換後の主張: `docs/working_paper_identification_obstacle_v0.md`（v1）。
- 実装記録: `docs/findings/0001-channel-decoupling-band.md`。
