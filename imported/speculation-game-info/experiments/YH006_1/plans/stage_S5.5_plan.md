# Stage S5.5 plan v1 — aggregate sub-sample 再分析: RT 数 / 時間軸 disparity 制御

| 項目 | 値 |
|---|---|
| Stage | S5.5 — aggregate (C0u/C0p) を LOB と RT 数 / 時間軸で揃えた sub-sample で再分析 |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Windows 30 分以内 (再分析のみ、新規 sim 不要) |
| 新規 sim | **なし** (既存 `data/C0u/` `data/C0p/` 各 400 parquet を使う) |
| 前提 | S5 完走済 (`data/ensemble_summary.parquet` 600 行、§S5 で仮説 A revised が浮上) |

本 plan は **S6 (A3 ablation) 着手前のサニティチェック** を担う。S5.5 と S5.6 は並行実行可 (本 S5.5 は再分析のみ、S5.6 は Mac sim)。両 stage 完了後の判定で S6 進行 / refactor を決める (本 plan §5)。

---

## 0. S5.5 着手前提と Yuito 指摘 1 の整理

### 0.1 Yuito 指摘 1 (本 plan 起点)

S5 完了時点で `tab_S3_full_summary` / `tab_S5_*` を観察した Yuito の方法論的指摘:

> aggregate と LOB で RT 数が **8 倍** (実測オーダーはより大きい可能性) 違う。これは対照実験として致命的な不揃いで、bin_var slope の世界軸差 (agg ≈ −0.3〜−0.4 vs LOB ≈ −0.05〜−0.18) や仮説 A revised が「microstructure 真効果」由来か「sample size / 時間軸 artifact」由来か区別できない。

**実測 RT 数 (S3 単 trial 値、`README.md §S1` より)**:
- C0u: n_rt = 1,041,712 (T=50,000)
- C0p: n_rt = 1,049,903 (T=50,000)
- C2:  n_rt = 879 (T=1,500)
- C3:  n_rt = 1,080 (T=1,500)

→ per-trial 比で agg / lob ≈ **~1,000x** (Yuito の「8 倍」は控えめ表現と解する。本 plan §3.1 で full 詰めし、実際の倍率を `tab_S5.5_subsample_comparison.csv` row 0 に明示)。

### 0.2 仮説 / 判定対象

S5.5 で **検証する 2 つの対立仮説**:

| 仮説 | 内容 | S5.5 が真ならどう支持される |
|---|---|---|
| **H_micro** (microstructure 真効果) | LOB 環境の市場 friction (約定難 + agent 長寿命) が bin_var slope を本質的に押し上げている (= agg vs LOB の差は世界軸の真の機構差) | aggregate を LOB と RT 数 / 時間軸で揃えても bin_var slope が −0.3〜−0.4 を保つ |
| **H_artifact** (sample / window artifact) | bin_var slope の世界軸差は単に aggregate が大量 RT × 長時間で heteroscedasticity を強く拾っているだけ。LOB と同 sample / 同 window に揃えれば差が消える | aggregate sub-sample の bin_var slope が LOB 値 (−0.05〜−0.18) に近づく |

判定境界 (本 plan §3.4):
- aggregate_RT10k の pooled bin_var slope が **|slope| ≤ 0.15** で LOB 範囲に入る → H_artifact 強支持、Phase 2 結論を refactor
- aggregate_RT10k の pooled bin_var slope が **|slope| ≥ 0.30** で agg full とほぼ同水準 → H_micro 強支持、S6 進行
- 中間 (0.15 < |slope| < 0.30) → 解釈保留、Yuito 議論

### 0.3 S5.5 sub-sample の選び方 (Yuito plan)

2 種類を抽出して 4 通り (full / T1500 / RT10k / LOB) 比較:

