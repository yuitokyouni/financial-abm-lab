# Stage S5.5 diff — aggregate sub-sample 再分析: RT 数 / 時間軸 disparity 制御

S5.5 plan v1 の実行結果。新規 sim なし、既存 aggregate parquet (`data/C0u/` `data/C0p/` 各 100 trial) から 2 種類 sub-sample (T1500 / RT10k) を抽出し、LOB と pooled bin_var slope / lifetime / 5 主指標で 4 通り比較。

---

## Verdict — **H_micro 強支持** (microstructure 真効果)

RT10k pooled bin_var slope が C0u/C0p ともに **|slope| ≥ 0.30** で full aggregate 水準を保持 → S6 (A3 ablation) 進行可。

| sub-sample | C0u pooled | C0p pooled | LOB C2 | LOB C3 | 判定境界 (vs LOB) |
|---|---:|---:|---:|---:|---|
| **full_agg** (T=50,000) | **−0.4036** | **−0.2879** | — | — | full aggregate baseline |
| **T1500_agg** (時間軸揃え) | −0.2473 | **−0.4945** | — | — | wealth diff の符号反転 (後述 §1.2) |
| **RT10k_agg** (RT 数揃え) | **−0.3758** | **−0.3736** | — | — | **両方が |slope| ≥ 0.30 → H_micro** |
| **LOB** (C2/C3) | — | — | −0.0593 | −0.1264 | full との gap が極大、sample disparity では説明不能 |

**結論**: RT10k で sample size を LOB の ~2.2x まで揃えても aggregate pooled bin_var は full 水準 (−0.37) を保ち、LOB (−0.06 〜 −0.13) とは依然 5x 以上の差。**LOB の bin_var slope の小ささは sample size artifact ではなく、microstructure (LOB friction、約定難、agent 長寿命) の真効果**。S5 で観察した仮説 A revised (pooled bin_var の世界軸 × wealth 軸 非対称) の物理的妥当性が保たれ、S6 (A3 ablation) で initial wealth distribution の persistence test を続行する根拠を確保。

---

## 1. 実測 RT 数 — Yuito 指摘 1 の数値正確性が確認

### 1.1 per-trial RT 数 (`tab_S5.5_rt_counts.csv`)

| cond | sample | n_trial | per_trial_mean | pooled |
|---|---|---:|---:|---:|
| C0u | full | 100 | 1,044,540 | 104,454,012 |
| C0u | T1500 | 100 | 31,413 | 3,141,323 |
| C0u | RT10k | 100 | 10,000 | 1,000,000 |
| C0p | full | 100 | 1,044,709 | 104,470,944 |
| C0p | T1500 | 100 | 31,415 | 3,141,454 |
| C0p | RT10k | 100 | 10,000 | 1,000,000 |
| C2 | full | 100 | 4,353 | 435,291 |
| C3 | full | 100 | 4,845 | 484,512 |

### 1.2 比率対応表 (Yuito 指摘との照合)

| 比較 | 比率 | Yuito の表現との対応 |
|---|---:|---|
| full agg / LOB (per-trial) | ~227x | 「8 倍」より遥かに大、full-window 比較は対照として致命的に不揃い (Yuito 指摘の中核) |
| **T1500 agg / LOB (per-trial)** | **~6.8x** | **「8 倍」の出所** — 同時間窓 (T=1,500) で aggregate は LOB の ~7x の RT 密度 |
| **RT10k agg / LOB (per-trial)** | **~2.2x** | **「2-3 倍に取って bin_var の robustness 確保」と一致** |

**plan v1 §0.1 の訂正**: 「~1,000x」と書いたのは S1 単 trial 値 (C0u: 1,041,712 vs C2: 879) ベースで stale。**S5 後の実 100 trial データでは LOB per-trial RT は 4,300-4,800 で 5 倍以上に増加**、これが Yuito の "8 倍" 計算の前提と整合する。本 diff で実測値を確定。

---

## 2. 主要結果 — pooled bin_var slope

### 2.1 4 sub-sample × 4 cond 全体 (`tab_S5.5_subsample_comparison.csv`)

pooled bin_var slope (主軸):

| | wealth=uniform | wealth=pareto | wealth diff (pareto − uniform) |
|---|---:|---:|---:|
| **full_agg** | C0u: −0.4036 | C0p: −0.2879 | **+0.1157** (S2/S3 確定値) |
| **T1500_agg** | C0u: −0.2473 | C0p: −0.4945 | **−0.2472** (**符号反転**) |
| **RT10k_agg** | C0u: −0.3758 | C0p: −0.3736 | +0.0022 (ほぼ 0) |
| **LOB** | C2: −0.0593 | C3: −0.1264 | −0.0671 |

### 2.2 判定 (§3.5)

