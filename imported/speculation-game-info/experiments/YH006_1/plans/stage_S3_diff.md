# Stage S3 diff — LOB ensemble + 4 条件 interaction 進捗ログ

S3 plan v2 に基づく実装・実行ログ。3 段階 (Mac sim → 転送 → Windows aggregation) の進捗を 1 行ずつ追記する形 (Yuito S3 v1 承認時要望)。

| Stage | Date | 状態 | Note |
|---|---|---|---|
| **0. plan v2 + 実装準備** | 2026-04-29 | **完了** | plan v2 反映、Mac/Windows 両側コード prep 済 (詳細下) |
| **1. Mac LOB 100 trial × 2 条件** | 2026-04-30 | **完了** | smoke PASS / determinism guard PASS / C2 100 + C3 100 完走、§3.8 censoring 100/100 件 = 仮説 A chain link の primary evidence (Yuito 判断: continue 確定、3 指標切替で Windows aggregation へ申し送り) |
| 2. Mac → Windows 転送 | 2026-04-30 | **完了 (git 経由)** | tar.gz は省略、parquet を直接 commit + push (S2 と同パターン、データ ~15MB と軽量のため) |
| **3. Windows aggregation** | 2026-05-01 | **完了** | combine (200→400 行) + aggregate_full_summary 実行、6 出力 + README 追記、§3.7 pattern δ (判定保留)、§3.8 仮説 A primary evidence 確定、Mac mandate の 3 主指標切替反映済 |

---

## Stage 0: plan v2 + 実装準備 (2026-04-29 完了)

### plan v2 反映
- `plans/stage_S3_plan.md` を v1 → v2 に更新
- 修正 1 (§3.7): primary metric を bin_var_slope 符号 4 マスから interaction 値 (= LOB diff − aggregate diff) に変更、α/β/γ/δ 4 パターン判定基準を再定義
- 修正 2 (§3.8): LOB lifetime T 張り付きの positioning を「censoring 重大 flag」から「**仮説 A 中間予測の primary evidence**」に変更
- 修正 3 (§0.4): Windows-PAMS unavailable 真因を `pip install pams==0.2.2 --dry-run` 実調査で特定、v1 の lifelines 説は誤記として撤回:
  - PAMS 自体: `py3-none-any.whl` (pure Python)
  - 真因: `numpy<2.0.0` 制約 → `numpy 1.26.4` の Python 3.13 + Windows prebuilt wheel が PyPI 不在 → source build 要 → MSVC 不在で fail
  - 復旧パス: Python 3.12 ダウングレード or MSVC Build Tools install

### 実装着手
新規 / 変更ファイル:

| パス | 役割 | 行数 | 動作確認 |
|---|---|---:|---|
| `code/run_experiment.py` (編集) | `run_lob_trial` 追加 + dispatcher で LOB full-length 経路有効化 | +25 | syntax OK、import 解決 OK (Windows で PAMS は import されない経路) |
| `code/lob_ensemble.py` (新規) | Mac 側 LOB ensemble runner + determinism guard | 200 | syntax OK |
| `code/combine_ensemble_summaries.py` (新規) | Windows 側 step 1: 整合性チェック + ensemble_summary 結合 (200 → 400 行) | 130 | syntax OK |
| `code/aggregate_full_summary.py` (新規) | Windows 側 step 2: 4 条件 full summary + interaction + lifetime + figures + README append | 360 | syntax OK |

### Note: LOB の wealth_ts は単一 snapshot
S3 plan v2 §3.2 で記載のとおり、`run_lob_trial` は smoke fn と同じく終了時 1 snapshot のみ取る。corr_winit_wt_T1..T10 は同値 (= corr(w_init, w_final)) に degenerate するが、aggregate との比較は trial-level で機能する。複数 snapshot 化は将来 stage で必要なら custom Saver で実装、本 S3 では scope 外 (Yuito 確認事項にも記載)。

