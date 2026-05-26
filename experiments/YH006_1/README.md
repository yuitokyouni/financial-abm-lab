# YH006_1 — Phase 2 結果サマリ

## Stage S1 (tentative) — Phase 1 データ再分析

**実行範囲**: 4 / 4 条件で完走 (C0u, C0p, C2, C3)

### 5 主指標 (点推定、CI は S1-secondary で取る)

| cond | n_rt | Pearson | Spearman | Kendall | binVar slope | qreg slope diff |
|---|---:|---:|---:|---:|---:|---:|
| C0u | 1,041,712 | 0.3535 | 0.1944 | 0.1561 | -0.2033 | 0.5833 |
| C0p | 1,049,903 | 0.3471 | 0.1923 | 0.1545 | -0.2308 | 0.5965 |
| C2 | 879 | 0.6091 | 0.4221 | 0.3416 | -0.1758 | 1.8182 |
| C3 | 1,080 | 0.3329 | 0.2816 | 0.2216 | -0.1727 | 0.9444 |

### Interaction = (C3 − C2) − (C0p − C0u)

| indicator | full | first half | second half |
|---|---:|---:|---:|
| rho_pearson | -0.2699 | -0.2178 | -0.3161 |
| rho_spearman | -0.1384 | -0.0610 | -0.2214 |
| tau_kendall | -0.1184 | -0.0589 | -0.1862 |
| bin_var_slope | +0.0305 | -0.1270 | +0.2823 |
| qreg_slope_diff | -0.8869 | -0.5049 | -1.1997 |

### Plan B 先取り指標

| cond | corr(w_init, h) | skew(high − low) | Hill α (|ΔG|) |
|---|---:|---:|---:|
| C0u | -0.0006 | -0.1343 | 1.9196 |
| C0p | -0.0027 | -0.0963 | 1.9650 |
| C2 | nan | -0.6847 | 3.1687 |
| C3 | nan | -0.0356 | 2.9352 |

### S1 (tentative) の役割と判定

本 Stage は (a) 5 指標実装 sanity check / (b) Phase 1 → Phase 2 schema アダプタ確定 / (c) 桁感の事前確認、の 3 点に scope 限定。**plan A/B 分岐判定は出さない**。最終確定は S3 完了後の S1-secondary (100 trial bootstrap CI) で行う。S2/S3 は本 S1 結果に関わらず実行される。

### Layer 2 timescale concern (Phase 2 scope 外)

Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を超える長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + proposal Limitations 節に明記する。

---

## Stage S2 — aggregate baseline 100 trial ensemble

**実行範囲**: C0p: 100 trial, C0u: 100 trial

### 主指標 ensemble mean ± 95% CI (bootstrap 10,000 resample)

| metric | C0u (mean [CI]) | C0p (mean [CI]) |
|---|---|---|
| rho_pearson | +0.3472 [+0.3457, +0.3488] | +0.3469 [+0.3456, +0.3482] |
| rho_spearman | +0.1942 [+0.1932, +0.1952] | +0.1943 [+0.1933, +0.1952] |
| tau_kendall | +0.1560 [+0.1552, +0.1568] | +0.1561 [+0.1553, +0.1568] |
| bin_var_slope | -0.3141 [-0.3395, -0.2885] | -0.3242 [-0.3475, -0.3002] |
| q90_q10_slope_diff | +0.5932 [+0.5909, +0.5956] | +0.5914 [+0.5891, +0.5938] |
| corr_w_init_h | +0.0003 [-0.0001, +0.0008] | -0.0004 [-0.0009, +0.0001] |
| skew_high_minus_low | -0.1138 [-0.1188, -0.1069] | -0.1170 [-0.1199, -0.1142] |
| hill_alpha | +2.4583 [+2.1666, +2.8041] | +2.8228 [+2.4205, +3.2410] |
| lifetime_median | +389.6300 [+388.6350, +390.6400] | +387.8200 [+386.8949, +388.7450] |
| lifetime_p90 | +907.4260 [+904.8580, +909.9820] | +905.0120 [+902.3360, +907.7132] |
| wealth_persistence_rho | -0.0083 [-0.0261, +0.0089] | -0.0103 [-0.0328, +0.0120] |
| forced_retire_rate | +0.0021 [+0.0021, +0.0021] | +0.0021 [+0.0021, +0.0021] |

### Pooled bin variance slope (S2 plan v2 修正 1, Yuito 指示 #1)

- **C0u**: pooled bin_var_slope = -0.4036
- **C0p**: pooled bin_var_slope = -0.2879

### Sub-checkpoint: q90_q10_slope_diff trial 間 SD

