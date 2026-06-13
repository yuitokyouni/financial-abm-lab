"""YH006: 2×2 比較のための aggregate-demand 側 (C0u / C0p) を N=100 で生成。

2×2 (world × wealth):
    aggregate-demand × uniform  = C0u (本 script で生成、N=100)
    aggregate-demand × Pareto   = C0p (本 script で生成、N=100)
    LOB × uniform               = C2  (既存、N=100)
    LOB × Pareto                = C3  (既存、N=100)

旧 YH005_1 C0 (N=1000, uniform) は 2×2 から外し、N scaling reference として
比較表の補遺に残す (`load_c0.py::load_c0_reference_1000`)。

出力:
    outputs/c0u_metrics.json
    outputs/c0p_metrics.json
    results_c0u_*.png (5 figure)
    results_c0p_*.png (5 figure)

所要時間の目安: N=100 × T=50000 × S=2 × M=5 で Apple Silicon 数秒程度。
parity 検証 (uniform mode ↔ YH005 simulate) は必要なら
tests/test_aggregate_sim_parity.py を別途追加。
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
YH005 = HERE.parent / "YH005"
sys.path.insert(0, str(YH005))
sys.path.insert(0, str(HERE))

from aggregate_sim import simulate_aggregate  # noqa: E402
from analysis import (  # noqa: E402  (YH005 の analysis を流用、read-only)
    plot_wealth_distribution,
    plot_roundtrip_horizon,
    plot_deltaG_vs_horizon,
    plot_hold_ratio,
    plot_order_size_time_series,
)


BASE_PARAMS = dict(
    N=100,
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

PARETO_ALPHA = 1.5
PARETO_XMIN = 9  # = B


def _to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if np.isfinite(v) else None
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def _collect_metrics(res, params, elapsed, label, figs_dir):
    prices = res["prices"]
    metrics = {
        "label": label,
        "params": dict(params),
        "runtime_sec": elapsed,
        "price_stats": {
            "min": float(prices.min()),
            "max": float(prices.max()),
            "n_nonpositive_steps": int((prices <= 0).sum()),
            "num_round_trips": int(res["round_trips"]["agent_idx"].size),
            "num_substitutions": int(res["num_substitutions"]),
            "total_wealth_T": int(res["total_wealth"]),
        },
    }
    title_suffix = f"(N={params['N']}, mode={label})"

    metrics["wealth"] = plot_wealth_distribution(
        res["final_wealth"],
        str(figs_dir / f"results_{label}_wealth_pareto.png"),
        title=f"Wealth distribution at T={params['T']}  {title_suffix}",
    )
    metrics["horizon"] = plot_roundtrip_horizon(
        res["round_trips"],
        str(figs_dir / f"results_{label}_horizon_distribution.png"),
        title=f"Round-trip horizon  {title_suffix}",
    )
    metrics["deltaG_vs_horizon"] = plot_deltaG_vs_horizon(
        res["round_trips"],
        str(figs_dir / f"results_{label}_deltaG_vs_horizon.png"),
        title=f"ΔG vs horizon  {title_suffix}",
    )
    metrics["hold_ratio"] = plot_hold_ratio(
        res,
        str(figs_dir / f"results_{label}_hold_ratio.png"),
        title=f"Action ratio (M={params['M']}) {title_suffix}",
    )
    metrics["order_size"] = plot_order_size_time_series(
        res,
        str(figs_dir / f"results_{label}_order_size_time_series.png"),
        xlim=(0, params["T"]),
        title=f"Order size decomposition  {title_suffix}",
        return_mode="log_return",
        p0=params["p0"],
    )
    return metrics


def run_one(wealth_mode: str, label: str, figs_dir: Path, out_dir: Path) -> dict:
    params = dict(BASE_PARAMS)
    params["wealth_mode"] = wealth_mode
    if wealth_mode == "pareto":
        params["pareto_alpha"] = PARETO_ALPHA
        params["pareto_xmin"] = PARETO_XMIN

    print(f"[{label}] simulate_aggregate start: {params}")
    t0 = time.perf_counter()
    res = simulate_aggregate(**params)
    elapsed = time.perf_counter() - t0
    print(
        f"[{label}] done in {elapsed:.1f}s  "
        f"(K={res['round_trips']['agent_idx'].size}, "
        f"substitutions={res['num_substitutions']})"
    )

    metrics = _collect_metrics(res, params, elapsed, label, figs_dir)
    out_json = out_dir / f"{label}_metrics.json"
    with open(out_json, "w") as f:
        json.dump(_to_jsonable(metrics), f, indent=2, default=str)
    print(f"[{label}] metrics saved: {out_json}")

    # raw simulate_aggregate dict も pkl で保存 (compare_figure が C0u/C0p を
    # raw 配列で描画するため、LOB 側 c{1,2,3}_result.pkl と schema を揃える)
    out_pkl = out_dir / f"{label}_result.pkl"
    with open(out_pkl, "wb") as f:
        pickle.dump(res, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[{label}] raw result saved: {out_pkl}  ({out_pkl.stat().st_size / 1e6:.1f} MB)")
    return metrics


def main() -> None:
    out_dir = HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    figs_dir = HERE

    c0u = run_one("uniform", "c0u", figs_dir, out_dir)
    c0p = run_one("pareto", "c0p", figs_dir, out_dir)

    print("\n--- 2×2 aggregate side summary (N=100) ---")
    print(f"{'metric':30s} {'C0u (uniform)':>18s} {'C0p (Pareto α=1.5)':>22s}")
    print("-" * 74)
    print(
        f"{'num_round_trips':30s} "
        f"{c0u['price_stats']['num_round_trips']:>18d} "
        f"{c0p['price_stats']['num_round_trips']:>22d}"
    )
    print(
        f"{'alpha_hill (xmin=p90)':30s} "
        f"{c0u['wealth']['alpha_hill_xmin_p90']:>18.3f} "
        f"{c0p['wealth']['alpha_hill_xmin_p90']:>22.3f}"
    )
    print(
        f"{'median_wealth':30s} "
        f"{c0u['wealth']['median_wealth']:>18.1f} "
        f"{c0p['wealth']['median_wealth']:>22.1f}"
    )
    print(
        f"{'median_horizon':30s} "
        f"{c0u['horizon']['median_horizon']:>18.1f} "
        f"{c0p['horizon']['median_horizon']:>22.1f}"
    )
    print(
        f"{'corr(|ΔG|, horizon)':30s} "
        f"{c0u['deltaG_vs_horizon']['corr_horizon_abs_dG']:>18.3f} "
        f"{c0p['deltaG_vs_horizon']['corr_horizon_abs_dG']:>22.3f}"
    )
    print(
        f"{'passive_hold':30s} "
        f"{c0u['hold_ratio']['passive_hold']:>18.3f} "
        f"{c0p['hold_ratio']['passive_hold']:>22.3f}"
    )
    print(
        f"{'active_hold':30s} "
        f"{c0u['hold_ratio']['active_hold']:>18.3f} "
        f"{c0p['hold_ratio']['active_hold']:>22.3f}"
    )


if __name__ == "__main__":
    main()
