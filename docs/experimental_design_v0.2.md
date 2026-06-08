# 実験計画書: SF-等価モデルに対する観察情報チャネル介入による機構識別

**版**: v0.2 (留保 1/2 resolved)
**日付**: 2026-06-08 (v0.1: 2026-06-05)
**著者**: Yuito (東大新領域人間環境学専攻 SCSLab 2026年秋 入学予定)
**コードネーム**: 真・PRISM (toy validation of intervention-response discriminative premise)
**ステータス**: 留保 1/2 を default で解決し pre-registration として運用。§2(仮説・判定基準)/§14(decision tree)は確定・post-hoc 変更禁止。§4-§6 は留保解決に伴い更新したが、**留保の substance(anchor の選び方・SF scope の妥当性)は別途詰める予定で、変更が生じれば v0.3 として versioned に切り直す**(サイレント編集はしない)。

---

## 0. 背景と立ち位置

本実験は、撤退決定された PRISM (Provenance-backed Reproducible Intervention-response Scoring of Mechanisms) の load-bearing な経験的前提:

> 「stylized facts では識別できない異機構モデルを、介入応答は識別できる」

を、構造論ではなく経験的に検証するための controlled toy experiment である。

PRISM 本体は構造論で死亡している(signal-limited tensor、Guerini-Moneta lineage が同じ問題空間を観察的因果同定で占有、real-world deployment の counterfactual ground-truth 欠如)。本実験は **PRISM を蘇生する試みではない**。dead な project の load-bearing 前提を経験的に閉じ、(a) 経験+構造の二重 obit 完了、(b) 結果が positive なら proof-of-concept の small clean paper、(c) 副次効果として SG (Speculation Game) 本線の検証 harness を整備する、の3つを目的とする。

特に (c) が重要で、本実験で構築する SF-equivalent calibration pipeline + classifier + 介入応答測定 framework は、後の SG 結果(未再現 fact の minimal-mechanism 内生発露)を defensible に示す道具とそのまま同型である。

---

## 1. リサーチクエスチョン

**RQ1 (main):** SF battery 上で観察上等価に calibrate された異機構 ABM ペアを、観察情報チャネルへの graded 介入の応答曲線で識別できるか?

**RQ2 (robustness):** 識別可能な場合、その識別力は介入の attenuation スキーム選択に対してどの程度 robust か?

**RQ3 (null):** 識別可能な場合、その識別力は同機構異パラメータの null pair に対しては期待通り消失するか? (= 介入応答が機構の差を拾っているのか、パラメータの差を拾っているのかの判別)

---

## 2. 仮説と pre-registered 判定基準

### 2.1 仮説

- **H1 (SF 等価性):** 適切なパラメータ calibration により、Model T (trend-following) と Model H (herding) の SF 分布は両 classifier で区別不能になる(accuracy 50-55%)。
- **H2 (主仮説):** 観察情報チャネルへの graded 介入後の応答曲線特徴量を用いた IR classifier は、T と H を高い精度で識別する(accuracy ≥ 75%)、かつこれは少なくとも 4 つの attenuation スキームのうち 3 つで成立する。
- **H3 (null):** 同機構異パラメータ pair (T1 vs T2) に対しては、IR classifier の accuracy は SF classifier と同程度(50-60%)に留まる。

### 2.2 Pre-registered 判定基準

実験完了時点で以下の判定を機械的に行う。post-hoc 移動禁止。

#### SF 等価性検証 (entry condition)

| 条件 | 基準 |
|------|------|
| Pass | 両 SF classifier (summary-stat + discriminator net) で T-vs-H 5-fold CV accuracy が 50-55% |
| Soft fail | 一方が 55-60% (=「観察等価」が弱いが続行可能、結果解釈時に注記) |
| Hard fail | いずれかが > 60% (= 等価性未達、calibration 不十分、grid search やり直し) |

#### Null sanity (T1 vs T1 異 seed)

