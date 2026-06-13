# YH006_1 (Phase 2) — SPEC v2.0

| 項目 | 値 |
|---|---|
| Version | 2.0 |
| Status | Draft (実装前最終) |
| Phase 1 reference | `experiments/YH006/SPEC.md` v1.3, `README.md` (Phase 1 完了状態) |
| Successor | YH006_2 (LOB で論文1+2 完全再現), YH007 (SOSG-on-LOB) |

---

## 0. Scope と唯一の問い

**Phase 2 (YH006_1) の唯一の問い**:

LOB 環境で観察された `corr(|ΔG|, h)` の wealth × world interaction (Phase 1 で Pearson −0.27) は、Speculation Game の `q_i = ⌊w_i / B⌋` 経路 ── 口座残高が注文サイズに伝播する経路 ── に causal に起因するか。

**Phase 2 から外すもの**:

- 2019 paper Fig 11/12/13 (asymmetric time scales / leverage effect / gain-loss asymmetry) の再現や評価 → YH006_2 で扱う
- SOSG (Self-Organized SG) 関連の実験 → YH007 で扱う
- N scaling 補遺 (N=1000 aggregate Pareto, etc) → 別補遺
- C1 (FCN-only baseline) → Phase 1 で役目を終えた
- MMFCN 流動性 sensitivity scan → proposal 用の保険として温存、Phase 2 の implementation に入れない
- 状況依存 q 規則 (Kelly, prospect theory, etc) → §11 Future work で言及のみ

---

## 1. Background framing

### 1.1 SG の核心主張 (Katahira 2019, Katahira-Chen 2020)

Speculation Game は、トレーダーの口座残高分布が往復取引を通じて内生的にべき乗則 (Pareto) を生成する ABM である。volatility clustering の起源は dynamic-wealth layer ── すなわち口座残高のヘテロ性が注文サイズのヘテロ性に伝播し、大単元/小単元の clustering として時間軸の分散構造を生む ── にあると主張されている。

### 1.2 SG の implementation 上の限界

Katahira モデルは需給集計型 (aggregate-demand) の価格更新 `Δp = (1/N)Σ a_i q_i` を採用しており、現実の取引所が持つ注文板 (Limit Order Book; LOB) の摩擦 ── スプレッド、スリッページ、約定不確実性 ── を捨象している。SG-on-LOB の実装は YH006 Phase 1 で初めて行われたが、LOB 摩擦が SG の dynamic-wealth 機構をどう変質させるかは未検証である。

### 1.3 Phase 1 で得た F1

SG decision rule を PAMS 0.2.2 (Hirano-Izumi 2023) の tick-scale LOB 環境に移植し、世界軸 (aggregate vs LOB) と初期 wealth 分布軸 (uniform vs Pareto α=1.5) の 2×2 で実験した結果、`corr(|ΔG|, h)` (funnel 構造の指標) に世界 × wealth の有意な交互作用が観察された (Phase 1 単 trial: Pearson −0.27)。

### 1.4 Pareto 初期分布の役割 ── probe としての位置づけ

本研究で初期 wealth を Pareto 分布で投入する設計は、現実の wealth 分布を再現することが目的ではない (Katahira モデルは uniform 初期から Pareto tail を内生的に生成する)。目的は、SG の emergent な wealth dynamics 機構が LOB 摩擦下でも動作するかを試す probe である。aggregate 環境では SG の機構が初期 Pareto を流すと予測される。LOB 環境で初期 Pareto が dynamics に残存するならば、それは LOB 摩擦が SG の core mechanism を阻害している signature となる。F1 はその signature の候補である。

---

## 2. 仮説空間と ablation の predictive footprint

| 仮説 | 機構 | A1 (q 固定) で予測 | A3 (lifetime cap) で予測 |
|---|---|---|---|
| **A: q-pollution** | 初期 Pareto wealth が LOB の低 turnover で persist し、`q = ⌊w/B⌋` 経由で注文単元数のヘテロ性が agent 集団に残存。これが round-trip 損益の桁違いスケールとして funnel 構造を pollute する | interaction 消失 (q heterogeneity を切れば pollute が消える) | interaction 縮小 (強制 substitute で初期分布の persistence が壊れる) |
| **B: strategy selection** | 上位 wealth agent が選択的に長 / 短 horizon の round-trip を取る (戦略テーブルが wealth と相関) | 変化なし (戦略選択は q 経路と独立) | 変化なし or 部分縮小 |
| **C: fill asymmetry** | 大 q order ほど LOB で fill されにくく、wealth 依存的に約定パターンが変わる | 部分縮小 (q を均すと約定率の wealth 差は残るが |ΔG| スケール差は消える) | 変化なし |