### 次のアクション (Mac 側)
1. Mac 側で `experiments/YH006_1` を `git pull` (本 commit を取得)
2. PAMS 0.2.2 venv 確認 (`pip install pams==0.2.2`、numpy<2.0)
3. smoke 1 trial (S3 plan §3.1):
   ```bash
   cd experiments/YH006_1
   python -c "from code.run_experiment import run_lob_trial_smoke; \
              import numpy as np; \
              r = run_lob_trial_smoke('C3', 9001); \
              assert np.all(~np.isnan(r.agents_df['w_init'])); \
              print(f'smoke PASS: n_rt={r.n_round_trips}, runtime={r.runtime_sec:.1f}s')"
   ```
4. determinism guard + full ensemble:
   ```bash
   python -m code.lob_ensemble  # default: --conds C2,C3 --n-trials 100
   ```
5. tar.gz バンドル → Windows 共有 (`logs/S3_mac_summary.json` 生成済を含めて)

---

## Stage 1: Mac LOB 100 trial × 2 条件 (2026-04-30 完了)

### 環境
- Mac venv: `experiments/.venv` (Python 3.12.7、PAMS 0.2.2、numpy 1.26.4、pandas 3.0.2)
- pyarrow 24.0.0 を本 stage で追加 install (parquet engine 不在で初回 guard 失敗、`pip install pyarrow` で resolve、`requirements.txt` 未更新)

### Mac 側で適用した実装 fix (Windows commit から漏れていた点)
- `code/run_experiment.py`: `sys.path` に `HERE` (=`code/`) を追加。Windows の S3 prep commit (`15700c1`) 時点では `from sg_agent import WInitLoggingSpeculationAgent` が PAMS 不在で実行されない経路だったため検出できなかった。Mac 側で smoke 初回実行時に `ModuleNotFoundError: No module named 'sg_agent'` が発生 → HERE を sys.path に追加して resolve。本修正は本 commit に同梱。

### §3.1 LOB smoke (C3 seed=9001, warmup=200/main=200)
| 指標 | 値 |
|---|---|
| n_round_trips | 3,521 |
| n_substitutions | 47 |
| runtime | 70.7s |
| `w_init` non-NaN assertion | PASS |
| `len(agents_df) == 100` assertion | PASS |
| w_init 範囲 | min=9, max=99, median=16 (Pareto α=1.5 整合) |

### §3.6 Determinism guard (LOB C3 seed=1000 × 2)
| 確認項目 | 結果 |
|---|---|
| `trial_1000.parquet` sha256 | MATCH (`0484bb795ad55d22...`) |
| `agents_1000.parquet` sha256 | MATCH (`ea793a8947654099...`) |
| `lifetimes_1000.parquet` sha256 | MATCH (`8144f2099f74b8f1...`) |
| `wealth_ts_1000.parquet` sha256 | MATCH (`93dc6bad78aa94c5...`) |
| rt_df semantic (8 cols `np.array_equal`) | PASS |
| 単 trial runtime | 178-181s (3 min) |
| log | `logs/runtime/20260430_005146_S3_lob_ensemble.log` |

→ **bit-一致 PASS、PAMS の `random.Random(seed)` + numpy `default_rng(seed)` が full bit-一致を提供する。subclass 副作用なし。**

### §3.3 / §3.4 LOB ensemble (C2/C3 各 100 trial)

`python -m code.lob_ensemble --skip-determinism --conds C2,C3 --n-trials 100` (8 worker、main_steps=1500、warmup=200)。

| cond | trial 完走 | 総 runtime | 単 trial runtime range | parquet 出力 |
|---|---|---:|---|---:|
| C2 | 100/100 | 4128s (~69 min) | 145-600s | 400 ファイル (4 schema × 100 trial) |
| C3 | 100/100 | 4075s (~68 min) | 143-543s | 400 ファイル |

データサイズ: C2 = 7.5 MB、C3 = 7.8 MB。S2 plan 見積 (~24 MB / trial) より遥かに小さい (LOB T=1500 vs aggregate T=50000 で 33x 短いため round-trip 数が少ない)。→ tar.gz バンドルせず git に直接 commit。

