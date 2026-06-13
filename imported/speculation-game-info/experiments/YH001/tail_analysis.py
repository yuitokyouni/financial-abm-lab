"""Tail exponent α estimation via Clauset et al. (2009) powerlaw package.

Sweep c = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0] and plot α vs c.

Usage:
    cd experiments/YH001
    python tail_analysis.py
"""

from __future__ import annotations

import time
import numpy as np
import powerlaw
import matplotlib.pyplot as plt
from model import simulate


def estimate_alpha(returns: np.ndarray) -> dict:
    """Fit power-law tail to |returns| using Clauset's method."""
    abs_r = np.abs(returns)
    abs_r = abs_r[abs_r > 0]
    fit = powerlaw.Fit(abs_r, discrete=True, verbose=False)
    return {
        "alpha": fit.power_law.alpha,
        "xmin": fit.power_law.xmin,
        "sigma": fit.power_law.sigma,
    }


def main():
    c_values = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
    N = 10000
    T = 50000
    a = 0.01

    results = []
    for c in c_values:
        print(f"c={c} ...", end=" ", flush=True)
        t0 = time.time()
        sim = simulate(N=N, c=c, a=a, T=T, seed=42, report_every=0)
        fit = estimate_alpha(sim["returns"])
        elapsed = time.time() - t0
        print(f"α={fit['alpha']:.3f} (xmin={fit['xmin']:.1f}, σ={fit['sigma']:.3f})  [{elapsed:.1f}s]")
        results.append({"c": c, **fit})

    alphas = [r["alpha"] for r in results]
    sigmas = [r["sigma"] for r in results]

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        c_values,
        alphas,
        yerr=sigmas,
        fmt="o-",
        color="navy",
        linewidth=2,
        markersize=8,
        capsize=5,
        label=r"$\hat{\alpha}$ (Clauset MLE)",
    )
    ax.axhline(y=3.0, color="red", linestyle="--", alpha=0.6, label=r"$\alpha=3$ (finite variance boundary)")
    ax.set_xlabel("Coordination parameter c", fontsize=13)
    ax.set_ylabel(r"Tail exponent $\alpha$", fontsize=13)
    ax.set_title("Cont-Bouchaud (1997): tail exponent vs herding strength", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Annotate
    for c, a_val in zip(c_values, alphas):
        ax.annotate(
            f"{a_val:.2f}",
            (c, a_val),
            textcoords="offset points",
            xytext=(0, 12),
            ha="center",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig("tail_exponent.png", dpi=150, bbox_inches="tight")
    print(f"\nSaved to tail_exponent.png")
    plt.close()


if __name__ == "__main__":
    main()