両 classifier ともに 50 ± 3% に収まること。これが失敗するなら実験プロトコル自体が壊れている。続行不可。

#### Null mechanism (T1 vs T2 同機構異パラメータ)

| 条件 | 基準 |
|------|------|
| Expected | IR classifier accuracy が SF baseline (50-55%) ± 10% 以内 |
| Concerning | IR classifier accuracy が 65%+ (= 介入応答が機構ではなくパラメータの差を拾っている、主仮説の解釈が複雑化) |

#### 主結果判定 (T vs H)

| 結果 | 4 schemes 中の高精度 (≥ 75%) scheme 数 | 解釈 |
|------|------|------|
| **GO** | 3 以上 | premise を強く支持、proof-of-concept 成立、論文化へ |
| **PARTIAL** | 1-2 | premise 限定的支持、scheme 依存性が強い、追加調査必要 |
| **PIVOT** | 0 | premise 経験的不支持、構造論+経験論の二重死、PRISM obit 完了、SG 本線へ集中 |

---

## 3. 市場モデル仕様

### 3.1 単一資産市場

- エージェント数: N = 500
- 資産: 単一リスク資産 + cash numeraire
- 価格更新: `p_{t+1} = p_t · exp(λ · ED_t / N)`
  - ED_t = Σ_i a_{i,t} (集約超過需要)
  - a_{i,t} ∈ {-1, 0, +1} (sell, hold, buy)
  - λ = 0.01 (calibration target、価格インパクト)
- 時間: 離散、1 step = 1 tick の抽象単位
- バーンイン: 1000 steps
- 測定: 10000 steps
- ファンダメンタル: 本実験では固定(p* = 100、エージェントには非公開)

### 3.2 機構仕様

#### Model T: trend-following

- 各 agent i は観測ベクトル o_{i,t} から内部で trend signal を計算
- `trend_{i,t} = mean(r_{t-h_i:t}) / std(r_{t-h_i:t})`
  - r_τ = log(p_τ / p_{τ-1})
  - h_i: agent i の trend horizon、heterogeneous
- 行動: `a_{i,t} = sign(trend_{i,t}) if |trend_{i,t}| > θ_i else 0`
- ヘテロ性: h_i ~ DiscreteUniform[5, 50], θ_i ~ Uniform[0.5, 2.0]
- Free parameters (calibration target): ヘテロ性パラメータ範囲、λ

#### Model H: herding

- 各 agent i は観測ベクトル o_{i,t} から内部で社会信号を計算
- `social_{i,t} = mean(ā_{t-h_i^s:t})`
  - ā_τ = (1/N) Σ_j a_{j,τ-1} (前期の集約行動)
- 行動: `a_{i,t} = sign(social_{i,t}) with prob p_i, else uniform on {-1, 0, +1}`
- ヘテロ性: p_i ~ Uniform[0.6, 0.95], h_i^s ~ DiscreteUniform[5, 50]
- Free parameters (calibration target): p の範囲、h^s の範囲

#### 設計上の重要点

両機構とも、agent には MA や momentum 指標を**直接渡さない**。観測ベクトル(後述)から**内部で計算する**ことで、観察チャネルへの介入は「機構の入力源」を degrade するが「機構そのもの」は ablate しない構造になる。これが B2 ≠ A の核心。

### 3.3 観測ベクトル(B2 が A に化けない設計)

各 agent に毎時刻渡される観測ベクトル o_{i,t}:

| 要素 | 次元 | 内容 |
|------|------|------|
| 価格履歴 (raw) | L = 100 | p_{t-L:t} の log-return 系列 |
| 出来高履歴 | L = 100 | v_{t-L:t} |
| 集約行動履歴 | L = 100 | ā_{t-L:t} (=社会信号の raw source) |

すべて raw な時系列で、MA や momentum や rank などの加工特徴量は含まない。Model T は価格履歴から内部で trend を抽出、Model H は集約行動履歴から内部で社会信号を抽出する。

---

## 4. Stylized Facts battery

