# 観測等価の観測量クラス依存性 —— 観測量クラスは政策の作用点から演繹される

### Observable-Class Dependence of Observational Equivalence: The Class is Deduced from the Policy's Point of Action

**ワーキングペーパー草稿 v1（2026-06-13）**。狙い: 主論文（JEDC）。P1 メイン（「SF 等価な異機構を
介入で識別」）の、より深く正しい再定式化として統合する候補。§6 の予測は order book で検証する
（本稿は §2 の定式化まで。検証は次段）。

> **改訂注記**: 前版 v0 は3試行の失敗を「介入による機構識別は構造的に不可能」と書いた。これは2つの
> 過剰一般化を含む。(i) channel-band の局所失敗（単一資産 price=λ·flow）を「核が達成不能」へ拡大。
> order book では price と flow は独立で、原因が消える。(ii) 「ABM」と「特定の証明戦略」を混同。ABM は
> P2 で機能している。加えて、ジレンマを「強い/弱い検出器」で並べたのが効きすぎていた。観測等価は検出器
> の強弱でなく政策の作用点が指定する観測量クラスで定義すべきである。v1 はこの定式化に置き換える。

---

## Abstract

Whether two agent-based models (ABMs) are "observationally equivalent" is not absolute; it is
relative to an observable class — the set of quantities admitted as observable. We argue that ABM
mechanism identifiability by intervention depends decisively on this class, and that the class must
be deduced from the policy's point of action in the market mechanism, independent of whether any
particular quantity turns out to respond. For a tick-size policy, the point of action is the price
grid, so the policy-relevant observables are the quantities defined at that level — quoted and
effective spread, depth, price impact — while return-distribution statistics are downstream
aggregates and are excluded a priori, before any measurement. The apparent tension between
"observationally equivalent" and "differently responding to the intervention" is a symptom of
choosing the class by detector strength rather than by the point of action: an over-strong class
(any difference in a raw trajectory) admits only reparameterizations of one model; an
over-weak or policy-irrelevant class (return moments under a tick change) carries no signal of the
intervention; neither is the point-of-action class. Three prior attempts each chose the class
wrongly in one of these three ways. We do not claim impossibility — causal inference distinguishes
structures equivalent over a specified observable class — nor that ABMs are exhausted as a tool. We
state a falsifiable prediction with a pre-registered success criterion and four outcome branches,
including the branch in which two mechanisms cannot be calibrated to equivalence in the
point-of-action class, and we specify its verification with order-book infrastructure.

---

## 1. 問題

ABM を市場設計政策の評価に用いる前提は「歴史データでは区別できない機構を、政策介入への応答で区別
できる」である。これは2要件を要する: (a) 2モデルが観測データで区別不能（でなければ介入は冗長）、
(b) 介入下で応答が異なる。本稿の主張は、(a) の成否が**何を観測量とするか**に依存し、その観測量クラスを
**政策の作用点から演繹**しない限り、識別が空回りするか、選択that循環する、というものである。

## 2. 観測等価は観測量クラスに相対的であり、クラスは政策の作用点から演繹される

### 2.1 観測等価は観測量クラスに相対的

「観測等価」は絶対概念でなく、観測量クラス O（何を観測できると認めるか）に相対的で、「O に属する量の
下で2モデルが区別できない」を意味する。経済学が問題にする観測等価は「意思決定者が利用可能な統計量の
下で区別できない」であり、「生の有限 trajectory を任意の検出器で見て少しでも違えば区別可能」ではない。
後者を基準にすると相異なる確率過程はほぼ全て区別可能になり、equifinality が空になる。因果推論も、
**観測変数の分布**（特定の O）が一致し介入分布が異なる構造を介入で区別する。観測等価は O に相対的である。

### 2.2 クラスは政策の作用点から演繹される（結果から選ばれない）

O を結果（どの量が応答したか）から選ぶと循環する。後から「応答した量」を「正しいクラス」と呼ぶのは、
channel-band で「縮退を壊す介入を後から選んだ」のと同型の循環の、クラス選択版である。これを避けるため、
O の正しさを**結果と独立**に定める原理を置く:

> **原理（作用点演繹）**: 観測量クラス O は、政策that市場機構の中で物理的に作用する点（point of action）
> で定義される量からなる。O は政策の作用機序のみから演繹され、「どの量が応答したか」を一切参照しない。

