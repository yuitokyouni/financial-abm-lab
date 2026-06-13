# Finding 0002 — 板での価格/注文流チャネルの脱共役（channel_band 罠の a priori ガード）

**Status**: probe 動作（`toy/orderbook.py`）。WP v2（`docs/working_paper_identification_obstacle_v0.md`）
§6 の order-book 検証の第一歩。

## なぜこの probe か

channel_band（単一資産 `p_{t+1}=p_t·exp(λ·ED_t/N)`）では return = λ·ED/N で価格変化と注文流が**同一
信号**（実測 corr 1.000）。価格を読む A と注文流を読む B は連続市場で bit 同一 ―― 異機構でなく同一
モデルの再パラメータ化だった（Finding 0001 撤回）。WP v2 §2.3 の言葉では、最強の O がレベル等価を
関数恒等に潰し、∂F も同一になった。

→ 板で M1（価格読み）と M2（注文流読み）が genuinely 異機構になりうるには、まず**価格変化と注文流が
脱共役**していなければならない。本 probe はそれだけを測る（full な機構識別の前の安価なガード）。

## 結果

最小 ZI 板（指値/成行/取消、Smith et al. 2003 系）で window 単位に (mid, net-flow, spread, depth) を測定:

| 量 | 値 |
|---|---|
| **corr(Δmid, net-flow)**（8 seed） | **0.329 ± 0.025** |
| spread mean | 2.39 |
| depth mean | 36.3 |
| mid std / Δmid std | 0.93 / 0.60 |

> **corr ≈ 0.33（channel_band は 1.000）。板は価格チャネルと注文流チャネルを脱共役する** ―― 成行が
> 最良気配の板厚内に収まる間は価格が動かないから。channel_band の罠（再パラメータ化）は回避された。
> 価格を読む機構と注文流を読む機構が「同一モデルの単位違い」でなく異機構になりうる前提条件that立つ。

corr は 0 でなく 0.33（共有分散 ~11%）。net フローは板厚を食い尽くせば価格を動かすので相関は残る。
要点は < 1、すなわち2チャネルが別物であること。

政策 θ=tick への応答（粗化で spread が広がる）:

| tick | spread | depth | corr |
|---|---|---|---|
| 1 | 2.39 | 36.3 | 0.307 |
| 2 | 2.65 | 356 | 0.268 |
| 4 | 4.42 | 316 | 0.219 |

spread は tick で単調に広がる（板は θ に応答）。corr は全 tick で < 1（ガード保持）。

## 既知の問題 / 次の作業

1. **depth の tick アーティファクト**: depth が tick=1→2 で 36→356 と 10x 跳ぶ。tick 丸めが少数 level に
   注文を集中させる artifact。corr ガードには影響しないが、**depth を O 成分（感度測定）に使う前に直す**
   （∂depth/∂tick that汚染される）。指値 offset を tick 単位で定義し直すなどが要る。
2. **M1/M2 機構の追加**: 価格モメンタム読み（M1）と注文流インバランス読み（M2）を ZI 背景に乗せ、
   両者の政策シフトベクトル S_k = [⟨o_j⟩(θ0±Δ) 差] を中心差分で測り、S_1≠S_2 と rank 条件（WP §5）を
   機械判定する。これが本番の識別実験。
3. **a priori rank チェック**: O={spread, depth, λ, …} で rank(∂g/∂θ)=m と
   rank[∂g/∂φ ; ∂²g/∂θ∂φ] > rank[∂g/∂φ]（WP §2.3）を、full 判定の前に数値ランク（SVD tolerance）で確認。
4. **probe の限界**: 最小 ZI 板。full §6 検証は WP §6 通り P2 のインフラ（板厚・学習 MM・実 venue）での
   構成を要する。本 probe は脱共役の前提条件の確認のみ。

## 関連
- 実装: `toy/orderbook.py`
- 撤回された前身: `docs/findings/0001-channel-decoupling-band.md`（単一資産、corr 1.000）
- 理論: `docs/working_paper_identification_obstacle_v0.md` §2.3（局所識別条件）・§5・§6
