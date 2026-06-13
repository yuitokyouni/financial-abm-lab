# 観測等価の観測量クラス依存性 —— ABM 機構識別は「何を観測量とするか」で決まる

### Observable-Class Dependence of Observational Equivalence in ABM Mechanism Identification

**ワーキングペーパー草稿 v1（2026-06-13）**。

> **改訂注記（v0→v1）**: 本ファイルの前版 v0 は、3つの試行（PRISM・T/H・channel-band）が失敗した
> ことを「介入による機構識別は構造的に不可能」という否定結論として書いた。これは2つの過剰一般化を
> 含んでいた: (i) channel-band の局所的失敗（単一資産で price=λ·flow ゆえ A/B が同一モデル化）を
> 「核が達成不能」へ拡大した。order book では price と flow は連続でも独立で、失敗の原因（比例関係）が
> 消える。(ii) 「ABM」と「SF 等価な異機構を介入で識別する特定の証明戦略」を混同した。ABM は P2
> （Calvano 移植可能性監査）で現に政策含意のある結果を出している。さらに、ジレンマの2本の角を
> 「強い判定器（生系列 CNN）/弱い判定器（要約統計）」で並べたのが効きすぎていた。任意の有限 trajectory
> 差で割れる検出器を観測等価の基準にすれば equifinality は空になる。観測等価は検出器の強弱でなく、
> **政策の問いが指定する観測量クラス**で定義すべきである。v1 はこの定義依存性の主張に書き直す。

---

## Abstract

The proposal to discriminate competing agent-based models (ABMs) by their response to a policy
intervention rests on an unexamined choice: what counts as an observable when judging whether two
models are "observationally equivalent." We show that ABM mechanism identifiability by intervention
depends decisively on this observable class, and that three independent attempts failed by choosing
the class wrongly, not because the task is impossible. Defined by the strongest raw-trajectory
discriminator (a classifier reading any difference in a finite return series), equifinality becomes
vacuous and the only equivalent pairs are reparameterizations of one model (channel-band). Defined
by summary statistics, genuinely distinct mechanisms can be equated, but a stronger discriminator
separates them (T/H); whether this makes the intervention redundant depends on whether that stronger
discriminator is itself a policy-relevant observable. Defined by the wrong class — return-distribution
statistics where a tick intervention deposits no signal — no effect is detectable at all (PRISM). The
observational equivalence that matters for policy is relative to the observable class the policy
question specifies: for market-design policy (tick size, batch auctions) these are microstructure
quantities — quoted and effective spread, depth, price impact — at intraday frequency, not raw-return
classifiers and not return-distribution moments. This aligns with causal inference, where
interventions distinguish structures that share an observational distribution over a specified set of
observed variables. We close with a falsifiable prediction: defining observational equivalence by the
policy-relevant observable class yields mechanism pairs that are equivalent in that class and
separated by the intervention, and we specify its verification with order-book infrastructure.

---

## 1. 問題

ABM を市場設計政策の評価に用いる際の前提は「歴史データでは区別できない機構を、政策介入への応答で
区別できる」である。これは2要件を要する: (a) 2モデルが観測データで区別不能（でなければ介入は冗長）、
(b) 介入下で応答が異なる。本稿の主張は、(a) の成否が**何を観測量とするか**に決定的に依存し、その選択を
誤ると識別が空回りする、というものである。

## 2. 観測等価は観測量クラスに相対的である

「観測等価」は絶対的概念ではない。それは**観測量クラス O**（何を観測できると認めるか）に相対的で、
「O に属する量の下で2モデルが区別できない」ことを意味する。

- 経済学が問題にする観測等価は、「意思決定者が利用可能な統計量の下で区別できない」である。「生の有限
  trajectory を任意の検出器で見て少しでも違えば区別可能」ではない。後者を基準にすると、相異なる確率
  過程はほぼ全て区別可能になり、equifinality という概念が空になる。
- 因果推論は、**観測された変数の分布**（特定の観測量クラス）が一致し介入分布が異なる因果構造を、介入で
  区別する。観測等価は「観測変数分布の一致」であって、生 trajectory の恒等ではない。介入による識別が
  成立するのは、まさにこの相対的な観測等価の下である。

したがって (a) を判定する観測量クラス O は、恣意的な検出器の強弱で選ぶものではなく、問いが決める。

## 3. 観測量クラスは政策の問いが決める

市場設計政策（tick size 変更、batch auction、speed bump）の評価において意思決定者が関与する観測量は、
microstructure 量である:

- quoted spread、effective spread
- 板厚（depth）、price impact（Kyle λ）
- 約定到着率・サイズ分布

これらは、tick/batch 介入が実際に効果を与える量である（Aquilina, Budish & O'Neill 2022、
Comerton-Forde, Gregoire & Zhong 2019 が実測）。一方、(i) 1000 ステップの生 return を分類器に入れた値、
(ii) 日次 return 分布の moment（GARCH persistence・尖度）は、どちらも政策が関与する観測量ではない。
(i) は強すぎて equifinality を空にし、(ii) は tick 介入の信号を含まない。**正しい観測等価は、この両極の
間、政策が指定する microstructure 量クラスにある。**

## 4. 3つの試行 —— 観測量クラスの3つの誤った選び方

### 4.1 channel-band（退化した市場）