A1 と A3 が両方効く → **A**。A1 だけ効く → A だが lifetime persistence は副次的。A1 が効かず A3 だけ効く → C 的。両方効かない → **B** ないし未知の機構。

---

## 3. 実験 matrix

各条件 100 trial を独立 seed で実行 (seed = 1000+i, i ∈ [0, 100))。

| ID | world | wealth init | q rule | lifetime | 役割 |
|---|---|---|---|---|---|
| C0u | aggregate (Eq.3) | uniform `U[B, B+100)` | `⌊w/B⌋` | 通常 | aggregate baseline |
| C0p | aggregate | Pareto α=1.5 | `⌊w/B⌋` | 通常 | aggregate Pareto |
| C2 | LOB (PAMS) | uniform | `⌊w/B⌋` | 通常 | Phase 1 LOB main |
| C3 | LOB | Pareto α=1.5 | `⌊w/B⌋` | 通常 | Phase 1 LOB Pareto |
| **C2_A1** | LOB | uniform | `q = q_const` | 通常 | A1 ablation |
| **C3_A1** | LOB | Pareto α=1.5 | `q = q_const` | 通常 | A1 ablation (主役) |
| **C3_A3** | LOB | Pareto α=1.5 | `⌊w/B⌋` | `τ_max` cap | A3 ablation |

- `q_const` の決定: Appendix A.1 (pilot 5 trial の `median_{t,i}(q_i(t))` のアンサンブル median)
- `τ_max` の決定: Appendix A.2 (pilot で C3 の agent lifetime 中央値の 0.5 倍を初期値、必要に応じ調整)
- 共通パラメタ: N=100, M=5, S=2, B=9, C=3, T (sim length) は Phase 1 と同一
- LOB 条件は MMFCNAgent 流動性層を Phase 1 と同じ設定で併走

---

## 4. 計測指標

### 4.1 主指標 (interaction の robustness)

`corr(|ΔG|, h)` を 3 種の相関係数で並走計算する:

- ρ_P (Pearson) — Phase 1 互換、artifact 検出用
- **ρ_S (Spearman)** — 主指標
- τ_K (Kendall) — 補助、外れ値最頑健

各条件で 100 trial 分の値を ensemble。

### 4.2 Funnel 構造の直接計測 (heteroscedasticity 直接測定)

Pearson に依存しない funnel 強度の指標:

- **Bin variance**: h を log-equal な K=15 ビンに切り、各ビン内で `Var(log|ΔG|)` を計算。h と bin variance の Spearman 相関 → これが funnel 本体 (heteroscedasticity の単調性)
- **Quantile regression slope**: τ ∈ {0.10, 0.50, 0.90} で h → ΔG の quantile slope を推定。`slope_{0.90} − slope_{0.10}` が funnel 開き度の定量化

### 4.3 Timescale sensitivity (Phase 1 の弱点を潰す)

F1 がタイムスケール短すぎる artifact である可能性を排除する:

- **Half-time interaction**: 各 trial の round-trip を時刻順に半分に分割し、前半と後半で別々に Spearman ρ(|ΔG|, h) を計算。後半で interaction が縮小していれば「初期分布の流れ」が観察される。完全に流れていれば後半で interaction が消える
- **Initial wealth correlation decay**: agent ごとの `corr(w_init, w(t))` を時刻 t = T/10, 2T/10, …, T で計測。`corr` が 0.5 になる時刻 (半減期) を condition 別に算出。LOB > aggregate なら persistence の定量証拠

### 4.4 機構の中間予測 (chain の link 検証)

仮説 A の chain がどこで効いているかを解像度高く見る:

- **Agent lifetime 分布**: 各 agent が市場に滞在した step 数。C2 vs C3 で比較。仮説 A なら C3 で平均 lifetime が長い
- **Wealth persistence**: agent ごとに `w_init` と `w_final` の Spearman 相関。C3 で高いはず
- **Forced retirement rate**: `wealth < B` で退場した agent の単位時間あたり数。仮説 A なら C3 で低い
- **Order size persistence**: agent ごとの `q_i(t)` の時間平均と分散。C3 で agent 間 variance が大きく、agent 内時間 variance は小さい (= 個体差が時間で固まっている)
- **Round-trip 開始時 wealth と horizon の joint distribution**: 仮説 B 検出用。上位 wealth で horizon 分布が偏っていれば B

