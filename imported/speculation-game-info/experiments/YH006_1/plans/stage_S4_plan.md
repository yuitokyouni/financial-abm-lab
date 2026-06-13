# Stage S4-S5 plan v1 — Ablation A1: q-fix 較正 + 100 trial ensemble + KPI L2 判定

| 項目 | 値 |
|---|---|
| Stage | S4-S5 — Ablation A1 (`q_rule="const"`、C2_A1 / C3_A1 × 100 trial) |
| Status | **Draft (Yuito 承認待ち)** |
| 想定 runtime | Win 5 分 (calibration) + Mac 2-3 時間 (smoke + determinism + 200 trial) + Win 30 分 (aggregation) |
| 新規 sim | LOB 200 trial (C2_A1 100 + C3_A1 100、Mac で実行) |
| 前提 | S3 完走済 (ensemble_summary.parquet 400 行、C3 trial parquet × 100 → q_const 較正源) |

本 plan は Stage S4 (calibration + smoke) と S5 (A1 ensemble + L2 判定) を一体で扱う。S6 (A3 ablation = lifetime cap) は別 plan で S5 完走後に着手。S1-secondary (4 条件 plan A/B 分岐確定) は本 ablation と独立、Mac sim 中の余時間に Win 側で並走実行可。

---

## 0. S3 完了状態と本 stage の起点

### 0.1 S3 主要 finding (本 plan の起点)

- **§3.7 Pattern δ (判定保留)**: pooled bin_var では interaction = −0.258 (符号反転、信号あり)、trial-level CI [−0.052, +0.042] では 0 跨ぎ。S1-secondary 待ち
- **§3.8 仮説 A 中間予測 primary evidence 確定**: LOB censoring 81.1% vs agg 0.9%、C2 p25=1500 vs C3 p25=212。LOB friction が agent turnover を抑制、tail composition persist
- **§3.9 5 主指標 interaction の 100 trial 値 (KPI L1 暫定 / S1-secondary 確定前)**:
  | metric | S3 100 trial interaction (mean [CI]) |
  |---|---|
  | rho_pearson | −0.020 [−0.042, +0.002] |
  | rho_spearman | −0.009 [−0.022, +0.004] |
  | tau_kendall | −0.007 [−0.018, +0.003] |
  | bin_var_slope | +0.005 [−0.054, +0.064] |
  | q90_q10_slope_diff | +0.006 [−0.009, +0.021] |

→ **S3 baseline F1 は trial-level では既にゼロ付近**。S5 では「A1 で interaction が更に縮小するか」を 100 trial bootstrap CI で問う構造。pooled bin_var (interaction = −0.258) の方が L2 判定で signal を取りやすい予測。

### 0.2 S4-S5 着手前提

- aggregate parity tests (Phase 1 既存) 全 27 件 **PASS** (Windows、本 plan §0.4 Phase 1 hook 追加後): `experiments/YH005/tests/test_parity.py` 18 件 + `experiments/YH006/tests/test_aggregate_parity.py` 9 件
- LOB 系 Phase 1 tests (`experiments/YH006/tests/test_parity.py` / `test_roundtrip_invariants.py` / `test_wealth_conservation.py`) は **Mac 側で要再走** (本 plan §3.1 で Mac 着手時に実施)
- `WInitLoggingSpeculationAgent` (S2 で実装、S3 で稼働確認済) を親に `QConstSpeculationAgent` (本 plan §3.2 で実装) を作成、ablation A1 を実装

### 0.3 KPI L2 (GLOSSARY 既定義) の本 stage 操作化

GLOSSARY L2:
> A1 ablation でinteractionが50%以上縮小 + bootstrap 95% CIが0を含まない → 因果経路（q）の特定

本 plan での具体判定 (§3.7 で実装):
- **shrinkage ratio** = |A1_interaction| / |S3_interaction| ≤ 0.5 (= 50% 以上縮小)
- **shrinkage = S3_interaction − A1_interaction** の bootstrap 95% CI が **0 を含まない** (= 縮小が statistical に有意)
- 両条件 satisfy で **L2 PASS** を当該 metric に出す。5 主指標で **PASS 件数** を報告

S3 で interaction がそもそも 0 付近の場合 (Pearson/Spearman/Kendall) は shrinkage の signal が取りにくい。**pooled bin_var_slope の interaction (−0.258、強い signal)** を補助 KPI として併記。

### 0.4 Phase 1 後方互換拡張 (S2 §0.4 統一ルール継承)

