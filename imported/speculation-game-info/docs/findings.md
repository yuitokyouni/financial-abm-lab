# Findings: 各実験で確認済みの事項

**目的**: 新しい YH を着手する前にここを grep / 通読することで、前の実験で既に確認済みの数値 / 設計判断 / 失敗ルートを再度踏まないようにする。

**書き方の方針**:
- 各 YH 完了時にセクションを追記する。
- **確認済み事実** (数値、定性的結論、設計判断) と **次フェーズで検証すべき仮説 / 保留事項** を分けて書く。
- 再現可能な parameter と seed は明記 (再検証できるように)。

---

## YH001 — Cont-Bouchaud Percolation (完了, 2025-04)

**確認済み**:
- パーコレーション cluster-size 分布が power-law (τ ≈ 2.5 付近) を再現、return が heavy tail。

**保留**: 特になし (シリーズの導入として完了)。

---

## YH002 — Lux & Marchesi (2000) Volatility Clustering (完了, 2026-04)

**使用 parameter**: Parameter Set I (p. 689): `N=500, ν1=3, ν2=2, β=6, Tc=10, Tf=5, α1=0.6, α2=0.2, α3=0.5, pf=10, σμ=0.05, Δt=0.01, Δp=0.01`。Parameter Set II–IV は実装外。

**確認済み** (seed=42, T=20000):
- **臨界値 z̄**: Appendix A の (cond 1) を解いて `z̄ = 0.660`、論文本文 0.65 と 0.01 の誤差で一致。on–off intermittency の分岐点が再現。
- **Hill tail index**: 10% tail で `α̂_H = 1.92` が論文中央値 1.93 とほぼ完全一致、5% tail 2.40 / 2.5% tail 2.59 も論文 range (1.26, 2.64) 内。
- **Excess kurtosis**: T=4000 で 10.19, T=20000 で 16.66 (論文 Set I の Table 2 値 135.73 には届かないが、kurtosis は単一 seed での最大級 burst 出現頻度に強く依存し、論文も中央値のみ報告)。
- **ACF**: raw returns lag 1-2 に小さな負スパイク (論文脚注 s と整合)、squared / absolute は lag 300 まで緩やかに減衰、論文 Fig. 3 と同形状。

**失敗ルートのメモ**:
- **ADF**: T=20000 では検出力が高く unit root を棄却 (`ADF stat = -87.0`)。論文 Table 1 の "non-rejection" は **500-obs subsample 設計由来の低検出力** ゆえで、母過程は stationary。一括 T=20000 で走らせるなら ADF を再現基準にしない (memo.txt に記載)。
- **価格更新の確率規約**: opinion/strategy 個体遷移は `rate × Δt` 形式だが、価格上昇/下降確率 `π_↑p, π_↓p` は `β(ED + μ)` をそのまま 1 ステップ確率として使う (論文 p.687 脚注 n: cents 単位で 100 割が組み込み済)。混同すると価格応答が 100 倍ずれる。

**保留**: Parameter Set II-IV / 適応 Δt 切り替え / Lux 1995, Lux-Marchesi 1999 Nature の定式化は意図的に除外。

---

## YH003 — Challet & Zhang (1997) Minority Game (完了, 2026-04)

**使用 parameter**: `(N, S) = (101, 2)` for σ²/N 相図、`(1001, 5)` for 詳細解析。`M ∈ [1, 12]`, `T_burn = 500-1000, T_measure = 5000-10000`, ensemble 10 trial (Panel 1)。