### 4.5 Plan B 用先取り指標 (S1 段階で同時計測)

(β/γ シナリオに備え、Phase 1 データの再分析時に同時計測):

- `corr(w_init, h)` — 仮説 B 検出用
- `Skewness(ΔG | h_high) − Skewness(ΔG | h_low)` — funnel の左右非対称性
- ΔG 分布の Hill exponent (tail index) の condition 間差

---

## 5. 統計設計

### 5.1 Seed 管理

各条件 100 trial を独立 seed で実行 (paired seed は採用しない)。実装上の単純さと条件比較の頑健性を優先。100 trial 規模では検出力は十分。

### 5.2 信頼区間

trial-level の Spearman ρ から **percentile bootstrap (resample = 10,000)** で 95% CI を構成。Fisher-z 変換は重尾分布で破綻するため不採用。

### 5.3 条件間比較

- **2 条件比較** (例: C3 vs C3_A1): Mann-Whitney U test (両側、サンプルサイズ各 100)
- **interaction の有意性** (例: `[ρ(C3) − ρ(C2)] − [ρ(C3_A1) − ρ(C2_A1)]` が 0 か):
   - 各条件 100 trial の値から bootstrap で interaction 推定値の経験分布を構成
   - 経験分布の 95% CI が 0 を含まないかつ符号が −0.27 を打ち消す方向 → A1 効果有意

### 5.4 多重比較

主指標 (Spearman) 1 + ablation 比較 2 (A1, A3) + funnel 直接指標 1 (bin variance) で **4 系統**。Bonferroni 補正で α = 0.05 / 4 = 0.0125 を主検定の閾値とする。

### 5.5 機構主張に必要な統計的整合性

仮説 A を主張するためには、以下の **すべて** が成立する必要がある:

1. F1 が指標横断で robust (Pearson, Spearman, Kendall, bin variance がすべて同方向)
2. F1 が timescale で安定 (前半/後半で大きく縮小しない、もしくは縮小が aggregate と同程度)
3. A1 ablation で interaction が **50% 以上** 縮小し、CI が 0 を含まない
4. A3 ablation でも interaction が部分縮小
5. 中間予測 (lifetime, wealth persistence, forced retirement) が C3 で C2 より強い、と仮説 A の chain と整合

任意の 1 点でも崩れた場合、機構主張は弱まる (§9 plan B に従い解釈を調整)。

---

## 6. 成功基準 (KPI)

| level | 基準 |
|---|---|
| **L1 (最低限)** | F1 が Spearman/Kendall/bin variance のうち **少なくとも 2 つ** で符号と桁が一致 (= Pearson の重尾 artifact ではない) |
| **L2 (機構の方向性)** | A1 ablation で interaction の絶対値が 50% 以上縮小、bootstrap 95% CI で有意 |
| **L3 (chain の検証)** | A3 ablation でも interaction が部分縮小 (≥30%) + 中間予測 (lifetime, wealth persistence) が仮説 A と整合 |
| **L4 (proposal 級)** | L1+L2+L3 すべて成立、かつ funnel 直接指標 (bin variance) でも同じ機構解釈が成立、かつ timescale 解析で interaction が long-run で消えない (もしくは半減期が aggregate より有意に長い) |

L2 まで届けば proposal の核として機能する。L4 まで届けば Chen lab に対して相当強いカード。

---

## 7. Runtime 試算

| 段階 | 単位 | 試算 |
|---|---|---|
| Phase 1 単 trial × 1 条件 | X 分 | Phase 1 README から実測値を要確認 |
| Phase 2 全実験 | 7 条件 × 100 trial = 700 X 分 | 並列化前 |
| 並列化 (multiprocessing N_core=8) | ~ 90 X 分 | trial 単位の並列 |
| X = 5 分の場合 | 7.5 時間 | 1 マシン 1 晩 |
| X = 30 分の場合 | 45 時間 | 段階的実行推奨 |

X が大きい場合は trial 数を 50 に落として spike runtime → variance 評価 → 必要なら 100 に拡張する段階実行。

S1 (Phase 1 データ再分析) は新規 simulation 不要で **runtime ≈ 0**。最優先で実行する。

---

## 8. 出力仕様

### 8.1 ディレクトリ構造