S2 plan §0.4 で確定済の Phase 2 全体ルール:
> 「Phase 1 への後方互換拡張は許容、動作変更は禁止」(`stage_S2_diff.md` で実証済、aggregate_sim.py に snapshot_callback + log_substitutes 追加 + 全 Phase 1 test pass)

本 S4 で同 protocol で 1 箇所追加:
- `experiments/YH006/speculation_agent.py::SpeculationAgent` に **method `_compute_open_quantity(self) -> int` を新規追加**
  ```python
  def _compute_open_quantity(self) -> int:
      return max(1, int(self.sg_wealth // self.B))
  ```
- 既存 `submit_orders_by_market` 内の `q = max(1, int(self.sg_wealth // self.B))` (line 218) を `q = self._compute_open_quantity()` に差し替え
- default 経路は完全に既存挙動と bit-一致 (関数名で 1 行包んだだけ)
- 既存 Phase 1 test 全 pass → 本 stage `stage_S4_diff.md` で記録

検証状況 (本 plan 提出時点):
- Windows: aggregate parity 27 件 PASS 済
- Mac: LOB tests 未確認 → §3.1 で実施

A1 subclass `QConstSpeculationAgent` は `_compute_open_quantity` を override して `max(1, q_const)` を返す (`code/sg_agent.py` 内、§3.2)。

### 0.5 q_const 較正方針 (Yuito S1 plan §0.6 確定 + S3 後の更新)

GLOSSARY 当初設計: 「C3 pilot 5 trial から median(q_i(t))、5 trial の median-of-medians」。

S3 完走で **C3 100 trial の RT parquet が揃っている**ので、pilot 5 trial に縛らず:
- **Primary**: pooled q の median (全 100 trial の RT を concat、`median(q)`) → S3 plan の subset 較正より高精度
- **Sanity**: per-trial median の median-of-medians (100 trial 値の median) + SD

両者が乖離 (e.g., |diff| > 1) なら設計再考。実測 (2026-05-13):
- pooled median = 3.00
- median-of-medians = 3.00 (SD = 0.611)
- **|diff| = 0.000 → 完全一致、q_const = 3 を確定**

C2_A1 と C3_A1 で **同 q_const = 3 を使用** (Yuito S1 plan §0.6 既定方針継承、wealth → q 経路を切る ablation design)。

---

## 1. S4-S5 の目的

(a) **A1 ablation の wiring 確定**: `_compute_open_quantity` hook (Phase 1) + `QConstSpeculationAgent` subclass + dispatcher (run_experiment.py / run_lob_trial / parallel.py) を組み、smoke + determinism guard で動作保証

(b) **q_const 較正の確定**: C3 100 trial pooled median = **3** を確定値とする (本 plan §0.5)

(c) **C2_A1 / C3_A1 × 100 trial 完走**: Mac 側で 200 LOB trial、parquet × 800 ファイルを生成

(d) **L2 判定**: 5 主指標 × A1 vs S3 baseline の shrinkage を bootstrap CI 付きで報告、PASS 件数を出す。pooled bin_var_slope の interaction も併記

(e) **S6 (A3) plan の前提整備**: A3 は `WInitLoggingSpeculationAgent` に lifetime cap を加える同 pattern。本 S4-S5 の design + 実装が S6 にそのまま転用可能 (本 plan には S6 詳細は書かない、別 plan で)

S6 (A3) と S1-secondary は本 plan の scope 外、別 plan。

---

## 2. 入力

### 2.1 既存資源 (流用、新規実装は最小限)

- `experiments/YH006/speculation_agent.py`: `_compute_open_quantity` hook を追加 (§0.4、本 stage で Phase 1 を編集する唯一の箇所)
- `code/sg_agent.py::WInitLoggingSpeculationAgent` (S2 で実装、A1 subclass の親)
- `code/run_experiment.py::run_lob_trial` / `run_lob_trial_smoke` (S3 で実装、`q_const` kwarg 追加)
- `code/parallel.py::run_parallel_trials` (S2 で実装、`q_const` kwarg 追加)
- `code/aggregate_ensemble.py::aggregate_ensemble_summaries` (S2/S3 で実装、6 cond combine で流用)
- `code/analysis.py::bin_variance_slope_pooled` (S2 で実装)
- `code/stats.py::bootstrap_ci` (S1 で実装)
- `outputs/tables/tab_S3_interaction.csv` (S3 で生成、L2 判定の baseline として読み込み)