Cont (2001) と SG 文脈で焦点の SF を採用。drawdown は経路依存量のため除外。

| ID | SF | 測定方法 |
|----|----|----|
| SF1 | return autocorrelation の不在 | ACF(r_t, lag=1..10) の sum-of-squares |
| SF2 | absolute return autocorrelation の slow decay | |r_t| の ACF decay rate (fit power law to lag 1-50) |
| SF3 | heavy tails | excess kurtosis(returns) + Hill estimator (top 5% tail) |
| SF4 | volatility clustering | GARCH(1,1) パラメータ (α + β) |
| SF5 | leverage effect | corr(r_t, σ_{t+k}^2) for k=1..10, look for negative sign |
| SF6 | gain-loss asymmetry | inverse statistics: time-to-reach-positive-threshold ρ vs time-to-reach-negative-threshold -ρ の比 (Donangelo-style) |

SF5 と SF6 は SG の未再現 fact 候補なので、本実験で SF battery に含めることで「SG 本線で達成したい性質」を toy phase から測定 pipeline に組み込んでおく。

#### 留保2 の解決(v0.2): calibration target vs 独立検証量

- **calibration target = SF1-SF4**。SF-等価性(§5)はこの 4 次元上で定義する。
- **SF5/SF6 = post-equivalence 独立検証量**。calibration の目的関数には入れない。SF1-4 で等価性を確立した *後* に、SF5/6 が両モデルで何を示すかを独立に測る(SG 未再現 fact の toy phase 観測)。
- 含意: §5 の距離最小化・§6.1 の SF classifier 入力は **SF1-4(4 次元)** に揃える。SF5/6 を等価性判定に混ぜると、calibrate していない次元で T/H が分離し equivalence が人工的に落ちうるため除外する。
  - ⚠ **v0.2 暫定**: 「SF1-4 で等価なら主結果の解釈は SF1-4 battery 上に限定される」という scope 縮小(§15.3 と整合)。SF5/6 を verification に回す妥当性・閾値は留保の substance 議論で確定する。

---

## 5. SF-等価 calibration 手順

### 5.1 目標

両モデルの **SF1-SF4** feature 分布(留保2)が、両 SF classifier で区別不能(accuracy 50-55%)になるパラメータ点を見つける。SF5/SF6 は等価性確立後に独立検証量として測る(calibration には用いない)。

### 5.2 探索アルゴリズム(留保1 の解決: 相互等価性 anchor)

**留保1 の解決(v0.2)**: anchor は **相互等価性**。実データ(S&P500 等)への近接は anchor から外す。Model T を任意のリーズナブルな固定点に置き、Model H をその T に対する SF 距離最小化で calibrate する。これにより「両モデルがどれだけ現実に似ているか」ではなく「両モデルが互いに SF-等価か」だけを問う設計になる(主結果は SF-等価な (T,H) が IR で分かれるか、であって現実妥当性ではない)。

1. **Stage 1: anchor 固定(Model T)**
   - Model T を固定点 T* に置く: λ = 0.01、heterogeneity は §3.2 の既定レンジ(h_i ~ DiscreteUniform[5,50]、θ_i ~ Uniform[0.5,2.0])。
   - T* で M=1000 runs を生成し、SF1-4 feature 分布(基準分布)を確定する。実データ参照は行わない。
2. **Stage 2: Model H を T* へ calibrate(SF1-4 距離最小化)**
   - Model H の free parameter(p の範囲、h^s の範囲)を Bayesian Optimization (Optuna, GP surrogate, 500 trial) で動かす。
   - 各 trial で H を M=200 runs 生成し、**SF1-4 feature 空間**での T* 基準分布との Wasserstein 距離を最小化する。
   - 最小距離点を H* とする。