### Trial-level basic stats (4 条件比較に最低限の桁感)

| metric | C2 (LOB uniform) | C3 (LOB pareto) | C0u (S2、参考) | C0p (S2、参考) |
|---|---:|---:|---:|---:|
| n_round_trips mean (range) | 4,273 (2,212-7,594) | 4,777 (2,714-7,781) | ~10,500 / trial (推定) | ~10,500 / trial (推定) |
| forced_retired mean (range) | 10.0 (3-23) | 35.0 (16-48) | ~210 / trial (S2) | ~210 / trial (S2) |
| lifetime_samples mean | 110.9 / trial | 138.9 / trial | n/a | n/a |

→ **forced_retired: aggregate ~210 vs LOB C2 10 / C3 35** で約 6x-20x の差。LOB friction が agent bankruptcy を抑制する仮説 A の中間予測と整合。Pareto 軸では C2→C3 で 3.5x 増 (uniform で長く生き残る agents が Pareto 下では tail から速く失敗)。

### **§3.8 Lifetime censoring — 仮説 A chain link の primary evidence (Yuito 判断: continue 確定)**

T=1500 で `lifetime_median > T/2 = 750` の trial 件数:

| cond | median > 750 件数 | pooled lifetime | trial-level conditional indicators |
|---|---:|---|---|
| C2 | **100/100 件** | median=1500 / p25=1500 / p90=1500 | censored 比率 90.1%、p25 mean = **1479.6** (= 下位 25% も T 張り付き) |
| C3 | **100/100 件** | median=1494 / p25=212 / p90=1500 | censored 比率 72.0%、p25 mean = **502.3** (= Pareto tail で早期退場) |

判定基準 (plan §3.8): `lifetime_median > 750` が 50 trial 以上 / 100 → 「LOB で lifetime 延長」が仮説 A 中間予測の primary evidence。本実測は **100/100、極端形に近い**。

#### Yuito 判断 (2026-04-30): continue 確定

**Plan §5 stop-trigger 該当性 — flag は HIT したが degenerate 形 (= substitute ゼロ) には至らず**:
- C2 trial 平均 forced_retired = 10、C3 = 35。substitute が観察されている以上、これは「観察対象として記録する現象」であって「実験を止めるべき bug」ではない
- むしろ F1 機構解明の中核 evidence の 1 つ → continue で Windows aggregation へ進む

#### 仮説 A chain link の直接デモンストレーション読み (Yuito interpretation)

C2 と C3 の lifetime tail の対比は、仮説 A chain (LOB friction → wealth variance 縮小 → agent lifetime 延長 → 初期 wealth 分布の persistence) の中間 link を **直接デモンストレーション**している可能性が高い:

| cond | lifetime tail 挙動 | mechanism reading |
|---|---|---|
| **C2 (LOB uniform)** | 全 agent が roughly 同 pace で生存、下位 25% (p25 ≈ 1480) も T 近く到達 | wealth variance が縮小、初期 uniform 分布が dynamics で増幅されない |
| **C3 (LOB pareto)** | 下位 25% (p25 ≈ 502) は早期退場、上位は確実残存 | **tail composition (Pareto 性) が persist**、初期 Pareto 分布が dynamics で潰れない |

→ **SG の dynamic-wealth turnover が LOB で阻害されることの直接 signature**。aggregate (T=50000、censoring 0 件、median 388-389) との対比で、LOB friction が agent identity の流動を実際に止めている定量証拠。

#### Windows aggregation での主指標切り替え (CC 提案通り、Yuito 承認)

LOB lifetime に対しては median が T 張り付きで信頼できないため、§3.8 中間予測の primary evidence として **以下の 3 指標** を使う:

1. **p25 lifetime** (主指標 1) — 右端 censoring に頑健、tail composition の差を直接捉える
2. **conditional median** (主指標 2) — 退場 agent (uncensored sample) のみの中央値、生き残れなかった agent の lifetime tail
3. **censoring 率** (主指標 3) — sim 終了時生存 agent の割合、LOB friction 強度の素朴指標

