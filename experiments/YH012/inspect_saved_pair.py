"""Verify saved F/B logs and summarize the finite-horizon shape of their impact."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
from lobcore import ExperimentMeta, LOG_DTYPE

from .impact import (
    ImpactSeries,
    align_mid_series,
    assert_pre_intervention_equal,
    time_mean_delta,
)


def read_verified_log(path: Path, expected: dict) -> tuple[ExperimentMeta, np.ndarray]:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"Truncated log header: {path}")
    offset = 8 + int.from_bytes(data[:8], "little")
    if offset > len(data) or (len(data) - offset) % LOG_DTYPE.itemsize:
        raise ValueError(f"Invalid log length: {path}")
    meta = ExperimentMeta(**json.loads(data[8:offset]))
    if hashlib.sha256(data[offset:]).hexdigest() != expected["log_sha256"]:
        raise ValueError(f"Log payload SHA-256 mismatch: {path}")
    if asdict(meta) != expected["meta"]:
        raise ValueError(f"ExperimentMeta mismatch: {path}")
    # A structured-array .copy() does not preserve padding. Keep the original
    # immutable bytes so the strict prefix check works after a save/load cycle.
    log = np.frombuffer(data, dtype=LOG_DTYPE, offset=offset)
    if len(log) != expected["n_records"]:
        raise ValueError(f"Record count mismatch: {path}")
    return meta, log


def time_structure(
    series: ImpactSeries, *, t0: int, t1: int, end_time: int, tail_start: int
) -> dict:
    if not t0 < t1 <= end_time or not t0 <= tail_start < end_time:
        raise ValueError("Invalid analysis windows")
    if not len(series.times) or series.times[-1] < end_time:
        raise ValueError("Series does not cover the requested horizon")
    times = np.unique(
        np.r_[
            t0, series.times[(series.times > t0) & (series.times < end_time)], end_time
        ]
    )
    indices = np.searchsorted(series.times, times, side="right") - 1
    if np.any(indices < 0) or not np.all(np.isfinite(series.delta[indices])):
        raise ValueError("Incomplete mid coverage in the post-intervention horizon")
    delta = series.delta[indices]
    nonzero = np.flatnonzero(delta != 0)
    onset = int(nonzero[0]) if len(nonzero) else None
    zero_after = (
        np.flatnonzero((delta == 0) & (times > times[onset]))
        if onset is not None
        else []
    )
    nonzero_intervals = np.flatnonzero(delta[:-1] != 0)
    candidate = int(nonzero_intervals[-1] + 1) if len(nonzero_intervals) else 0
    zero_since = (
        int(times[candidate])
        if times[candidate] < end_time and np.all(delta[candidate:] == 0)
        else None
    )

    def point(i):
        return None if i is None else {"time": int(times[i]), "delta": float(delta[i])}

    boundaries = sorted(
        {t0, t1, *range(((t1 // 5000) + 1) * 5000, end_time, 5000), end_time}
    )
    return {
        "t0": t0,
        "t1": t1,
        "end_time": end_time,
        "onset": point(onset),
        "first_zero_after_onset": int(times[zero_after[0]])
        if len(zero_after)
        else None,
        "zero_through_end_since": zero_since,
        "peak": point(int(np.argmax(delta))),
        "trough": point(int(np.argmin(delta))),
        "final_delta": float(delta[-1]),
        "late_window": {
            "start": tail_start,
            "end": end_time,
            "time_mean_delta": time_mean_delta(series, t0=tail_start, t1=end_time),
        },
        "full_post_time_mean_delta": time_mean_delta(series, t0=t0, t1=end_time),
        "intervals": [
            {
                "start": a,
                "end": b,
                "time_mean_delta": time_mean_delta(series, t0=a, t1=b),
            }
            for a, b in zip(boundaries[:-1], boundaries[1:])
        ],
        "interpretation_scope": "Finite observed horizon and this seed; not an estimate of the infinite-time limit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--tail-start", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = json.loads((args.run_dir / "summary.json").read_text())
    f_meta, factual = read_verified_log(
        args.run_dir / "factual.bin", summary["arms"]["factual"]
    )
    b_meta, baseline = read_verified_log(
        args.run_dir / "baseline.bin", summary["arms"]["baseline"]
    )
    for name in (
        "master_seed",
        "allocation_rule",
        "n_agents",
        "n_markets",
        "end_time",
        "lobcore_version",
    ):
        if getattr(f_meta, name) != getattr(b_meta, name):
            raise ValueError(f"F/B metadata disagree on {name}")
    t0, t1, end = summary["t0"], summary["t1"], f_meta.end_time
    prefix = assert_pre_intervention_equal(factual, baseline, t0=t0)
    series = align_mid_series(factual, baseline, boundaries=(t0, t1, end))
    tail_start = (
        args.tail_start
        if args.tail_start is not None
        else end - max(1, (end - t0) // 5)
    )
    profile = time_structure(series, t0=t0, t1=t1, end_time=end, tail_start=tail_start)
    report = {
        "analyzed_saved_logs": True,
        "lobcore_version": f_meta.lobcore_version,
        "prefix": prefix,
        "time_structure": profile,
        "log_sha256": {
            arm: summary["arms"][arm]["log_sha256"] for arm in ("factual", "baseline")
        },
    }
    output = args.output or args.run_dir / "time_structure.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(profile, indent=2))
    print(f"Saved verified reanalysis: {output}")


if __name__ == "__main__":
    main()