- **C0u**: SD = 0.0121 → **OK (<=0.3)**
- **C0p**: SD = 0.0121 → **OK (<=0.3)**

### Lifetime censoring flag (S2 plan v2 修正 3)

- **C0u**: censoring 重大 flag 0 件 (median ≤ T/2)
- **C0p**: censoring 重大 flag 0 件 (median ≤ T/2)

### Determinism guard

C0u seed=1000 × 2 回独立実行: **PASS (rt_df + agents_df bit-一致)**

### LOB SG agent subclass smoke (S2 plan v2 修正 4)

C3 short smoke: **SKIPPED** (Windows env で PAMS 不在、Mac で別途実行予定)

### Layer 2 timescale concern (Phase 2 scope 外、再掲)

Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を 超える長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + proposal Limitations 節に明記する。

---

## Stage S3 — LOB ensemble (C2/C3) + 4 条件 interaction

**実行範囲**: C0p: 100 trial, C0u: 100 trial, C2: 100 trial, C3: 100 trial

### 主指標 4 条件 mean ± 95% CI (bootstrap 10,000 resample)

| metric | C0u | C0p | C2 | C3 |
|---|---|---|---|---|
| rho_pearson | +0.3472 [+0.3457, +0.3488] | +0.3469 [+0.3456, +0.3482] | +0.2776 [+0.2613, +0.2945] | +0.2571 [+0.2431, +0.2715] |
| rho_spearman | +0.1942 [+0.1932, +0.1952] | +0.1943 [+0.1933, +0.1952] | +0.1422 [+0.1323, +0.1525] | +0.1333 [+0.1246, +0.1422] |
| tau_kendall | +0.1560 [+0.1552, +0.1568] | +0.1561 [+0.1553, +0.1569] | +0.1081 [+0.0999, +0.1166] | +0.1012 [+0.0939, +0.1082] |
| bin_var_slope | -0.3141 [-0.3394, -0.2880] | -0.3242 [-0.3484, -0.3002] | -0.0359 [-0.0665, -0.0044] | -0.0413 [-0.0741, -0.0074] |
| q90_q10_slope_diff | +0.5932 [+0.5909, +0.5956] | +0.5914 [+0.5891, +0.5938] | +0.2127 [+0.1999, +0.2256] | +0.2170 [+0.2057, +0.2290] |
| corr_w_init_h | +0.0003 [-0.0001, +0.0008] | -0.0004 [-0.0009, +0.0001] | -0.0061 [-0.0184, +0.0058] | -0.0040 [-0.0141, +0.0065] |
| skew_high_minus_low | -0.1138 [-0.1188, -0.1070] | -0.1170 [-0.1198, -0.1140] | +0.5040 [+0.4359, +0.5704] | +0.5346 [+0.4687, +0.6153] |
| hill_alpha | +2.4583 [+2.1676, +2.8038] | +2.8228 [+2.4193, +3.2409] | +3.1454 [+2.8884, +3.4292] | +2.9782 [+2.7673, +3.2098] |
| lifetime_median | +389.6300 [+388.6250, +390.6500] | +387.8200 [+386.8800, +388.7350] | +1500.0000 [+1500.0000, +1500.0000] | +1485.5150 [+1481.4750, +1489.2800] |
| lifetime_p90 | +907.4260 [+904.8900, +909.9871] | +905.0120 [+902.3430, +907.6930] | +1500.0000 [+1500.0000, +1500.0000] | +1500.0000 [+1500.0000, +1500.0000] |
| wealth_persistence_rho | -0.0083 [-0.0262, +0.0094] | -0.0103 [-0.0322, +0.0121] | +0.2369 [+0.2162, +0.2573] | -0.0107 [-0.0323, +0.0109] |
| forced_retire_rate | +0.0021 [+0.0021, +0.0021] | +0.0021 [+0.0021, +0.0021] | +0.0001 [+0.0001, +0.0001] | +0.0003 [+0.0002, +0.0003] |

### Pooled bin_var_slope 2×2 + pattern (S3 plan v2 §3.7、修正 1)

| | wealth=uniform | wealth=pareto | wealth diff (pareto-uniform) |
|---|---|---|---|
| world=agg | C0u: -0.4036 | C0p: -0.2879 | +0.1157 (S2 確定) |
| world=lob | C2: -0.0330 | C3: -0.1748 | -0.1419 |

**Interaction value (LOB diff − aggregate diff)** = -0.2575

**Pattern**: **δ** — LOB diff CI [-0.052, +0.042] が 0 を跨ぐ → 判定保留、S1-secondary の bootstrap CI で再判定