**median lifetime は補助** として併記、ただし interpretation で「censoring によって T に張り付いている、median > T/2 は下界推定」と注記する。p90 も同様 (T 張り付きで discrimination 不能、補助のみ)。

`aggregate_full_summary.py` で 4 条件 × 上記 3 主指標 + 補助 (median, p90) を `tab_S3_lifetime.csv` に出力、`fig_S3_lifetime_distributions.png` で 4 条件の lifetime histogram を可視化 (T 張り付きと p25 対比が visual で見える)。

#### S1-secondary への申し送り

本 §3.8 finding (censoring 100/100 + C2/C3 p25 対比) を **「仮説 A 中間予測の primary evidence」** として S1-secondary plan に申し送る。S1-secondary は本来 4 条件 100 trial bootstrap CI で plan A/B 分岐判定を確定する役割だが、§3.8 finding は分岐判定とは別軸の **mechanism evidence** として独立に位置付け、Phase 2 最終 README で:

- **Fig.4** (中間予測 figure): C2/C3 の lifetime histogram + p25 / conditional median / censoring 率を bar/violin で 4 条件並列、aggregate との対比を強調
- **Fig.5** (timescale 解析 figure): `corr(w_init, w(t))` の time decay と lifetime 延長を 1 figure に統合 (LOB で wealth persistence が高い → lifetime 延長が下支え) で可視化

を予定する。survival analysis (Kaplan-Meier) は引き続き Phase 2 scope 外 (S2 plan v2 §0.7 を継承)、p25 + conditional median + censoring 率の 3 指標で qualitative 確認に留める。

### §3.7 Pooled bin_var_slope は Mac 側で計算しない方針継承
plan §3.5 / §3.7 の bin_var_slope pooled 計算は Windows 側 `aggregate_full_summary.py` で実施。Mac 側は trial parquet 出力に専念。

### Mac → Windows 転送
- `tar.gz` バンドル不要 (データ ~15MB と軽量、git 直 commit が S2 のパターン)
- `data/C2/` `data/C3/` (各 400 parquet) + `logs/S3_mac_summary.json` + `logs/runtime/*S3_*log` を本 commit に同梱

### S3_mac_summary.json
```json
{
  "stage": "S3-mac",
  "conds": ["C2", "C3"],
  "n_trials_per_cond": 100,
  "seed_base": 1000,
  "n_workers": 8,
  "main_steps": 1500,
  "warmup_steps": 200,
  "determinism_pass": true,
  "timestamp": "2026-04-30T03:18:18.340424"
}
```

(注: `--skip-determinism` で本 ensemble run を実行したため `determinism_pass: true` は default 値。実際の guard PASS は別 run で `logs/runtime/20260430_005146_S3_lob_ensemble.log` に記録済。)

---

## Stage 2: Mac → Windows 転送 (2026-04-30 完了 / git 経由)

tar.gz バンドルは Stage 1 §「データサイズ」のとおり省略、`data/C2/` `data/C3/` の parquet を本 commit に直接含めて git push。Windows 側で `git pull` するだけで Stage 3 に進める。

### Windows 整合性チェック (pull 後に実行する手順)
- ファイル数: `ls data/C2/ | wc -l` → 400、同 C3 → 400
- 1 trial sample: `pd.read_parquet('data/C2/trial_1000.parquet')` で n_rt 行数が桁通り (~3,000-5,000 行)
- agent parquet で `w_init` 列 non-NaN: `pd.read_parquet('data/C2/agents_1000.parquet')['w_init'].isna().sum() == 0`

---

## Stage 3: Windows aggregation (2026-05-01 完了)

