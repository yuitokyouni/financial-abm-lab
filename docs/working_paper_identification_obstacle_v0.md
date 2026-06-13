# 観測等価の判定基準と、介入応答による ABM 機構識別の障害 —— 3つの試行からの観察

### The Equivalence-Criterion Dilemma: An Obstacle to Intervention-Based Mechanism Identification in Agent-Based Models

**ワーキングペーパー草稿 v0（2026-06-13）**。本稿は、3つの独立な試行（PRISM の自然実験、T/H の
ブロック単離ペア、channel-band の再パラメータ化）が同じ障害に当たった観察を整理し、その障害を
観測等価の判定基準の選択に関するジレンマとして特定する。先行する正の主張（バッチによる機構識別、
`docs/working_paper_batch_identification_v0.md`）は §4 の理由で撤回し、本稿に置き換える。

---

## Abstract

A recurring proposal in the agent-based model (ABM) literature is to discriminate competing
mechanisms by their response to an intervention, on the premise that mechanisms which are
indistinguishable in observational data can be told apart by how they react to a policy change.
We report that three independent attempts to realize this premise failed, and we identify why.
The premise requires two conditions: (a) the two models are indistinguishable in observational
data, so that the intervention is not redundant, and (b) the two models respond differently to
the intervention. Whether (a) holds depends on the discriminator used to judge "indistinguishable."
Under a strong discriminator — a learned classifier on raw output series, which approximates the
best observational test and pre-empts simulation-based inference — genuinely distinct mechanisms
are separable in our experiments, and the only model pairs that pass are reparameterizations of a
single model, for which there is no mechanism to discriminate. Under a weak discriminator —
summary statistics — genuinely distinct mechanisms can be made equivalent, but a stronger
discriminator then separates them, so observation does not in fact fail and the intervention is
redundant. The discriminative value of the intervention over observation and the existence of
genuinely distinct observationally-equivalent pairs are therefore in direct conflict, mediated by
the strength of the observational discriminator. We do not claim general impossibility — causal
inference distinguishes observationally-equivalent causal structures by intervention — but we
document that, in the ABM-with-stylized-facts setting, the criterion strong enough to make the
intervention non-redundant admits only reparameterizations. We state what remains achievable
(parameter identifiability under a designed intervention; the weak-criterion claim with the
discriminator caveat made explicit; real-data model selection with its own obstacles).

---

## 1. 主張と要件

ABM 文献で繰り返し提案されるのは、複数の機構を介入応答で区別することである。前提は「観測データでは
区別できない機構を、政策変更への反応で区別できる」。これを実現するには2要件が要る:

- **(a) 観測等価**: 2モデルが観測データ上で区別できない。区別できるなら、介入を待たず観測で選別でき、
  介入は冗長になる。
- **(b) 介入応答差**: 2モデルが介入下で異なる出力を出す。

本稿の観察は、(a) が成り立つか否かが、何を「区別できない」の判定器とするかに依存し、その選択が
(a) と (b) の両立を妨げる、というものである。

## 2. 判定基準のジレンマ

観測等価の判定器 D を、出力の分離精度（chance = 区別不能）で測る。

- **強い判定器**（生の出力系列を入力とする学習分類器。最良の観測的検定および simulation-based
  inference を近似する）で (a) を要求する場合:
  - 異なる機構は生の動学が異なるため、D が分離する（後述 §3.2、T/H で D の精度 ≈ 0.9）。
  - D を通るのは、出力過程が（ほぼ）恒等のペア、すなわち単一モデルの再パラメータ化に限られる
    （後述 §3.3、channel-band で bit 同一）。
  - よって強い判定器の下では、観測等価は実質的に同一モデルを意味し、識別すべき機構が存在しない。
    介入下の「分離」は、その単一モデルのパラメータ推定（可識別性）であって機構識別ではない。