3. **Stage 3: 等価性事前検証**
   - (T*, H*) で M=1000 runs ずつ生成、両 SF classifier(§6、入力は SF1-4 / 生 return 系列)で 5-fold CV accuracy を計算。
   - 50-55%(§2.2 Pass)に入らなければ Stage 1-2 をやり直し(T* の固定点を変える、または H の探索空間を広げる)、または SF battery 修正(=主結果のスコープ縮小として明示記録、§14 Hard fail 経路)。
   - ⚠ **v0.2 暫定**: T* の「リーズナブルな固定点」の具体値・選定根拠、および H の探索空間の十分性は留保の substance 議論で確定する。

---

## 6. SF classifier 仕様 (等価性検証)

### 6.1 Summary-stat classifier
- 入力: **4 次元 SF feature vector (SF1-SF4)**(留保2: calibration target に揃える。SF5/6 は等価性判定に用いず独立検証へ回す)
- モデル: L2-regularized logistic regression
- 訓練: 5-fold CV、stratified
- 各 fold で 800 runs train / 200 runs test
- 出力: accuracy + AUC

### 6.2 Discriminator network
- 入力: 生 log-return 系列 r_{t-T_d:t}, T_d = 1000
- モデル: 1D-CNN (3 layers, kernel size 5, channels [16, 32, 64]) + global average pooling + 2-class linear head
- 訓練: Adam, lr=1e-3, batch size 32, epochs 20, early stopping on val acc
- 5-fold CV
- 出力: accuracy + AUC

両者ともに 50-55% であることが「SF-等価」の operational definition。

---

## 7. 介入仕様: 観察情報チャネル介入 (B2)

### 7.1 介入対象

観測ベクトル o_{i,t} の特定要素に対する graded degradation。**価格形成 process そのものには介入しない**(B1 を回避)、**agent の内部 decision rule にも介入しない**(A を回避)。

### 7.2 介入軸

| 軸 | 介入対象 | 期待される favored target |
|----|----|----|
| Trend masking | 価格履歴 p_{t-L:t} を degrade | Model T |
| Social masking | 集約行動履歴 ā_{t-L:t} を degrade | Model H |

両軸を独立に動かす(2D intervention space)。各 model は両介入に応答するが、応答曲線の形が異なる(と仮説する)。

### 7.3 Attenuation スキーム (4 種、比較対象)

各介入軸に対し、以下 4 スキームを独立に実装。介入強度 θ ∈ {0, 0.1, 0.2, ..., 1.0} を連続パラメータとして扱う。

| Scheme | 操作 | パラメータ意味 | Real-world counterpart |
|--------|------|----------------|------------------------|
| (a) Time aggregation | 時系列を Δt 刻みで平均化 | Δt = floor(θ · L) | ティック表示集約、低解像度チャート |
| (b) Low-pass filter | Butterworth filter、normalized cutoff f_c | f_c = (1-θ) · 0.5 | 短期変動の表示制限 |
| (c) Observation noise | Gaussian noise 注入、SNR 連続 | σ_noise = θ · σ_signal | ランキング display の noise/threshold |
| (d) Time delay | 観測の lag | lag = floor(θ · L) | ランキング更新遅延、停止板情報 |

各スキーム単独で動かし、結果を比較。robust な premise なら scheme に大きく依存しないはず。

### 7.4 実装上の注意

- θ = 0 (介入無し) と θ = 1 (完全 mask) の中間点が response curve の有効領域
- θ = 1 で機構が完全に止まらない設計にする(止まると ablation と同型)
  - 例: scheme (a) Δt = L だと履歴全体の平均しか見えない = 機構は微弱に動く
- 各 θ で M = 1000 runs

---

## 8. Response curve 設計

### 8.1 二種類の response (混同しないこと)

| 種類 | 定義 | 用途 |
|------|------|------|
| Susceptibility curve | 出力指標 y を θ の関数として θ ∈ [0, 1] で plot | 主たる識別特徴 |
| Post-intervention dynamics | θ を固定し、介入後 t = 1..K step の時系列 y_t を見る | 副次的特徴 |

### 8.2 出力指標 y

各 run で以下を測定:

