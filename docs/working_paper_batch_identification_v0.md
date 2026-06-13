# 市場設計改革によるトレーダー行動の識別 —— バッチオークションをモデル弁別実験として

> **撤回（2026-06-13）**: 本稿の中心主張（バッチが価格を読む機構と注文流を読む機構を識別する）は
> 成立しない。単一資産市場では return = λ·order-flow で両者が同一信号となり、価格を読むモデル A と
> 注文流を読むモデル B は連続市場で bit 同一の出力を生む。これは異なる2機構の equifinality ではなく、
> 同一モメンタム関数の入力単位の違い（再パラメータ化）である。バッチ下の「分離」は機構識別ではなく
> パラメータ可識別性。詳細と、3例（PRISM/T-H/channel-band）に共通する障害の分析は
> `docs/working_paper_identification_obstacle_v0.md` に置き換える。以下は記録として残す。

### Identifying Trader Behavior through Market-Design Reform: The Batch Auction as a Model-Discrimination Experiment

**ワーキングペーパー草稿 v0（2026-06-13）**。投稿候補: 日本銀行 IMES / JPX ワーキングペーパー / JEDC。
実装と再現コードは `toy/channel_band.py`・`experiments/runners/band_analyses.py`、記録は
`docs/findings/0001-channel-decoupling-band.md`。

---

## Abstract

Agent-based models (ABMs) are used to evaluate market-design policies such as tick-size changes
and frequent batch auctions. When several ABMs are calibrated to the same historical data and
fit it equally well, but predict different outcomes under a policy intervention, historical data
cannot determine which model to trust. This paper shows when an intervention can resolve such an
ambiguity. Discriminating two models by their intervention response requires that the two models
be indistinguishable in observational data (otherwise the intervention is unnecessary) and that
they respond differently to the intervention; we document, from our own exploratory experiments,
that these two requirements are in tension. We then construct a case where both hold. In a
single-asset excess-demand market the log return equals λ times the aggregate order flow
(return = λ × order flow, measured correlation 1.000), so a trader who reads the price channel
and a trader who reads the order-flow channel produce bit-identical market paths in a continuous
market and cannot be distinguished by any classifier. A batch auction holds the price fixed
within each batch while order flow accumulates, so the two channels carry different information,
and the two traders produce different market paths. The reform thus determines which channel
drives the market — a quantity that continuous-market history leaves undetermined. We report this
for (i) price- vs order-flow-reading traders, (ii) learning vs fixed-rule traders, and (iii) the
choice of measured quantities (microstructure vs return-distribution), and state the implications
for JPX/BoJ market-design decisions.

---

## 1. はじめに

エージェント型モデル（ABM）は、tick size 変更・frequent batch auction・speed bump などの市場設計
政策の評価に、JPX・日銀を含む各国当局で用いられてきた。ABM を政策に使う際に生じる問題は識別
（identification）である:

> 同じ歴史データに較正され、歴史データへの当てはまりが同程度に良い複数の ABM が、政策介入下では
> 異なる結果を予測する。どのモデルを採るかで政策結論が変わるが、歴史データはどれが正しいかを
> 決められない。

本稿は、この場合に政策介入そのものがモデルを識別しうる条件を示し、その条件を満たす具体例を、実在の
市場設計政策である batch auction（一括清算オークション）について構成する。batch auction は
Budish, Cramton & Shim (2015) 以来の市場設計の論点であり、JPX の立会方式・tick 政策に直接対応する。

## 2. 介入による識別が成立する条件

2モデルを介入応答で識別するには、次の両方が必要である:

- (a) 2モデルが**観測データ上で区別不能**であること。区別可能なら、介入を待たず観測だけで選別でき、
  介入は不要になる。
- (b) 2モデルが**介入下で異なる応答**を示すこと。

この2要件は両立しにくい。観測等価は2モデルが似ていることを要するが、似たモデルは介入応答も似る。
介入応答の差は2モデルが異なることを要するが、異なるモデルは観測データ上でも分離される。我々の予備的
実験は両側を示す:

- 同一方程式 `excess_demand = w_f·d_fund + w_c·d_chart + w_n·d_noise` のパラメータ変種どうしでは、
  tick/取引税介入下の応答差が ~10⁻⁴ に縮退し、識別できなかった。
- 機構を変えた2モデル（トレンド追随・群衆模倣）では、介入を加える前に、生の価格系列を入力とする
  1D-CNN が約 0.9 の精度で2モデルを区別した。較正で要約統計（GARCH persistence・尖度・自己相関）を
  一致させても、CNN は分離した。

