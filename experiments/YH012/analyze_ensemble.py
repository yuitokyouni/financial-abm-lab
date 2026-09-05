"""Re-verify every archived pair, then average all preselected seed trajectories."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from .ensemble import (
    bootstrap_weights,
    sample_delta,
    seed_statistics,
    window_statistics,
)
from .impact import align_mid_series, time_mean_delta
from .run_ensemble import save_json, verified_pair


def analyze(directory: Path, output: Path):
    plan = json.loads((directory / "plan.json").read_text())
    progress = json.loads((directory / "progress.json").read_text())
    if (
        progress["status"] != "COMPLETE: all prefixes byte equal"
        or sorted(progress["completed"]) != plan["seeds"]
    ):
        raise ValueError(
            "Ensemble is incomplete or stopped; no aggregate will be produced"
        )
    config = plan["config"]
    t0, t1 = config["impact"]["t0"], config["impact"]["t1"]
    end = config["end_time"]
    times = np.arange(end + 1, dtype=np.int64)
    rows, certificates = [], []
    # Perform every integrity check before producing statistics or figures.
    for seed in plan["seeds"]:
        seed_config = deepcopy(config)
        seed_config["seed"] = seed
        summary, (factual, baseline) = verified_pair(
            directory / f"seed{seed:04d}", seed_config, plan["lobcore_commit"]
        )
        series = align_mid_series(factual, baseline, boundaries=(t0, t1, end))
        row = sample_delta(series, times)
        if not np.isfinite(row[t0:]).all():
            raise ValueError(
                f"seed={seed}: missing post-intervention mid; no seed exclusions"
            )
        if np.any(np.isfinite(row[:t0]) & (row[:t0] != 0)):
            raise ValueError(f"seed={seed}: aligned pre-intervention delta differs")
        # Independent event-time integration cross-checks the unit grid.
        for start, stop in ((t0, t1), (plan["analysis"]["tail_start"], end)):
            if not np.isclose(
                row[start:stop].mean(),
                time_mean_delta(series, t0=start, t1=stop),
                rtol=0,
                atol=1e-12,
            ):
                raise ValueError(f"seed={seed}: grid and native integral disagree")
        rows.append(row)
        nonzero = np.flatnonzero(row[t0:] != 0)
        zero_since = (
            int(t0 + nonzero[-1] + 1)
            if len(nonzero) and nonzero[-1] < end - t0
            else (t0 if not len(nonzero) else None)
        )
        certificates.append(
            {
                "seed": seed,
                "prefix": summary["prefix"],
                "arms": summary["arms"],
                "initial_window_mean": summary["mean_delta"],
                "impact_executed_qty": summary["impact_executed_qty"],
                "impact_fill_count": summary["impact_fill_count"],
                "peak": float(row[t0:].max()),
                "trough": float(row[t0:].min()),
                "final_delta": float(row[-1]),
                "zero_through_end_since": zero_since,
            }
        )
    delta = np.stack(rows)
    analysis = plan["analysis"]
    weights = bootstrap_weights(
        len(rows),
        replicates=analysis["bootstrap_replicates"],
        seed=analysis["bootstrap_seed"],
    )
    stats = seed_statistics(delta, weights)
    windows = [
        window_statistics(times, delta, weights, start=a, end=b)
        for a, b in (
            (t0, t1),
            (t1, 30000),
            (30000, 35000),
            (35000, 40000),
            (40000, analysis["tail_start"]),
            (analysis["tail_start"], end),
            (t0, end),
        )
        if a < b <= end
    ]
    tail = window_statistics(
        times, delta, weights, start=analysis["tail_start"], end=end
    )
    post = stats["mean"][t0:]

    def point(index):
        return {"time": int(t0 + index), "mean": float(post[index])}

    tail_mask = times >= analysis["tail_start"]
    summary = {
        "status": "ALL_SEEDS_VERIFIED",
        "plan": plan,
        "n_seeds": len(rows),
        "all_pre_intervention_bytes_equal": True,
        "statistics": {
            "sd": "Sample standard deviation across seeds (ddof=1); not a confidence interval.",
            "ci": "Pointwise 95% percentile bootstrap CI of the seed mean; resample whole seed trajectories with fixed common weights across time; not a simultaneous band.",
            "tail_ci": "Bootstrap of the per-seed time averages; no assumption of independent timestamps.",
            "missing": "Report a grid point only if all seeds have a mid. Require full post-t0 coverage; never zero-fill or discard seeds.",
            "mid": "Last pre-acceptance quote snapshot at each timestamp, previous-value hold; lobcore one-sided fallback; no future backfill.",
            "window": "Unit-spaced integer grid, exact step-function integral on [start,end); endpoint at end has zero time weight.",
            "scope": "Monte Carlo uncertainty for this fixed model/configuration; [45000,50000] is a finite-horizon proxy, not proof of an infinite-time limit.",
        },
        "mean_peak": point(int(np.argmax(post))),
        "mean_trough": point(int(np.argmin(post))),
        "individual_peak": float(delta[:, t0:].max()),
        "individual_trough": float(delta[:, t0:].min()),
        "final_mean": float(stats["mean"][-1]),
        "final_sd": float(stats["sd"][-1]),
        "final_ci": [float(stats["ci_low"][-1]), float(stats["ci_high"][-1])],
        "tail": tail,
        "windows": windows,
        "tail_trajectory_mean_range": [
            float(stats["mean"][tail_mask].min()),
            float(stats["mean"][tail_mask].max()),
        ],
        "n_seeds_exactly_zero_whole_tail": int(
            np.all(delta[:, tail_mask] == 0, axis=1).sum()
        ),
        "n_initial_window_positive": sum(
            c["initial_window_mean"] > 0 for c in certificates
        ),
        "per_seed": certificates,
    }
    output.mkdir(parents=True, exist_ok=True)
    paths = output / "ensemble_paths.npz"
    np.savez_compressed(
        paths, times=times, seeds=np.array(plan["seeds"]), delta=delta, **stats
    )
    summary["ensemble_paths_sha256"] = hashlib.sha256(paths.read_bytes()).hexdigest()
    save_json(output / "summary.json", summary)
    from .plot import plot_ensemble

    plot_ensemble(
        times,
        delta,
        stats,
        t0=t0,
        t1=t1,
        qty=config["impact"]["qty"],
        tail=tail,
        output=output,
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("plan", "per_seed", "windows", "statistics")
            },
            indent=2,
        )
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.run_dir, args.out_dir)


if __name__ == "__main__":
    main()