| ID | 指標 | 集計 |
|----|------|------|
| Y1 | volatility | std(r_t) over 1000 steps post-intervention |
| Y2 | crash probability | P(min(r_t) < -3σ) over 1000 steps |
| Y3 | volume | mean(\|ED_t\|) over 1000 steps |
| Y4 | order imbalance persistence | ACF(ED_t, lag=1) |
| Y5 | leverage effect strength | corr(r_t, σ_{t+1}^2) |
| Y6 | recovery time after shock | time to return to pre-intervention volatility level after a controlled price shock |

(Y6 は post-intervention dynamics 系、Y1-Y5 は susceptibility curve の y 軸)

### 8.3 Susceptibility curve feature 抽出

各 (model, scheme, intervention軸, Y_i) について、θ ∈ {0, ..., 1.0} の susceptibility curve を生成し、以下 4 特徴を抽出:

- f1: 初期勾配 dY/dθ at θ = 0
- f2: 飽和水準 Y(θ = 1)
- f3: 半減点 θ such that Y(θ) = (Y(0) + Y(1)) / 2
- f4: 曲線下面積 ∫ Y(θ) dθ

IR classifier の入力 = (susceptibility curve features) × (出力指標 Y) × (介入軸) × (scheme)。

---

## 9. IR classifier 仕様

### 9.1 メイン classifier
- 入力: 8.3 の susceptibility curve features ベクトル
  - 4 特徴 × 5 (Y1-Y5) × 2 (trend/social) × 4 (schemes) = 160 次元 (full)
  - per-scheme version: 4 × 5 × 2 = 40 次元 (各 scheme 独立評価用)
- モデル: gradient boosting (XGBoost) + L2-regularized logistic regression (両方試す)
- 訓練: 5-fold CV
- 各 fold で 800 runs/condition train、200 test
- 出力: accuracy + AUC + per-scheme breakdown

### 9.2 比較対照: post-intervention dynamics classifier
- 入力: Y6 (recovery time) + 介入後 1000 step の (vol, vol, imbalance) 時系列の summary stats
- モデル: 同上 (XGBoost + LR)
- これは前回 v0 設計で「response curve」と呼んでた量。susceptibility curve とは別。
- どちらが分けるかも記録(susceptibility が勝てば理論的整合、dynamics が勝てば追加調査)

---

## 10. Null controls

### 10.1 Null Layer 1: T1 vs T1 異 seed (sanity)
- 同パラメータ点で seed だけ変えて 2 群生成
- 全 SF classifier、IR classifier で accuracy ≈ 50% を確認
- 失敗時: 実装バグ、データリーク、分析パイプラインの問題

### 10.2 Null Layer 2: T1 vs T2 同機構異パラメータ
- Model T を 2 つの異なるパラメータ点 (T1, T2) で 5.1 と同じ SF-等価 calibration
- IR classifier accuracy を測定
- SF baseline (50-55%) ± 10% 以内に収まることを期待
- 大きく超えた場合: 介入応答は機構ではなくパラメータ感応で群を分けている → 主結果の解釈に重大な留保

---

## 11. サンプルサイズと計算量

| 量 | 値 | 根拠 |
|----|----|------|
| Runs per (model, scheme, θ) | M = 1000 | tail statistic の variance 抑制、Hill estimator が安定する下限 |
| Run length | 11000 step (burn-in 1000 + measure 10000) | autocorrelation 構造の安定推定 |
| θ grid | 11 点 ({0, 0.1, ..., 1.0}) | curve fitting に十分 |
| Conditions | 2 model (T, H) × 2 軸 × 4 scheme × 11 θ + null × 2 layer | 約 360 (model, scheme, θ) cell + null |
| Total runs | ~360,000 | |
| 1 run の実時間 | 約 0.5 秒(目標)に最適化 | |
| 並列化 | embarrassingly parallel、~32 cores 想定 | |
| Wall time | ~2 hours (32-core full saturation) | |