したがって介入による識別は、(a) と (b) を同時に満たすモデルペアに限られる。以下はその一例を構成する。

## 3. 価格チャネルと注文流チャネルの共線性、および batch auction による分離

### 3.1 連続市場では両チャネルが同一信号

単一資産の超過需要市場 `p_{t+1} = p_t · exp(λ · ED_t / N)` では、対数 return と集約注文流が

> **return_t = λ · ED_t / N = λ · (order-flow)_t**

と厳密に比例する（数値実測で相関 1.000）。よって:

- **価格チャネルを読むトレーダー A** と **注文流チャネルを読むトレーダー B** は、連続市場では同一の
  正規化シグナルを見る（モメンタムは尺度不変）。
- 同一 seed で bit 同一の市場軌道を生む（`test_channel_band.py` で固定）。観測データ・分類器では
  区別できない。これが §2 の要件 (a) を満たす。

### 3.2 batch auction が両チャネルに異なる情報を与える

batch auction（interval N 期ごとに注文を集約し一括清算）では、バッチ内は価格が動かず（return = 0）、
注文流のみが毎期蓄積する。よって:

- **A（価格を読む）**: バッチ内の動かない価格を見て発注せず、バッチ境界の価格変化にのみ反応する。
- **B（注文流を読む）**: 注文流を毎期見て発注を続ける。

両者は異なる市場軌道を生む。これが §2 の要件 (b) を満たす。連続では同一・batch では分岐するため、
batch auction の有無が A と B を識別する。

## 4. 三つの分析

すべて `toy/channel_band.py`（外部依存なし・ベクトル化・決定論）上で実施。識別精度は、SF1-4 要約統計
を入力とするロジスティック回帰（LR）と、生 return 系列を入力とする 1D-CNN の 5-fold CV accuracy
（0.5 = 区別不能、1.0 = 完全識別）。各条件 M = 60 runs。

### 4.1 案1 —— バッチ強度と識別精度（中核）

価格を読む A vs 注文流を読む B を、batch interval N を変えて識別:

| batch interval N | LR (SF1-4) | CNN (生系列) | |
|---|---|---|---|
| 1（連続=政策なし） | 0.38 | **0.46** | 区別不能 |
| 2 | 0.94 | **0.94** | 2期集約で識別 |
| 5 | 0.93 | 0.95 | |
| 10 | 0.87 | 0.94 | |
| 20 | 0.55 | **1.00** | |
| 50 | 0.98 | **1.00** | 完全識別 |

連続（N=1）では区別不能なモデルが、2期集約という最小のバッチでも CNN=0.94 で識別でき、N≥20 で完全
識別に達する。

> 政策含意: 市場が価格に反応するトレーダーで動くか注文流に反応するトレーダーで動くかは、歴史データ
> では決まらないが、batch auction への応答が一意に決める。

### 4.2 案2 —— 学習トレーダー vs 固定ルールトレーダー

固定ルール（価格チャネルに固定）vs 適応型（直近で |momentum| の大きいチャネルを各自選ぶ最小学習則）:

| batch interval N | LR | CNN | |
|---|---|---|---|
| 1（連続） | 0.40 | **0.47** | 区別不能 |
| 10 | 0.83 | 0.94 | 分岐 |
| 20 | 0.56 | **1.00** | 完全識別 |

連続市場では両チャネルが同一なので、適応型は選ぶ対象がなく固定型と同じ軌道を生み、区別不能になる。
batch 下では適応型が注文流チャネルへ移り、固定型と分岐する。

> 政策含意: トレーダーが学習するか固定ルールかは、平時データからは区別できないが、batch 改革後の
> データでは区別できる。アルゴ取引の学習化が市場設計改革の効果を変えるかという日銀・JPX の論点に、
> 区別の手段を与える。

### 4.3 案3 —— microstructure 量で測るか return 分布で測るか

我々の予備的検討では、tick/取引税という microstructure 介入の効果を return-distribution 量
（GARCH persistence・尖度・歪度・自己相関）で測ると、有効な自然実験（JPX 2014 の tick 引き下げ、
treatment 40 + control 20 銘柄、12ヶ月、yfinance 日次）でも全6量の 95% 信頼区間がゼロを跨ぎ、有意な
効果を検出できなかった。tick 変更の効果は spread・depth・price impact という microstructure 量に
現れ（Aquilina, Budish & O'Neill 2022、Comerton-Forde, Gregoire & Zhong 2019 が実測）、日次 return
分布にはほとんど現れないためである。

