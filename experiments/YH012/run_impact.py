"""Run and certify the Phase 2/3 paired intervention; save logs, metrics and plot."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import numpy as np
from lobcore import write_log_file

from .experiment import ImpactExperiment
from .impact import assert_pre_intervention_equal, align_mid_series, time_mean_delta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "configs/impact_seed42.yaml",
    )
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    exp = ImpactExperiment.from_yaml(args.config)
    out = (
        args.out_dir
        or Path(__file__).parent / "artifacts" / f"impact_seed{exp.seed}_q{exp.qty}"
    )
    out.mkdir(parents=True, exist_ok=True)
    print(
        f"YH012 F/B: seed={exp.seed}, Q={exp.qty}, t0={exp.t0}, t1={exp.t1}", flush=True
    )
    pair = exp.run_pair(suppress_agent_ids=[exp.impact_id])
    summary = {
        "seed": exp.seed,
        "impact_id": exp.impact_id,
        "qty": exp.qty,
        "t0": exp.t0,
        "t1": exp.t1,
        "price_offset": exp.price_offset,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "matplotlib": importlib.metadata.version("matplotlib"),
        },
        "arms": {},
    }
    for label, result in (("factual", pair.factual), ("baseline", pair.baseline)):
        write_log_file(str(out / f"{label}.bin"), result.meta, result.log)
        summary["arms"][label] = {
            "meta": asdict(result.meta),
            "state_hash": result.state_hash,
            "log_sha256": hashlib.sha256(result.log.tobytes()).hexdigest(),
            "n_records": len(result.log),
            "n_fills": int(np.sum(result.log["kind"] == 1)),
            "n_rejects": int(np.sum(result.log["kind"] == 3)),
        }
    summary_path = out / "summary.json"
    try:
        # All downstream measurements and plots depend on this exact prefix gate.
        summary["prefix"] = assert_pre_intervention_equal(
            pair.factual.log, pair.baseline.log, t0=exp.t0
        )
    except RuntimeError as exc:
        summary["prefix"] = {"byte_equal": False, "error": str(exc)}
        summary["status"] = "STOP: pre-intervention mismatch"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(summary["status"] + ": " + str(exc), file=sys.stderr)
        return 2

    series = align_mid_series(
        pair.factual.log, pair.baseline.log, boundaries=(exp.t0, exp.t1, exp.end_time)
    )
    mean_delta = time_mean_delta(series, t0=exp.t0, t1=exp.t1)
    summary["mean_delta"] = mean_delta
    summary["positive_mean_delta"] = mean_delta > 0
    summary["status"] = "PASS" if mean_delta > 0 else "FAIL: mean delta <= 0"
    impact_fills = pair.factual.log[
        (pair.factual.log["kind"] == 1)
        & ((pair.factual.log["order_id"] >> 32) == exp.impact_id)
    ]
    summary["impact_executed_qty"] = int(impact_fills["qty"].sum())
    summary["impact_fill_count"] = len(impact_fills)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    np.savez_compressed(
        out / "mid_paths.npz",
        times=series.times,
        factual_mid=series.factual_mid,
        baseline_mid=series.baseline_mid,
        delta=series.delta,
    )
    from .plot import plot_impact

    plot_impact(
        series,
        t0=exp.t0,
        t1=exp.t1,
        mean_delta=mean_delta,
        seed=exp.seed,
        qty=exp.qty,
        path=out / "impact.png",
    )
    plot_impact(
        series,
        t0=exp.t0,
        t1=exp.t1,
        mean_delta=mean_delta,
        seed=exp.seed,
        qty=exp.qty,
        path=out / "impact_window.png",
        xlim=(max(1, exp.t0 - (exp.t1 - exp.t0) // 5), exp.t1),
    )
    print(f"prefix: {summary['prefix']}")
    print(f"mean delta: {mean_delta:+.6f} ticks; {summary['status']}")
    print(f"impact executed: {summary['impact_executed_qty']}/{exp.qty}")
    print(f"lobcore: {pair.factual.meta.lobcore_version}")
    print(f"saved: {out}")
    return 0 if mean_delta > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
