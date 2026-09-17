"""Compare archived means without hiding their different vertical scales."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old, new = np.load(args.before), np.load(args.after)
    if not np.array_equal(old["seeds"], new["seeds"]):
        raise ValueError("Comparison requires identical cohorts")
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), layout="constrained", sharex=True)
    for ax, data, label, color in zip(
        axes, [old, new],
        ["Before: copied RNG state (historical output)", "After: kernel-owned RNG state"],
        ["#a84439", "#146a9e"],
    ):
        times = data["times"]
        visible = times >= 24000
        ax.fill_between(times[visible], data["ci_low"][visible], data["ci_high"][visible],
                        color=color, alpha=.18, step="post", label="Pointwise 95% bootstrap CI")
        ax.step(times[visible], data["mean"][visible], where="post", color=color,
                lw=1.1, label="39-seed mean")
        ax.axvline(25000, color=".35", ls="--", lw=.8)
        ax.axhline(0, color=".35", lw=.6)
        ax.set(title=label, ylabel="Mean F - B [ticks]")
        ax.grid(alpha=.16)
        ax.legend(loc="upper right", fontsize=8)
    axes[-1].set(xlabel="Simulation time", xlim=(24000, 50000))
    fig.suptitle("Same 39 seeds, Q=200, t0=25,000 — different y-axis scales", fontsize=12)
    fig.savefig(args.output, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
