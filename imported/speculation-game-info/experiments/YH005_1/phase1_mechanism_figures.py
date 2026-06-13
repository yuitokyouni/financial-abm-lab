"""YH005-1 Phase 1: Mechanism figures for Speculation Game.

Runs a single baseline simulation (N=1000, M=5, S=2, T=50000, seed=777,
B=9, C=3.0) and generates 5 figures that together establish the 3-layer
mechanism claim of Katahira-Chen 2019 arXiv:

    Fig 4 相当: wealth Pareto distribution             -> results_wealth_pareto.png
    Fig 8 相当: round-trip horizon distribution        -> results_horizon_distribution.png
    Fig 7 相当: ΔG vs horizon 2D histogram             -> results_deltaG_vs_horizon.png
    Fig 10 相当: active / passive hold ratio (single M)-> results_hold_ratio.png
    Fig 2 相当: big / medium / small order time series -> results_order_size_time_series.png

All metrics are aggregated into outputs/phase1_metrics.json.

Usage:
    cd experiments/YH005_1
    python phase1_mechanism_figures.py

Phase 1 は固定 parameter なので CLI 引数は無し。Phase 2 以降で scan する。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

# YH005 本体を sys.path 経由で import (既存シリーズ規約、_mg_gcmg_baseline.py と同系統)
HERE = Path(__file__).resolve().parent
YH005 = HERE.parent / "YH005"
sys.path.insert(0, str(YH005))

from simulate import simulate  # noqa: E402
from analysis import (  # noqa: E402
    plot_wealth_distribution,
    plot_roundtrip_horizon,
    plot_deltaG_vs_horizon,
    plot_hold_ratio,
    plot_order_size_time_series,
)


PARAMS = dict(
    N=1000,
    M=5,
    S=2,
    T=50000,
    B=9,
    C=3.0,
    seed=777,
    p0=100.0,
    history_mode="endogenous",
    decision_mode="strategy",
    order_size_buckets=(50, 100),
)


def _to_jsonable(obj):
    """numpy scalar / ndarray を JSON 化可能な形に変換。"""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if np.isfinite(v) else None  # NaN/Inf は JSON に乗らない
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def main() -> None:
    print(f"[phase1] running simulate with params: {PARAMS}")
    t0 = time.perf_counter()
    res = simulate(**PARAMS)
    elapsed = time.perf_counter() - t0
    print(f"[phase1] simulate done in {elapsed:.1f}s  "
          f"(num_substitutions={res['num_substitutions']}, "
          f"num_round_trips={res['round_trips']['agent_idx'].size})")

    # p(t) が負になった step 数 (extreme state 診断、§4.7 マスクと対応)
    prices = res["prices"]
    n_nonpos = int((prices <= 0).sum())
    print(f"[phase1] prices: min={prices.min():.2f}, max={prices.max():.2f}, "
          f"n(p<=0)={n_nonpos}")

    figs_dir = HERE
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)

    metrics = {"params": {k: v for k, v in PARAMS.items()}, "runtime_sec": elapsed}
    metrics["price_stats"] = {
        "min": float(prices.min()),
        "max": float(prices.max()),
        "n_nonpositive_steps": n_nonpos,
        "num_round_trips": int(res["round_trips"]["agent_idx"].size),
        "num_substitutions": int(res["num_substitutions"]),
        "total_wealth_T": int(res["total_wealth"]),
    }

    print("[phase1] figure 1/5: wealth Pareto")
    metrics["wealth"] = plot_wealth_distribution(
        res["final_wealth"],
        str(figs_dir / "results_wealth_pareto.png"),
        title=f"Wealth distribution at T={PARAMS['T']}  (N={PARAMS['N']}, M={PARAMS['M']})",
    )

    print("[phase1] figure 2/5: round-trip horizon")
    metrics["horizon"] = plot_roundtrip_horizon(
        res["round_trips"],
        str(figs_dir / "results_horizon_distribution.png"),
        title="Round-trip horizon distribution  (log-log count)",
    )

    print("[phase1] figure 3/5: ΔG vs horizon")
    metrics["deltaG_vs_horizon"] = plot_deltaG_vs_horizon(
        res["round_trips"],
        str(figs_dir / "results_deltaG_vs_horizon.png"),
        title="ΔG vs horizon  (cognitive P&L by round-trip length)",
    )

    print("[phase1] figure 4/5: hold ratio")
    metrics["hold_ratio"] = plot_hold_ratio(
        res,
        str(figs_dir / "results_hold_ratio.png"),
        title=f"Action ratio  (M={PARAMS['M']}, time-averaged)",
    )

    print("[phase1] figure 5/5: order size time series")
    # 論文2 Fig. 2 と揃えて log_return を採用 (Q1 の推奨通り)
    metrics["order_size"] = plot_order_size_time_series(
        res,
        str(figs_dir / "results_order_size_time_series.png"),
        xlim=(0, PARAMS["T"]),
        title=f"Order size decomposition  (small≤50 < medium≤100 < large)",
        return_mode="log_return",
        p0=PARAMS["p0"],
    )

    # JSON 出力
    out_json = out_dir / "phase1_metrics.json"
    with open(out_json, "w") as f:
        json.dump(_to_jsonable(metrics), f, indent=2, default=str)
    print(f"[phase1] metrics saved: {out_json}")

    print("\n[phase1] --- summary ---")
    print(f"  wealth      α_hill(p90)     = {metrics['wealth']['alpha_hill_xmin_p90']:.3f}")
    print(f"  horizon     median / mean    = {metrics['horizon']['median_horizon']:.1f} / "
          f"{metrics['horizon']['mean_horizon']:.1f} steps   "
          f"(K={metrics['horizon']['num_round_trips']})")
    print(f"  ΔG vs h     corr(|ΔG|, h)    = {metrics['deltaG_vs_horizon']['corr_horizon_abs_dG']:.3f}")
    print(f"  hold ratio  passive={metrics['hold_ratio']['passive_hold']:.3f}  "
          f"active={metrics['hold_ratio']['active_hold']:.3f}  "
          f"buy={metrics['hold_ratio']['buy']:.3f}  "
          f"sell={metrics['hold_ratio']['sell']:.3f}  "
          f"idle={metrics['hold_ratio']['idle']:.3f}")
    print(f"  order size  mean(small/med/large) = "
          f"{metrics['order_size']['mean_small']:.1f} / "
          f"{metrics['order_size']['mean_medium']:.1f} / "
          f"{metrics['order_size']['mean_large']:.1f}   "
          f"peak(large)={metrics['order_size']['peak_large']}")


if __name__ == "__main__":
    main()