(計算量は run の最適化に依存。Numba/Cython/Rust 実装で大幅短縮可能。Python 素朴実装だと 10x 以上時間がかかる。実装段階で profiling 必須)

---

## 12. 統計手順

### 12.1 推定
- すべての classifier accuracy は 5-fold stratified CV
- 信頼区間: bootstrap (B = 1000) で 95% CI
- per-scheme effect の比較: Cochran's Q test (4 scheme 間の一致性)

### 12.2 多重比較
- 4 scheme × 5 Y × 2 軸 = 40 cell の同時検定
- Holm-Bonferroni 補正で family-wise error rate を 5% に制御
- Pre-registered なので post-hoc subgroup analysis は禁止

---

## 13. Provenance / 再現性レイヤー

PRISM-original の dream の中で生き残る部分。本実験は監査可能・bit 再現可能な形で実施する。

### 13.1 仕様
- すべての run に対し以下を記録:
  - Git commit hash (実装コード)
  - 全パラメータの YAML config
  - RNG seed (Numpy + Python random + Torch RNG 全部)
  - 実行時刻 (UTC ISO 8601)
  - 環境スナップショット (Python version, key library versions、`pip freeze`)
  - 出力データの SHA256 hash
- メタデータは run ごとに sidecar JSON、全体は `run_index.parquet` で管理
- 設定管理: Hydra (composable YAML)
- ワークフロー: Snakemake または Nextflow で DAG として記述

### 13.2 再現可能性宣言
- 任意の cell について、ハッシュから run を bit 単位で再生成できることを保証
- 公開時にはコード + config + seed 一式を Zenodo に DOI 付きで deposit

---

## 14. Pre-registered decision tree (再掲)

実験完了後、以下を機械的に判定。

```
1. Null Layer 1 (T1 vs T1 異 seed) 両 classifier ≈ 50% ?
   No → 実装または分析の不整合、修正後やり直し
   Yes ↓

2. SF 等価性: T vs H 両 SF classifier 50-55% ?
   Hard fail → calibration 不十分、Stage 1-2 やり直し
   Soft fail → 続行、結果解釈に注記
   Pass ↓

3. Null Layer 2 (T1 vs T2): IR classifier accuracy ?
   > 65% → 介入応答はパラメータ感応の可能性、主結果に重大留保
   50-60% → 期待通り、続行
   ↓

4. 主結果: T vs H IR classifier accuracy across 4 schemes
   3+ scheme で ≥ 75% → GO: premise 支持、論文化
   1-2 scheme で ≥ 75% → PARTIAL: scheme 依存、追加調査
   0 scheme → PIVOT: premise 不支持、PRISM obit 完了、SG 集中
```

---

## 15. Limitations (honest scope)

本実験で立った結果が言わないこと:

1. **PRISM-original は蘇生しない**。本実験は toy controlled lab で premise を確認するもの。real-world deployment(規制当局向けインフラ)の壁(counterfactual ground truth 欠如、Guerini-Moneta lineage 占有)は別問題。
2. **General claim は立たない**。本実験は (T, H) 1 ペアでの検証。他の機構ペア (e.g., fundamentalist vs noise trader、Brock-Hommes 系) で同じ結果が出る保証は無い。一般化には追加実験が必要。
3. **SF battery 依存**。等価性は SF1-SF4 上で定義される(留保2、§4 末尾)。他の SF(SF5/6 自体、Epps effect、market impact 関数、intraday seasonality 等)を含めると等価性が崩れる可能性。pre-register された結論は「この SF1-4 battery 上で等価な (T, H) は IR で分けられる」まで。SF5/6 は等価性確立後の独立検証量であって calibration target ではない。
4. **Linearity / single asset**。多資産・cross-asset spillover・非定常レジームには結果が転移しない可能性。
5. **Real-world counterpart の operational gap**。B2 の 4 scheme は real-world 規制(disclosure、display rules)に philosophically transferable だが、real markets は人間+algo の混合系で behavioral econ 的に messy。toy の B2 で立った IR > SF が real markets で立つ保証は別。