### 2.2 パラメタ (Phase 1 と同一 + 新規 q_const)

`config.py::CONDITIONS` の `C2_A1` / `C3_A1` (S2 で placeholder 定義済):
- `world="lob"`, `q_rule="const"`, `lifetime_cap=False`
- `wealth_mode`: C2_A1 → uniform、C3_A1 → pareto

LOB session params は `LOB_PARAMS` (S3 と同一、`main_steps=1500, warmup_steps=200, c_ticks=28.0, N_sg=100, num_fcn=30`)。

**新規**: `qConst = 3` を `cfg["SGAgents"]["qConst"]` に注入、`QConstSpeculationAgent.setup` で読む。

---

## 3. 作業項目

### 3.1 Phase 1 hook 追加 + Phase 1 test 再走 (S4)

実装手順:
1. `experiments/YH006/speculation_agent.py`: `_compute_open_quantity` method 追加 + `submit_orders_by_market` line 218 を hook 呼び出しに差し替え (§0.4)
2. Phase 1 test 全再走:
   - Windows: `python -m pytest experiments/YH005/tests/test_parity.py experiments/YH006/tests/test_aggregate_parity.py -x` (aggregate-only)
   - Mac: `python -m pytest experiments/YH006/tests/test_parity.py experiments/YH006/tests/test_roundtrip_invariants.py experiments/YH006/tests/test_wealth_conservation.py -x` (LOB)
3. 全 pass 確認 → `stage_S4_diff.md` に記録 (pass 件数 + 所要時間)

実測 (本 plan 提出時点、Windows 側):
- `test_parity.py` (YH005): **18 / 18 PASS** (6.33s)
- `test_aggregate_parity.py` (YH006): **9 / 9 PASS** (23.18s)

Mac 側 LOB tests は §3.4 着手前に実施 (失敗時は § 5 stop trigger 該当 → Yuito 相談)。

### 3.2 `QConstSpeculationAgent` 実装 (S4、Windows)

`code/sg_agent.py` に追加 (実装済):

```python
class QConstSpeculationAgent(WInitLoggingSpeculationAgent):
    def setup(self, settings, accessible_markets_ids, *args, **kwargs):
        super().setup(settings, accessible_markets_ids, *args, **kwargs)
        q_const = int(settings.get("qConst", 0))
        if q_const < 1:
            raise ValueError(...)
        self.q_const: int = q_const

    def _compute_open_quantity(self) -> int:
        return max(1, int(self.q_const))
```

Wealth dynamics (sg_wealth の round-trip 累積、bankruptcy 判定) は親 `WInitLoggingSpeculationAgent` のまま。`corr(w_init, w_final)` 等の wealth persistence 指標は引き続き観測可能 (= ablation A1 が q 経路だけを切り、wealth 経路は残す意図と整合)。

dispatcher 更新 (`run_experiment.py`):
- `run_lob_trial_smoke` に `q_const: Optional[int] = None` を追加、`is_ablation_a1 = (cond.q_rule == "const")` で分岐、register に `QConstSpeculationAgent` を追加
- `run_lob_trial` に同 kwarg 追加、`run_lob_trial_smoke` に passthrough
- `run_one_trial` も `q_const` passthrough
- `parallel.py::_worker_run_trial` / `run_parallel_trials` も `q_const` passthrough

### 3.3 q_const 較正 (S4、Windows、完了済)

`code/q_const_calibration.py` 実装 + 実行 (本 plan 提出前に確定):

```
$ python -m code.q_const_calibration
pooled median = 3.00 (n_rt=477,695)
median of medians = 3.00 (n=100 trial, SD=0.611)
|pooled - median_of_medians| = 0.000
→ q_const = 3
```

結果: `logs/S4_q_const_calibration.json` に永続化、後続 Mac 側で `ablation_ensemble.py` が auto-load。

### 3.4 A1 smoke (S4、Mac)

Mac 側で:
```bash
cd experiments/YH006_1
git pull
# (LOB Phase 1 tests を念のため再走)
python -m pytest experiments/YH006/tests/test_parity.py experiments/YH006/tests/test_roundtrip_invariants.py experiments/YH006/tests/test_wealth_conservation.py -x
# A1 smoke
python -m code.ablation_ensemble --determinism-only  # smoke + guard + 終了
```

`ablation_ensemble.py` 内 `smoke()` の assertion:
- `len(agents_df) == 100` (N_sg)
- `w_init` 列 non-NaN
- **rt_df の `q` 列 unique values が `[q_const]` のみ** (A1 の wiring 確認、wealth 非依存 = 全 RT で q=3)