```
experiments/YH006_1/
├── SPEC.md                 # 本書
├── README.md               # 結果サマリ
├── code/
│   ├── run_experiment.py   # 主 runner
│   ├── ablation.py         # A1/A3 実装
│   ├── analysis.py         # 指標計算
│   ├── stats.py            # bootstrap, MW-U, etc
│   └── plots.py            # figure 生成
├── pilot/
│   ├── q_const_calibration.json
│   └── tau_max_calibration.json
├── data/
│   ├── C0u/, C0p/, C2/, C3/, C2_A1/, C3_A1/, C3_A3/
│   │   └── trial_{seed}.parquet     # round-trip 単位の生データ
│   └── ensemble_summary.parquet     # trial-level 集計値
├── outputs/
│   ├── tables/
│   │   ├── tab1_correlations.csv
│   │   ├── tab2_ablation_effects.csv
│   │   └── tab3_intermediate_predictions.csv
│   └── figures/
│       ├── fig1_funnel_scatter.png
│       ├── fig2_ablation_bars.png
│       ├── fig3_bin_variance_heatmap.png
│       ├── fig4_lifetime_persistence.png
│       ├── fig5_timescale_decay.png
│       └── fig6_a3_effect.png
└── logs/
    └── runtime/, errors/
```

### 8.2 Figure list

- **Fig.1**: 4 条件 (C0u/C0p/C2/C3) の funnel scatter (h vs ΔG, log-log) + Spearman ρ 注釈
- **Fig.2**: 全 7 条件の Spearman ρ(|ΔG|, h) bar chart with 95% CI
- **Fig.3**: bin variance heatmap (h-bin × condition) で funnel 直接構造の可視化
- **Fig.4**: 中間予測 (agent lifetime CDF, wealth persistence scatter) の C2 vs C3 比較
- **Fig.5**: timescale 解析: `corr(w_init, w(t))` の time decay、condition 別
- **Fig.6**: A3 ablation の効果 (C3 vs C3_A3 の interaction 比較)

### 8.3 Table list

- **Tab.1**: 全条件の Pearson/Spearman/Kendall 値 + 95% CI
- **Tab.2**: ablation 効果 (`Δ_A1`, `Δ_A3`) と Mann-Whitney U の p 値
- **Tab.3**: 中間予測 (lifetime mean/median, wealth persistence ρ, forced retirement rate) を condition 別

---

## 9. 段階的実行 (Stage)

| Stage | 内容 | 完了条件 | 新規 sim |
|---|---|---|---|
| **S1** | Phase 1 データ (C2/C3 既存 trial) を Spearman/Kendall/bin variance/quantile regression/timescale で再分析 | F1 が指標横断で robust か判定 (= L1 達成判定 + plan A/B 分岐) | 不要 |
| **S2** | C0u/C0p の 100 trial ensemble (aggregate baseline、安価) | aggregate side の seed 安定性確認 | 必要 |
| **S3** | C2/C3 の 100 trial ensemble (LOB ベースライン) | LOB side の seed 安定性確認、F1 ensemble 確定 | 必要 |
| **S4** | A1 ablation 実装 + pilot 1 trial (C3_A1) で挙動確認 + `q_const` calibration | q_const 動作正常性 | pilot のみ |
| **S5** | C2_A1 / C3_A1 の 100 trial ensemble | L2 判定 | 必要 |
| **S6** | A3 ablation 実装 + `τ_max` calibration + C3_A3 100 trial | L3 判定 | 必要 |
| **S7** | 中間予測の集計、図表作成、README 執筆 | L4 判定 + proposal 用素材完成 | 不要 |

**S1 を最優先**。新規 simulation 不要で 2-3 日で完了する。ここで F1 が指標選定 artifact だと判明したら S2 以降の意味が変わる (§9 plan B に従う)。S1 をスキップして S2 以降に入るのは砂上の楼閣。

---

## 10. Plan B 分岐

S1 結果による分岐:

| シナリオ | Pearson | Spearman/Kendall | bin variance | timescale | 解釈 | 次の手 |
|---|---|---|---|---|---|---|
| **(α)** | 動く | 動く | 動く | 安定 | F1 は本物 | S2-S7 を本 SPEC 通り実行 |
| **(β)** | 動く | 動かない | 動かない | - | Pearson 重尾 artifact、funnel は LOB/Pareto で不変 | plan B-3 (positive finding として framing) |
| **(γ)** | 動く | 動かない | 動く | - | funnel の分散構造のみ変質、Pearson は別理由で動く | 主指標を bin variance に置換、SPEC 継続 |
| **(δ)** | 動く | 動く | 動く | 後半で消失 | LOB は aggregate より流れが遅いだけ | 半減期を定量化、「LOB-aggregate の時間スケール差」を主結果に |
| **(ε)** | 動く | 動く | 動く | 安定 | 機構は本物だが A1 で消えない | 仮説 B か未知の機構、状況依存 q (§11) に切替の検討 |

