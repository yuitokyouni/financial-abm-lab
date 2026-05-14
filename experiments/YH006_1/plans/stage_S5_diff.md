# Stage S5 diff — A1 ablation aggregation + L2 判定 + 仮説 A revision

S4-S5 plan v1 の最終 stage (Windows aggregation + L2 判定) のログ。S4 implementation/calibration の進捗は `stage_S4_diff.md`、Mac sim 100 trial × 2 cond の進捗もそちら参照。本ファイルは **L2 判定結果 + 仮説 A の改訂** に focus する。

---

## L2 fail の意義 — 仮説 A 単純版の反証 + 仮説 A revised の浮上

KPI L2 は 5 metrics 全 fail (0/5)。ただしこれは「実験失敗」ではなく **causal hypothesis の改訂イベント** として解釈する。S6 (A3 ablation) 起案の根拠は本節に集約される。

### 仮説 A 単純版 (反証)

「q heterogeneity → funnel pollution」: A1 ablation で q を定数化 (q_const = 3) すれば interaction が S3 baseline から有意縮小すべき、という対偶が成立しなかった。

- **Spearman ratio 1.006 / Kendall ratio 1.090** (両者 ≈ 1.0): funnel の monotonic structure が q heterogeneity 由来でないことの直接反証。これが仮説 A 単純版反証の最も明確な指標。
- **shrinkage CI が 0 を跨ぐ** (5/5 metric): 縮小が statistical に有意でない。

### 仮説 A revised (新規 causal candidate、S6 で test 予定)

pooled bin_var_slope の 6 条件 非対称から **「Pareto 条件下では initial wealth distribution の persistence が dominant 因子」** という仮説が浮上。

| 条件 | pooled bin_var_slope | 解釈 |
|---|---:|---|
| C0u | −0.4036 | uniform aggregate baseline |
| C0p | −0.2879 | Pareto aggregate baseline |
| C2 | −0.0593 | LOB uniform |
| C3 | −0.1264 | LOB Pareto (funnel 強) |
| **C2_A1** | **−0.3071** | **≈ C0u**: uniform 条件では q 定数化で aggregate baseline 寄りにシフト = q heterogeneity が部分寄与 |
| **C3_A1** | **−0.0901** | **≈ C3**: Pareto 条件では q 定数化してもほぼ動かず = q 以外の因子が dominant |

非対称の含意: uniform 条件下では q heterogeneity が **部分寄与** する一方、Pareto 条件下では **initial wealth distribution の persistence が dominant 因子** であることが示唆される。これは S6 (A3 ablation = initial wealth distribution を C2 同様 uniform 化) で direct causal test 可能。

---

## 数値解釈の補足 (5 metrics 別)

- **Pearson の 90% 縮小 (ratio = 0.092)**: variance reduction effect (外れ値が均された結果) であり、機構的縮小ではない可能性が高い。S3 baseline 自体が小さく (−0.020) shrinkage CI が +0.0061 まで伸びて 0 を跨ぐので L2 fail。
- **Spearman/Kendall ratio ≈ 1.0**: q heterogeneity が funnel の monotonic structure を作っていないことの直接反証。S3 baseline (−0.009 / −0.007) と A1 (−0.009 / −0.008) がほぼ同値で、shrinkage = 0 近傍。
- **bin_var ratio 3.8x の拡大**: q heterogeneity を切ると funnel の "純粋な" heteroscedasticity が観察しやすくなる現象として理解可能 (q が wealth-coupled noise として作用していた可能性)。S3 +0.005 → A1 +0.018 で A1 のほうが拡大。
- **q90_q10 ratio 0.759**: 軽度縮小 (約 24%) だが L2 閾値 50% に届かず、CI も 0 を跨ぐ。

---

## Stage 進捗 (S4_diff の Stage 3 に対応)