assertion fail → §5 stop trigger、`stage_S4_diff.md` で報告 + Yuito 相談。

### 3.5 Determinism guard (S4、Mac)

S3 と同 pattern:
- C3_A1 seed=1000 を 2 回独立 run、4 parquet sha256 比較 + rt_df semantic 比較
- bit-一致 or semantic-一致 で PASS
- log: `logs/runtime/{ts}_S5_ablation_ensemble.log` 内

S3 で確認済 `random.Random(seed)` + `np.random.default_rng(seed)` の bit-一致が QConstSpeculationAgent でも保たれることを検証。subclass の `q_const` 注入が PAMS 内部の RNG 消費順を変えていないか確認。

### 3.6 A1 ensemble 200 trial (S5、Mac)

Mac 側で:
```bash
cd experiments/YH006_1
python -m code.ablation_ensemble
# (default: --conds C2_A1,C3_A1 --n-trials 100、q_const は JSON から auto)
```

各 trial で 4 parquet (`trial_*.parquet`, `agents_*.parquet`, `lifetimes_*.parquet`, `wealth_ts_*.parquet`)。

**runtime 見積**:
- S3 LOB 1 trial = 145-600 秒 (mean ~410 秒)、A1 は wealth-fixed なので大体同じか短め (注文サイズ q が固定で大きくならない → LOB 約定が軽い可能性)
- 100 trial × 8 worker 並列 = ~1.5-2 時間 / cond
- C2_A1 + C3_A1 合計 **2-4 時間**

データサイズ: S3 LOB は C2=7.5 MB / C3=7.8 MB、A1 も同程度。tar.gz 不要、git 直 commit (S3 と同パターン)。

### 3.7 Windows aggregation + L2 判定 (S5)

Mac → Windows 転送後:
```bash
cd experiments/YH006_1
git pull
python -m code.aggregate_ablation_summary
```

`aggregate_ablation_summary.py` の処理:
1. integrity check (C2_A1 / C3_A1 各 400 parquet、sample で q unique = `[q_const]` を assertion)
2. ensemble_summary.parquet を **400 → 600 行** に拡張 (C0u/C0p/C2/C3 + C2_A1/C3_A1)
3. Pooled bin_var_slope を 6 条件すべて計算
4. A1 interaction = `(C3_A1 − C2_A1) − (C0p − C0u)` を 5 metrics × trial-level で bootstrap CI 計算
5. **Shrinkage** = `S3_interaction − A1_interaction` を trial-level で算出、bootstrap CI
6. **L2 判定** per metric:
   - shrinkage ratio = |A1| / |S3| ≤ 0.5
   - shrinkage CI が 0 を含まない
   - 両 satisfy で `L2_pass=True`
7. 出力:
   - `tab_S5_ablation_interaction.csv` (A1 5 metrics × interaction CI)
   - `tab_S5_shrinkage.csv` (5 metrics × shrinkage + L2 判定)
   - `fig_S5_ablation_shrinkage.png` (S3 vs A1 bar plot + L2 annotation)
   - `S5_summary_for_diff.json`
   - `README.md` 追記 (S5 セクション)

### 3.8 出力

| パス | 内容 |
|---|---|
| `data/C2_A1/*.parquet` × 400 | C2_A1 100 trial × 4 schema |
| `data/C3_A1/*.parquet` × 400 | C3_A1 同上 |
| `data/ensemble_summary.parquet` | 600 行 (S3 版 上書き、C0u/C0p/C2/C3/C2_A1/C3_A1 各 100) |
| `logs/S4_q_const_calibration.json` | 較正結果 + q_const = 3 |
| `logs/runtime/{ts}_S4_q_const_calibration.log` | Windows 較正 ログ |
| `logs/runtime/{ts}_S5_ablation_ensemble.log` | Mac sim 全 ログ |
| `logs/runtime/{ts}_S5_ablation_agg.log` | Windows aggregation ログ |
| `logs/S5_mac_summary.json` | Mac 完走サマリ (seed range, q_const, n_workers, timestamp) |
| `logs/S5_summary_for_diff.json` | Windows aggregation 全 key 数値 dump |
| `outputs/tables/tab_S5_ablation_interaction.csv` | 5 metrics × A1 interaction CI |
| `outputs/tables/tab_S5_shrinkage.csv` | 5 metrics × shrinkage + L2 |
| `outputs/figures/fig_S5_ablation_shrinkage.png` | S3 vs A1 bar + L2 annotation |
| `README.md` | "Stage S5" セクション追記 |

