# Finding 0001 — 観測チャネルの分離による機構識別の構成例(再設計 P1)

**Status**: 実証済(2026-06-13、`toy/channel_band.py` + `experiments/runners/band_analyses.py`、
test で核を固定)。再設計 P1 の起点。

## 背景: 介入による識別が成立する条件(Issue #11)

介入応答で2モデルを識別するには、2モデルが観測データ上で区別不能(でなければ介入は不要)かつ介入
応答が異なる必要がある。この両立は一般には難しい:

- 同一方程式 `excess_demand = w_f·d_fund + w_c·d_chart + w_n·d_noise` のパラメータ変種どうしでは、
  介入応答の差が ~10⁻⁴ に縮退し識別できない(我々の予備的検討)。
- 機構を変えた2モデル(chartist vs herding)では、介入前に held-out の 1D-CNN が生価格系列から
  約 0.9 で区別する(joint/敵対 calibration の2法で一貫)。較正で要約統計を一致させても CNN は分離。

本 finding は両要件を同時に満たす例を、実在の政策介入(batch auction)で構成する。

## 鍵: 単一資産市場では価格と注文流が同一信号

超過需要市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` では:

> **return_t = λ·ED_t/N = λ·(order-flow)_t** ―― 価格 return チャネルと注文流チャネルは同一信号
> (実測 相関 1.000)。

→ 価格を読むモデル A と 注文流を読むモデル B は、連続市場では同一 seed で bit 同一の軌道を生み
(`test_channel_band.py::test_continuous_A_equals_B_bitwise`)、観測データ・分類器で区別できない。
これが要件(観測等価)を満たす。

## 介入: batch auction が両チャネルに異なる情報を与える

batch auction(interval N 期ごとに一括清算)では、バッチ内は価格が動かず(return=0)注文流のみ毎期
蓄積する。よって A はバッチ境界の価格変化にのみ反応し、B は注文流に毎期反応して、両者は異なる軌道を
生む(`test_batch_decouples_A_and_B`)。これが要件(介入応答の差)を満たす。

## 結果(`band_demo`、M=60、CNN/LR で識別精度)

| regime | LR(SF1-4) | CNN(生系列) | 解釈 |
|---|---|---|---|
| 連続市場(batch=1) | 0.33 | **0.46** | A=B、**歴史データで区別不能** |
| batch auction(batch=10) | 0.83 | **0.94** | batch 政策が**脱共役して鋭く識別** |

> **連続市場データでは原理的に区別不能なモデル(price-reader vs orderflow-reader)を、
> batch auction という政策改革が CNN=0.94 で識別する。**

介入は合成の人工軸ではなく実在の市場設計政策(batch vs continuous、Budish, Cramton & Shim 2015
以来の論点、JPX/BoJ の政策対象、P2 と共通)。

## P2 / BoJ への接続

- **当初の目的との関係**: 「従来モデルが区別できなかったものを介入で区別する」目的を保ち、対象を
  「異機構を要約統計で一致させたペア(CNN が分離する)」から「同じ軌道を生むが読むチャネルが異なる
  ペア × 両チャネルを分離する政策」に置き換えた。
- **主張案**: 「市場が価格に反応する機構で動くか注文流に反応する機構で動くかは、連続市場の歴史
  データからは区別できないが、batch auction(または tick/speed-bump)への応答が区別する。ゆえに
  政策改革は、歴史データでは決まらないモデルの選択を、改革後データで決める。」
- **P2 連結**: P2 は batch vs continuous × 学習マーケットメイカー × 実 venue(BCS ES–SPY)。本 P1 は
  同じ batch を、共謀耐性ではなくモデル識別の観点から扱う。JPX の batch/tick 政策に対応。

## 既知の限界 / 次の作業

1. 単一資産・離散行動・閾値モメンタムの簡略市場。order book(板厚・スプレッド)へ拡張すれば
   price/flow/depth の3つ以上のチャネルが立ち、より現実的な「同じ軌道・異なるチャネル」のペアを
   構成できる(P2 のインフラ)。
2. batch 下で A の発注が乏しくなる。両機構が発注を続けたまま分岐する設計(A も境界の価格変化に
   反応する momentum、観測遅延など)への精緻化。
3. 「どちらが現実か」は、実 batch/tick 改革(JPX 2014 等)の前後でどちらの予測が当たるかで決める。
   その際は介入が効果を与える microstructure 量を intraday で測る。
4. 検出力設計・帰無対照・事前登録は、識別の成立を確認した後に paper-grade で行う。

## 関連
- 実装: `toy/channel_band.py`、`experiments/runners/band_analyses.py`、`tests/unit/test_channel_band.py`
- 経緯: Issue #11、`docs/program_claims_v1.md`(P1/P2/P3)