| sub-sample | 抽出ルール | 何を揃えるか |
|---|---|---|
| **aggregate_T1500** | 各 trial の `open_t < 1500` の RT のみ抽出 (close_t cap は付けない、ただし censoring 影響を §3.3 で評価) | **時間軸** を LOB と揃える (T=1,500 step window) |
| **aggregate_RT10k** | 各 trial の `open_t` 昇順で最初 10,000 RT を抽出 | **RT 数** を LOB と揃える (10k / trial × 100 trial = 1M pooled、LOB pooled の ~10x、bin_var の robustness を確保しつつオーダー揃え) |

**Yuito 注**: aggregate_RT10k の 10,000 は LOB per-trial RT (~1,000) の 10x。完全一致 (1,000) では bin_var の K=15 bin で trial-level slope が不安定になる risk があるため、2 桁上で robustness を確保しつつ「同 order of magnitude」を維持する設計 (本 plan で「2-3 倍」と当初書いたのを 10x に修正した経緯、Yuito 承認時に再確認)。完全一致版 (`aggregate_RT1k`) を追加で出すかは §5 で確認。

### 0.4 S5 結論との関係

S5 で確定した仮説 A revised (`pooled bin_var_slope`):
- C2_A1 (−0.31) ≈ C0u (−0.40) (uniform で aggregate baseline に大幅シフト)
- C3_A1 (−0.09) ≈ C3 (−0.13) (Pareto はほぼ動かず)

この **非対称** が「真の構造差」か「sample disparity の二次効果」かは S5.5 で初めて分離できる。H_artifact 支持なら、C2_A1 が aggregate 側にシフトしたのは aggregate baseline 値自体が artifact である可能性を示し、仮説 A revised の formulation を refactor する必要がある。

---

## 1. S5.5 の目的

(a) **既存 aggregate parquet (C0u/C0p × 100 trial) から 2 種類の sub-sample を抽出** し、Phase 2 と同じ pipeline (`bin_variance_slope_pooled` 等) で bin_var slope / censoring 率 / lifetime distribution を再計算

(b) **4 通り比較表** (full agg / agg_T1500 / agg_RT10k / LOB) を `tab_S5.5_subsample_comparison.csv` に出力

(c) **H_micro / H_artifact 判定** を §0.2 基準で実施、`stage_S5.5_diff.md` で報告

(d) **S6 進行 / refactor の go/no-go signal** を出す (S5.6 と並走、両 stage 完了後に Yuito 判定)

本 stage は **新規 sim 不要、bug fix も伴わない再分析 stage**。実装は 1 つの新規 script (`code/subsample_aggregate.py`) で完結する見込み。

---

## 2. 入力

### 2.1 既存資源 (流用、新規実装最小限)

- `data/C0u/trial_*.parquet` × 100 (S2 で生成、each: `agent_idx, open_t, close_t, entry_action, entry_quantity, delta_G`)
- `data/C0p/trial_*.parquet` × 100 (S2 で生成、同 schema)
- `data/C2/trial_*.parquet` × 100 (S3 で生成、比較対象)
- `data/C3/trial_*.parquet` × 100 (S3 で生成、比較対象)
- `code/analysis.py::bin_variance_slope_pooled` (K=15 bin、log h、pooled 単一値)
- `code/analysis.py::bin_variance_slope` (trial-level 版)
- `code/analysis.py::corr_pearson / corr_spearman / corr_kendall / q90_q10_slope_diff` (5 主指標一式)
- `code/stats.py::bootstrap_ci` (CI 計算)

### 2.2 lifetime / censoring 再計算用

- `data/C0u/lifetimes_*.parquet` × 100 (各 RT の close_t / open_t / agent_idx を含む)
- 同 C0p × 100

aggregate_T1500 で lifetime を再評価する際は **「sim 終了時点を t=1500 と仮定して censoring 判定」** する必要がある (本 plan §3.3 で正確に定義)。

### 2.3 パラメタ

