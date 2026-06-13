"""YH005: YH003 MG / YH004 GCMG / YH005 SG の 3 モデル比較.

inductive learning を S=1 で無効化し、N=1000, M=5, T=50000 に揃えた上で、
(1) r(t) 時系列, (2) volatility ACF (log-log), (3) CCDF (log-log) を描画。
Speculation Game のみが slow-decay vol ACF + heavy-tailed returns を示すことを確認する。

レイアウト: 3 行 × 3 列 (row: stat, col: model)

出力:
  experiments/YH005/results_compare_three.png
  experiments/YH005/outputs/three_models_metrics.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt

import numpy as np

from simulate import simulate as sg_simulate
from _mg_gcmg_baseline import run_mg, run_gcmg
from analysis import (
    volatility_acf,
    ccdf,
    stylized_facts_summary,
)


def _returns_as_dp(prices: np.ndarray) -> np.ndarray:
    """Δp = D/N を return として使う (論文1 Eq. 5)。log を経由しないので MG の
    負価格問題を回避でき、3 モデルで同じ次元 (絶対価格増分) の比較になる。
    """
    p = np.asarray(prices, dtype=np.float64)
    return np.diff(p)


COMPARE_PARAMS = dict(
    N=1000,
    M=5,
    T=50000,
    S=1,
    p0=100.0,
)
DISPLAY_T = 10000
ACF_MAX_LAG = 500


def _to_json(obj):
    if isinstance(obj, dict):
        return {str(k): _to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _run_model(label: str, runner, **kwargs):
    print(f"[{label}] start")
    t0 = time.perf_counter()
    res = runner(**kwargs)
    t1 = time.perf_counter()
    print(f"[{label}] done in {t1-t0:.1f}s")
    return res


def run_compare(seed: int = 123, save_dir: Path | None = None) -> dict:
    if save_dir is None:
        save_dir = Path(__file__).resolve().parent
    outputs_dir = save_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    N = COMPARE_PARAMS["N"]
    M = COMPARE_PARAMS["M"]
    T = COMPARE_PARAMS["T"]
    S = COMPARE_PARAMS["S"]
    p0 = COMPARE_PARAMS["p0"]

    # --- Run all three models ---
    mg_res = _run_model("MG",    run_mg,          N=N, M=M, T=T, seed=seed, S=S, p0=p0)
    gcmg_res = _run_model("GCMG", run_gcmg,       N=N, M=M, T=T, seed=seed, S=S, p0=p0,
                          T_win=50, r_min_static=0.0)
    sg_res = _run_model("SG",    sg_simulate,     N=N, M=M, S=S, T=T, seed=seed, p0=p0)

    models = {
        "MG":   {"prices": mg_res["prices"]},
        "GCMG": {"prices": gcmg_res["prices"]},
        "SG":   {"prices": sg_res["prices"]},
    }

    # --- Returns + metrics (Δp = D/N, no log) ---
    for name, entry in models.items():
        r = _returns_as_dp(entry["prices"])
        entry["returns"] = r
        entry["summary"] = stylized_facts_summary(r, acf_lags=(1, 14, 50, 200, 500))
        nan_frac = float(np.isnan(r).mean())
        print(f"[{name}] NaN fraction in Δp returns: {nan_frac:.4f}, std={np.nanstd(r):.4e}")

    # --- 3x3 figure ---
    fig, axes = plt.subplots(3, 3, figsize=(14, 10))
    model_order = ["MG", "GCMG", "SG"]
    col_titles = ["YH003: Minority Game", "YH004: Grand-Canonical MG", "YH005: Speculation Game"]

    for col, name in enumerate(model_order):
        entry = models[name]
        r = entry["returns"]

        # Row 1: r(t) 時系列
        ax = axes[0, col]
        ax.plot(r[:DISPLAY_T], linewidth=0.4, color="tab:blue")
        ax.axhline(0, color="k", linewidth=0.3)
        ax.set_title(col_titles[col], fontsize=11)
        if col == 0:
            ax.set_ylabel(r"r(t) = $\Delta p$ = D/N")
        ax.set_xlabel(f"t  (first {DISPLAY_T} shown)")
        ax.grid(alpha=0.2)

        # Row 2: volatility ACF log-log
        ax = axes[1, col]
        acf = volatility_acf(r, max_lag=ACF_MAX_LAG)
        lags = np.arange(1, ACF_MAX_LAG + 1)
        positive = acf > 0
        neg = ~positive & ~np.isnan(acf)
        ax.loglog(lags[positive], acf[positive], ".", markersize=3,
                  color="tab:red", label=r"$\rho_{|r|} > 0$")
        if neg.any():
            ax.loglog(lags[neg], -acf[neg], ".", markersize=3, color="lightgray",
                      alpha=0.5, label=r"$|\rho_{|r|}|$ where $\rho_{|r|} < 0$")
        ax.set_xlabel("lag τ (log)")
        if col == 0:
            ax.set_ylabel(r"$\rho_{|r|}(\tau)$  (log)")
        ax.grid(alpha=0.3, which="both")
        ax.axhline(0.05, color="gray", linestyle=":", linewidth=0.5)
        ax.set_ylim(1e-4, 1.0)
        ax.legend(loc="lower left", fontsize=7, framealpha=0.7)

        # Row 3: CCDF of |r| normalized
        ax = axes[2, col]
        xs, cc = ccdf(r, normalize=True)
        # そのまま全点描画だと重くなるので間引く
        if xs.size > 3000:
            step = xs.size // 3000
            xs = xs[::step]
            cc = cc[::step]
        mask = (xs > 0) & (cc > 0)
        ax.loglog(xs[mask], cc[mask], ".", markersize=2, color="tab:green")
        ax.set_xlabel(r"$|r| / \sigma$  (log)")
        if col == 0:
            ax.set_ylabel(r"P(|r|/\sigma \geq x)  (log)")
        ax.grid(alpha=0.3, which="both")
        hill_a = entry["summary"]["hill_alpha"]
        ax.set_title(f"Hill α ≈ {hill_a:.2f}" if not np.isnan(hill_a) else "Hill α: NaN",
                     fontsize=9)

    fig.suptitle(
        "Stylized facts comparison with inductive learning disabled "
        f"(S={S}, N={N}, T={T}, seed={seed}). Only the Speculation Game (right column) "
        "reproduces slow decay of |r| ACF and heavy-tailed returns.",
        fontsize=10, y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    png_path = save_dir / "results_compare_three.png"
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"\nFigure saved: {png_path}")

    # --- JSON ---
    serializable = {
        "seed": seed,
        "params": COMPARE_PARAMS,
        "models": {
            name: _to_json(entry["summary"]) for name, entry in models.items()
        },
    }
    json_path = outputs_dir / "three_models_metrics.json"
    with open(json_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"Metrics saved: {json_path}")

    # --- Print key comparison ---
    print("\n== Row 2 summary: |r| ACF at selected lags ==")
    print(f"{'model':<6}  " + "  ".join(f"τ={l:<4d}" for l in [1, 50, 200, 500]))
    for name in model_order:
        acfs = models[name]["summary"]["vol_acf"]
        row = f"{name:<6}  " + "  ".join(f"{acfs.get(l, float('nan')):+.4f}  " for l in [1, 50, 200, 500])
        print(row)

    print("\n== Hill α (tail index) ==")
    for name in model_order:
        print(f"  {name}: {models[name]['summary']['hill_alpha']:.3f}")

    return {
        "models": {name: entry["summary"] for name, entry in models.items()},
        "png": str(png_path),
        "json": str(json_path),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()
    run_compare(seed=args.seed)