| Stage | Date | 状態 | Note |
|---|---|---|---|
| 1. Mac LOB Phase 1 test + 200 trial sim | (Mac 側、本 diff 範囲外) | **完了** | `stage_S4_diff.md` 参照 |
| 2. Mac → Windows 転送 | (本 diff 範囲外) | **完了** | git 経由、`data/C2_A1/` `data/C3_A1/` 各 400 parquet |
| 3. **Windows aggregation + L2 判定** | **2026-05-14** | **完了** | 本ファイルが該当、下記詳細 |

### Stage 3 詳細 (2026-05-14、Windows、完了)

実行: `python -m code.aggregate_ablation_summary` (`experiments/YH006_1` 配下)

実施内容 (S4 plan §3.6-§3.8):
1. **integrity check**: C2_A1 / C3_A1 各 400 parquet (= 4 file × 100 seed) 確認、`q == q_const` (= 3) を sample trial で再 assertion。
2. **ensemble_summary 拡張**: 400 → 600 rows、`data/ensemble_summary.parquet` 更新済。per-cond 100 trial × 6 condition。
3. **Pooled bin_var_slope (6 cond)** (上表参照、C2_A1 ≈ C0u / C3_A1 ≈ C3 の非対称を発見)。
4. **A1 interaction (5 metrics) + bootstrap CI** (n_resample = 10,000): `tab_S5_ablation_interaction.csv`。
5. **Shrinkage = S3 − A1 の bootstrap CI** + L2 判定 (ratio ≤ 0.5 AND CI が 0 を含まない): `tab_S5_shrinkage.csv`。

出力 (`outputs/`):
- `tables/tab_S5_ablation_interaction.csv`
- `tables/tab_S5_shrinkage.csv`
- `figures/fig_S5_ablation_shrinkage.png`
- `logs/S5_summary_for_diff.json`
- `README.md` §S5 追記済 (解釈軸 + テーブル)

### L2 判定結果 (5 metrics、ratio = |A1| / |S3|、ratio ≤ 0.5 AND CI excludes 0 で PASS)

| metric | S3 mean [CI] | A1 mean [CI] | shrinkage [CI] | ratio | L2 |
|---|---|---|---|---:|---|
| rho_pearson | −0.0201 [−0.0422, +0.0020] | −0.0018 [−0.0148, +0.0105] | −0.0183 [−0.0428, +0.0061] | 0.092 | fail |
| rho_spearman | −0.0090 [−0.0224, +0.0041] | −0.0091 [−0.0185, +0.0005] | +0.0001 [−0.0152, +0.0149] | 1.006 | fail |
| tau_kendall | −0.0070 [−0.0179, +0.0035] | −0.0076 [−0.0158, +0.0009] | +0.0006 [−0.0119, +0.0129] | 1.090 | fail |
| bin_var_slope | +0.0046 [−0.0540, +0.0640] | +0.0176 [−0.0375, +0.0731] | −0.0130 [−0.0746, +0.0483] | 3.806 | fail |
| q90_q10_slope_diff | +0.0061 [−0.0088, +0.0212] | −0.0046 [−0.0130, +0.0036] | +0.0107 [−0.0064, +0.0280] | 0.759 | fail |

**L2 pass 件数: 0 / 5** (解釈は冒頭節参照)

---

## 次のアクション

- **S6 (A3 ablation)**: 仮説 A revised の direct causal test として価値が高い。別 plan (`plans/stage_S6_plan.md`) で起案、Yuito 承認後着手。design point は **C3 の initial wealth distribution を C2 と同じ uniform に置換** (q dynamics は C3 のまま残す)、それ以外は C3 と bit-同一 (seed、agent count、LOB 設定、Phase 1 後方互換拡張ルール継続)。期待: C3_A3 の interaction / pooled bin_var が C2 側へ大幅シフトすれば仮説 A revised 支持。
- **figure 目視確認**: `outputs/figures/fig_S5_ablation_shrinkage.png` (Yuito 側で別途実施、本 commit は figure 目視と並行で進めて良い旨 Yuito 承認済)。
- **Layer 2 timescale concern**: Phase 2 scope 外 (Phase 1 T=1500、Katahira 標準 T=50000 比 33x 短）、最終 README + proposal Limitations 節に明記する方針継続。