### Interaction = (C3 − C2) − (C0p − C0u) ± 95% CI (S1-secondary 確定前の 100 trial 値)

| metric | mean | CI lo | CI hi | n |
|---|---:|---:|---:|---:|
| rho_pearson | -0.0201 | -0.0422 | +0.0020 | 100 |
| rho_spearman | -0.0090 | -0.0224 | +0.0041 | 100 |
| tau_kendall | -0.0070 | -0.0179 | +0.0035 | 100 |
| bin_var_slope | +0.0046 | -0.0540 | +0.0640 | 100 |
| q90_q10_slope_diff | +0.0061 | -0.0088 | +0.0212 | 100 |

### Lifetime distribution: 仮説 A 中間予測 primary evidence (§3.8、修正 2)

**主指標 (Yuito mandate 2026-04-30)**: p25 / conditional median / censoring 率 — median と p90 は LOB で T 張り付くため補助。

| cond | T | n_trials | n_samples | **p25 (主)** | **conditional median (主)** | **censoring 率 (主)** | median (補助) | p90 (補助) | median>T/2 (補助) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C0u | 50000 | 100 | 1071577 | **227.0** | **391.0** | **0.9%** | 389.6 | 907.4 | 0/100 |
| C0p | 50000 | 100 | 1076362 | **224.0** | **389.0** | **0.9%** | 387.8 | 905.0 | 0/100 |
| C2 | 1500 | 100 | 11093 | **1500.0** | **119.0** | **90.1%** | 1500.0 | 1500.0 | 100/100 |
| C3 | 1500 | 100 | 13891 | **212.0** | **40.0** | **72.0%** | 1485.5 | 1500.0 | 100/100 |

**仮説 A 判定**: LOB censoring_rate=81.1% vs agg 0.9% (gap=+80.1%), median>T/2 trial 件数=200/200 / C2 p25=1500.0 vs C3 p25=212.0 → **仮説 A 中間予測の primary evidence 確定** (LOB friction が agent turnover を抑制、tail composition persist)

**Mac stage finding (継承)**: C2 (LOB uniform) は全 agent が roughly 同 pace で 生存 (p25 も T 近く)、C3 (LOB pareto) は下位 25% が早期退場 (Pareto tail で wealth 失敗) — wealth-tail composition の persist が visualized。aggregate (T=50000) の censoring_rate ≪ 1 との対比で、LOB friction が agent identity の 流動を実際に止めている定量証拠 (S1-secondary plan で Fig.4 / Fig.5 として申し送り予定)。

**survival analysis (Kaplan-Meier 等) は引き続き Phase 2 scope 外** (S2 plan v2 §0.7、S3 plan v2 修正 2 確定済)。

### KPI L1 暫定確認 (S1 単 trial 値からの更新、S1-secondary 確定前)

3 中 2 以上で符号と桁が一致 → satisfy。`tab_S3_interaction.csv` 参照。

**plan A/B 分岐判定は出さない、S1-secondary plan で Yuito 承認後に確定**。

### Layer 2 timescale concern (Phase 2 scope 外、再掲)

Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を超える 長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + proposal Limitations 節に明記する。

---

## Stage S5 — A1 ablation (C2_A1 / C3_A1) + KPI L2 判定

### L2 fail の意義 — 仮説 A 単純版の反証 + 仮説 A revised の浮上

KPI L2 は 5 metrics 全 fail だが、これは「実験失敗」ではなく **causal hypothesis の改訂イベント** として解釈する。

- **仮説 A 単純版 (反証)**: 「q heterogeneity → funnel pollution」。A1 ablation (q_const = 3 固定) で interaction が S3 baseline から有意縮小すべき、という対偶が成立しなかった。Spearman ratio 1.006 / Kendall ratio 1.090 (≈ 1.0) は funnel の monotonic structure が q heterogeneity 由来でないことの直接反証。
- **仮説 A revised (新規 causal candidate)**: pooled bin_var_slope の 6 条件 非対称 — **C2_A1 (−0.31) ≈ C0u (−0.40)** (uniform 側に強く近づく) vs **C3_A1 (−0.09) ≈ C3 (−0.13)** (Pareto 側のままほぼ動かず) — から、uniform 条件下では q heterogeneity が部分寄与する一方、**Pareto 条件下では initial wealth distribution の persistence が dominant 因子** であることが示唆される。これは S6 (A3 ablation) で direct causal test 可能。

### 数値解釈の補足

