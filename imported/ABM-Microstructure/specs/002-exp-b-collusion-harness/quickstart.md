# Quickstart — 実験B 学習 MM collusion harness

## 検証（gate 分類器・機構・benchmarks・sanity・地図/予算）

```bash
uv run pytest tests/test_benchmarks.py tests/test_env_mechanics.py \
              tests/test_verdict_gate.py tests/test_qlearn_sanity.py \
              tests/test_us1_pipeline.py tests/test_design_comparison.py \
              tests/test_designmap.py -q
```

**ここが緑 = B の測定装置（分母・gate・機構 ablation・予算 enforcement）が信用できる状態**。001 の battery（既存 6 ファイル）も含め全 suite 緑を維持する。

## 単一セルを回す（US1 の最小ループ）

下は数十秒で完走するスモークスケール（`t_max` 縮小）。**本番は t_max=2×10⁶（既定）・
seeds≥5 を ledger 管理下で**——縮小スケールの markup は非収束の探索値であり結果として
引用しない。

```python
from microstructure import LearnConfig, train, measure, impulse_response, certify

cfg = LearnConfig(dt=1e-2, lambda_jump=5.0, jump_size=1.0, alpha=0.3,
                  noise_rate=1.0, mechanism="continuous", staleness="committed",
                  n_mm=2, memory=1, seed=0,
                  t_max=60_000, stable_window=15_000, measure_periods=3_000)  # smoke
results = [train(cfg.replace(seed=s)) for s in range(2)]
cells   = [measure(cfg.replace(seed=s), r) for s, r in enumerate(results)]
irs     = [impulse_response(cfg.replace(seed=s), r) for s, r in enumerate(results)]
verdict = certify(cells, irs)
print(verdict.certified, cells[0].markup, cells[0].floors)
```

## 設計マップ（tiered、予算 enforcement 付き）

```bash
python scripts/run_design_map.py --tier coarse --out results/coarse.csv --budget-ledger results/budget.json
# 変調の符号が変わる近傍が見えたら:
python scripts/run_design_map.py --tier dense --around <cell-id> --out results/dense.csv --budget-ledger results/budget.json
# headline 確定後:
python scripts/run_design_map.py --tier robustness --headline <cell-id,...> --out results/robust.csv --budget-ledger results/budget.json
```

- 総予算 3×10⁹ 学習期、tier 各 ≤1×10⁹（research D-B9）。ledger 超過 run は起動拒否。
- 出力 CSV の各行 = DesignMapPoint（条件、(抽出, markup)±SE、certified、converged_frac、退出フラグ）。

## 読み方（spec の対応）

- US1: 単一セルの `verdict.certified`（markup 有意 ∧ 懲罰 ∧ 再確立）。null（創発せず）も結論。
- US2: 同一セルで `mechanism/staleness` を振った markup 差。revisable は extraction≡0 の ablation（predation OFF）。
- US3: coarse→dense→robustness の地図。memory 閾値は certified セルのみで sweep。
- US4: BCS ES–SPY 較正セル（research D-B10）を grid に追加して同じ pipeline を通す。
