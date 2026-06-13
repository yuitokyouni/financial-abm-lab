"""Cont-Bouchaud (1997) — simulation runner & visualization.

Usage:
    python experiments/YH001/run_simulation.py
"""

from __future__ import annotations

import time
import numpy as np
import powerlaw
import matplotlib.pyplot as plt
from scipy.stats import norm
from model import simulate


def run_and_plot():
    print("=" * 60)
    print("Cont-Bouchaud (1997) — YH001")
    print("=" * 60)

    # --- Main simulation ---
    params = dict(N=10000, c=0.9, a=0.01, lam=1.0, T=50000, seed=42)
    print(f"\nRunning main simulation: {params}")
    t0 = time.time()
    result = simulate(**params)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s")

    returns = result["returns"]
    cluster_sizes = result["cluster_sizes"]

    # --- Excess kurtosis ---
    from scipy.stats import kurtosis as sp_kurtosis

    kurt = sp_kurtosis(returns, fisher=True)
    print(f"\nExcess kurtosis: {kurt:.2f}  (Gaussian = 0)")

    # --- Figure ---
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(
        "Cont-Bouchaud (1997) Percolation Model — YH001",
        fontsize=14,
        fontweight="bold",
    )

    # 1. Return time series
    ax = axes[0, 0]
    ax.plot(returns[:5000], linewidth=0.3, color="black")
    ax.set_title("Return time series (first 5000 steps)")
    ax.set_xlabel("t")
    ax.set_ylabel("Δx(t)")

    # 2. Return distribution vs Gaussian (linear)
    ax = axes[0, 1]
    std = returns.std()
    bins = np.linspace(-5 * std, 5 * std, 200)
    ax.hist(returns, bins=bins, density=True, alpha=0.7, label="Simulation")
    x_gauss = np.linspace(-5 * std, 5 * std, 500)
    ax.plot(
        x_gauss,
        norm.pdf(x_gauss, loc=returns.mean(), scale=std),
        "r-",
        linewidth=1.5,
        label="Gaussian",
    )
    ax.set_title("Return distribution vs Gaussian")
    ax.set_xlabel("Δx")
    ax.set_ylabel("Density")
    ax.legend()

    # 3. Log-scale tail comparison
    ax = axes[0, 2]
    counts, bin_edges = np.histogram(returns, bins=200, density=True)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    mask = counts > 0
    ax.semilogy(bin_centers[mask], counts[mask], "o", markersize=2, label="Simulation")
    ax.semilogy(
        x_gauss,
        norm.pdf(x_gauss, loc=returns.mean(), scale=std),
        "r-",
        linewidth=1.5,
        label="Gaussian",
    )
    ax.set_title("Log-scale tail comparison")
    ax.set_xlabel("Δx")
    ax.set_ylabel("log P(Δx)")
    ax.legend()

    # 4. Cluster size distribution (log-log)
    ax = axes[1, 0]
    max_size = int(cluster_sizes.max())
    size_counts = np.bincount(cluster_sizes.astype(int))[1:]  # skip size=0
    sizes_range = np.arange(1, len(size_counts) + 1)
    mask = size_counts > 0
    ax.loglog(sizes_range[mask], size_counts[mask] / size_counts[mask].sum(), "o", markersize=2)
    # Theoretical slope: P(W) ~ W^{-5/2}
    w_th = np.logspace(0, np.log10(max_size), 100)
    p_th = w_th ** (-2.5)
    p_th = p_th / p_th.sum() * (size_counts[mask].sum() / size_counts[mask].sum())
    # Normalize for visual comparison
    ax.loglog(w_th, p_th * (sizes_range[mask][0] ** 2.5) * (size_counts[mask][0] / size_counts[mask].sum()), "--", color="red", label=r"$W^{-5/2}$ (theory)")
    ax.set_title("Cluster size distribution")
    ax.set_xlabel("Cluster size W")
    ax.set_ylabel("P(W)")
    ax.legend()

    # 5 & 6: Parameter sweep — compute kurtosis and α together
    c_values = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
    kurtosis_values = []
    alpha_values = []
    alpha_sigmas = []
    print("\nParameter sweep (c → kurtosis, α):")
    for c_val in c_values:
        print(f"  c={c_val} ...", end=" ", flush=True)
        t0 = time.time()
        res = simulate(N=10000, c=c_val, a=0.01, T=10000, seed=42, report_every=0)
        r = res["returns"]
        k = sp_kurtosis(r, fisher=True)
        kurtosis_values.append(k)
        abs_r = np.abs(r)
        abs_r = abs_r[abs_r > 0]
        fit = powerlaw.Fit(abs_r, discrete=True, verbose=False)
        alpha_values.append(fit.power_law.alpha)
        alpha_sigmas.append(fit.power_law.sigma)
        print(f"kurtosis={k:.2f}, α={fit.power_law.alpha:.3f}  ({time.time()-t0:.1f}s)")

    # 5. Tail exponent α vs c
    ax = axes[1, 1]
    ax.errorbar(
        c_values, alpha_values, yerr=alpha_sigmas,
        fmt="o-", color="navy", linewidth=2, markersize=7, capsize=4,
    )
    ax.axhline(y=3.0, color="red", linestyle="--", alpha=0.6, label=r"$\alpha=3$")
    ax.set_title(r"Tail exponent $\alpha$ vs c  (Clauset MLE)")
    ax.set_xlabel("c")
    ax.set_ylabel(r"$\alpha$")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # 6. Kurtosis vs c
    ax = axes[1, 2]
    ax.plot(c_values, kurtosis_values, "o-", color="navy", linewidth=2, markersize=7)
    ax.set_title("Excess kurtosis vs c")
    ax.set_xlabel("c")
    ax.set_ylabel("Excess kurtosis")
    ax.axhline(y=0, color="red", linestyle="--", alpha=0.5, label="Gaussian")
    ax.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig("results.png", dpi=150, bbox_inches="tight")
    print(f"\nFigure saved to experiments/YH001/results.png")
    plt.close()


if __name__ == "__main__":
    run_and_plot()