適用:
- **tick size 政策**は**最小価格刻み（価格グリッド）**に作用する。グリッドの水準で定義される量 ——
  quoted spread / effective spread（tick が下限を与える）、各価格水準の depth、price impact（グリッド
  所与で flow が価格をどう動かすか）—— が O。**日次 return 分布**（GARCH persistence・尖度・ACF）は
  価格パスを時間集約した**下流の派生量**で、グリッドより数段上の集約。よって tick の O ではない。
- **batch auction 政策**は**清算のタイミング**に作用する。注文流のタイミングと価格更新の関係、バッチ内
  vs バッチ間の動学が O。

この判定は**政策の定義のみから事前に**可能で、測定結果を参照しない。後述 §4.3 の通り、PRISM の return
facts が不適切だったのは「検出できなかったから」ではなく、「tick の作用点（価格解像度）より下流の派生量
だったから」であり、事前に判定できる。spread/depth が tick 介入に応答することを Aquilina et al. (2022) 等が
実測している事実は、本原理の選択を**裏づける**が、選択が**依拠する**ものではない（選択は作用点から演繹済み）。

### 2.3 「2要件の緊張」はクラス誤選択の症状であり、作用点クラスで解消する

(a) と (b) の緊張は、観測等価を**検出器の強弱**で定義したときにのみ生じる見かけの症状である。O を作用点で
固定すると次のように整理され、構造的障害ではなくなる:

- **強すぎる O**（生 trajectory の任意差を読む検出器）: 通るのは出力過程が恒等のペア、すなわち再
  パラメータ化のみ（§4.1 channel-band）。
- **弱すぎる/政策無関係な O**（tick 政策に対する日次 return moment）: 介入の信号がそこに無い（§4.3 PRISM）。
- **作用点 O**（tick/batch に対する microstructure 量）: 上の両極のいずれでもない。そこで (a) かつ (b) を
  満たすペアが存在するかは**経験的な問い**であり（§6）、構造的不可能性ではない。

## 3. 3つの試行 —— 観測量クラスの3つの誤った選び方

### 3.1 channel-band（退化した市場 + 強すぎるクラス）

