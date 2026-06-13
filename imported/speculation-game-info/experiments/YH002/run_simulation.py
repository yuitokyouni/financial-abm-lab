"""YH002: Lux & Marchesi (2000) — シミュレーション実行と 6 パネル図生成.

Usage:
    python run_simulation.py --seed 42
"""

from __future__ import annotations

import argparse
import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, kurtosis as sp_kurtosis
from statsmodels.tsa.stattools import acf, adfuller

from model import Params, simulate


def hill_estimate(abs_returns: np.ndarray, fraction: float) -> float:
    """Hill tail index α̂_H. fraction = 2.5% / 5% / 10% などの裾サイズ.

    sorted x_(n) ≥ x_(n-1) ≥ ... に対し
        α̂_H = 1 / [(1/k) · Σ_{i=1..k} (ln x_(n-i+1) − ln x_(n-k))]
    """
    x = np.sort(abs_returns)
    x = x[x > 0]
    n = len(x)
    k = int(n * fraction)
    if k < 5:
        return float("nan")
    tail = x[-k:]
    threshold = x[-k - 1] if n > k else x[0]
    if threshold <= 0:
        return float("nan")
    return float(1.0 / np.mean(np.log(tail) - np.log(threshold)))


def run_and_plot(seed: int = 42, n_integer_steps: int = 4000) -> None:
    print("=" * 60)
    print(f"Lux & Marchesi (2000) Parameter Set I — YH002  seed={seed}")
    print("=" * 60)

    params = Params()
    t0 = time.time()
    result = simulate(
        params=params, n_integer_steps=n_integer_steps, seed=seed, verbose=True
    )
    elapsed = time.time() - t0
    print(f"\nSimulation done in {elapsed:.1f}s")

    prices = result["prices"]
    returns = result["returns"]
    z = result["z"]
    zbar = result["zbar"]

    # --- 統計量 ---
    kurt = sp_kurtosis(returns, fisher=True)
    abs_r = np.abs(returns)
    hill_25 = hill_estimate(abs_r, 0.025)
    hill_5 = hill_estimate(abs_r, 0.05)
    hill_10 = hill_estimate(abs_r, 0.10)
    # Dickey-Fuller on log-prices
    log_p = np.log(prices)
    adf_stat, adf_pvalue, *_ = adfuller(log_p, regression="c", autolag=None, maxlag=0)

    print(f"\n--- Summary statistics ---")
    print(f"  Computed z̄ (from cond 1 / Jacobian):  {zbar:.4f}")
    print(f"  Paper-reported z̄ (Parameter Set I):   0.65")
    print(f"  Excess kurtosis:                      {kurt:.2f}")
    print(f"  Hill α (2.5% tail):                   {hill_25:.2f}")
    print(f"  Hill α (5%   tail):                   {hill_5:.2f}")
    print(f"  Hill α (10%  tail):                   {hill_10:.2f}")
    print(f"  ADF test stat (log p):                {adf_stat:.3f}  (p={adf_pvalue:.3f})")

    # --- 6 パネル図 ---
    fig = plt.figure(figsize=(16, 11))
    fig.suptitle(
        f"Lux & Marchesi (2000) Parameter Set I — YH002 (seed={seed}, T={n_integer_steps})",
        fontsize=14,
        fontweight="bold",
    )
    gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 1])

    # 1. Returns time series
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(returns, linewidth=0.4, color="black")
    ax1.set_title("(1) Returns time series  $r_t = \\ln p_t - \\ln p_{t-1}$")
    ax1.set_xlabel("integer time step $t$")
    ax1.set_ylabel("$r_t$")
    ax1.axhline(0, color="red", alpha=0.3, linewidth=0.7)

    # 2. z(t) と z̄
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(z, linewidth=0.5, color="navy", label="$z(t)=n_c/N$")
    ax2.axhline(
        zbar,
        color="red",
        linestyle="--",
        linewidth=1.2,
        label=f"$\\bar z$ (computed) = {zbar:.3f}",
    )
    ax2.axhline(
        0.65,
        color="orange",
        linestyle=":",
        linewidth=1.2,
        label="$\\bar z$ (paper) = 0.65",
    )
    ax2.set_title("(2) Fraction of chartists $z(t)$ and critical $\\bar z$")
    ax2.set_xlabel("integer time step $t$")
    ax2.set_ylabel("$z$")
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_ylim(0, 1)

    # 3. Returns histogram vs Gaussian (linear)
    ax3 = fig.add_subplot(gs[0, 2])
    std = returns.std()
    bins = np.linspace(-6 * std, 6 * std, 120)
    ax3.hist(
        returns, bins=bins, density=True, alpha=0.7, color="steelblue", label="Simulation"
    )
    xg = np.linspace(-6 * std, 6 * std, 400)
    ax3.plot(
        xg,
        norm.pdf(xg, loc=returns.mean(), scale=std),
        "r-",
        linewidth=1.5,
        label=f"N(0, {std:.4f}²)",
    )
    ax3.set_title("(3) Returns histogram vs same-variance Gaussian (linear)")
    ax3.set_xlabel("$r_t$")
    ax3.set_ylabel("density")
    ax3.legend(fontsize=9)

    # 4. Survival function (log-log)
    ax4 = fig.add_subplot(gs[1, 0])
    abs_r_pos = abs_r[abs_r > 0]
    abs_r_sorted = np.sort(abs_r_pos)
    n = len(abs_r_sorted)
    surv = 1.0 - np.arange(1, n + 1) / (n + 1)
    ax4.loglog(abs_r_sorted, surv, ".", markersize=2, color="steelblue", label="Simulation")
    # 同分散ガウスの survival
    gauss_abs = np.sort(np.abs(np.random.default_rng(0).normal(0, std, size=n)))
    surv_g = 1.0 - np.arange(1, n + 1) / (n + 1)
    ax4.loglog(
        gauss_abs, surv_g, "--", color="red", linewidth=1.2, label="Gaussian (same σ)"
    )
    ax4.set_title("(4) Survival function $P(|r|>x)$ (log-log)")
    ax4.set_xlabel("$|r|$")
    ax4.set_ylabel("$P(|r|>x)$")
    ax4.legend(fontsize=9)
    ax4.grid(True, which="both", alpha=0.3)

    # 5. ACF (raw, squared, absolute), lags 0-300
    ax5 = fig.add_subplot(gs[1, 1:])
    max_lag = 300
    acf_raw = acf(returns, nlags=max_lag, fft=True)
    acf_sq = acf(returns ** 2, nlags=max_lag, fft=True)
    acf_abs = acf(abs_r, nlags=max_lag, fft=True)
    lags = np.arange(max_lag + 1)
    ax5.plot(lags, acf_raw, label="raw $r_t$", color="gray", linewidth=1.0)
    ax5.plot(lags, acf_sq, label="squared $r_t^2$", color="orange", linewidth=1.2)
    ax5.plot(lags, acf_abs, label="absolute $|r_t|$", color="navy", linewidth=1.2)
    ci = 1.96 / np.sqrt(len(returns))
    ax5.axhline(ci, color="red", linestyle=":", linewidth=0.8, alpha=0.7)
    ax5.axhline(-ci, color="red", linestyle=":", linewidth=0.8, alpha=0.7)
    ax5.axhline(0, color="black", linewidth=0.5)
    ax5.set_title("(5) Autocorrelation of raw / squared / absolute returns (lag 0–300)")
    ax5.set_xlabel("lag")
    ax5.set_ylabel("ACF")
    ax5.legend(fontsize=9, loc="upper right")
    ax5.set_xlim(0, max_lag)

    # 6. Summary stats table
    ax6 = fig.add_subplot(gs[2, :])
    ax6.axis("off")
    paper_kurtosis = 135.73  # Table 2, Parameter Set I
    paper_hill_25 = 2.04
    paper_hill_5 = 2.11
    paper_hill_10 = 1.93
    paper_zbar = 0.65

    rows = [
        ["Statistic", "This run (seed={})".format(seed), "Paper Parameter Set I"],
        ["Excess kurtosis", f"{kurt:.2f}", f"{paper_kurtosis:.2f} (Table 2)"],
        ["Hill α̂, 2.5% tail", f"{hill_25:.2f}", f"{paper_hill_25:.2f} (median)"],
        ["Hill α̂, 5%   tail", f"{hill_5:.2f}", f"{paper_hill_5:.2f} (median)"],
        ["Hill α̂, 10%  tail", f"{hill_10:.2f}", f"{paper_hill_10:.2f} (median)"],
        ["ADF stat (log p)", f"{adf_stat:.3f} (p={adf_pvalue:.3f})", "no rejection (Table 1)"],
        [
            "$\\bar z$ (critical)",
            f"{zbar:.3f} (computed)",
            f"{paper_zbar:.2f} (paper text, p.690)",
        ],
        ["Sample size T", f"{len(returns)}", "20,000 (paper uses longer)"],
    ]
    table = ax6.table(cellText=rows, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    for j in range(3):
        table[(0, j)].set_facecolor("#d0d0d0")
        table[(0, j)].set_text_props(weight="bold")
    ax6.set_title(
        "(6) Summary statistics  (paper values: Table 2 for kurt/Hill, p.690 for $\\bar z$)",
        pad=20,
    )

    plt.tight_layout(rect=(0, 0, 1, 0.97))
    plt.savefig("results.png", dpi=150, bbox_inches="tight")
    print("\nFigure saved to experiments/YH002/results.png")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="YH002 Lux-Marchesi (2000) Parameter Set I")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument(
        "--steps", type=int, default=4000, help="number of integer time steps (default 4000)"
    )
    args = parser.parse_args()
    run_and_plot(seed=args.seed, n_integer_steps=args.steps)


if __name__ == "__main__":
    main()
