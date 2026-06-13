# Quickstart — 実験A harness

## セットアップ
```
uv venv && .venv\Scripts\activate      # Windows（PowerShell）
uv pip install numpy pytest            # 最小依存。scipy/matplotlib は任意
```

## 検証を回す（= 本 feature の成果物 / SC-001〜004）
```
pytest -q tests/
```
- `test_anchors_match.py`：sim の competitive_spread / extraction が GM break-even / Budish 閉形式と許容誤差内に一致（≥8 パラメータ点・複数 seed）。
- `test_continuous_vs_batch.py`：batch < continuous かつ σ で単調（SC-003）。
- `test_determinism.py`：同一 seed → 同一出力（SC-004）。
- `test_incentive.py`：MM 純 PnL の符号（US3）。

**全 pass = SC-005 gate 成立**（実験Bを信じる license）。pass しなければ B に進まない。

## 単発 run
```
python -c "from microstructure import run; from microstructure.config import SimConfig; \
print(run(SimConfig(n_periods=200000, seed=0, dt=1e-2, sigma=0.2, lambda_jump=5.0, jump_size=1.0, alpha=0.3, fee=0.0, opp_cost=0.0, mechanism='continuous')))"
```

## sweep（連続 vs batch の定量化 / B1 の compute 入力）
```
python scripts/run_sweep.py --sigma 0.1,0.2,0.4 --N 1,5,20 --fee 0,0.0005 --seeds 8 --out results.csv
```
- `results.csv` に (σ,N,fee,seed)→(extraction, effective_spread, mm_net_pnl, runtime_sec)。
- `runtime_sec` の総和が B の grid 見積もり（B1）の入力になる。

## 構造図
commit すると `scripts/generate_diagrams.sh`（pre-commit）が `ABM_PKG=src/microstructure` で `docs/architecture.md` を再生成し、Obsidian で閲覧可。