| パラメタ | 値 | 根拠 |
|---|---|---|
| `T_window` (aggregate_T1500) | 1,500 step | LOB main_steps と一致 |
| `n_rt_per_trial` (aggregate_RT10k) | 10,000 RT | LOB per-trial RT (~1,000) の 10x、bin_var K=15 bin 安定性 |
| bin_var K | 15 | Phase 2 default (S2/S3/S5 と同) |
| bootstrap n_resample | 10,000 | Phase 2 default |

---

## 3. 作業項目

### 3.1 RT count / time-window 実測 (S5.5 §3 の起点)

新規 script `code/subsample_aggregate.py` の最初の step:

1. 4 条件 (C0u/C0p/C2/C3) 各 100 trial の **per-trial RT count** を集計
2. **per-trial 比** (mean ± SD)、**pooled 比** を計算
3. 結果を `tab_S5.5_subsample_comparison.csv` row 0-3 (raw counts) に出力
4. Yuito 指摘の「8 倍」を実測値で更新 (実測 ~1,000x なら本 plan §0.1 を訂正コメント付きで記録)

**所要**: 5 分以内 (parquet 100 個読み × 4 = 400 file の RT 数集計)。

### 3.2 sub-sample 抽出 (S5.5 §3 の核)

#### aggregate_T1500 抽出ルール

各 trial の RT について:
- **open_t < 1500** の RT のみ keep (close_t は cap しない、ただし §3.3 で censoring 再評価)
- 100 trial 分を pool して `rt_df_agg_T1500_{cond}` を作る

**期待 RT 数** (sanity check): aggregate substitute rate ≈ 0.0021/step、平均 RT 長 ~390 step → per agent per step RT rate ≈ 0.005 → 100 agent × 1500 step × 0.005 = ~750 RT/trial、× 100 trial = ~75,000 pooled。LOB pooled の ~7x 程度を想定。

#### aggregate_RT10k 抽出ルール

各 trial の RT について:
- **open_t 昇順 sort 後の最初 10,000 RT** を keep (1 trial で n_rt < 10,000 の場合は全件 keep、件数を log 記録)
- 100 trial 分を pool して `rt_df_agg_RT10k_{cond}` を作る

**期待 RT 数** (sanity check): aggregate 1 trial = ~10,000 RT。すべての trial で 10k ≤ n_rt の可能性は中程度 (C0u/C0p で per-trial RT mean ≈ 10,700)。短い trial は全件 keep される。

### 3.3 censoring / lifetime 再計算 (aggregate_T1500 のみ)

aggregate_T1500 で「sim T=1,500 step window」を仮定する以上、lifetime と censoring も再評価する必要がある:

各 agent について:
1. open_t < 1500 で alive だった lifetime sample を抽出
2. close_t ≥ 1500 の sample は **censoring 重大 flag** = True
3. censoring 重大の sample は **lifetime = 1500 − open_t (= censored at T=1500)** に置換
4. condition ごとに **censoring 率** = censored sample 数 / 全 sample 数
5. **p25 / conditional median / median** を 4 条件 (C0u_T1500, C0p_T1500, C2, C3) で並べる

aggregate_RT10k では時間軸を切らないので lifetime / censoring は full aggregate と同じ (= 0.9%)、`tab_S5.5_lifetime_subsample.csv` には full aggregate 値を copy する。

### 3.4 bin_var slope / 5 主指標 再計算 + L1 風判定

各 sub-sample × 各 condition で:
1. **pooled bin_var slope** = `bin_variance_slope_pooled(rt_df_subsample_cond, K=15)`
2. **trial-level bin_var slope** = 100 trial 各で `bin_variance_slope(h, dG, K=15)`、mean ± 95% CI (bootstrap)
3. **5 主指標** (Pearson / Spearman / Kendall / bin_var_slope / q90_q10_slope_diff) の trial-level mean ± 95% CI

出力テーブル `tab_S5.5_subsample_comparison.csv` の構造:

| row | sample | cond | n_rt_pooled | n_trial_mean | pooled_bin_var | trial_bin_var [CI] | rho_spearman [CI] | tau_kendall [CI] | q90_q10_slope_diff [CI] | censoring 率 | p25 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | full | C0u | ~107M | ~10,700 | -0.4036 | … | … | … | … | 0.9% | 227 |
| 2 | full | C0p | … | … | -0.2879 | … | … | … | … | 0.9% | 224 |
| 3 | T1500 | C0u | ~75K | ~750 | NEW | … | … | … | … | NEW | NEW |
| 4 | T1500 | C0p | … | … | NEW | … | … | … | … | NEW | NEW |
| 5 | RT10k | C0u | ~1M | ~10,000 | NEW | … | … | … | … | (= full) | (= full) |
| 6 | RT10k | C0p | … | … | NEW | … | … | … | … | (= full) | (= full) |
| 7 | full | C2 | ~88K | ~879 | -0.0593 | … | … | … | … | 90.1% | 1500 |
| 8 | full | C3 | … | … | -0.1264 | … | … | … | … | 72.0% | 212 |

### 3.5 判定 + figure

**判定 logic** (`stage_S5.5_diff.md` の冒頭節):

1. **H_artifact 強支持**: aggregate_RT10k pooled bin_var slope の絶対値が **0.15 以下** (≈ LOB 範囲) で C0u/C0p 両方
2. **H_micro 強支持**: aggregate_RT10k pooled bin_var slope の絶対値が **0.30 以上** で C0u/C0p 両方 (full agg とほぼ同水準)
3. **中間 / mixed**: それ以外。Yuito 議論ポイント、`stage_S5.5_diff.md` で各 condition の具体値と解釈候補を列挙

時間軸版 (aggregate_T1500) は **追加情報** として扱う:
- H_artifact 強支持なら、aggregate_T1500 でも同方向 (LOB に近い) のはず → consistency 確認
- H_micro 強支持なら、aggregate_T1500 では中間値 (時間軸短縮の効果 + microstructure 不在の効果) の可能性 → 解釈は限定的

**figure** `fig_S5.5_microstructure_vs_artifact.png`:
- 上段: 4 条件 × 4 sub-sample (full / T1500 / RT10k / LOB) の **pooled bin_var slope** を grouped bar (色: condition、列: sub-sample)
- 下段: 4 sub-sample × 2 wealth_mode の `pooled diff = pareto − uniform` を bar 表示 (S3 plan §3.7 の interaction 議論の延長)

### 3.6 出力

| パス | 内容 |
|---|---|
| `code/subsample_aggregate.py` | 新規 script (~150 行)、§3.1-§3.5 を実装 |
| `data/ensemble_summary_subsample.parquet` | 4 sub-sample × 4 cond の trial-level summary (160 行: 100 trial × 4 cond × 4 sample) |
| `outputs/tables/tab_S5.5_subsample_comparison.csv` | §3.4 構造のテーブル (上表) |
| `outputs/tables/tab_S5.5_lifetime_subsample.csv` | lifetime + censoring 4 cond × 4 sample |
| `outputs/figures/fig_S5.5_microstructure_vs_artifact.png` | §3.5 の 2 段 figure |
| `logs/S5.5_summary_for_diff.json` | RT count 実測値、判定境界の数値、H_micro / H_artifact 判定結果 |
| `logs/runtime/{ts}_S5.5_subsample.log` | 実行 ログ |
| `plans/stage_S5.5_diff.md` | 判定結果 + Yuito レビュー用 diff |
| `README.md` | `## Stage S5.5 — aggregate sub-sample 再分析` 節を追記 |

### 3.7 README 追記

`## Stage S5.5 — aggregate sub-sample 再分析 (sample disparity 制御)`:
- Yuito 指摘 1 と H_micro / H_artifact 二択
- 実測 RT 数比 (per-trial / pooled)
- §3.4 の 4 sub-sample × 4 cond 表
- §3.5 判定結果 (H_micro / H_artifact / 中間)
- S6 進行 / refactor の signal 結論 (S5.6 結果と合わせて Yuito 判定)
- Layer 2 timescale concern 言及継続