---

## 16. Timeline & milestones

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | 市場 + Model T + Model H 実装、SF 測定 pipeline、provenance layer | Working simulator, 1 run/sec target |
| 2 | SF-等価 calibration (Stage 1-2) | (T*, H*) パラメータ点 |
| 3 | SF classifier 構築 + 等価性検証 (Stage 3)、null layer 1 | 等価性 pass/fail 判定 |
| 4 | Null layer 2 (T1 vs T2) calibration + 介入実装 (4 scheme × 2 軸) | Intervention runner |
| 5 | Response curve 生成 (full sweep)、susceptibility feature 抽出 | All susceptibility data |
| 6 | IR classifier 訓練、null 検証、主結果集計 | All accuracy numbers |
| 7 | Robustness check、解釈、writeup draft | Paper draft v0 |
| 8 | 内部レビュー、SCSLab 陳教授との議論、修正 | Reviewable draft |

**実時間見積もり: 6-8 週間 (フルタイム相当)**。Yuito の他プロジェクト(PCG 内部、SG 本線、JFWE)との並行で考えると、実暦時間は 12-16 週間。

最初に書いた「1 週間」は minimum triage version の見積もりで、フル設計に拡張された今の見積もりではない。当初見積もりから大幅にスコープが膨らんだことを認識しておく。

---

## 17. SG 本線への接続 (dual-use 設計)

本実験の以下のコンポーネントは、後の SG 本線研究で再利用する:

| コンポーネント | SG 本線での用途 |
|----|----|
| SF battery (SF1-SF6) | SG が leverage effect / gain-loss asymmetry を内生発露するかの測定基準 |
| SF-等価 calibration pipeline | SG vs 競合機構(例: Franke-Westerhoff)の SF-同等性検証 |
| Two SF classifier | SG の「ノブを足さず」主張を defensible にする測定 |
| Observation channel framework | SG の cognitive world にも同型の介入を適用可能 |
| Provenance layer | SG paper の reproducibility 保証 |

つまり本実験は **PRISM obit + SG harness 整備の同時進行**。これが timeline 投資を merit ベースで正当化する追加根拠。

---

## Appendix A: パラメータ表

(実装着手時に確定)

## Appendix B: 出力スキーマ

(実装着手時に確定)

## Appendix C: 参考文献

- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. Quantitative Finance, 1(2), 223-236.
- Katahira, K., Chen, Y., Hashimoto, G., Okuda, H. (2019). Development of an agent-based speculation game for higher reproducibility of financial stylized facts. arXiv:1902.02040.
- Guerini, M., Moneta, A. (2017). A Method for Agent-Based Models Validation. Journal of Economic Dynamics and Control.
- Nagy, P., et al. (2025). LOB-Bench: Benchmarking Generative AI for Finance. ICML 2025.
- Donangelo, R., et al. (関連 inverse statistics papers, 確定後追記)
- Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.

---

## 改訂履歴

- v0.1 (2026-06-05): 初版 draft、PRISM 撤退判定後の真・PRISM toy 設計。留保 1/2 未解決。
- v0.2 (2026-06-08): 留保 1/2 を default で解決。
  - **留保1 → 相互等価性 anchor**: Model T を固定点 T* に置き、Model H を SF1-4 距離最小化で calibrate(§5.2)。実データ(S&P500)参照を anchor から除去。
  - **留保2 → SF1-4 を calibration target、SF5/6 を post-equivalence 独立検証量**(§4 末尾、§5.1、§6.1)。SF classifier 入力を 6→4 次元に変更。
  - §2(仮説・判定基準)/§14(decision tree)は不変。
  - ⚠ **未確定(留保 substance、後日議論 → 変更時 v0.3)**: T* の具体固定値と選定根拠、Model H 探索空間の十分性、SF5/6 を verification に回す妥当性/閾値。これらは §4-§6 に「v0.2 暫定」として inline マーク済み。