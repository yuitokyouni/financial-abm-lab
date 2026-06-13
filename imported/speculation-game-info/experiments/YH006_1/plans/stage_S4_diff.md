# Stage S4-S5 diff — A1 ablation 進捗ログ

S4-S5 plan v1 に基づく実装・実行ログ。S3 と同じ 3 段階 (Win 準備 → Mac sim → Win aggregation) の進捗を 1 行ずつ追記。

| Stage | Date | 状態 | Note |
|---|---|---|---|
| **0. Plan v1 + Windows 側 実装 + 較正** | 2026-05-13 | **完了** | Phase 1 hook、A1 subclass、dispatcher、calibration、Mac 用 ensemble runner、Win 用 aggregation 全 prep 済。q_const = 3 確定 |
| 1. Mac LOB Phase 1 test + smoke + determinism + 200 trial | — | 未着手 | `python -m code.ablation_ensemble` |
| 2. Mac → Windows 転送 | — | 未着手 | git 経由 (S3 と同パターン、データ ~15MB) |
| 3. Windows aggregation + L2 判定 | — | 未着手 | `python -m code.aggregate_ablation_summary` |

---

## Stage 0: plan + Windows 側 実装 + 較正 (2026-05-13 完了)

### plan v1 作成
- `plans/stage_S4_plan.md` 起草、A1 ablation (S4 較正 + smoke + S5 100 trial ensemble + L2 判定) を一体扱い
- S6 (A3) と S1-secondary は別 plan で

### Phase 1 後方互換拡張 (`speculation_agent.py`)
S2 plan §0.4 で確定済の Phase 2 統一ルール「Phase 1 後方互換拡張は許容、動作変更は禁止」を継承。
- `experiments/YH006/speculation_agent.py` に method `_compute_open_quantity` を追加 (default = `max(1, sg_wealth // B)`、Phase 1 既存挙動と bit-一致)
- 既存 `submit_orders_by_market` line 218 を `q = self._compute_open_quantity()` に差し替え

### Phase 1 test 再走 (Windows 側)

| test | 件数 | 所要時間 |
|---|---:|---:|
| `experiments/YH005/tests/test_parity.py` | **18 / 18 PASS** | 6.33s |
| `experiments/YH006/tests/test_aggregate_parity.py` | **9 / 9 PASS** | 23.18s |
| **合計 (Windows aggregate)** | **27 / 27 PASS** | 29.51s |

**LOB 系 Phase 1 tests は Mac 側で必須再走** (本 diff Stage 1 着手時に Mac で実施):
- `experiments/YH006/tests/test_parity.py`
- `experiments/YH006/tests/test_roundtrip_invariants.py`
- `experiments/YH006/tests/test_wealth_conservation.py`

### `QConstSpeculationAgent` subclass + dispatcher
- `code/sg_agent.py`: `QConstSpeculationAgent(WInitLoggingSpeculationAgent)` を追加
  - `setup` で `settings["qConst"]` を読み、`int < 1` なら ValueError
  - `_compute_open_quantity` を override で `max(1, q_const)` を返す
  - wealth dynamics (sg_wealth 累積、bankruptcy 判定) は親のまま、`corr(w_init, w_final)` 等は引き続き観測可能
- `code/run_experiment.py`:
  - `run_lob_trial_smoke` に `q_const: Optional[int]` 追加、`cond.q_rule == "const"` で `QConstSpeculationAgent` 切替 + `cfg["SGAgents"]["qConst"]` 注入
  - `run_lob_trial` に同 kwarg 追加、smoke へ passthrough
  - `run_one_trial` dispatcher も `q_const` passthrough
- `code/parallel.py::run_parallel_trials` に `q_const` kwarg 追加、worker fn `_worker_run_trial` に渡す

### q_const 較正 (S4 §3.3、Windows、完了)

`code/q_const_calibration.py` 実装 + 実行:

```
$ python -m code.q_const_calibration --cond C3
======================================================================
q_const calibration — cond=C3, n_trials=100, n_rt_total=477,695
======================================================================
pooled q distribution:
  median = 3.00 (→ q_const_primary = 3)
  mean   = 15.75
  p25    = 1.00
  p75    = 10.00
per-trial median 統計 (n=100 trial):
  median of medians = 3.00
  SD of medians     = 0.611
agreement check: |pooled_median - median_of_trial_medians| = 0.000
--> q_const = 3 (C2_A1 / C3_A1 で共通使用)
```

**結果**: `q_const = 3` 確定、`logs/S4_q_const_calibration.json` に保存。

注: mean = 15.75 vs median = 3 で大きく乖離 = C3 の q 分布は **下位 50% で q=1-3、上位で大きい (高 wealth agent の q)**。median 採用は ablation の趣旨 (wealth heterogeneity を除去) と整合。

### Mac 用 ensemble runner (`code/ablation_ensemble.py`)
- smoke (S4 §3.4): C3_A1 seed=9001 短縮、`q == q_const` assertion
- determinism guard (S4 §3.5): C3_A1 seed=1000 × 2 run、sha256 + semantic 比較
- 100 trial 並列実行 (S5 §3.6): default `--conds C2_A1,C3_A1 --n-trials 100`
- q_const は `S4_q_const_calibration.json` から auto-load (`--q-const N` で上書き可)

### Windows 用 aggregation (`code/aggregate_ablation_summary.py`)
- integrity check (`q == q_const` を assertion で再確認)
- ensemble_summary.parquet を 400 → 600 行に拡張
- Pooled bin_var_slope 6 cond
- A1 interaction (5 metrics) + bootstrap CI
- **Shrinkage = S3 − A1** の bootstrap CI、KPI L2 判定 (ratio ≤ 0.5 AND CI が 0 を含まない)
- 出力: `tab_S5_ablation_interaction.csv` / `tab_S5_shrinkage.csv` / `fig_S5_ablation_shrinkage.png` / `S5_summary_for_diff.json` + README 追記

### 全 syntax check OK
```
sg_agent.py, run_experiment.py, parallel.py, q_const_calibration.py,
ablation_ensemble.py, aggregate_ablation_summary.py,
YH006/speculation_agent.py
→ 全 7 ファイル syntax OK
```

### 次のアクション (Mac 側)
1. Mac で `git pull` (本 commit を取得)
2. LOB Phase 1 tests 全 pass 確認:
   ```bash
   cd experiments/YH006_1
   python -m pytest experiments/YH006/tests/test_parity.py experiments/YH006/tests/test_roundtrip_invariants.py experiments/YH006/tests/test_wealth_conservation.py -x
   ```
3. A1 smoke + determinism guard:
   ```bash
   python -m code.ablation_ensemble --determinism-only
   ```
4. 本実行 (200 trial、見積 2-4 時間):
   ```bash
   python -m code.ablation_ensemble
   ```
5. `data/C2_A1/` `data/C3_A1/` (各 400 parquet) + `logs/S5_mac_summary.json` + `logs/runtime/*S5*log` を commit + push

---

## Stage 1: Mac LOB sim (未着手)

(Mac 実行後に追記)

---

## Stage 2: Mac → Windows 転送 (未着手)

(転送後に追記)

---

## Stage 3: Windows aggregation + L2 判定 (未着手)

(`aggregate_ablation_summary.py` 実行後に追記)