本案は、注文流の microstructure 量（流れの標準偏差・自己相関・尖度）が return 量より介入に敏感かを
toy で測った:

| batch interval N | return 量 | microstructure 量 |
|---|---|---|
| 1（連続） | 0.34 | 0.40 |
| 2 | 0.95 | 0.95 |
| 5 | 0.96 | **0.97** |
| 10 | 0.82 | **0.88** |

microstructure 量は return 量に対し一貫して同等以上、弱い介入（N=10）で僅かに優位（0.88 vs 0.82）。
ただし本 toy のバッチ介入は return 分布も大きく動かすため（案1 の通り A/B が return で分岐する）、
return 量で効果が出ないという上記の日次データの状況は toy では再現しない。本案の根拠は toy ではなく、
(i) 上記の日次データでの非検出と (ii) microstructure 文献にある。toy での検証には order book
（spread・depth）を持つシミュレータ（P2 のインフラ）が要る。3案中、toy 上の検証力は本案が最も弱い。

## 5. 政策的含意（BoJ / JPX）

1. 市場設計改革は、市場に副作用を与える介入であると同時に、改革前データでは区別できないモデルの量を、
   改革後データで区別可能にする。改革の事前評価そのものに、改革後の観測でモデルを検証する手順が
   付随する。
2. JPX は tick size・立会方式の評価に人工市場 ABM を用いてきた。本枠組みは、複数 ABM のうちどれを
   採るかを、改革の前後データで決める手順を与える。
3. ABM による政策助言は、歴史データでは決まらない行動仮定（価格を読むか注文流を読むか、学習するか
   固定か）に依存し、改革効果の符号がこの仮定で反転しうる。反転が起きるパラメータ範囲を事前に
   特定することが、政策助言の信頼性に資する。

## 6. 本研究プログラムとの接続

- **P2（共謀×市場設計、`ABM-Microstructure`）**: P2 は batch vs continuous × 学習マーケットメイカー ×
  実 venue（BCS ES–SPY）較正で、アルゴリズム共謀の移植可能性を検証する。本稿（P1）は同じ batch という
  政策を、共謀耐性ではなくモデル識別の観点から扱う。両者は batch auction という共通の政策レバーで
  接続する。
- **当初の目的との関係**: 「従来モデルが区別できなかったものを介入で区別する」という目的を保ち、対象を
  「異機構を要約統計で一致させたペア（§2 の通り CNN が分離する）」から「同じ市場軌道を生むが異なる
  チャネルを読むペア × 両チャネルを分離する政策」に置き換えた。

## 7. 限界と次の作業

1. 単一資産・離散行動・閾値モメンタムの簡略市場。order book（価格・注文流・板厚の3つ以上のチャネル）
   へ拡張すれば、より現実的な「同じ軌道・異なるチャネル」のペアを構成できる（P2 のインフラ）。
2. batch 下で固定型 A の発注が乏しくなる。両機構が発注を続けたまま分岐する設計（境界の価格変化に
   反応する momentum、観測遅延など）への精緻化が要る。
3. 「どちらが現実か」は、実在の batch/tick 改革（JPX 2014 等）の前後で、どちらのモデルの予測が当たるか
   で決める。その際は §4.3 の通り、介入が効果を与える microstructure 量を intraday（J-Quants 等）で
   測る。
4. 本草稿は探索的。識別が成立すると確認した後、検出力設計・帰無対照・縮退規則を OSF に事前登録する
   （プログラム共通要件）。

## 8. 結論

ABM を市場設計政策に用いる際、複数モデルが歴史データへの当てはまりで区別できず政策予測のみ異なると、
歴史データではモデルを選べない。介入応答でこれを選ぶには、2モデルが観測等価かつ介入応答が異なる必要が
あり、この両立は一般には難しい。単一資産市場では価格と注文流が同一信号（return = λ × order flow）で
あるため、同じ市場軌道を生むが読むチャネルが異なる2モデルが存在し、batch auction が両チャネルに
異なる情報を与えて両者を識別する。よって batch auction 改革は、価格を読むか注文流を読むか・学習するか
固定かといった、歴史データでは決まらない行動を、改革後データで区別可能にする。これは JPX/日銀の市場
設計政策に直接の含意を持つ。

---

*再現*: `uv run python -m experiments.runners.band_analyses`（3案の数値）。各条件 M=60、seed 固定で
決定論的に再現可能。