### 実行
1. **Mac mandate 反映** (Yuito 2026-04-30 の 3 主指標切替): `code/aggregate_full_summary.py` の lifetime 部を更新
   - `lifetime_evidence_table`: 主指標 = p25 / conditional median / **sample-level censoring 率** (新規、`lifetimes_*.parquet` の `censored` 列から計算)、補助 = median / p90 / median>T/2 件数
   - `hypothesis_A_evidence`: 判定軸を「LOB sample-level censoring vs aggregate のギャップ」+「median>T/2 件数」+「C2/C3 p25 対比」に再構成
   - `append_readme`: lifetime テーブルを 主指標太字 + 補助併記 のフォーマットに変更、Mac stage finding (C2 p25=1500 vs C3 p25=212 の対比解釈) を継承
2. `python -m code.combine_ensemble_summaries` 実行 (~32 秒): 整合性チェック PASS、`data/ensemble_summary.parquet` を 200 → 400 行に拡張
3. `python -m code.aggregate_full_summary` 実行 (~47 秒): 4 条件 full summary + interaction + lifetime + 3 figures + README 追記 + JSON dump

### §3.7 Pooled bin_var_slope 4 条件 + Pattern 判定

| | wealth=uniform | wealth=pareto | wealth diff |
|---|---:|---:|---:|
| world=agg | C0u: **−0.4036** | C0p: **−0.2879** | **+0.1157** (S2 確定) |
| world=lob | C2: **−0.0330** | C3: **−0.1748** | **−0.1418** |

- **Pooled interaction value** = LOB diff − aggregate diff = **−0.2575** (符号反転、桁同等)
- **Trial-level bootstrap** (100 trial pair、§3.7 v2 mandate の primary metric):
  - LOB diff mean = **−0.0054**, CI = [**−0.0524, +0.0415**]
  - aggregate diff = +0.1157
  - LOB diff CI が **0 を跨ぐ** → **Pattern δ (判定保留)**

→ pooled (n_rt が C2=427k / C3=478k で aggregate より遥かに少ない) では symmetric な符号反転が見えるが、trial-level CI では 0 を跨いでしまうため、§3.7 v2 mandate の primary metric (trial-level) では確定不能。**S1-secondary plan の bootstrap CI で再判定** (Yuito 確定済方針)。

### §3.9 4 条件 Interaction (S1 単 trial 値からの大変化)

| metric | S1 単 | S3 100 trial mean ± 95% CI | KPI L1 |
|---|---:|---:|---|
| rho_pearson | −0.27 | **−0.020** [−0.042, +0.002] | 弱負、CI ほぼ 0 跨ぎ |
| rho_spearman | −0.14 | **−0.009** [−0.022, +0.004] | CI 0 跨ぎ |
| tau_kendall | −0.12 | **−0.007** [−0.018, +0.003] | CI 0 跨ぎ |
| bin_var_slope | +0.03 | **+0.005** [−0.054, +0.064] | CI 大幅 0 跨ぎ |
| q90_q10_slope_diff | −0.89 | **+0.006** [−0.009, +0.021] | 符号反転 + CI 0 跨ぎ |

→ 100 trial で **interaction が ほぼ ゼロに収束**、S1 単 trial の sign は trial-by-trial noise だった可能性が高い。S1 plan v2 の警告 (「plan A/B 分岐判定は S1 単 trial では出さない、S2/S3 で確定」) が的中した形。**KPI L1 (3 中 2 で同符号 + 桁一致) は判定保留、S1-secondary plan の bootstrap CI で確定**。

### §3.8 Lifetime: 仮説 A 中間予測 primary evidence (Mac mandate 主指標切替後)

| cond | T | n_samples | **p25 (主)** | **conditional median (主)** | **censoring 率 (主)** | median (補助) | p90 (補助) | median>T/2 件 (補助) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| C0u | 50000 | 1,071,577 | 227.0 | 391.0 | **0.9%** | 389.6 | 907.4 | 0/100 |
| C0p | 50000 | 1,076,362 | 224.0 | 389.0 | **0.9%** | 387.8 | 905.0 | 0/100 |
| C2 | 1500 | 11,093 | **1500.0** | 119.0 | **90.1%** | 1500.0 | 1500.0 | 100/100 |
| C3 | 1500 | 13,891 | **212.0** | 40.0 | **72.0%** | 1485.5 | 1500.0 | 100/100 |