単一資産の超過需要市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` では return = λ·ED/N で価格と注文流が同一信号。価格を
読む A と注文流を読む B は連続市場で bit 同一の出力を生む。これは異機構の equifinality ではなく、同一
モメンタム関数の入力単位の違い（再パラメータ化）。観測等価を強すぎる O（生系列の CNN）で定義したことと、
市場が退化している（単一資産で price=net flow）ことが重なった。order book では price は net flow の決定論的
関数でなく、価格を読むことと注文流を読むことは作用点クラスでも独立な観測になりうる。channel-band は「核が
達成不能」ではなく「単一資産 toy が不適切」を示す。

### 3.2 T/H（強すぎるクラス）

共有 chassis 上で投機ブロックのみ差し替えた異機構ペア。要約統計（SF1-4）を joint calibration で一致させ、
要約統計分類器の精度を 0.58 まで下げたが、held-out の生系列 CNN は 0.85–0.91 で分離した。これは観測等価を
**最強の検出器（生 trajectory の任意差）**で定義した帰結である。要約統計クラスでは等価だが、要約統計も
tick/batch の作用点クラスではない。T/H は、O を生 CNN（強すぎ）に取ると対象が消え、要約統計（政策無関係）に
取ると介入が冗長に見える、両極の不適切さを示す。

### 3.3 PRISM（間違ったクラス）

PRISM（撤退済の内部試行）は、tick/取引税という microstructure 介入の効果を、日次 return-distribution 量で
測り、有効な自然実験（JPX 2014 tick）でも全6量の信頼区間がゼロを跨いだ。加えて用いた4 ABM が同一方程式の
パラメータ変種で独立でなかった。§2.2 の作用点原理により、これは事前に判定できる誤りである: 日次 return
分布は tick の作用点（価格グリッド）より下流の派生量で、tick の O ではない。正しい O（spread/depth/impact、
intraday）であれば、§2.2 の文献が示す通り tick 効果は検出される。

## 4. 主張しないこと

- **一般的不可能性を主張しない**。因果推論は、O を観測変数分布に取れば観測等価な構造を介入で区別する。
  本稿は「観測等価を検出器の強弱で定義するのが誤りで、政策の作用点が指定する O で定義すべき」を主張する。
- **ABM が道具として終わっているとは主張しない**。ABM は P2（Calvano 移植可能性監査、batch×共謀の境界、
  BCS 接地）で政策含意のある結果を出している。終わっているのは「SF 再現が機構を識別する」パラダイムであり、
  それは本プログラムが当初から賭けていた命題である。本稿はその一段深い形（介入応答による識別すら、O の
  定義次第で空回りする）を特定し、正しい O の原理を与える。

## 5. 反証可能な予測と、事前登録した成功判定・分岐（§6 検証の設計）

> **予測**: 観測等価を tick/batch の作用点クラス O（order book の spread・depth・price impact、intraday）で
> 定義すると、(a) O で観測等価かつ (b) 介入（tick/batch）で O が分離する機構ペアが存在する。

**成功判定（事前登録）**: 2機構が「O で観測等価」とは、改革前データで O の各量（および同時分布）が TOST で
等価（差の CI が事前帯内）と判定されること。「O で分離」とは、改革後に O の量が seed 横断 ±2SE で異なること。

**4つの分岐（事前登録、後知恵の逃げ場を塞ぐ）**:
- **A（予測支持）**: O で等価化が達成でき、介入で O が分離する。
- **B（予測反証）**: O で等価化が達成できるが、介入下でも O が等価（応答も等価）。→ 作用点クラスでも識別
  できず、主張は弱い形（パラメータ可識別性、または要約統計レベル）に後退する。
- **C（設計失敗）**: O で等価化が達成できるが、その2機構が再パラメータ化に潰れる（channel-band の再来）。
  → genuinely 異機構でなく、設計をやり直す。
- **D（検証不能）**: **2機構を O で等価化する calibration that達成できない**（spread/depth/impact の同時
  分布を2機構で TOST 通過まで一致させられない）。→ 「この設計では予測を検証できなかった」と正直に報告し、
  反証とも支持とも主張しない。T/H が2自由度で要約統計を合わせられたのに対し、microstructure 同時分布の
  一致は遥かに難しく、この分岐は現実的に起こりうる。

## 6. 検証設計（order book、次段）

1. order book（板厚・約定過程。P2 のインフラが該当）で、価格に反応する機構と注文流/板に反応する機構を
   構成する。単一資産と違い、両者は連続でも作用点クラス O で異なりうる。
2. 改革前データで §5 の成功判定（O での TOST 等価化）を試みる。達成不能なら分岐 D を報告して終了。
3. 達成できたら、tick/batch 介入下で O が分離するか（分岐 A）、しないか（B）、潰れるか（C）を §5 の規則で
   機械判定する。
実データ照合（JPX 2014）は、同じ O を実在の改革に適用する段で、`docs/realdata_method_and_p3_coherence.md`。

## 7. 含意

ABM の検証論は「観測等価」を観測量クラスを明示せず用いてきた（SF=要約統計、または暗黙の「データ」）。
SBI 批判は暗にそれを最強検出器へ押し上げ equifinality を空にした。本稿は、観測等価を**政策の作用点が指定
する観測量クラス**で定義せよ、と主張する。機構識別を主張する ABM 研究は、用いる O と、その作用点演繹の
根拠、その O で対象が genuinely 異機構か再パラメータ化かを明示せねばならない。3例は O を誤る3つの仕方が
それぞれ失敗する様を示す。Fagiolo, Moneta & Windrum (2007) 系の検証方法論に正面から接続する。

## 8. 関連
- 3例: PRISM（内部・撤退済）、T/H（`docs/program_claims_v1.md`、Issue #11）、channel-band
  （`toy/channel_band.py`、`docs/findings/0001-channel-decoupling-band.md`、機構識別の解釈は撤回済）。
- 検証設計・実データ・P3: `docs/realdata_method_and_p3_coherence.md`。
- 文献: Fagiolo, Moneta & Windrum (2007); Aquilina, Budish & O'Neill (2022);
  Comerton-Forde, Gregoire & Zhong (2019); Guerini & Moneta (2017); Cranmer, Brehmer & Louppe (2020)。