**確認済み** (seed=42):
- **σ²/N 相図 (Panel 1)**: N=101 の離散サンプリングで `σ²/N` 最小値 = **0.268 at α = 0.634 (M=6)`、典型的な U 字 (log-log)。Savit ら 1999 の `α_c ≈ 0.337` と離散ステップ込みで整合。
- **Crowded regime**: M ≤ 4 で σ²/N ≫ 1 (戦略空間 2^M が N に対し狭く、戦略共有率が高い)。
- **Random regime**: M = 12 (α = 40.5) で σ²/N = 0.968、ランダム極限 1.0 に漸近。Success rate も M=10 で 0.485 とほぼ 0.5。
- **Aggregate 対称性**: A(t) 平均 = 499.75 (N/2 = 500.5)、skew = -0.021 で対称。
- **Score 広がりのスケーリング**: 中心化スコアの std が `√(t/4)` 的に広がり (Panel 5)、`t = 1000 → 10000` で √10 倍を目視確認。best-strategy 選択が情報を持つ機構の数値裏付け。

**設計判断** (YH004/YH005 への共通基盤として固定):
- 行動 = ±1 (符号演算でスコア更新)、履歴 = 整数 μ ∈ [0, 2^M-1] の右シフト + mask、戦略テーブル = (N, S, 2^M) int8、同点破り = `argmax(scores + U[0, 0.5))` で同点組のみランダム化。
- `Agent.decide()` は `(action, s_idx)` を返す形に統一 (YH004 の `action ∈ {-1, 0, +1}` 拡張、YH005 の signal-based score update へ最小改変で移行可能)。

**保留**: 戦略の進化・淘汰 (Challet-Zhang §4 以降) / 熱的ノイズ付き softmax 選択 / 応答関数 / χ² order parameter 解析は意図的に除外。

---

## YH004 — Jefferies et al. (2001) Grand-Canonical MG (完了, 2026-04)

**使用 parameter**: `N=101 (主), 1001 (Panel 4), M=2-10, S=2, T_win=50, r_min ∈ [-T, T] sweep`、5 trial ensemble (Panel 1/2)。動的モードは `λ ∈ {0.5, 1.5, 3.0}`。

**確認済み** (seed=42):
- **Figure 1 転移曲線**: ⟨N_active⟩ が r_min を上げるにつれ N → 0 へ単調降下、σ[N_active] は中間 r_min でピーク。形状一致。
- **Fat tails の発現**: Panel 4 で MG (`r_min=-T-1`) excess kurtosis = **−0.91 (sub-Gaussian)** vs GCMG (`r_min=0.3T`) = **+41.3 (強い fat tail)**。MG の少数派制約は aggregate を押し戻すのに対し、GCMG は静穏期 → 同時参加 → burst の生成機構が効く (論文 §2.2 の主張の定量裏付け)。
- **σ²/N 相図反転** (Panel 5): Crowded 相 (α=0.317) で MG=1.46 vs GCMG=4.10 (GCMG が volatile、相関した participate/abstain スイッチング)、Dilute 相 (α=10.14) で MG=1.02 vs GCMG=0.57 (弱い戦略 agent が abstain して参加減)。
- **YH003 同値サニティ**: `T_win ≥ T_total` かつ `r_min < -T_win` で全期間 active=N, σ²/N=0.257 (YH003 の 0.268 とほぼ一致、不一致分は perturb/abstain RNG 消費順差)。

**失敗ルートのメモ**:
- **二項近似との乖離**: 論文 p.5 の独立二項 RW 近似 `⟨N_active⟩ ≈ N(1 - P^s)` は crowded 相で大きくズレる (本実験で sim 転移点 ≈ -5、理論 ≈ +5)。論文も `T ≫ 2^m` を前提にしており本実験の `T/2^m = 12.5` は近似が悪い域。crowded 相では r_S が強く mean-reverting し独立 RW から外れる、と読む。

**設計判断**:
- スコアは signed (+1/-1)、ring buffer (T_win, N, S) int8 で集計。
- `BaseMGAgent` を YH003-005 共通インタフェースとして切り出し、YH004 は `GCMGAgent(BaseMGAgent)` で abstain 判定だけ追加。

**保留**: §2.3 wealth heterogeneity / value-trend mix / §3.2 market-maker (Bouchaud-Cont-Farmer) / Figure 3-5 / §4 real data ($/Yen) 予測は対象外。一部は YH005 (SG) で扱う。

---

## YH005 Lite — Speculation Game 最小実装 + 3 モデル比較 (完了, 2026-04)

**使用 parameter**: `N=1000, M=5, S=2, B=9, C=3.0, p0=100.0`。log-return ではなく `Δp = D/N` を使う (論文1 Eq. 5 準拠、p ≤ 0 問題回避)。

**確認済み**:
- **Parity**: reference ↔ vectorized の bit-parity を 5 seeds × (default / S=1 / Null A / Null B) で検証、pytest で常時 green。§7 RNG 消費順の契約が機能することを実証。
- **Baseline stylized facts** (`T=20000, seed=777`): std(r)=3.26e-3, vol_acf(τ=200)=+0.016, kurt(w=1)=3.63, kurt(w=640)=-0.40, Hill α=4.53。論文1 Fig. 4 の α≈3.8 と整合。aggregational Gaussianity を数値で確認。
- **Null tests** (`T=50000, seed=777`): baseline |r| ACF(50)=+0.119 vs Null A=+0.005 / Null B=+0.017。baseline/null 比 ~10-24x、論文2 Fig. 11 と定性一致。
- **3 モデル比較** (`S=1, T=50000, seed=123`): MG Hill α≈10^14 (離散化 artifact), GCMG Hill α≈1429 (very thin), **SG Hill α=4.33** (power-law)。vol ACF も SG のみ slow decay を示す。
- **設計ホール 8 項目** (§4.1-4.8) は `experiments/YH005/README.md` の表で固定。以後これに従う。特に:
  - 4.1 argmax tie-break: 現 j* が argmax 集合に含まれれば継続、さもなくば argmax から uniform
  - 4.5 Null B は literal 解釈 (position 非参照)
  - 4.9 return 定義は Δp = D/N (log-return ではない)

**失敗ルートのメモ**:
- 3 モデル比較を log-return で最初に書いたら MG の 77% の step で p ≤ 0 になり NaN 化 → Δp 基準に切り替えた。今後の parameter scan でも log-return が破綻しうることを意識する。

**次フェーズで検証したい仮説**:
- T=50000 baseline の |r| ACF(50)=0.119 は論文1 Fig. 7 fit の 0.211 より低め。100 trial 平均で収束するか要確認 → Phase 2 で検証。

---

## YH005_1 — Phase 1: 3 層機構の数値実証 (完了, 2026-04-22)

**使用 parameter**: `N=1000, M=5, S=2, T=50000, B=9, C=3.0, seed=777, p0=100.0, order_size_buckets=(50, 100)`。1 trial。

**確認済み (5 figure)**:
- **Wealth Pareto**: Hill α (xmin=p90) = **2.54** (論文2 Fig. 4: 1.94)。単一 trial 揺らぎの範囲、[1.5, 3] 内。tail は我々がやや軽い。
- **Round-trip horizon**: K=10,419,681 件、median=2 / mean=3.3 / max=484 steps。log-log で明確な右下がり (論文2 Fig. 8 と定性一致)。
- **ΔG vs horizon**: corr(|ΔG|, τ) = **+0.416**。明確な漏斗形 (論文2 Fig. 7)。
- **Action ratio (M=5)**: passive_hold=**0.251**, active_hold=0.237, buy=sell=0.212, idle=0.088。論文2 Fig. 10 (M=5) と同水準。buy ≈ sell で対称性維持。
- **Order size 時系列**: mean(small/med/large) = 415.9 / 0.8 / 0.1、peak(large)=12 agents/step。large burst が r(t) 高 vol 期と visual に同期。ただし large 件数は tail が軽い分少なめ。

**simulate ログの拡張 (YH005 本体に追加)**:
- `round_trips` dict (K レコード, 6 配列: agent_idx, open_t, close_t, entry_action, entry_quantity, delta_G)
- `num_orders_by_size{,_buy,_sell}` (T×3 配列、bucket: small≤50 < medium≤100 < large)
- 新 state `entry_step` を Agent に追加 (open 時記録、close/substitute でクリア)
- **RNG 消費順不変** — 既存 14 parity ケースに新 9 配列の bit-parity チェックを重ねて全通過。invariant 4 追加も通過。

**性能**: T=50000 × N=1000 × S=2 × M=5 で vectorized 実装 97.5 秒 (Apple Silicon)。Phase 2 の 100 trial × 7M × 15B = 10500 run で単純掛け算すると 285 時間。並列化 + さらなる vectorize 改善が必須。

**失敗ルートのメモ**:
- 最初 `plot_hold_ratio` で N を hard-code していなかったが、sim_result から推定 (buy+sell+act+pas の max) する方式で対応。num_idle を別 key で返す形に simulate 側を変えない。
- p ≤ 0 チェック: seed=777 では n(p≤0)=0、prices ∈ [92, 107] に収まる。log_return 安全。ただし B を下げたり C を上げる parameter scan では要再確認。

**次フェーズで検証したい仮説**:
- 100 trial 平均で Hill α が論文値 1.94 に近づくか (Phase 2)
- parameter scan (M-B phase diagram、kurtosis vs S, vs C) で機構が parameter-robust か (Phase 2)
- 論文1 Fig. 11 (asymmetry), Fig. 12 (leverage), Fig. 13 (gain/loss asymmetry) は **post-processing のみで出せる** (新規 simulate 不要、round_trips と h_series から計算可能) → Phase 3 で追加予定

**YH006 着手時の注意点** (これを見て重複回避):
- YH005 Lite の simulate は bit-parity 契約が重要。YH006 で論文1 全 11 stylized facts を網羅する際、simulate の RNG 順を絶対に壊さない。ログ追加だけなら parity 維持可能。
- 設計ホール 8 項目は YH005 README で確定しているので YH006 でも同じ選択を踏襲すること。
- round_trips / order size bucket のログ構造は YH005_1 で確立した形をそのまま使える。

---

## YH006 Lite — Speculation Game on LOB (PAMS) (完了, 2026-04-25)

**研究設計**: 2×2 (world × wealth, N=100 統一) + LOB 流動性 null。SG decision rule (YH005) を PAMS 0.2.2 の tick-scale LOB に移植し、aggregate-demand 世界の YH005_1 Phase 1 5 figure と直接比較。

**使用 parameter**:
- LOB 側: 30 MMFCN + 100 SG, warmup=200 / main=1500, c_ticks ≈ 28.0 tick (= 3 × median|Δmid| from C1), seed=777, marketPrice=300, tickSize=1e-5
- aggregate 側: 100 SG × T=50000, M=5, S=2, B=9, C=3.0, p0=100, seed=777 (uniform / Pareto α=1.5 xmin=9)
- 1 trial。bootstrap CI / ensemble は Phase 2 (= YH007 以降) に送る。

**確認済み (2×2 主結果)**:
- **corr(\|ΔG\|, horizon) の交互作用 −0.27** (主 finding): aggregate では Pareto 初期化に対し robust (C0u 0.353 → C0p 0.347)、LOB では半減 (C2 0.61 → C3 0.33)。LOB が dynamic-wealth の自己組織化を弱め、初期 wealth heterogeneity を **funnel 形成の妨げに変換**する。
- **world 効果 ≫ wealth 効果**: num_round_trips ÷10³ (LOB friction で round-trip 率が 1183x 減速)、α_hill −2 (LOB の基本 signature)、passive/active_hold 共に +0.09 (SG が約定できず holding 強制)。
- **N scaling 補遺**: hold ratio は N 不変 (N 1000→100 で差 < 0.01)、α_hill は N 効果に強く依存 (旧表 −0.56 → 真値 −1.93、3.4x 過小評価)。**N を揃えなければ α 比較は意味がない**事実そのものが論文 material。

**実装の要点**:
- `SpeculationAgent` (pams.agents.Agent subclass): SG decision rule + MARKET_ORDER open/close + Plan A' liquidity guard (反対板 dry 時の MARKET 累積を抑制し book O(N²) 経路を回避)
- `MMFCNAgent` (FCNAgent subclass): pams 0.2.2 の `submit_orders_by_market` が order_volume=1 ハードコードしている問題に対し、settings 経由で 30 に上げる structural workaround。論文 body では「外部流動性条件」として spec 化。
- `history_broadcast`: 全 SG が共有する cognitive history μ(t) を Simulator attribute に貼る idempotent state
- `aggregate_sim.py`: YH005 simulate の YH006 local fork。`wealth_mode ∈ {uniform, pareto}` 対応、uniform は YH005 と bit-parity (4 seeds 検証済)。
- 検証 4 ファイル全 pass: aggregate parity 9 / LOB parity 2 / round-trip invariants 1 / wealth conservation 1 = 計 13 case。

**失敗ルートのメモ**:
- **両側 MARKET_ORDER は不約定**: pams/market.py:798-834 の matching engine 制約により SG-only pure-MARKET 系は LOB で round-trip が閉じない。FCN 等の外部 LIMIT 流動性層が必須 (`sg_only_smoke` で 0% fill を確認)。
- **Plan A の book accumulation**: 反対板 dry 時に MARKET が積み上がり O(N²) 発火、runtime 300s。Plan A' の liquidity guard で 26s に短縮。
- **N=1000 旧 C0 vs N=100 C2/C3 の混成比較**: pre-2×2 では α_hill −0.56 と読んでいたが、N effect (1000→100 で +1.37) が confound。N=100 同士で −1.93 = 真値の 3.4x 過小評価。
- **lob_mtm の発散**: PAMS cash + asset×price が ±数千ドルにぶれる SG sizing artifact (q=⌊w/B⌋ が cost basis を LOB 単位で負にする)。`sg_wealth` (cognitive) と分離して追跡する 2-account 設計で internal logic は維持。

**次フェーズ (YH006_1 / Phase 2) で検証したい仮説 / 引き継ぎ事項** (memo.txt 由来; bootstrap CI / ensemble は YH006_1 で実施済):
- **bootstrap CI / 100 trial ensemble**: α_hill (n_tail=10 で誤差 ~α/√n ≈ 1.2) と corr(\|ΔG\|, h) の方向性を統計的に確定。現状 1 trial の点推定。
- **LIMIT_ORDER open 拡張**: zero-fill open 率 ≈ 30% (流動性不足) → SG 信号の 3 割が LOB で消失。論文1 Fig 11/12/13 (asymmetry / leverage / gain-loss) の再現には致命的。MARKET-only から LIMIT mid±n% / ttl=k への拡張で改善見込み。
- **iterative C_ticks calibration**: 現状 C1 で median|Δmid|×3 較正 → C2/C3 で再使用 (1 次近似)。SG 投入で Δmid 分布が変わるので self-consistency が崩れる。SG 投入後の price から再較正する iteration が必要。
- **MMFCNAgent order_volume sensitivity scan**: 現状 1 点 (=30) のみ。論文 body で「外部流動性条件」として defend するには 10/30/100 等の scan が必要。
- **warmup/main スケール依存性**: 主実験は warmup=200/main=1500 のみ。`measurement_7_all` で warmup=100/main=600 も走らせているが、本表に組み込んでいない。スケール依存補足プロットがあると堅い。
- **lob_mtm の論文 limitation 段落**: 2-account 設計を「LOB 実装としての realism を一部諦めている」と正直に書く必要。

**YH007 着手時の注意点** (これを見て重複回避):
- **C_ticks 互換性**: YH007 で C を内生化する際、外生固定モードを残して YH006 の C_ticks ≈ 28 tick (= 3 × median|Δmid|) と数値合わせができること。bit-parity は要求しないが、内生化 mode と外生固定 mode の同一 seed run で stylized facts が連続すること。
- **aggregate_sim parity 契約**: uniform mode × 4 seeds (1, 42, 777, 12345) で YH005 simulate と bit-parity、Pareto mode × 2 seeds で determinism、uniform vs Pareto × 3 seeds で divergence の計 9 ケース は絶対に壊さない (YH007 で aggregate_sim を継承する場合)。
- **MMFCNAgent / SpeculationAgent / history_broadcast の設計判断**: LOB 路線を続けるなら同じ structural choices を踏襲 (両側 MARKET 不約定問題、liquidity guard、2-account wealth)。
- **pams 0.2.2 を patch しない**: subclass + config のみ。order_volume hardcode 等は subclass で吸収。

---

## YH006_1 — Phase 2: F1 interaction 機構解明 (S1/S2/S3 完了, 2026-05)

**研究設計**: YH006 Phase 1 の 1-trial 点推定を 100-trial ensemble に拡張し、`corr(|ΔG|, h)` の wealth × world interaction の統計的確定を目指す。ablation (causal 特定) は保留 → YH006_2 以降。

**使用 parameter**: YH006 と同一 (N=100, M=5, S=2, B=9, C=3.0, LOB: 30 MMFCN + 100 SG, warmup=200/main=1500, tickSize=1e-5)。seed = 1000+i, i ∈ [0, 100)。4 条件 × 100 trial。

**確認済み (4 条件 ensemble mean ± 95% CI)**:

| metric | C0u | C0p | C2 | C3 |
|---|---|---|---|---|
| rho_pearson | +0.347 [+0.346, +0.349] | +0.347 [+0.346, +0.348] | +0.278 [+0.261, +0.295] | +0.257 [+0.243, +0.272] |
| rho_spearman | +0.194 [+0.193, +0.195] | +0.194 [+0.193, +0.195] | +0.142 [+0.132, +0.153] | +0.133 [+0.125, +0.142] |
| bin_var_slope | -0.314 [-0.339, -0.288] | -0.324 [-0.348, -0.300] | -0.036 [-0.067, -0.004] | -0.041 [-0.074, -0.007] |
| q90_q10_slope_diff | +0.593 [+0.591, +0.596] | +0.591 [+0.589, +0.594] | +0.213 [+0.200, +0.226] | +0.217 [+0.206, +0.229] |
| lifetime censoring 率 | 0.9% | 0.9% | 90.1% | 72.0% |
| lifetime p25 | 227.0 | 224.0 | 1500.0 | 212.0 |

**主 finding**:
- **仮説 A primary evidence 確定**: LOB censoring_rate = 81.1% vs aggregate 0.9% (gap +80.1%)、median>T/2 trial 200/200。LOB friction が agent turnover を実際に抑制し、tail composition が persist する定量証拠。
- **C2 (LOB uniform)**: 全 agent が roughly 同 pace で生存 (p25=T、censoring 90%)。C3 (LOB pareto): 下位 25% が早期退場 (p25=212)。初期 wealth heterogeneity が LOB 環境では dynamics に残存。
- **Interaction (C3−C2)−(C0p−C0u)**: rho_pearson = −0.020 [−0.042, +0.002]、CI が 0 を跨ぐ → plan A/B 分岐判定保留。S1-secondary (bootstrap 確定) 待ち。
- **wealth_persistence_rho**: C2 = +0.237 [+0.216, +0.257] で有意、C3 ≈ 0 → LOB + uniform では初期 wealth rank が持続するが pareto 投入で壊れる非対称性を確認。

**保留事項**:
- **S1-secondary (plan A/B 分岐確定)**: 100-trial bootstrap CI の最終確認。Yuito 承認後に plan A ablation (C2_A1, C3_A1, q 固定) / plan B 分岐。
- **Ablation 実験 (C2_A1, C3_A1, C3_A3)**: 因果経路 (`q = ⌊w/B⌋` vs strategy selection) の特定。YH006_1 SPEC v2.0 §3 参照。
- **Layer 2 timescale**: LOB T=1500 は Katahira 標準 T=50000 の 1/33。本 sim 長を超える長期での F1 持続性は未検証。proposal Limitations 節に明記予定。

**YH006_2 着手時の注意点**:
- **S1-secondary を先に完了させる**: plan A/B 判定が確定しないと YH006_2 の scope が固まらない。
- **Interaction CI の解釈**: 現状 5 指標中 CI が 0 を跨ぐものが多い。YH006_2 の hypothesis framing はこの結果を踏まえた上で確定する。
- **コード引き継ぎ**: `YH006_1/code/adapter.py` (Phase 1 → Phase 2 schema)、`lob_ensemble.py`、`aggregate_ensemble.py` はそのまま流用可能。ensemble infrastructure は確立済み。