---

## 4. 完了条件

### Windows 側 (全工程 Windows 単独で可、PAMS 不要)
- [ ] §3.1 実測 RT count 4 条件で確認、`tab_S5.5_subsample_comparison.csv` row 0-3 に記録
- [ ] §3.2 sub-sample 抽出 (T1500 / RT10k) 各 100 trial × 2 cond で完了、parquet 化
- [ ] §3.3 aggregate_T1500 の censoring / lifetime 再計算完了
- [ ] §3.4 4 sub-sample × 4 cond の pooled bin_var + trial-level 5 主指標 CI 完了
- [ ] §3.5 H_micro / H_artifact 判定実施 (3 区分のどれか確定)、figure 生成
- [ ] §3.6 全出力ファイル生成、README 追記
- [ ] `stage_S5.5_diff.md` 提出、Yuito レビュー待ち

---

## 5. Yuito 確認事項 (実装中 stop trigger + 完了後レビュー)

### 実装中の停止トリガー (発生したら停止 → Yuito 相談)

- §3.1 で実測 RT 比が想定外 (per-trial 比が 100x 未満 or 10,000x 超) → 入力 parquet の schema 誤認 / scope misunderstanding 疑い
- §3.2 aggregate_T1500 抽出で C0u/C0p のいずれかで pooled RT 数が **5,000 未満** (= bin_var K=15 bin が機能不全)、または逆に **500,000 超** (= 抽出 logic バグ)
- §3.4 で aggregate_RT10k の pooled bin_var slope が **+0.1 以上 (符号反転)** で C0u/C0p の少なくとも一方 → 仮説整理が必要、即停止
- §3.4 で trial-level CI が **>5x の trial 間ばらつき** (full agg の SD 0.012 に対し 0.06 超) → bin_var の安定性破綻

### 完了後 (Yuito レビュー) 確認事項

1. §3.1 RT 数比の **実測値** が「8 倍」の表現とどれくらい乖離していたか、`stage_S5.5_diff.md` の表現修正の要否
2. §0.3 の `aggregate_RT10k` を 10k にした選択 (LOB との 10x ギャップ) を承認するか、追加で `aggregate_RT1k` (LOB と厳密一致) を出すべきか
3. §3.4 4 sub-sample 表を見て、H_micro / H_artifact / 中間のどれと判定するか (本 plan 提出時点では実測前なので Yuito 承認時に judgment criteria を最終確定)
4. §3.5 figure の design (上段の grouped bar / 下段の wealth diff bar) の代替案 (例: pooled vs trial-level の並置、log-log scatter 等)
5. S6 進行 / refactor 判断: S5.5 = H_micro 強支持 AND S5.6 = MMFCN sensitivity flat → S6 進行 / それ以外 → S6 scope 再定義
6. 仮説 A revised の formulation refactor が必要な場合の S5.5_diff 記載方針 (本 plan scope 内 / S6 plan scope か)

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | Yuito 方法論的指摘 1 (aggregate と LOB の RT 数 disparity) への応答 stage。新規 sim なし、既存 aggregate parquet から 2 種類 sub-sample (T1500 / RT10k) を抽出して LOB と 4 通り比較、H_micro / H_artifact 二択判定。S5.6 (MMFCN sensitivity) と並走、両 stage 完了後に S6 進行 / refactor を判定。RT10k 選択を「LOB の 10x、bin_var K=15 安定性確保」で正当化、完全一致版 (RT1k) は §5 で Yuito 確認後オプション化。本 plan scope は再分析のみ、Phase 2 結論 refactor は S5.5 + S5.6 結果を見てから別 plan で着手 (S6 plan か別 stage)。 |
