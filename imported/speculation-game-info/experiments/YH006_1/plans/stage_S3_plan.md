# Stage S3 plan v2 — LOB baseline 100 trial ensemble + 4 条件 interaction 確定

| 項目 | 値 |
|---|---|
| Stage | S3 — LOB ensemble (C2/C3 × 100 trial) + interaction 計算 |
| Status | **承認済 (Yuito v2 反映、実装着手可)** |
| 想定 runtime | Mac 側 LOB 200 trial: 2-4 時間 (PAMS overhead、aggregate より重め) / Windows 側 aggregation: 30 分 |
| 新規 sim | LOB 200 trial (C2 100 + C3 100、Mac で実行) |
| 前提 | S2 完走済 (aggregate ensemble C0u/C0p × 100 trial、`data/ensemble_summary.parquet` 200 行) |

本 plan は Stage S3 のみを扱い、S4 (S1-secondary) 以降の話は **意図的に混ぜていない** (Brief §0 two-step workflow)。S3 完了後に S1-secondary plan を別途作成、4 条件 100 trial の bootstrap CI で plan A/B 分岐判定を確定する。

---

## v2 改訂サマリ (v1 → v2)

Yuito v1 承認時の 3 点修正を反映:

1. **修正 1 (§3.7 判定基準)**: α/β/γ/δ パターン分類の **primary metric を bin_var_slope 符号 2×2 から interaction 値に変更**。`interaction_bin_var = (bin_var(C3) − bin_var(C2)) − (bin_var(C0p) − bin_var(C0u))`。S2 で aggregate diff = C0p − C0u = −0.288 − (−0.404) = **+0.116** が確定済。LOB diff (= C3 − C2) がこれと **同符号同桁なら α (interaction ≈ 0、世界依存性なし)**、反転 / 桁違いなら **β/γ/δ (世界依存性あり)**。bin_var_slope の符号そのものの 4 マス表は 補助 KPI として併記。
2. **修正 2 (§3.8 positioning)**: LOB で lifetime_median = T 張り付き現象を「**仮説 A の中間予測の primary evidence**」として記録 (S2 plan v2 §0.7 の「censoring 重大 flag」用語からは脱却)。aggregate (T=50000) census 0 件 vs LOB census >> 0 件は F1 機構解明の中核 finding 候補。p25 と conditional median は補助指標として併走、survival analysis (Kaplan-Meier 等) は引き続き Phase 2 scope 外。
3. **修正 3 (§0.4 Mac 採用理由の正確化)**: Windows で PAMS unavailable の **真の原因を解明**。v1 で書いた「lifelines が原因」は誤り (lifelines は survival analysis library で PAMS の dependency ではない、`requirements.txt` にも不在)。実際の原因は次の depend chain (本 Windows env で `pip install pams==0.2.2` を実行して特定):
   - PAMS 0.2.2 自体は `py3-none-any.whl` (pure Python、Windows でも問題なし)
   - PAMS が `numpy<2.0.0,>=1.25.1` を制約として要求
   - numpy 1.x の最新 1.26.4 は **Python 3.13 + Windows 用 prebuilt wheel が PyPI に存在しない**
   - pip が source build に fallback → MSVC + meson 必要 → `vswhere.exe` 不在で失敗
   - つまり **MSVC Build Tools を入れるか、Python を 3.12 まで下げれば Windows でも PAMS install 可能**。将来 Windows サポート復旧時の DRI 情報として §0.4 に記録。

---

## 0. S2 完了状態と S3 着手前提

### 0.1 S2 完走サマリ (本 plan 起点)

`data/ensemble_summary.parquet` 200 行 (C0u 100 + C0p 100)、主要結果:

| metric | C0u (mean [CI]) | C0p (mean [CI]) |
|---|---|---|
| rho_pearson | +0.347 [+0.346, +0.349] | +0.347 [+0.346, +0.348] |
| bin_var_slope (trial-level) | -0.314 [-0.339, -0.289] | -0.324 [-0.347, -0.300] |
| q90_q10_slope_diff | +0.593 | +0.591 |
| lifetime_median | 389.6 | 387.8 |