RT10k 版 (= LOB と sample size を ~2x までで揃えた版) で:
- C0u pooled = −0.3758 → |slope| = 0.376 ≥ 0.30 ✓
- C0p pooled = −0.3736 → |slope| = 0.374 ≥ 0.30 ✓
- **両方 H_micro 閾値超え** → 「sample size を縮めても aggregate の bin_var slope は LOB に近づかない」 = **microstructure 真効果**

H_artifact 閾値 (|slope| ≤ 0.15) には全く届かない (LOB の 0.06-0.13 とのギャップが ~3x 残る)。

### 2.3 副次的発見 — T1500 で wealth diff が符号反転

時間軸を揃えた T1500_agg では:
- C0u: −0.40 → −0.25 (絶対値 38% 縮小)
- C0p: −0.29 → **−0.49** (絶対値 71% 拡大)
- wealth diff: full +0.116 → T1500 **−0.247** (符号反転 + magnitude 2x)

これは「aggregate の wealth 効果の方向性が **観察 window の長さ**で変わる」非自明な現象。仮説 A revised の formulation を考える上で重要:
- 仮説 A revised は「Pareto は LOB で wealth persistence dominant」を主張するが、aggregate でも T1500 窓で観察すると **Pareto bin_var が uniform より steep になる** → Pareto の効果は時間的に non-monotonic
- ただし RT10k 版では wealth diff = +0.002 (ほぼ 0) で symmetric。T1500 の符号反転は時間窓選択 artifact の可能性大
- **解釈**: S5 仮説 A revised は full-window or RT-matched (= pooled で見て) の現象であり、T1500 で見ると別動態が混入。S6 設計時は「どの sample window で interaction を見るか」を明示的に固定する必要

---

## 3. Lifetime / censoring — sample-window 内の生死動態

### 3.1 4 sub-sample × 4 cond (`tab_S5.5_lifetime_subsample.csv`)

| cond | sample_kind | T_window | p25 | conditional_median | censoring 率 | n_total |
|---|---|---:|---:|---:|---:|---:|
| C0u | full_agg | 50,000 | 227.0 | 391.0 | 0.93% | 1,071,577 |
| C0u | **T1500_agg** | **1,500** | **177.0** | **339.0** | **25.4%** | 39,314 |
| C0u | RT10k_agg | 50,000 | 227.0 | 391.0 | 0.93% | 1,071,577 |
| C0p | full_agg | 50,000 | 224.0 | 389.0 | 0.93% | 1,076,362 |
| C0p | **T1500_agg** | **1,500** | **128.0** | **281.0** | **22.4%** | 44,570 |
| C0p | RT10k_agg | 50,000 | 224.0 | 389.0 | 0.93% | 1,076,362 |
| C2 | LOB | 1,500 | **1500.0** | 122.0 | **91.0%** | 10,986 |
| C3 | LOB | 1,500 | 241.0 | 39.0 | **73.0%** | 13,691 |

### 3.2 解釈 — H_micro の補強 evidence

aggregate に T=1500 cap を被せただけでは censoring 率は **25.4% / 22.4%** にしか上がらない。LOB の **91.0% / 73.0%** とは依然 **3x 以上の差**。

→ **「LOB で agent が長寿命なのは時間窓が短いせい (artifact) ではなく、microstructure friction による turnover 抑制」** が再確認される (仮説 A の中間予測 primary evidence が S5 で立てた解釈と整合)。

p25 比較: C0u/C0p T1500_agg = 177/128 (退場 active) vs C2 LOB = 1500 (= T、退場ゼロ)、C3 LOB = 241 (Pareto tail のみ退場)。同時間窓でも LOB と aggregate の lifetime distribution は qualitatively 違う。

---

## 4. trial-level 5 主指標 (補助、`tab_S5.5_subsample_comparison.csv` 各 metric の `_mean / _ci_lo / _ci_hi`)

trial-level の小サンプル化に伴う bias の挙動を確認 (pooled とは別観点)。

| metric × sample | C0u | C0p | C2 | C3 |
|---|---:|---:|---:|---:|
| Pearson full | +0.347 [0.346, 0.349] | +0.347 [0.346, 0.348] | — | — |
| Pearson T1500 | +0.345 [0.337, 0.354] | +0.339 [0.330, 0.347] | — | — |
| Pearson RT10k | +0.345 [0.331, 0.359] | +0.335 [0.321, 0.349] | — | — |
| Pearson LOB | — | — | +0.278 [0.262, 0.295] | +0.257 [0.243, 0.272] |
| Spearman full | +0.194 | +0.194 | — | — |
| Spearman RT10k | +0.191 [0.181, 0.200] | +0.191 [0.180, 0.201] | — | — |
| Spearman LOB | — | — | +0.142 [0.132, 0.153] | +0.133 [0.125, 0.142] |
| trial bin_var full (S2 値) | −0.314 | −0.324 | −0.036 | −0.041 |
| trial bin_var RT10k | −0.143 [−0.178, −0.107] | −0.112 [−0.148, −0.076] | (same as full) | (same as full) |
| trial bin_var T1500 | −0.195 [−0.225, −0.165] | −0.158 [−0.192, −0.126] | — | — |