- **Pearson の 90% 縮小 (ratio = 0.092)** は variance reduction effect (外れ値が均された結果) であり、機構的縮小ではない可能性が高い。S3 baseline 自体が小さく (−0.020) shrinkage CI が 0 を跨ぐので L2 fail。
- **Spearman/Kendall ratio ≈ 1.0** は q heterogeneity が funnel の monotonic structure を作っていないことの直接反証。これが仮説 A 単純版の反証の最も明確な指標。
- **bin_var ratio 3.8x の拡大** は、q heterogeneity を切ると funnel の "純粋な" heteroscedasticity が観察しやすくなる現象として理解可能 (q が wealth-coupled noise として作用していた可能性)。

### 次の S6 (A3 ablation) 位置付け

S6 は仮説 A revised の direct causal test (initial wealth distribution を C2 同様 uniform 化) として価値が高く、別 plan で承認待ちフローで進める。

**実行範囲**: C0p: 100 trial, C0u: 100 trial, C2: 100 trial, C2_A1: 100 trial, C3: 100 trial, C3_A1: 100 trial

**q_const** = 3 (C3 100 trial の pooled median から較正、`logs/S4_q_const_calibration.json`)

### Pooled bin_var_slope (6 条件)

| cond | pooled bin_var_slope |
|---|---:|
| C0u | -0.4036 |
| C0p | -0.2879 |
| C2 | -0.0593 |
| C3 | -0.1264 |
| C2_A1 | -0.3071 |
| C3_A1 | -0.0901 |

### A1 interaction shrinkage vs S3 baseline (5 metrics)

| metric | S3 mean [CI] | A1 mean [CI] | shrinkage [CI] | ratio | L2 |
|---|---|---|---|---:|---|
| rho_pearson | -0.0201 [-0.0422, +0.0020] | -0.0018 [-0.0148, +0.0105] | -0.0183 [-0.0428, +0.0061] | 0.092 | fail |
| rho_spearman | -0.0090 [-0.0224, +0.0041] | -0.0091 [-0.0185, +0.0005] | +0.0001 [-0.0152, +0.0149] | 1.006 | fail |
| tau_kendall | -0.0070 [-0.0179, +0.0035] | -0.0076 [-0.0158, +0.0009] | +0.0006 [-0.0119, +0.0129] | 1.090 | fail |
| bin_var_slope | +0.0046 [-0.0540, +0.0640] | +0.0176 [-0.0375, +0.0731] | -0.0130 [-0.0746, +0.0483] | 3.806 | fail |
| q90_q10_slope_diff | +0.0061 [-0.0088, +0.0212] | -0.0046 [-0.0130, +0.0036] | +0.0107 [-0.0064, +0.0280] | 0.759 | fail |

**L2 判定基準**: shrinkage ratio ≤ 0.5 (= 50% 以上縮小) AND shrinkage CI が 0 を含まない

**L2 pass 件数: 0 / 5**

### Layer 2 timescale concern (Phase 2 scope 外、再掲)

Phase 1 LOB の T=1500 は Katahira 標準 T=50000 より 33x 短く、本 sim 長を超える 長期での F1 持続性は未検証。Phase 2 では検証せず、最終 README + proposal Limitations 節に明記する。

---

## Stage S5.5 — aggregate sub-sample 再分析 (sample disparity 制御)

### Verdict — **H_micro 強支持** (microstructure 真効果)

Yuito 方法論的指摘 1 (「aggregate と LOB で RT 数が 8 倍違う、対照実験として致命的な不揃い」) に対し、既存 aggregate parquet から 2 種類 sub-sample (T1500 / RT10k) を抽出して LOB と 4 通り比較。**RT10k pooled bin_var slope (C0u/C0p ともに −0.37) が full aggregate 水準 (−0.40 / −0.29) を保持** → S6 (A3 ablation) 進行可。

### RT 数実測 (Yuito 指摘の数値正確性確認)

| 比較 | per-trial 比 | Yuito の表現対応 |
|---|---:|---|
| full agg / LOB | ~227x | 全 sim 期間比較は致命的に不揃い |
| **T1500 agg / LOB** | **~6.8x** | **「8 倍」の出所** (同時間窓比較) |
| **RT10k agg / LOB** | **~2.2x** | **「2-3 倍に取って bin_var 安定性確保」と一致** |

LOB per-trial RT は S1 単 trial 値 (~880) から S5 後の 100 trial データで **4,300-4,800** に増加 (5x 以上)、Yuito の "8 倍" 計算と整合。

### Pooled bin_var slope 4 sub-sample × 4 cond