- **弱い判定器**（要約統計）で (a) を要求する場合:
  - 異なる機構が要約統計を一致させられる（equifinality、後述 §3.2、T/H で要約統計の分離精度 0.58）。
  - しかし強い判定器（学習分類器/SBI）は同じペアを分離できる。よって「観測では区別できない」は
    強い意味で偽になり、介入が観測に対して持つはずの独自価値が消える。

要約すると: **介入が観測に対して非冗長であるためには、観測が（強い判定器の下で）失敗する必要がある。
だが強い判定器を通すのは再パラメータ化に限られる。ゆえに、介入を非冗長にする判定基準の下では、識別
すべき異機構ペアが存在しない。** これが2要件の両立を妨げる障害である。

一般的な不可能性は主張しない。因果推論は、観測分布が一致し介入分布が異なる因果構造を、介入で区別
する。本稿の主張は、ABM × stylized facts という具体的設定で、上記のジレンマが3つの独立な試行で
再現した、という観察である。

## 3. 3つの試行（ジレンマの3つの角）

### 3.1 PRISM（実データの自然実験、パラメータ変種の角）

PRISM（撤退済の内部プロジェクト）は、実在の市場介入（tick 引き下げ・取引税）の前後データで、複数
ABM のうちどれが現実を記述するかを介入応答で選ぼうとした。結果は 120 セル中 0 セルが結論的で、有効
な自然実験（JPX 2014 tick）でも全6量の信頼区間がゼロを跨いだ。原因のうち本稿に関わるもの:

- 4つの ABM が同一方程式 `excess_demand = w_f·d_fund + w_c·d_chart + w_n·d_noise` のパラメータ変種
  であり、独立な機構でなかった。介入応答の差が ~10⁻⁴ に縮退し、(b) が成り立たなかった。
- 加えて、測った量（日次 return 分布）に介入の信号が現れず（信号は spread/depth 等の microstructure
  量にある。Aquilina, Budish & O'Neill 2022、Comerton-Forde, Gregoire & Zhong 2019）、また実データの
  反実仮想に正解がないため、仮に予測差があっても照合できない。

PRISM は、(a) を満たすほど似たモデル（パラメータ変種）を選ぶと (b) が失われる角を示す。

### 3.2 T/H（異機構ペア、強い判定器の角）

T/H は、共有 chassis 上で投機ブロックのみを差し替えた、原典由来の異機構ペア（T = チャーティスト
需要、H = 群衆模倣）である。要約統計（SF1-4）を joint calibration で一致させ、要約統計の分類器
（ロジスティック回帰）の精度を 0.58 まで下げられた。しかし held-out の生系列分類器（1D-CNN）は
両者を 0.85–0.91 で分離した。敵対 calibration（分類器精度を直接最小化）と held-out certification
でも、CNN は分離した（search で 0.62 に下げても held-out で 0.91 に戻った）。

T/H は、機構を実際に異ならせると、要約統計では等価化できても強い判定器が分離する角を示す。弱い判定器
（要約統計）では (a) が成り立つが、強い判定器では成り立たない。

### 3.3 channel-band（再パラメータ化の角）

channel-band は、価格チャネルを読むモデル A と注文流チャネルを読むモデル B を、単一資産の超過需要
市場 `p_{t+1}=p_t·exp(λ·ED_t/N)` 上で構成した。この市場では return = λ·ED/N で価格と注文流が同一
信号であり、正規化モメンタムは尺度不変なので、A と B は連続市場で **bit 同一**の出力を生む（強い
判定器でも精度 0.5）。

しかしこの bit 同一は、(a) の本来の意味（異なる2機構が同じ出力分布を持つ = equifinality）ではなく、
**計算グラフの恒等**である。A の信号 = λ × B の信号であり、A と B は同じモメンタム関数を異なる入力
単位で計算しているにすぎない。バッチオークション（interval N で一括清算、バッチ内は価格不変・注文流
のみ蓄積）下では、バッチ境界の return = λ·N·（バッチ平均注文流）となり、A は注文流のバッチ平均を、
B は毎期の注文流を読む。両者の差は入力の時間解像度の差であって、行動原理の差ではない。