**仮説 A 判定** (`hypothesis_A_primary_evidence: true`):

> LOB censoring_rate=**81.1%** vs agg **0.9%** (gap = **+80.1%**)、median>T/2 trial 件数 = **200/200**、C2 p25=1500 vs C3 p25=212 → **仮説 A 中間予測の primary evidence 確定** (LOB friction が agent turnover を抑制、tail composition persist)。

Mac stage の解釈そのまま継承:
- **C2 (LOB uniform)**: 全 agent が roughly 同 pace で生存 (p25 も T 近く 1500)、wealth variance が縮小、初期 uniform 分布が dynamics で増幅されない
- **C3 (LOB pareto)**: 下位 25% (p25 ≈ 212) は早期退場、上位は確実残存、**tail composition (Pareto 性) が persist**、初期 Pareto 分布が dynamics で潰れない
- → **SG の dynamic-wealth turnover が LOB で阻害されることの直接 signature**。aggregate (T=50000、censoring 0.9%、median 388-389) との対比で、LOB friction が agent identity の流動を実際に止めている **定量証拠**。

`fig_S3_lifetime_distributions.png` で 4 条件 histogram visual 化 (T 張り付き + p25 対比が見える)。

### 出力ファイル一覧

| パス | 内容 |
|---|---|
| `data/ensemble_summary.parquet` | 400 行 (C0u/C0p/C2/C3 各 100、S2 版上書き) |
| `outputs/tables/tab_S3_full_summary.csv` (5.3 KB) | 4 条件 × 全指標 (16 + bin_var_pooled) mean ± 95% CI |
| `outputs/tables/tab_S3_interaction.csv` (0.4 KB) | 5 主指標 interaction + bootstrap CI |
| `outputs/tables/tab_S3_lifetime.csv` (0.4 KB) | 4 条件 lifetime 主指標 3 + 補助 3 |
| `outputs/figures/fig_S3_pooled_bin_var_2x2.png` (34 KB) | 世界軸 × wealth 軸 2×2 heatmap + Pattern δ ラベル |
| `outputs/figures/fig_S3_interaction_violin.png` (90 KB) | 5 metrics の interaction trial 間分布 violin |
| `outputs/figures/fig_S3_lifetime_distributions.png` (75 KB) | 4 条件 lifetime histogram + T/2 / T 縦線 |
| `logs/S3_summary_for_diff.json` | 全 key 数値 (pooled, interaction, lifetime, hyp_A) JSON dump |
| `README.md` | "Stage S3" セクション追記 (4 条件主指標表 + interaction + lifetime + Pattern + Layer 2 再掲) |

### Yuito レビュー待ち事項 (S3 plan v2 §5)

1. **§3.7 Pattern δ (判定保留) の解釈**: pooled では symmetric 符号反転 (interaction = −0.258、有意な信号) なのに trial-level CI では 0 跨ぎ。pooled と trial-level の estimator 差を S1-secondary でどう扱うか
2. **§3.8 仮説 A primary evidence 確定** の Phase 2 最終 README + proposal Discussion 強化方針
3. **§3.9 interaction が S1 単 trial の値から 100 trial で ≈ 0 に収束** の解釈 (sample size 効果? S1 noise?)
4. **KPI L1 暫定確認 — CI 0 跨ぎが多い**: S1-secondary で確定 / 別 KPI 採用検討
5. S1-secondary plan 着手の go/no-go (本 S3 完了で着手可、Yuito 承認後)

### S1-secondary plan への申し送り
- 4 条件 100 trial bootstrap CI で plan A/B 分岐判定確定 (本来 scope)
- 仮説 A primary evidence (§3.8 finding) を Fig.4 (lifetime + p25/cond_median/censoring) + Fig.5 (timescale + persistence) として最終 README に組み込む方針 (Yuito mandate 継承)
- Pattern δ 保留中、pooled vs trial-level の estimator 差をどう reconcile するか議論