### 3.9 README 追記

`## Stage S5 — A1 ablation (C2_A1 / C3_A1) + KPI L2 判定` セクション:
- 6 条件 100 trial 完走確認
- q_const = 3 (較正源 = C3 100 trial pooled median)
- Pooled bin_var_slope 6 条件表
- 5 主指標 × (S3 baseline vs A1) interaction + bootstrap CI 表
- Shrinkage + L2 判定表 (PASS 件数 / 5)
- Layer 2 timescale concern 言及継続

---

## 4. 完了条件

### Windows 側 (本 plan 提出前に完了済 / これから完了)
- [x] §0.4 Phase 1 hook 追加 (`_compute_open_quantity`)
- [x] §3.1 aggregate parity tests 27 件 PASS (Windows)
- [x] §3.2 `QConstSpeculationAgent` 実装 + dispatcher 更新
- [x] §3.3 q_const 較正完了 (= 3)
- [ ] §3.7 aggregate_ablation_summary 実行 (Mac sim 完了後)

### Mac 側
- [ ] git pull で Windows commit を取得
- [ ] §3.1 LOB Phase 1 tests 全 pass
- [ ] §3.4 A1 smoke PASS (w_init non-NaN + q == q_const)
- [ ] §3.5 Determinism guard PASS (C3_A1 seed=1000 × 2)
- [ ] §3.6 A1 100 trial × C2_A1 / C3_A1 完走 (各 400 parquet)
- [ ] git commit + push (parquet 同梱、S3 と同パターン)

### Windows 側 (Mac 後)
- [ ] git pull
- [ ] `aggregate_ablation_summary.py` 実行 → 600 行 ensemble_summary、5 出力、README 追記
- [ ] L2 判定結果を `stage_S4_diff.md` で報告 (PASS 件数 / 5、各 metric の shrinkage CI)
- [ ] Yuito レビュー待ち

---

## 5. Yuito 確認事項 (実装中 stop trigger + 完了後レビュー)

### 実装中の停止トリガー (発生したら停止 → Yuito 相談)

- §3.1 LOB Phase 1 tests fail (Mac 側、Phase 1 hook 拡張に伴う既存挙動破壊)
- §3.4 smoke の `q == q_const` assertion fail (subclass / dispatcher wiring 不具合)
- §3.5 Determinism guard で C3_A1 seed=1000 × 2 が bit-一致 fail (QConstSpeculationAgent 副作用)
- §3.6 A1 100 trial で **runtime > 6 hours / 条件** (S3 の 1.5x 超)
- §3.7 で **A1 interaction の絶対値が S3 baseline の 2 倍超** (理論的には縮小するはずが拡大 = 設計バグ疑い)

### 完了後 (Yuito レビュー) 確認事項

1. §3.7 L2 PASS / fail 件数 (5 metrics 中)、特に rho_pearson と bin_var_slope の判定
2. Pooled bin_var_slope の C2_A1/C3_A1 値、S3 の interaction (−0.258) からどう動いたか
3. S3 で trial-level interaction がほぼ 0 だった metrics の場合、shrinkage 信号が取れない問題への対応 (補助 KPI 採用 / S1-secondary 待ち)
4. q_const = 3 が **下位 50% は q=1-3、上位は q が大きい** という C3 分布の median であることの解釈 (= ablation 後の LOB 動態は「全 agent が小口注文」 状態、これが ablation 設計として適切か再確認)
5. S6 (A3 = lifetime cap) plan 着手の go/no-go (本 S5 完了後、別 plan)
6. S1-secondary plan 着手の go/no-go (本 ablation と並走可能)

---

## 改訂履歴

| Version | 内容 |
|---|---|
| v1.0 (本書、Draft) | Stage S4-S5 plan 初版、ablation A1 (q-fix) を S4 (較正 + smoke) + S5 (100 trial ensemble + L2 判定) として統合。S2 plan §0.4 の Phase 1 後方互換拡張 protocol で `_compute_open_quantity` hook を Phase 1 SpeculationAgent に追加、`QConstSpeculationAgent` subclass で override。q_const 較正は C3 100 trial pooled median = 3 で確定 (本 plan 提出前に Windows で実行済、median-of-medians と完全一致確認)。S6 (A3) と S1-secondary は本 plan scope 外、別 plan で。 |