したがって channel-band でバッチ下に観測される「分離」は機構識別ではなく、単一モデルのパラメータ
（注文流をどの解像度で読むか）の可識別性である。連続データでは推定不能なこのパラメータが、バッチ
（価格と注文流の比例が崩れる介入）で推定可能になる。さらに、その介入は A/B の縮退を壊すように後から
選ばれたものであり、識別の成立は循環的である（縮退と、それを壊す介入の両方を構成した）。

channel-band は、(a) を厳密（bit 同一）にすると、モデルが単一の再パラメータ化に潰れる角を示す。
これは §3.1 の PRISM の「独立でないモデル」と同型であり、独立に再現した。

## 4. 先行する正の主張の撤回

`docs/working_paper_batch_identification_v0.md`（バッチによる機構識別）は、§3.3 の通り A/B が同一
モデルの再パラメータ化であるため、機構識別の主張としては成立しない。同稿の数値（連続で区別不能、
バッチで分離）は、パラメータ可識別性の例としては正しいが、機構識別ではない。撤回し本稿に置き換える。

## 5. 形式的記述（証明済みと予想の区別）

- **証明済み（本稿の3例）**: (i) パラメータ変種は介入応答差が縮退する（PRISM）。(ii) 原典由来の異機構
  ペアは、要約統計で等価化しても強い判定器が分離する（T/H、2つの calibration 法と held-out で一貫）。
  (iii) 強い判定器の下で観測等価を厳密に満たす構成は、単一モデルの再パラメータ化に潰れる（channel-band）。
- **予想（未証明）**: 強い判定器（学習分類器）を観測等価の基準とするとき、その基準を通す異機構ペアは
  存在しない（再パラメータ化のみが通る）。本稿はこの予想に反する例を示せていないが、存在しないことを
  証明してもいない。反例（強い判定器を通る genuinely 異機構ペア）が見つかれば、本障害は回避される。

## 6. 残る達成可能なもの

- **設計された介入下のパラメータ可識別性**: §3.3 のように、特定の縮退を壊す介入は、その縮退の
  パラメータを推定できる。これは真だが、機構識別とは別の、弱い主張である。
- **弱い基準での主張（判定器の留保を明示）**: 要約統計の下で異機構を等価化し、介入で区別する主張は
  立つ（T/H の要約統計レベル）。ただし「強い判定器（SBI）なら観測でも区別できる」ことを明示し、介入の
  価値を「要約統計を超えるが SBI 未満の識別」と正直に限定する必要がある。
- **実データのモデル選択**: 実在の介入の前後で予測の当否によりモデルを選ぶ道（§3.1 の修復版）。ただし
  反実仮想に正解がないこと、介入の信号がある量（microstructure・intraday）を測る必要があること、独立な
  モデルを用いること、の3条件を満たす必要がある。データ要件は `docs/realdata_method_and_p3_coherence.md`。

## 7. 含意

ABM を政策評価に用いる際、「歴史データでは決まらないモデルを介入応答で選ぶ」という手続きは、観測
等価の判定基準を強くするほど識別対象が再パラメータ化に潰れ、弱くするほど介入が観測に対して冗長になる。
この障害は、3つの独立な試行（実データ・異機構ペア・再パラメータ化）で再現した。ABM ベースの政策助言を
介入応答で正当化する研究は、用いる観測等価の基準と、その下で識別対象が genuinely 異機構か再パラメータ化
かを、明示する必要がある。

## 8. 関連
- 3例の実装と記録: PRISM（内部・撤退済）、T/H（`docs/program_claims_v1.md`、Issue #11）、
  channel-band（`toy/channel_band.py`、`docs/findings/0001-channel-decoupling-band.md`）。
- 実データ手法と P3 整合: `docs/realdata_method_and_p3_coherence.md`。
