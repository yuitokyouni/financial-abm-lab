"""Export the paired mid paths and delta with matplotlib only."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


from .impact import ImpactSeries


def plot_impact(
    series: ImpactSeries,
    *,
    t0: int,
    t1: int,
    mean_delta: float,
    seed: int,
    qty: int,
    path: str | Path,
    xlim: tuple[int, int] | None = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, layout="constrained")
    axes[0].step(
        series.times,
        series.factual_mid,
        where="post",
        color="#1879b5",
        label="Factual (buy)",
    )
    axes[0].step(
        series.times,
        series.baseline_mid,
        where="post",
        color="#d66a28",
        label="Baseline (suppressed)",
    )
    axes[0].set_ylabel("Mid price [ticks]")
    axes[0].legend(loc="best")
    axes[1].step(
        series.times,
        series.delta,
        where="post",
        color="#3f745b",
        label="Factual - baseline",
    )
    axes[1].axhline(0, color="0.5", linewidth=0.8)
    axes[1].set_ylabel("Delta [ticks]")
    axes[1].set_xlabel("Simulation time")
    for ax in axes:
        ax.axvline(
            t0, color="0.3", linestyle="--", linewidth=1, label="Decision time t0"
        )
        ax.axvspan(t0, t1, color="#dcb744", alpha=0.20, label="Evaluation window")
        ax.grid(alpha=0.2)
    axes[1].legend(loc="best")
    if xlim is not None:
        axes[1].set_xlim(*xlim)
        visible = (series.times >= xlim[0]) & (series.times <= xlim[1])
        for ax, values in (
            (axes[0], np.r_[series.factual_mid[visible], series.baseline_mid[visible]]),
            (axes[1], np.r_[0.0, series.delta[visible]]),
        ):
            finite = values[np.isfinite(values)]
            if finite.size:
                low, high = float(finite.min()), float(finite.max())
                margin = max(0.1, (high - low) * 0.15)
                ax.set_ylim(low - margin, high + margin)
                ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    fig.suptitle(
        f"YH012 | seed {seed} | buy Q={qty}\n"
        f"Time-weighted mean delta [{t0}, {t1}]: {mean_delta:+.6f} ticks"
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
