"""YH005: ベースライン単体実行 (§8.4 検証用).

N=1000, M=5, S=2, T=20000, B=9, C=3.0, seed=777 で SG を走らせ、
stylized facts サマリを print する。期待値:
  - vol_acf_at_200 ≈ 0.01–0.05
  - ret_acf_at_14  ∈ noise zone
  - kurt_at_1 >> kurt_at_640 (aggregational Gaussianity)
  - Hill α ∈ [3, 5]  (論文1 Fig. 4 の α ≈ 3.8)

出力: stdout (console) + outputs/baseline_metrics.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from simulate import simulate
from analysis import log_returns_from_prices, stylized_facts_summary


BASELINE_PARAMS = dict(N=1000, M=5, S=2, T=20000, B=9, C=3.0, p0=100.0)


def _to_json(obj):
    if isinstance(obj, dict):
        return {str(k): _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def run_baseline(seed: int = 777, save_dir: Path | None = None) -> dict:
    if save_dir is None:
        save_dir = Path(__file__).resolve().parent
    outputs_dir = save_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    print(f"[baseline] params: {BASELINE_PARAMS}, seed={seed}")
    t0 = time.perf_counter()
    res = simulate(seed=seed, **BASELINE_PARAMS)
    t1 = time.perf_counter()
    print(f"[baseline] done in {t1-t0:.1f}s, num_substitutions={res['num_substitutions']}")

    returns = log_returns_from_prices(res["prices"])
    n_valid = int((~np.isnan(returns)).sum())
    n_nan = int(np.isnan(returns).sum())
    print(f"  valid log-returns: {n_valid}/{len(returns)} (NaN: {n_nan})")

    summary = stylized_facts_summary(
        returns,
        acf_lags=(1, 14, 50, 200, 500),
        kurt_windows=(1, 16, 64, 256, 640),
    )

    print("\n== Stylized facts summary ==")
    print(f"  std(r)      = {summary['std']:.4e}")
    print(f"  ret_acf     = " + ", ".join(f"τ={l}: {summary['ret_acf'][l]:+.4f}" for l in summary['ret_acf']))
    print(f"  vol_acf     = " + ", ".join(f"τ={l}: {summary['vol_acf'][l]:+.4f}" for l in summary['vol_acf']))
    print(f"  kurt        = " + ", ".join(f"w={w}: {summary['kurt'][w]:+.2f}" for w in summary['kurt']))
    print(f"  Hill α      = {summary['hill_alpha']:.3f}")

    json_path = outputs_dir / "baseline_metrics.json"
    with open(json_path, "w") as f:
        json.dump({"seed": seed, "params": BASELINE_PARAMS, **_to_json(summary)}, f, indent=2)
    print(f"\nMetrics saved: {json_path}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()
    run_baseline(seed=args.seed)