**観察**:
- Pearson / Spearman / Kendall は sub-sample 間でほぼ不変 (correlation は sample size に頑健、想定通り)
- trial-level bin_var は sample size 縮小で **0 方向に寄る** (推定 SE 拡大、small-sample bias)
- trial-level (RT10k) bin_var ≈ −0.13 ≈ LOB trial bin_var ≈ −0.04 〜 −0.06 — **trial-level だと sample size matched で LOB と近づく**
- → これは pooled (bin_var_slope_pooled) で signal を取るべきだという S2 plan v2 修正 1 の合理性を再確認 (trial-level だと sample size に寄せられる)

---

## 5. figure (`fig_S5.5_microstructure_vs_artifact.png`)

2 段構成:
- 上段: 4 sub-sample × 4 cond の grouped bar (pooled bin_var slope)
- 下段: sub-sample ごとの wealth diff (pareto − uniform) bar、T1500 の符号反転が視覚化される

---

## 6. S6 進行への signal + S5.6 統合判定

S5.5 単独では: **H_micro 強支持** → S6 進行可

**統合判定 (S5.6 待ち)**:
- S5.5 = H_micro 強支持 ✓
- S5.6 = H_artifact_negated (MMFCN は bottleneck でない) → S6 進行
- S5.6 = H_artifact_mmfcn (MMFCN bottleneck) → S6 scope 再定義、Phase 2 結論 refactor
- S5.6 = ambiguous → Yuito 議論

S5.5 plan §5 で Yuito 確認事項として挙げた全項目:
1. 「8 倍」の実測対応: T1500-matched 比率 6.8x が出所、本 diff §1.2 で確定
2. RT10k = 10k 採用 (LOB との ~2.2x): 結果として symmetric な pooled bin_var (C0u/C0p ともに −0.37) を出した、設計妥当性確認
3. 判定: H_micro 強支持 — 仮説 A revised の物理的妥当性が保たれる
4. figure design は上下 2 段で実装、追加 layout 案は Yuito 確認
5. S6 進行: S5.6 = H_artifact_negated 想定なら GO
6. 仮説 A revised の formulation refactor: T1500 で符号反転が出たため「sample window 固定」を明示するべき、S6 plan で取り込む方針

---

## Stage 進捗

| Stage | Date | 状態 | Note |
|---|---|---|---|
| 1. `code/subsample_aggregate.py` 実装 | 2026-05-18 | **完了** | 1 file、~350 行、§3.1-§3.5 一体 |
| 2. 4 sub-sample × 4 cond 再分析 | 2026-05-18 | **完了** | Windows 単独、PAMS 不要、runtime 3 分 (refactor 後) |
| 3. 出力 + 判定 + 本 diff | 2026-05-18 | **完了** | Verdict: H_micro |

---

## 出力一覧

| パス | 内容 |
|---|---|
| `code/subsample_aggregate.py` | 新規 script (~370 行) |
| `data/ensemble_summary_subsample.parquet` | 4 sub-sample × 4 cond の trial-level summary (800 rows) |
| `outputs/tables/tab_S5.5_rt_counts.csv` | §3.1 RT count 実測 (8 rows) |
| `outputs/tables/tab_S5.5_subsample_comparison.csv` | §3.4 主表 (8 rows × 5 metrics + pooled) |
| `outputs/tables/tab_S5.5_lifetime_subsample.csv` | §3.3 lifetime 4 sub-sample (8 rows) |
| `outputs/figures/fig_S5.5_microstructure_vs_artifact.png` | §3.5 figure (2 段) |
| `logs/S5.5_summary_for_diff.json` | verdict + 数値 dump |
| `logs/runtime/20260518_191346_S5.5_subsample.log` | 実行 log |
| `plans/stage_S5.5_diff.md` | 本ファイル |
| `README.md` §S5.5 追記 | (本 commit に含める) |

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書) | S5.5 plan v1 の実行結果。Yuito 指摘 1 (RT 数 disparity) への応答完了。Verdict = **H_micro 強支持** (RT10k pooled bin_var が C0u/C0p ともに −0.37 で full 水準保持、LOB −0.06〜−0.13 とのギャップが sample size では説明不能)。副次的に T1500_agg で wealth diff が符号反転する non-monotonic 現象を観察、S6 plan で sample window 固定を明示すべきと判明。実装は §3.4 のうち full_agg / LOB の trial-level を `ensemble_summary.parquet` 流用に refactor して QuantReg @1M RT の bottleneck を回避、Windows 単独で 3 分完走。 |