単一資産の超過需要市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` では return = λ·ED/N で価格と注文流が同一信号。
価格を読むモデル A と注文流を読むモデル B は連続市場で bit 同一の出力を生む。だがこれは異なる2機構の
equifinality ではなく、同一モメンタム関数の入力単位の違い（再パラメータ化）である。バッチ下の分離は
機構識別でなく、単一モデルのパラメータ（注文流の読み解像度）の可識別性。

この失敗は**単一資産という市場の退化**に局所化する。order book では price は net flow の決定論的関数では
なく（板厚・約定過程が介在）、価格を読むことと注文流を読むことは連続でも独立な観測になる。channel-band は
「核が達成不能」を示すのではなく、「単一資産 toy が不適切」を示す。

### 4.2 T/H（最強の観測量クラス）

共有 chassis 上で投機ブロックのみ差し替えた異機構ペア（T=チャーティスト需要、H=群衆模倣）。要約統計
（SF1-4）を joint calibration で一致させ、要約統計分類器の精度を 0.58 まで下げた。だが held-out の生系列
分類器（1D-CNN）は 0.85–0.91 で分離した。

これは、観測等価を**最強の検出器（生 trajectory の任意の差を読む CNN）**で定義したことの帰結である。
この基準では、相異なる機構はほぼ常に割れる。要約統計クラスでは T/H は等価だが、要約統計クラスもまた
政策が指定する観測量クラスではない。T/H は、観測量クラスを生 CNN（強すぎ）に取ると識別対象が消え、
要約統計（政策と無関係）に取ると介入が冗長に見える、という両極の不適切さを示す。

### 4.3 PRISM（間違った観測量クラス）

PRISM（撤退済の内部試行）は、tick/取引税という microstructure 介入の効果を、日次 return-distribution
量で測った。有効な自然実験（JPX 2014 tick）でも全6量の信頼区間がゼロを跨ぎ、効果を検出できなかった。
加えて、用いた4 ABM が同一方程式のパラメータ変種で独立でなかった。

PRISM の失敗は、観測量クラスの選択ミスとして最も明確である: **tick 介入の信号がある量（spread/depth/
impact）でなく、信号のない量（日次 return 分布）を測った。** 正しい観測量クラス（microstructure、
intraday）であれば、§3 の文献が示す通り tick 効果は検出される。

## 5. 主張しないこと（過剰一般化の明示的排除）

- **一般的不可能性を主張しない**。因果推論は、観測量クラスを観測変数分布に取れば、観測等価な構造を介入で
  区別する。本稿の主張は「観測等価を検出器の強弱で定義するのが誤りで、政策の問いが指定する観測量クラスで
  定義すべき」である。
- **ABM が道具として終わっているとは主張しない**。ABM は P2（Calvano 移植可能性監査、batch×共謀の境界、
  BCS 接地）で政策含意のある結果を出している。終わっているのは「SF 再現が機構を識別する」というパラダイム
  であり、それは本プログラムが当初から賭けていた命題そのものである。本稿はその命題の、一段深い形
  （介入応答による識別すら、観測等価の定義次第で空回りする）を特定する。

## 6. 反証可能な前向き予測と検証設計

> **予測**: 観測等価を政策関連の観測量クラス（order book の spread・depth・price impact、intraday）で
> 定義すると、(a) そのクラスで観測等価かつ (b) 介入（tick/batch）で分離する機構ペアが存在する。

検証設計:
1. order book を持つ市場（板厚・約定過程。P2 のインフラが該当）で、価格に反応する機構と注文流/板に反応
   する機構を構成する。単一資産と違い、両者は連続でも microstructure 量クラスで異なりうる。
2. 改革前（連続/baseline）データで、両機構が microstructure 量クラスで区別不能になるよう calibrate する
   （要件 a）。
3. tick/batch 介入下で、両機構の microstructure 量が異なるかを測る（要件 b）。
4. 反証: もしこのクラスでも両機構が再パラメータ化に潰れる（channel-band の再来）か、または改革前から
   microstructure 量で区別される（T/H の再来）なら、予測は偽。その場合、観測等価かつ介入分離なペアは
   政策関連クラスでも存在せず、識別論は弱い主張（パラメータ可識別性、要約統計レベル）に後退する。

この検証は P2 の order book インフラに橋渡しされる。`docs/realdata_method_and_p3_coherence.md` の実データ
照合は、同じ microstructure 量クラスを実在の改革（JPX 2014）に適用する段である。

## 7. 含意

ABM の検証論は、「観測等価」を観測量クラスを明示せずに用いてきた（SF=要約統計、あるいは暗黙の「データ」）。
SBI 批判は暗にそれを最強の検出器へ押し上げ、equifinality を空にした。本稿の主張は、観測等価を問いが指定
する観測量クラスで定義せよ、というものである。機構識別を主張する ABM 研究は、用いる観測量クラスと、その
クラスで対象が genuinely 異機構か再パラメータ化かを明示せねばならない。3例は、クラスを誤る3つの仕方が
それぞれ失敗する様を示す。Fagiolo, Moneta & Windrum (2007) 系の検証方法論に正面から接続する。

## 8. 関連
- 3例: PRISM（内部・撤退済）、T/H（`docs/program_claims_v1.md`、Issue #11）、channel-band
  （`toy/channel_band.py`、`docs/findings/0001-channel-decoupling-band.md`、機構識別の解釈は撤回済）。
- 検証設計・実データ・P3: `docs/realdata_method_and_p3_coherence.md`。
- 文献: Fagiolo, Moneta & Windrum (2007); Aquilina, Budish & O'Neill (2022);
  Comerton-Forde, Gregoire & Zhong (2019); Guerini & Moneta (2017); Cranmer, Brehmer & Louppe (2020)。