### 10.1 plan B-1 (シナリオ γ): 指標を変えて F1 を救う

bin variance/quantile slope で interaction が出るなら、主指標を入れ替えて元の SPEC を継続。「Pearson は重尾で破綻、Spearman も中央傾向しか測らない、funnel の本質である分散の変質を bin variance で捉える」が proposal の見出しになる。

### 10.2 plan B-2 (シナリオ β + 機構候補温存): 別の wealth-conditional な歪みを探す

F1 interaction が消えても、Pareto wealth が LOB で何らかの distortion を起こしている可能性は残る:

- `corr(w_init, h)` — 上位 wealth が選択的に長 horizon の round-trip
- `Skewness(ΔG | h_bin)` の condition 間差 — funnel の左右非対称性
- ΔG 分布の Hill exponent の condition 間差 — heavy-tail の太さ自体
- agent lifetime と round-trip 数の joint distribution の condition 間差

これらは S1 で同時計測する (§4.5)。S1 完了時点で次の interaction 候補が見えていれば乗り換える。

### 10.3 plan B-3 (シナリオ β + 主張切り替え): positive finding として書く

すべての wealth-conditional 指標で interaction が出ない場合、negative result ではなく以下の positive finding として書ける:

> 「Speculation Game の dynamic-wealth 機構は LOB friction 下でも頑健に funnel 構造を再現する。aggregate 世界の funnel 強度と LOB 世界の funnel 強度に有意差はなく、Pareto 初期分布の影響も両世界で類似である。これは SG の機構が implementation-invariant であることを示し、Katahira 2019 の核心主張を強化する」

これは Chen lab proposal としても十分成立する。

### 10.4 plan B-4 (シナリオ δ): timescale 解析を主結果に

「LOB friction が初期 wealth 分布の persistence を有意に伸ばす」という定量的 claim に切り替える。半減期を condition 別に提示し、仮説 A の chain (LOB friction → 約定率低下 → lifetime 延長 → persistence) の **間接的検証** として位置付ける。直接の causal identification は将来研究に譲る。

### 10.5 plan B-5 (シナリオ ε): 状況依存 q への切替を検討

A1 で消えない場合、機構は q heterogeneity ではなく戦略選択性 (仮説 B) か未知の経路。**Phase 2 の scope では仮説 B の identification は行わない** (実装が大きすぎる)。Phase 2 は「仮説 A 不支持」の結論で閉じ、将来研究 (§11) として状況依存 q または戦略テーブル ablation を提案する。

---

## 11. Future work (proposal 用)

### 11.1 状況依存 q 規則 (post-Phase 2)

Phase 2 の ablation 設計 (q_const) は、口座残高 → 注文サイズ伝播経路の causal な役割を identify することを目的とし、現実のポジションサイジングを模倣するものではない。実際のトレーダーは戦略の確信度や損益履歴に応じて発注量を調整する。Phase 2 の結果を踏まえ、状況依存的 sizing 規則を組み込んだ拡張は自然な次ステップ:

- **戦略確信度依存**: 複数戦略の一致度や過去勝率で q を調整
- **Kelly criterion 型**: 期待リターンと variance に基づく最適 sizing
- **Prospect theory 統合** (Kahneman-Tversky, λ≈2.25): 含み損益状態で risk attitude が変動 (含み益 → risk-averse、含み損 → risk-seeking)

これらは SG が未再現の gain/loss asymmetry と leverage effect の機構解明への直接ルートとなる。これらの未再現は元々「SG が price-direction symmetric だから」と説明されているが、「SG が q を口座残高だけで決めているから」と読み替えられる可能性が Phase 2 の結果次第で開く。

### 11.2 SOSG-on-LOB (YH007) との接続

Phase 2 で「LOB friction が agent lifetime を伸ばし wealth persistence を高める」(仮説 A 支持) が示された場合、SOSG (Self-Organized SG, Katahira-Chen-Akiyama 2021) の outflow rate が LOB で抑制されることが直接の含意となる。SOSG は inflow / outflow の time-averaged balance に依存するモデルであり、outflow 抑制は self-organized criticality 成立を脅かす。Phase 2 の結果は SOSG-on-LOB 設計の必須前提条件となる。