**Pooled bin_var_slope (Yuito 指示 #1)**: C0u = **-0.4036**、C0p = **-0.2879** (両方有意に負)。
**Sub-checkpoint q90_q10_slope_diff trial 間 SD**: C0u/C0p ともに 0.0121 (≪ 0.3 threshold) → interaction 計算が tight CI で機能する見込み。
**Lifetime censoring flag**: C0u/C0p ともに 0 件 (median ≤ T/2 = 25,000)。

### 0.2 Yuito からの S3 反映指示 (本 plan 起点)

Yuito S2 承認時のコメントから、S3 plan に組み込む 3 点:

1. **bin_var_slope 符号解釈 (§3.7)**: aggregate (C0u/C0p) で両方 −0.4 / −0.3、S1 単 trial の +0.03 から大きく変わった。100 trial で sample size 効果として両方有意に負になったのは予想内。LOB 100 trial 集計後、世界軸 × wealth 軸の 2×2 で symmetric / asymmetric pattern を確認する。LOB で正に転じるなら funnel 構造が世界依存で qualitatively 違うことを示し、これは F1 機構解明にとって positive な signal。
2. **Lifetime censoring re-check (§3.8)**: LOB T=1500 は aggregate T=50,000 の 33x 短い。`lifetime_median > T/2 = 750` の censoring 重大 flag が立つ可能性が高い。発生していれば仮説 A の中間予測 (LOB で agent lifetime 延長) と整合、ただし censoring 下で median が信頼できるか、survival analysis (Kaplan-Meier) が必要かを判断。S3 では発生数 flag のみ、survival analysis 自体は Phase 2 主目的に含めない方針 (S2 plan v2 §0.7 確定済) を継承するが、censoring 重大の場合は補助 KPI として lower percentile (例: 25 percentile) を併記。
3. **PAMS / Mac 環境ワークフロー (§0.4)**: LOB simulation は PAMS が必要、Windows env で PAMS unavailable のため **Mac 上で実行**。S1 で C2/C3 pkl を Mac → Windows 転送した運用と同じパターンで、S3 では parquet bundle を Mac → Windows 転送、Windows 側で aggregation。

### 0.3 S2 で deferred な事項 (S3 で再対応)

- **Determinism guard 確認**: S2 最終ランは `--skip-determinism` で実行 (前回 PID 24392 で `_guard_a/b` parquet 生成済みだったため)。実際の bit-一致判定ログは記録漏れ。S3 では LOB 側 (C3 seed=1000 × 2) で改めて determinism guard を必ず走らせる (§3.6)。
- **LOB SG subclass smoke**: S2 plan v2 §3.5 / 修正 4 の LOB smoke は Windows env で PAMS 不在のため SKIPPED。S3 着手前 (Mac 側) で改めて smoke 1 trial を走らせ、`WInitLoggingSpeculationAgent` の wiring (N=100 SG 全員 w_init non-NaN) を assertion 確認 (§3.1)。

### 0.4 Mac → Windows データ転送ワークフロー (Yuito 指示 #3 詳細)

**Mac 側の役割** (`experiments/YH006_1/code/` 配下のスクリプトを Mac でも動かす):
1. PAMS 0.2.2 環境を整備 (`pip install pams==0.2.2` 等、Mac 側 venv に S1 と同じ)
2. LOB SG subclass smoke 1 trial (§3.1)
3. LOB 100 trial × C2 (§3.3)
4. LOB 100 trial × C3 (§3.4)
5. `data/C2/` `data/C3/` 配下の parquet 群を **tar.gz でバンドル**:
   ```
   tar czf lob_ensemble_$(date +%Y%m%d).tar.gz \
       experiments/YH006_1/data/C2/ \
       experiments/YH006_1/data/C3/ \
       experiments/YH006_1/logs/runtime/{ts}_S3_lob_*.log \
       experiments/YH006_1/logs/runtime/{ts}_S3_determinism_guard.log
   ```
6. 生成 tar.gz を Windows 側に共有 (Google Drive / scp / git LFS / USB 等、Yuito 環境による)

**Windows 側の役割**:
1. tar.gz を `experiments/YH006_1/data/_lob_imported/` に展開
2. `data/C2/` `data/C3/` に移動 (既存 0 ファイル状態を上書きしない、空ディレクトリ前提)
3. **整合性チェック** (S1 §0.7 の pkl 整合性チェックと同じ精神):
   - ファイル数: C2 = 400, C3 = 400 (各 100 trial × 4 parquet)
   - 1 trial sample 読み: `pd.read_parquet(data/C2/trial_1000.parquet)` で n_rt 行数が桁通り (~1,000 行 / trial、Phase 1 LOB と整合)
   - agent parquet で `w_init` 列が non-NaN (subclass 動作確認の ex-post)
4. 整合性 OK で aggregation 開始 (§3.5)。fail なら Mac 側で再生成。

**Mac single-platform を採用する理由 (修正 3 再掲、本 plan §v2 改訂サマリで詳述)**:
- PAMS 0.2.2 は pure Python wheel で配布されているが、その `numpy<2.0.0,>=1.25.1` constraint が Python 3.13 + Windows env で source build を強いる
- numpy 1.26.4 (1.x 最新) は Python 3.13 用 Windows prebuilt wheel が PyPI 不在
- pip が source build → MSVC + meson 要求 → 本 env に MSVC 不在 (vswhere.exe 不在) → fail
- 解決策: **(a) Python 3.12 までダウングレード**、または **(b) Visual Studio Build Tools をインストール**。S3 では負担を避けて Mac 採用、将来 Windows サポート復旧時は (a) (b) どちらか
- v1 で記述した「lifelines が原因」は誤記、`requirements.txt` にも lifelines 無し

---

## 1. S3 の目的

(a) **LOB baseline ensemble の確定**: C2/C3 各 100 trial (seed = 1000..1099) を Mac で実行、`data/C{2,3}/` 配下に Phase 2 §2.1/§2.2/§2.3/§2.4 schema の parquet を生成。

(b) **4 条件 interaction の 100 trial 値確定**: aggregate (S2 完了) + LOB (S3) を結合した `data/ensemble_summary.parquet` 400 行 (C0u/C0p/C2/C3 × 100) を作る。Brief §6 KPI L1 「F1 が Spearman/Kendall/bin variance のうち少なくとも 2 つで符号と桁が一致」を 100 trial 値で再評価 (S1 単 trial では 2/3 一致、bin variance のみ符号反転、S3 で確定)。

(c) **Pooled bin_var_slope の 4 条件比較** (Yuito 指示 #1): aggregate −0.40/−0.29 vs LOB ±? を 2×2 で並べ、世界軸 × wealth 軸の symmetric / asymmetric pattern を確認 (§3.7)。

(d) **Lifetime censoring re-check** (Yuito 指示 #2): LOB T=1500 で censoring 重大 flag 発生数を確認、補助 KPI 検討 (§3.8)。

(e) **Determinism guard (LOB)**: S2 で deferred、S3 で C3 seed=1000 × 2 回独立実行 → bit-一致確認 (§3.6)。

S3 のみで Stage 完了。S1-secondary (4 条件 100 trial の bootstrap CI で plan A/B 分岐判定確定) は別 plan で Yuito 承認後。

---

## 2. 入力

### 2.1 既存資源 (流用、新規実装なし)

S2 で実装済の以下は **そのまま流用**、新規実装は最小限:

- `code/sg_agent.py::WInitLoggingSpeculationAgent` (S2 で実装、smoke は Windows で skip)
- `code/run_experiment.py::run_lob_trial_smoke()` (S2 で実装、本 S3 では full-length 版が必要 → §3.2 で関数追加)
- `code/adapter.py` (aggregate/LOB 両世界対応済)
- `code/parallel.py` (multiprocessing wrapper)
- `code/analysis.py` (`bin_variance_slope_pooled` 含む S2 で全実装済)
- `code/aggregate_ensemble.py` (集計 logic 流用、`ACTIVE_CONDS` を C2/C3 に拡張)
- `code/config.py::CONDITIONS["C2"], CONDITIONS["C3"]` (S2 で placeholder 定義済)

### 2.2 パラメタ (Phase 1 と完全一致、SPEC §3、`code/config.py::LOB_PARAMS`)

LOB (C2/C3):
- `N_sg=100, num_fcn=30, M=5, S=2, B=9`
- `warmup_steps=200, main_steps=1500` (Phase 1 default)
- `c_ticks=28.0` (Phase 1 較正値、`data/_phase1_imported/c_ticks_calibration.json` から load 必須)
- `max_normal_orders=500`
- `wealth_mode`: C2 → uniform、C3 → pareto (α=1.5, xmin=9)
- seed: 1000, 1001, ..., 1099

---

## 3. 作業項目

### 3.1 LOB smoke (Mac 側、S2 で deferred 分)

S2 plan v2 §3.5 / 修正 4 の smoke を Mac 上で実施。

**手順**:
1. Mac 側 `experiments/YH006_1` の最新 git pull
2. PAMS 0.2.2 + 依存揃った venv をアクティベート
3. C3 seed=9001 で smoke (warmup=200, main=200 短縮):
   ```bash
   cd experiments/YH006_1
   python -c "from code.run_experiment import run_lob_trial_smoke; \
              r = run_lob_trial_smoke('C3', 9001); \
              import numpy as np; \
              assert np.all(~np.isnan(r.agents_df['w_init'])); \
              assert len(r.agents_df) == 100; \
              print(f'smoke PASS: n_rt={r.n_round_trips}, runtime={r.runtime_sec:.1f}s')"
   ```
4. assertion fail なら停止 → `stage_S3_diff.md` で報告 + Yuito 相談
5. PASS で §3.2 に進む

**runtime**: ~5-10 秒。

### 3.2 LOB full-length runner 追加 (Mac/Windows 共通コード)

`code/run_experiment.py` に `run_lob_trial(cond_name, seed)` を新規追加。`run_lob_trial_smoke` と同 logic だが:
- `warmup_steps=200, main_steps=1500` (Phase 1 default)
- `is_lob_smoke=False` flag で内部分岐
- 出力: SimResult dataclass (rt_df / agents_df / lifetime_samples_df / wealth_ts_df)、smoke と同 schema

**重要**: snapshot_callback 経路は LOB では使わない (PAMS の SequentialRunner ループ内に hook を入れるのは Phase 1 改変が必要、Brief §4.4 の monkey patch 禁止に抵触)。代わりに **agent.wealth_history 属性から事後抽出** (§3.4 で記述、`SpeculationAgent` は内部で wealth time-series を保持する想定。無ければ `wealth_ts` 列は T/10, 2T/10, ..., T = 10 snapshot を agent ごとに記録する subclass 機能を追加で実装、~30 行)。

**実装後**: `run_one_trial(cond, seed)` から world 分岐で `run_lob_trial` を呼ぶ統一インタフェース。これで `parallel.py::run_parallel_trials` が C2/C3 にも何の変更もなく対応する。

### 3.3 LOB 100 trial × C2 (Mac 側)

```bash
cd experiments/YH006_1
python -m code.lob_ensemble --conds C2 --seed-base 1000 --n-trials 100
```

**新規 script**: `code/lob_ensemble.py` (~120 行)。`aggregate_ensemble.py` をテンプレートに、以下の変更:
- `ACTIVE_CONDS = ["C2", "C3"]`
- `--conds` 引数で部分実行可 (`--conds C2` で C2 のみ)
- `T_total = LOB_PARAMS["main_steps"]` (= 1500、`AGG_PARAMS["T"]` の代わり)
- LOB は smoke が S3 §3.1 で済んでいるので determinism guard は §3.6 で別実行 (本 ensemble script 内には組み込まない、`--skip-determinism` 相当)
- LOB は smoke step 不要 (§3.1 で実行済)
- aggregate 集計 logic (Step C 以降) は `aggregate_ensemble.py` の `aggregate_ensemble_summaries` 等を直接 import して流用

`data/C2/trial_*.parquet` × 100、`agents_*` × 100、`lifetimes_*` × 100、`wealth_ts_*` × 100。

**runtime**: 1 trial あたり Phase 1 LOB は ~30-60 秒の見積もり (warmup 200 + main 1500 = 1700 step、PAMS overhead あり)。Mac の core 数による。8 worker 並列で 100 trial = 100 × 50秒 / 8 ≈ 10 分理想、PAMS overhead で実測 1.5-2x = **20-40 分 / 条件**。

### 3.4 LOB 100 trial × C3 (Mac 側)

```bash
python -m code.lob_ensemble --conds C3 --seed-base 1000 --n-trials 100
```

C2 と同じ流れ。**runtime: 同 20-40 分**。

### 3.5 Mac → Windows 転送 + Windows 側 aggregation

**Mac**: §0.4 のとおり tar.gz バンドル → Windows へ共有。

**Windows**:
1. tar.gz 展開 → `data/C2/` `data/C3/` に配置、整合性チェック (§0.4 の手順)
2. aggregate ensemble との結合:
   ```bash
   cd experiments/YH006_1
   python -m code.combine_ensemble_summaries
   ```
   新規 script `code/combine_ensemble_summaries.py` (~80 行):
   - 既存 `data/ensemble_summary.parquet` (C0u/C0p 200 行) を読む
   - `data/C2/` `data/C3/` の parquet 群から `aggregate_ensemble_summaries` を呼んで C2/C3 各 100 行を計算
   - 4 条件結合した 400 行版を `data/ensemble_summary.parquet` に上書き保存
   - Pooled bin_var_slope を C2/C3 でも計算して JSON に追記

3. 4 条件 interaction + sub-checkpoint + figure 等は新規 script `code/aggregate_full_summary.py` (~150 行) で生成:
   - `outputs/tables/tab_S3_full_summary.csv` (4 条件 × 全指標 mean ± 95% CI、bootstrap 10,000 resample)
   - `outputs/tables/tab_S3_interaction.csv` (5 主指標 + plan B 先取りの 100 trial interaction、(C3-C2) - (C0p-C0u) を bootstrap CI 付きで)
   - `outputs/figures/fig_S3_pooled_bin_var_2x2.png` (世界軸 × wealth 軸の 2×2 grid プロット、§3.7 の symmetric/asymmetric 視覚化)
   - `outputs/figures/fig_S3_interaction_violin.png` (interaction の trial 間 distribution、5 主指標)
   - `outputs/figures/fig_S3_lifetime_distributions.png` (4 条件 lifetime 分布、censoring flag visual)
   - `logs/S3_summary_for_diff.json` (sub-checkpoint, censoring counts, determinism, key numbers)
   - `README.md` への S3 サマリ追記 (S2 と同 format)

**runtime**: aggregation/plotting は S2 の Step C-G と同等規模 (200 → 400 行に増えるが logic 同じ)、**~30 分**。

### 3.6 Determinism guard (LOB、S2 で deferred)

C3 seed=1000 を Mac 側で 2 回独立に実行、`run_lob_trial("C3", 1000)` の SimResult 4 parquet が完全一致 (np.array_equal) を確認。

`code/lob_ensemble.py --determinism-only` モード (or 別 script `code/_determinism_guard_lob.py`) で実装。

**注意**: PAMS 内部で `random.Random(seed)` を使うため、Python の standard random が seed 経路に入る。`run_lob_trial` 内で `prng=_stdlib_random.Random(seed)` を渡す (smoke 関数と同じ)。NumPy 側の RNG は `np.random.default_rng(seed)` で別系統。**両方 seed 固定で bit-一致するかは S3 の重要検証ポイント**。

bit-一致 fail なら:
- Mac/Windows 同 PAMS 0.2.2 でも内部 hash randomization (`PYTHONHASHSEED`) 影響の可能性 → `PYTHONHASHSEED=0` で再走
- それでも fail なら Phase 1 LOB は S1 段階で「同 seed 同 prng で同結果」は確認していたはずなので、subclass 実装による副作用を疑う。`stage_S3_diff.md` で報告 + Yuito 相談

`logs/runtime/{ts}_S3_determinism_guard.log` に 4 parquet × 2 run の hash + 一致判定結果を記録。

### 3.7 Pooled bin_var_slope の interaction 値による pattern 判定 (Yuito 指示 #1、v2 修正 1)

**Primary metric (v2 修正)**: bin_var_slope の符号 4 マスではなく **interaction 値**:

```
interaction_bin_var = (bin_var(C3) − bin_var(C2)) − (bin_var(C0p) − bin_var(C0u))
                    = (LOB diff)              − (aggregate diff)
```

S2 で確定した aggregate diff:
- aggregate diff = bin_var(C0p) − bin_var(C0u) = −0.2879 − (−0.4036) = **+0.1157** (uniform → pareto で +0.116 ぶん bin_var_slope が増加)

**判定基準** (4 パターン α/β/γ/δ):

| パターン | LOB diff の領域 | interaction 値 | 解釈 |
|---|---|---|---|
| **α** | LOB diff ≈ +0.116 (= aggregate diff、同符号同桁) | ≈ 0 | 世界依存性なし。wealth 軸の効果が両世界で **共通** に現れる。F1 機構は world-invariant な wealth-structural property |
| **β** | LOB diff が反転 (≪ 0、−0.1 以下) | ≪ 0 (−0.2 以下) | 世界依存性 **大**。wealth heterogeneity が funnel に与える効果が世界で qualitative に逆転。F1 機構解明の primary signal |
| **γ** | LOB diff が同符号だが桁違い (例: +0.5 や +0.02) | ±0.4 以下、0 跨ぎなし | 世界依存性 **中**。wealth 効果の方向性は同じだが magnitude が違う。F1 機構が world-modulated |
| **δ** | LOB diff の bootstrap CI が **0 を跨ぐ** | CI が 0 を含む | LOB 内で wealth 効果が見えない or sample 不足。S1-secondary の CI で再判定必要、判定保留 |

**S2 では aggregate diff = +0.116 が確定**しているので、本判定は実質「LOB diff の bootstrap CI がどこに来るか」を観察する作業。

**実装**: `code/aggregate_full_summary.py` 内で:
1. 4 条件すべて pooled `bin_variance_slope_pooled(rt_df_concat, K=15)` を計算
2. trial-level `bin_var_slope` の C2/C3 100 trial bootstrap で LOB diff の 95% CI を出す (bootstrap pair 抽出: trial_i の C3 vs C2 を 100 ペア生成、resample)
3. 上表のどの領域に LOB diff が落ちるか + interaction 値を `stage_S3_diff.md` で報告

**補助 KPI** (符号 4 マス、v1 から残置): bin_var_slope 符号そのものの 2×2 表も並列出力する (解釈の visual 補助)。

| | wealth=uniform | wealth=pareto |
|---|---|---|
| world=agg | C0u: -0.404 (S2 値) | C0p: -0.288 (S2 値) |
| world=lob | C2: ??? | C3: ??? |

**S3 での action**: 上記 4 パターンのどれか、interaction 値、+ trial-level CI を `tab_S3_full_summary.csv` に記載。判定の最終確定 (Plan A/B 分岐) は S1-secondary の役割、本 S3 では pattern を **観察**して `stage_S3_diff.md` で報告するに留める。

### 3.8 Lifetime distribution: 仮説 A 中間予測の primary evidence (Yuito 指示 #2、v2 修正 2)

**S2 plan v2 §0.7 の「censoring 重大 flag」用語からは脱却** — LOB で lifetime_median が T に張り付く現象を **仮説 A (= F1 機構が agent lifetime 延長を経由する) の中間予測の primary evidence** として記録する (v2 修正 2)。aggregate (T=50000) census 0 件 vs LOB census >> 0 件は F1 機構解明の **中核 finding 候補の 1 つ**。

**S2 確定値** (aggregate 側):
- C0u: lifetime_median = 389.6 [388.6, 390.6]、lifetime_p90 = 907.4 [904.9, 909.9]
- C0p: lifetime_median = 387.8 [386.9, 388.7]、lifetime_p90 = 905.0 [902.3, 907.7]
- censoring 重大 flag (median > T/2 = 25,000) **0 件 / 100 trial**
- substitute rate ≈ 0.0021 / step → 1 agent ≈ 476 step lifetime expectation

**LOB 予測 (T=1500)**:
- Phase 1 単 trial では LOB で substitute がほぼ発生していない (S1 中間値: C2 で num_subst ≈ 0、C3 で num_subst ≈ 数件) → **lifetime ≈ T = 1500 に張り付き**、`lifetime_median > T/2 = 750` がほぼ全 trial で発生する見込み
- これが **発生すれば仮説 A の中間予測の primary evidence**: 「LOB の orderbook constraint が agent の bankruptcy を抑え、lifetime を延長する」 → F1 機構の中核

**S3 での実装** (4 条件分):
1. `aggregate_full_summary.py` で 4 条件すべて以下を計算:
   - lifetime_median, lifetime_p90 の trial 間 mean ± 95% CI (bootstrap 10000 resample)
   - **censored sample 比率** = sim 終了時生存 agent 数 / 総 lifetime sample 数 (条件ごと)
   - **conditional median** = censored sample を除外した median (生存打ち切られていない sample のみ)
   - **25 percentile** (右端 censoring に頑健、median より低 percentile は影響軽微、補助 KPI)
   - `lifetime_median > T_cond / 2` の trial 数 (aggregate: T/2=25000、LOB: T/2=750)
2. `tab_S3_lifetime.csv` に上記 5 列 × 4 条件を出力
3. `fig_S3_lifetime_distributions.png` で 4 条件の lifetime histogram (T 張り付きが LOB で見えれば仮説 A primary evidence の visual)
4. `stage_S3_diff.md` で以下を **finding として記述**:
   - aggregate 側 (T=50000) では census 0、LOB 側 (T=1500) では census X 件 (X = 実測値)
   - LOB の conditional median と p25 を report (T 張り付きが起きていても tail behavior が見える)
   - X / 100 ≥ 50 trial → **「LOB で lifetime 延長」が中間予測の primary evidence として確定** と記述、proposal Discussion 強化候補
   - X / 100 < 50 trial → 「Phase 1 substitute rate が aggregate より低い」程度の弱い signal、別 mechanism (例: wealth conservation の slack) の検討余地を明記

**survival analysis (Kaplan-Meier 等) は引き続き Phase 2 scope 外** (S2 plan v2 §0.7 確定済)。conditional median + p25 で「LOB で lifetime 延長」の qualitative 確認に留め、quantitative survival curve 推定は将来 stage または Phase 3 に preserve。

**判定基準**: T=1500 で `lifetime_median > 750` が C2/C3 各 100 trial 中 **50 trial 以上**で発生 → 「LOB で lifetime 延長」が **仮説 A の中間予測の primary evidence** として確定。50 trial 未満なら補助 mechanism の signal にとどまる旨を記述。

### 3.9 4 条件 interaction の 100 trial 確定値

`aggregate_full_summary.py` で以下を計算、`outputs/tables/tab_S3_interaction.csv` に出力:

| metric | full | first half | second half |
|---|---|---|---|
| rho_pearson | (C3-C2) - (C0p-C0u) ± 95% CI | first 半分 RT count | second 半分 RT count |
| rho_spearman | … | … | … |
| tau_kendall | … | … | … |
| bin_var_slope | trial-level mean | trial-level mean | trial-level mean |
| bin_var_slope_pooled | (C3-C2) - (C0p-C0u) (pooled 単一値、CI なし、補助) | — | — |
| q90_q10_slope_diff | … | … | … |

S1 単 trial 値:

| indicator | full | first | second |
|---|---:|---:|---:|
| rho_pearson | -0.27 | -0.22 | -0.32 |
| rho_spearman | -0.14 | -0.06 | -0.22 |
| tau_kendall | -0.12 | -0.06 | -0.19 |
| bin_var_slope | +0.03 | -0.13 | +0.28 |
| qreg_slope_diff | -0.89 | -0.50 | -1.20 |

→ S3 100 trial 値で Pearson/Spearman/Kendall の符号 (-) が **bootstrap CI が 0 を跨がない** ことを確認できれば KPI L1 (3 中 2 つ以上) を satisfy。bin_var_slope は S1 の +0.03 が単 trial sample 不足 artifact かを 100 trial pooled で再検証。

**S3 での確定**: 数値だけ出して `stage_S3_diff.md` で報告。**plan A/B 分岐判定は S3 では出さない、S1-secondary plan で Yuito 承認後に確定する**。

### 3.10 出力

| パス | 内容 |
|---|---|
| `data/C2/{trial,agents,lifetimes,wealth_ts}_*.parquet` × 100 | LOB uniform RT/agent/lifetime/wealth_ts |
| `data/C3/{trial,agents,lifetimes,wealth_ts}_*.parquet` × 100 | LOB Pareto 同上 |
| `data/ensemble_summary.parquet` | 400 行 (C0u 100 + C0p 100 + C2 100 + C3 100、S2 版上書き) |
| `outputs/tables/tab_S3_full_summary.csv` | 4 条件 × 全指標の mean ± 95% CI + pooled |
| `outputs/tables/tab_S3_interaction.csv` | interaction (full / first / second half) × 5 主 + plan B 指標、bootstrap CI 付き |
| `outputs/figures/fig_S3_pooled_bin_var_2x2.png` | 世界軸 × wealth 軸の 2×2 plot (§3.7) |
| `outputs/figures/fig_S3_interaction_violin.png` | interaction の trial 間分布 |
| `outputs/figures/fig_S3_lifetime_distributions.png` | 4 条件 lifetime 分布 + censoring flag |
| `logs/runtime/{ts}_S3_lob_C2.log` `{ts}_S3_lob_C3.log` | 各 LOB ensemble runtime/統計 |
| `logs/runtime/{ts}_S3_determinism_guard.log` | LOB C3 seed=1000 × 2 bit-一致 |
| `logs/S3_summary_for_diff.json` | sub-checkpoint, censoring, determinism, pooled values JSON dump |
| `README.md` 追記 | S3 結果サマリ (4 条件 × 主指標 + interaction + censoring + determinism + 世界軸/wealth 軸 pattern) |

### 3.11 README 追記

`## Stage S3 — LOB ensemble (C2/C3) + 4 条件 interaction` セクション、以下を含む:
- 4 条件 100 trial 完走の確認
- 4 条件 × 主指標 mean ± 95% CI 表
- Pooled bin_var_slope 2×2 (§3.7 判定パターン α/β/γ/δ のうちどれか)
- Interaction (full / first / second half) × 5 主指標 + bootstrap CI
- KPI L1 暫定確認 (3 中 2 以上で同符号 + 桁一致 → 100 trial 値で再評価)
- Lifetime censoring flag (LOB で何件発生、補助 KPI 必要か)
- Determinism guard PASS (C3 seed=1000)
- Layer 2 timescale concern 言及継続 (Phase 2 scope 外)
- **plan A/B 分岐判定は出さない、S1-secondary 待ち**

---

## 4. 完了条件

### Mac 側 (sim 実行)
- [ ] `experiments/YH006_1` 最新 git 状態を Mac で pull
- [ ] PAMS 0.2.2 環境 + venv 確認
- [ ] §3.1 LOB smoke 1 trial PASS (w_init non-NaN assertion)
- [ ] `run_lob_trial` 関数追加 (§3.2、`run_experiment.py` 末尾)、smoke と同 schema で full-length 動作
- [ ] §3.6 Determinism guard PASS (C3 seed=1000 × 2 bit-一致)
- [ ] §3.3 LOB C2 100 trial 完走 (parquet 400 個)
- [ ] §3.4 LOB C3 100 trial 完走 (parquet 400 個)
- [ ] tar.gz バンドル生成、Windows 共有 (§0.4)

### Windows 側 (aggregation)
- [ ] tar.gz 展開、整合性チェック PASS (file 数、1 trial sample 読み、w_init non-NaN)
- [ ] `combine_ensemble_summaries` 実行 → `data/ensemble_summary.parquet` 400 行
- [ ] `aggregate_full_summary` 実行 → 全出力ファイル生成 (§3.10)
- [ ] `tab_S3_full_summary.csv` で 4 条件 × 主指標の mean ± 95% CI 揃う
- [ ] `tab_S3_interaction.csv` で 5 主 + plan B 指標の interaction CI 揃う
- [ ] `fig_S3_pooled_bin_var_2x2.png` で §3.7 判定パターンが視覚化済み
- [ ] §3.7 pooled bin_var_slope 4 条件値を `stage_S3_diff.md` で報告 (α/β/γ/δ パターン記述)
- [ ] §3.8 LOB lifetime censoring flag 件数を `stage_S3_diff.md` で報告 (補助 KPI 必要なら p25 + conditional median 追記)
- [ ] §3.9 interaction 100 trial 値を S1 単 trial 値と並べて `stage_S3_diff.md` で報告
- [ ] `README.md` に S3 結果サマリ追記
- [ ] `plans/stage_S3_diff.md` 提出、Yuito レビュー待ち状態

---

## 5. Yuito 確認事項 (実装中の停止トリガー + 完了後レビュー項目)

### 実装中の停止トリガー (発生したら停止 → Yuito 相談)

- §3.1 smoke で `w_init` non-NaN assertion **fail** (subclass wiring 不具合)
- §3.2 `run_lob_trial` 実装で `wealth_ts` 経路 (T/10 snapshot 取得) が PAMS の SequentialRunner ループ改変なしに作れない場合 (§3.2 で wealth time-series を agent 内 hook で取る案を検討、これも fail なら Yuito 相談で `wealth_ts` を LOB では空 schema にする方針切替を検討)
- §3.3/§3.4 LOB 100 trial で **runtime > 8 hours / 条件** (見積 40 分の 12x 超)
- §3.6 Determinism guard で C3 seed=1000 × 2 が **bit-一致 fail** (subclass 副作用、Phase 1 改変なしで再現困難)
- §3.7 で 4 条件 pooled bin_var_slope が **±10 オーダー越えで桁感破綻** (実装バグ疑い)
- §3.8 で C3 censoring 重大 flag 件数が **trial 全 100 件で発生** (= LOB 全 trial で 1 agent も substitute 起きてない)、これは仮説 A 中間予測の極端形なので Yuito 議論ポイント

### 完了後 (Yuito レビュー) 確認事項

1. §3.7 pooled bin_var_slope の世界軸 × wealth 軸 pattern (α/β/γ/δ どれか) の解釈
2. §3.8 LOB censoring flag 件数と補助 KPI (p25, conditional median) の解釈、survival analysis を proposal Limitations に追記する/しないの判断
3. §3.9 interaction 100 trial 値の S1 単 trial 値からの変化、KPI L1 (3 中 2 以上で符号 + 桁一致) の暫定 satisfy 状況
4. S1-secondary plan 着手の go/no-go (本 S3 完了後の bootstrap CI で plan A/B 分岐判定確定)
5. PAMS 0.2.2 環境差 (Mac vs 仮の Linux 等) で再現性が崩れていないか (今回 Mac single-platform で済むので疑念は薄いが念のため)

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (Draft、廃止) | Stage S3 plan 初版、Yuito S2 承認時の 3 点指示反映: (1) bin_var_slope 符号解釈の世界軸 × wealth 軸 2×2 判定 §3.7 / (2) LOB lifetime censoring re-check + 補助 KPI 検討 §3.8 / (3) Mac → Windows データ転送ワークフロー §0.4。S2 で deferred な determinism guard (§3.6) と LOB smoke (§3.1) を S3 で再対応。S2 既存実装 (sg_agent / adapter / parallel / aggregate_ensemble の集計 logic) を最大限流用、新規実装は `run_lob_trial`、`lob_ensemble.py`、`combine_ensemble_summaries.py`、`aggregate_full_summary.py` の 4 ファイル + 既存 `run_experiment.py` に full-length runner 追加のみ。S1-secondary (4 条件 100 trial bootstrap CI で plan A/B 分岐判定) は別 plan で Yuito 承認後。 |
| v2.0 (本書、承認版) | Yuito v1 承認時 3 点修正反映: (修正 1, §3.7) primary metric を bin_var_slope 符号 4 マスから **interaction 値** に変更、aggregate diff = +0.116 が S2 で確定済を起点に LOB diff の bootstrap CI で α/β/γ/δ 4 パターン判定 / (修正 2, §3.8) LOB lifetime T 張り付きを「censoring 重大 flag」から「**仮説 A 中間予測の primary evidence**」に positioning 変更、p25 + conditional median を補助、survival analysis は引き続き scope 外 / (修正 3, §0.4 + v2 改訂サマリ) Mac single-platform 採用の真因を実調査 (`pip install pams==0.2.2 --dry-run`) で確認、`PAMS → numpy<2.0 → numpy 1.26.4 が Python 3.13 + Windows prebuilt wheel 不在 → MSVC 必要 → 不在で fail` の chain を記録、v1 の lifelines 説は誤記として明記、将来 Windows 復旧パス (Python 3.12 ダウングレード or MSVC Build Tools install) も明記。 |
