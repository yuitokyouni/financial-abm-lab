# Finding 0001 — 観測チャネル脱共役による機構識別の構成的実例(再設計 P1)

**Status**: 実証済(2026-06-13、`toy/channel_band.py` + `experiments/runners/band_demo.py`、
test で核を pin)。再設計 P1 の起点。

## 背景: 二本の角(旧 toy の構造的詰み)

「異機構を SF-等価に似せて介入で分ける」旧 toy(T/H)は構造的に詰む(Issue #11):

- **PRISM の角**: モデルが似すぎ(同一コア方程式のパラメータ変種、PRISM FATAL-3)→ 介入応答が
  同じ(delta ~10⁻⁴)→ 弁別力なし。
- **toy の角**: genuinely 異機構(chartist vs herding)にすると → 介入を見るまでもなく観測で
  分かれる(held-out CNN ~0.9、joint/敵対 calibration の2法で一貫)。

介入弁別の価値は「**観測等価 ∧ 介入分離**」の細い帯にしか棲まない。この finding はその帯の
**構成的実例**を、実在の政策介入(batch auction)で作って見せる。

## 鍵: 単一資産市場では価格と注文流が同一信号

超過需要市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` では:

> **return_t = λ·ED_t/N = λ·(order-flow)_t** ―― 価格 return チャネルと注文流チャネルは厳密に
> 同一信号(実測 corr = 1.000)。

→ **価格を読むモデル A** と **注文流を読むモデル B** は、連続市場では**観測上 identical**
(同一 seed で bit 同一の軌道、`test_channel_band.py::test_continuous_A_equals_B_bitwise`)。
歴史データ・分類器でいくら調べても区別できない。これが「観測等価」の角を回避。

## 介入: batch auction が両チャネルを脱共役

batch auction(interval N 期ごとに一括清算)では、**バッチ内は価格 flat(return=0)だが
注文流は毎期蓄積**する。よって:
- **A(価格 reader)**: バッチ内の flat な価格を見て沈黙、境界の跳びにだけ反応。
- **B(注文流 reader)**: 注文流を毎期見て活動。

→ 両機構が**別挙動**になる(`test_batch_decouples_A_and_B`)。これが「介入分離」の角を回避。

## 結果(`band_demo`、M=60、CNN/LR で識別精度)

| regime | LR(SF1-4) | CNN(生系列) | 解釈 |
|---|---|---|---|
| 連続市場(batch=1) | 0.33 | **0.46** | A=B、**歴史データで区別不能** |
| batch auction(batch=10) | 0.83 | **0.94** | batch 政策が**脱共役して鋭く識別** |

> **連続市場データでは原理的に区別不能なモデル(price-reader vs orderflow-reader)を、
> batch auction という政策改革が CNN=0.94 で識別する。**

二本の角を両方回避した構成的実例。介入は合成の人工軸でなく**実在の市場設計政策**
(batch vs continuous = Budish 以来の論争、JPX/BoJ の関心、P2 の核)。

## P2 / BoJ への接続(再設計 P1 の論文線)

- **理念は保たれる**: 「従来モデルが出来なかった切り分けを介入で行う」。だが弁別対象を
  「異機構の SF-等価ペア(詰み)」から「**観測等価だが reach の違う機構ペア × 脱共役政策**」へ
  sharpening。
- **主張(目標文)案**: 「市場が *価格* に反応する機構で動くか *注文流/板* に反応する機構で動くかは、
  連続市場の歴史データからは識別不能だが、batch auction(または tick/speed-bump)への応答が識別する。
  ゆえに政策改革は、歴史データでは決まらないモデル選択を決める識別実験になる。」
- **P2 連結**: P2 は batch vs continuous × 学習 MM × 実 venue(BCS ES–SPY)。本 P1 はその
  identification 面を担う(「P2 の介入が機構を識別する」)。BoJ: JPX の batch/tick 政策に直結。

## 既知の限界 / BoJ-grade への次手

1. **styl化**: 単一資産・離散行動・閾値モメンタム。order book(板厚・スプレッド)へ richening
   すれば price/flow/depth の3チャネル以上が立ち、より現実的な reach-twin が組める(P2 infra)。
2. **batch 下で A が degenerate(沈黙)気味**: 両機構が active なまま分岐する設計に詰める
   (例: A も境界跳びに反応する momentum、observation lag 等)。
3. **実データ照合が未**: 「どちらが現実か」は、実 batch/tick 改革(JPX 2014 等)の前後で
   どちらの予測が当たるかで決める(PRISM の category-mismatch を回避するため microstructure 量を
   intraday で測る)。これが essence(政策モデル選択)の本番。
4. 検出力設計・null・事前登録は本実装が GO を出した後に paper-grade で切る。

## 関連
- 実装: `toy/channel_band.py`、`experiments/runners/band_demo.py`、`tests/unit/test_channel_band.py`
- 経緯: Issue #11(二本の角の確定)、`docs/program_claims_v1.md`(P1/P2/P3)