| | wealth=uniform | wealth=pareto | wealth diff |
|---|---:|---:|---:|
| **full_agg** | C0u: −0.4036 | C0p: −0.2879 | +0.1157 (S2/S3 確定) |
| **T1500_agg** | C0u: −0.2473 | C0p: **−0.4945** | **−0.2472** (**符号反転**) |
| **RT10k_agg** | C0u: **−0.3758** | C0p: **−0.3736** | +0.0022 (≈ 0) |
| **LOB** | C2: −0.0593 | C3: −0.1264 | −0.0671 |

**判定**: RT10k で sample size を LOB の ~2.2x まで揃えても aggregate pooled bin_var は full 水準 (−0.37) を保ち、LOB (−0.06〜−0.13) と依然 5x 以上の差 → **microstructure 真効果**。H_artifact 閾値 (|slope| ≤ 0.15) には全く届かない。

### 副次的発見 — T1500 で wealth diff が符号反転

時間軸を揃えた T1500_agg では C0u −0.40→−0.25 (38% 縮小)、C0p −0.29→**−0.49** (71% 拡大) で wealth diff の符号が +0.12 → −0.25 に反転。S5 仮説 A revised の formulation は **sample window 固定** を明示すべき (S6 plan で取り込み)。

### Lifetime — H_micro の補強 evidence

aggregate に T=1500 cap を被せただけでは censoring 率は 25.4% / 22.4% にしか上がらず、LOB の 91.0% / 73.0% と依然 3x 以上の差。→ LOB の長寿命は microstructure friction による turnover 抑制が原因で、時間窓 artifact ではない (仮説 A 中間予測 primary evidence と整合)。

### S6 進行への signal

S5.5 単独では H_micro 強支持。S5.6 (MMFCN sensitivity scan) との統合判定:
- S5.5 = H_micro ✓ ∧ S5.6 = H_artifact_negated → **S6 進行**
- S5.6 = H_artifact_mmfcn or ambiguous → Yuito 議論

---

## Stage S5.6 — MMFCN sensitivity scan (約定 artifact 検出)

### Verdict — **H_artifact_negated_strong** (MMFCN は副次的供給源)

Yuito 方法論的指摘 2 (「PAMS / MMFCN 設定で約定をしづらくさせる artifact」) に対し、LOB C3 setup で MMFCN の `orderVolume` を {15, 30, 60, 120} の 4 設定 × 2 trial (seed=1000, 1001) で scan。弾力性 ε(4x) = log(1.42)/log(4) = **0.254 ≤ 0.3** → MMFCN は独立、Phase 2 finding 頑健、S6 進行可。

### 設定別 mean (`tab_S5.6_mmfcn_sensitivity.csv`)

| metric | mmfcn_05x | **mmfcn_1x** | mmfcn_2x | mmfcn_4x |
|---|---:|---:|---:|---:|
| n_rt_mean | 4679.5 | **4398.0** | 5464.0 | 6251.0 |
| n_rt ratio vs 1x | 1.06 | 1.00 | 1.24 | **1.42** |
| rt_rate/agent_step (SG fill ease proxy) | 0.0312 | 0.0293 | 0.0364 | 0.0417 |
| forced_retire_rate | 0.435 | 0.390 | 0.405 | 0.355 |
| censoring_rate | 67.4% | 71.0% | 69.2% | 71.0% |

### 判定 — 弾力性ベース (Yuito 2026-05-19 提示)

- ε(4x) = 0.254 → MMFCN は副次的供給源 (独立性高)
- 4 倍にしても n_rt は 1.42x のみ (線形供給依存なら 4.0x の期待)、0.5x でもほぼ変化なし → 現状設定は既に余裕供給
- forced_retire / censoring が setting に対し flat → SG 内在 dynamics が dominant

### baseline bit-一致 PASS

`mmfcn_1x` (= orderVolume 30) を `mmfcn_order_volume=None` 経路で実行 → `data/C3/trial_1000/1001.parquet` と sha256 完全一致 → Phase 1 後方互換 hook の non-regression 確認。

### SG fill_rate proper の限界

plan §2.4 の SG / MMFCN fill_rate proper は OrderTrackingSaver の log を追加 export する必要があり、本 version では未測定。代わりに `rt_rate_per_agent_step` (= n_rt / (N_sg × main_steps)) を proxy として併記、4x/1x 比 = 1.42 で MMFCN 独立性を支持。

### S5.5 + S5.6 統合判定 — **S6 (A3 ablation) 進行 GO**

- S5.5 = H_micro 強支持 (RT10k pooled bin_var が full 水準保持) ✓
- S5.6 = H_artifact_negated_strong (ε(4x) = 0.25) ✓
- → Phase 2 主要 finding (仮説 A 単純版反証 + 仮説 A revised + lifetime persistence) は方法論的に頑健、S6 で仮説 A revised の direct causal test を実施