逆に Phase 2 で仮説 A が不支持の場合 (シナリオ β/ε)、SOSG-on-LOB はより clean に成立する見込みがあり、YH007 への移行がより自然になる。**いずれの結果でも Phase 2 は次研究の前提を作る**。

### 11.3 MMFCN 流動性 sensitivity (proposal の保険)

Phase 2 の F1 機構が PAMS-specific でないことを示すため、MMFCN 流動性層の order rate / spread を 1 パラメタで scan しておくことが望ましい。Phase 2 の implementation には入れないが、proposal 執筆時に追加実験として実施を検討する。

---

## 12. Out of scope (再確認)

| 項目 | 扱い |
|---|---|
| Fig 11/12/13 (asymmetric time scales / leverage / gain-loss) の再現 | YH006_2 |
| SOSG (N の自己組織化) | YH007 |
| 状況依存 q (Kelly, prospect theory) | Future work |
| MMFCN 流動性 sensitivity scan | proposal 用追加、Phase 2 の実装外 |
| N scaling 補遺 (N=1000) | 別補遺 |
| 戦略テーブル ablation (仮説 B 直接検証) | Phase 2 不支持時の next step |
| C1 (FCN-only baseline) | Phase 1 で完了、Phase 2 不要 |

---

## Appendix A. Pilot 手順

### A.1 `q_const` の決定

**目的**: A1 ablation で全 agent の注文単元数を固定する際の値。

**方針**: Pareto α=1.5 の重尾下で平均は不安定なため、典型 agent の活動量を保存する目的で **中央値ベース** で決定する。具体には:

1. C3 (LOB + Pareto α=1.5) の設定で 5 trial の pilot run を実行 (seed = 9001..9005)
2. 各 trial で `median_{t,i}(q_i(t))` を計算 (全時刻 × 全 agent の `q` の median)
3. 5 trial 分の median のさらに median を取る → これを `q_const` として固定

**フォールバック**: pilot が偏った値 (例: q_const = 1) を出した場合、パラメタ B の妥当性を再検討する。`q_const ≥ 2` を minimum requirement とする。

**出力**: `pilot/q_const_calibration.json` に 5 trial 各 median と最終 `q_const` を記録。

### A.2 `τ_max` の決定

**目的**: A3 ablation で agent を強制 substitute する step 数。

**方針**:

1. C3 setup の 5 trial pilot run で agent ごとの lifetime (= retirement step − birth step、または sim 終了時点までの滞在 step 数) を集計
2. agent lifetime 中央値 `L_50` を計算
3. `τ_max = round(0.5 × L_50)` を初期値として採用
4. C3_A3 の pilot 1 trial を実行し、強制 substitute が trial 全体で 50 件以上発生していることを確認 (発生数が少なすぎると ablation が機能しない)
5. 不足の場合は `τ_max` を 0.4 × L_50, 0.3 × L_50 と段階的に下げる

**出力**: `pilot/tau_max_calibration.json` に lifetime 統計、最終 `τ_max`、強制 substitute 発生数を記録。

### A.3 Pilot 実行の運用

両 calibration は S4 (A1) と S6 (A3) の **直前** に実行する。Phase 1 の C3 既存データから lifetime 統計を取れる場合はそれを優先 (新規 sim 不要)。

---

## Appendix B. 実装上の注意点 (要 Claude Code 確認事項)

実装に進む前に Claude Code 側で以下を確認・report すること:

1. Phase 1 (`experiments/YH006/`) の round-trip 単位データ schema (どの列が `|ΔG|`, `h`, `w_init`, `agent_id` に対応するか)
2. Phase 1 の sim 長 T の正確な値、および timescale 解析で「前半/後半」を切る基準時点
3. PAMS 0.2.2 の MMFCNAgent 設定が Phase 1 で何だったか (流動性層の再現に必須)
4. `ablation.py` で q を上書きする場所 (Katahira 2019 Eq.1 の対応コード位置)
5. `τ_max` cap を実装する際、agent の active limit order を強制 cancel するか (要件: 必ず cancel してから substitute、Phase 1 の forced liquidation ロジックと共通化)

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (引き継ぎ) | Phase 1 完了状態の SPEC、Phase 2 は paired seed 方式で観察拡張中心 |
| v2.0 (本書) | ablation を主軸に再設計、timescale sensitivity を追加、Pearson 単独依存を廃止、plan B 分岐を明文化、q_const と τ_max の pilot 手順を appendix 化 |