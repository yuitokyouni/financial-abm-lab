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


def plot_ensemble(times, delta, stats, *, t0, t1, qty, tail, output):
    """Show individual spread separately from uncertainty of the seed mean."""
    output = Path(output)
    visible = times >= t0 - 1000
    t = times[visible]
    mean, sd = stats["mean"][visible], stats["sd"][visible]
    low, high = stats["ci_low"][visible], stats["ci_high"][visible]

    def decorate(ax):
        ax.axhline(0, color="0.35", linewidth=0.7)
        ax.axvline(t0, color="0.3", linestyle="--", linewidth=1)
        ax.axvspan(t0, t1, color="#e5b83b", alpha=0.16)
        ax.grid(alpha=0.18)
        ax.ticklabel_format(axis="y", style="plain", useOffset=False)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True, layout="constrained")
    for row in delta:
        axes[0].step(
            t, row[visible], where="post", color="0.55", alpha=0.25, linewidth=0.5
        )
    axes[0].fill_between(
        t,
        mean - sd,
        mean + sd,
        step="post",
        color="#297bb5",
        alpha=0.22,
        label="Mean ± 1 seed SD",
    )
    axes[0].step(
        t, mean, where="post", color="#146a9e", linewidth=1.3, label="Seed mean"
    )
    axes[0].set_ylabel("Individual delta [ticks]")
    axes[0].legend(loc="upper right")
    axes[1].fill_between(
        t,
        low,
        high,
        step="post",
        color="#297bb5",
        alpha=0.24,
        label="Pointwise 95% bootstrap CI",
    )
    axes[1].step(
        t, mean, where="post", color="#146a9e", linewidth=1.1, label="Seed mean"
    )
    axes[1].set_ylabel("Mean delta [ticks]")
    axes[1].legend(loc="upper right")
    axes[2].step(
        t,
        sd,
        where="post",
        color="#9b5d28",
        linewidth=1.1,
        label="Across-seed sample SD (ddof=1)",
    )
    axes[2].set_ylabel("Seed SD [ticks]")
    axes[2].set_xlabel("Simulation time")
    axes[2].legend(loc="upper right")
    for ax in axes:
        decorate(ax)
    axes[2].set_xlim(t0 - 1000, times[-1])
    fig.suptitle(
        f"YH012 | buy Q={qty} | {len(delta)} seeds | end={times[-1]:,}\nAll pre-t0 F/B prefixes byte-identical; no seed exclusions"
    )
    fig.savefig(output / "ensemble.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), layout="constrained")
    for ax, (start, end), label in zip(
        axes,
        ((t0 - 100, t1 + 1000), (tail["start"], tail["end"])),
        ("Onset", "Late window"),
    ):
        mask = (times >= start) & (times <= end)
        ax.fill_between(
            times[mask],
            stats["ci_low"][mask],
            stats["ci_high"][mask],
            step="post",
            color="#297bb5",
            alpha=0.24,
            label="Pointwise 95% CI",
        )
        ax.step(
            times[mask],
            stats["mean"][mask],
            where="post",
            color="#146a9e",
            linewidth=1.2,
            label="Seed mean",
        )
        decorate(ax)
        ax.set_xlim(start, end)
        ax.set_xlabel("Simulation time")
        ax.set_ylabel("Mean delta [ticks]")
        ax.set_title(label)
        ax.legend(loc="best")
    axes[1].axhline(tail["mean"], color="#ba6c26", linestyle=":", label="Time mean")
    fig.suptitle(
        f"Q={qty}, n={len(delta)} | Late time mean: {tail['mean']:+.4f} ticks\nSeed-bootstrap 95% CI of late time mean: [{tail['ci_low']:+.4f}, {tail['ci_high']:+.4f}]"
    )
    fig.savefig(output / "ensemble_windows.png", dpi=170)
    plt.close(fig)
