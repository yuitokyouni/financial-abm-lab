"""Counterfactual prefix gate and aligned, time-weighted impact measurements."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from lobcore import log_before_time, logs_byte_equal, mid_series


class CounterfactualMismatch(RuntimeError):
    """Stop analysis when the pre-intervention paths do not match exactly."""


def impact_execution(log: np.ndarray, impact_id: int) -> dict:
    """Include subsequent maker fills of the residual aggressive limit order."""
    fills = log[log["kind"] == 1]
    taker = (fills["order_id"] >> 32) == impact_id
    maker = (fills["maker_id"] >> 32) == impact_id
    involved = taker | maker
    return {
        "impact_executed_qty": int(fills["qty"][involved].sum()),
        "impact_fill_count": int(involved.sum()),
        "impact_taker_executed_qty": int(fills["qty"][taker].sum()),
        "impact_maker_executed_qty": int(fills["qty"][maker].sum()),
    }


def assert_pre_intervention_equal(
    factual: np.ndarray, baseline: np.ndarray, *, t0: int
) -> dict:
    f_prefix = log_before_time(factual, t0)
    b_prefix = log_before_time(baseline, t0)
    if not len(f_prefix) or not len(b_prefix):
        raise CounterfactualMismatch(
            "Empty pre-intervention log; cannot certify prefix equality"
        )
    prefix_equal = logs_byte_equal(f_prefix, b_prefix)
    if not prefix_equal and not np.array_equal(f_prefix, b_prefix):
        raise CounterfactualMismatch(
            "Pre-intervention fields differ; counterfactual analysis stopped"
        )
    # Also inspect original buffers to locate padding-only mismatches precisely.
    for name, log in (("factual", factual), ("baseline", baseline)):
        if np.any(np.diff(log["received_at"]) < 0):
            raise CounterfactualMismatch(f"{name} log is not time ordered")
    f_raw = factual[: len(f_prefix)].tobytes()
    b_raw = baseline[: len(b_prefix)].tobytes()
    if f_raw != b_raw:
        first = next(i for i, (a, b) in enumerate(zip(f_raw, b_raw)) if a != b)
        raise CounterfactualMismatch(
            f"Pre-intervention raw byte mismatch at byte {first} "
            f"(record {first // factual.dtype.itemsize}, offset {first % factual.dtype.itemsize}); "
            "counterfactual analysis stopped"
        )
    return {
        "records": len(f_prefix),
        "bytes": len(f_raw),
        "sha256": hashlib.sha256(f_raw).hexdigest(),
        "byte_equal": True,
    }


@dataclass
class ImpactSeries:
    times: np.ndarray
    factual_mid: np.ndarray
    baseline_mid: np.ndarray

    @property
    def delta(self) -> np.ndarray:
        return self.factual_mid - self.baseline_mid


def align_mid_series(
    factual: np.ndarray, baseline: np.ndarray, *, boundaries=()
) -> ImpactSeries:
    def observations(log):
        if not len(log):
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=float)
        if np.any(np.diff(log["received_at"]) < 0):
            raise ValueError("mid timestamps must be ordered")
        # Retain the last logged observation at each timestamp, including an
        # empty book. Dropping empty snapshots would carry a stale price forward.
        last = np.r_[np.diff(log["received_at"]) != 0, True]
        snapshots = log[last]
        times = snapshots["received_at"]
        valid_times, valid_mids = mid_series(snapshots)
        mids = np.full(len(times), np.nan)
        mids[np.searchsorted(times, valid_times)] = valid_mids
        return times, mids

    f_t, f_m = observations(factual)
    b_t, b_m = observations(baseline)
    times = np.unique(
        np.concatenate((f_t, b_t, np.asarray(boundaries, dtype=np.int64)))
    )

    def align(t, m):
        if np.any(np.diff(t) < 0):
            raise ValueError("mid timestamps must be ordered")
        idx = np.searchsorted(t, times, side="right") - 1
        values = np.full(len(times), np.nan)
        valid = idx >= 0
        values[valid] = m[idx[valid]]
        return values

    return ImpactSeries(times, align(f_t, f_m), align(b_t, b_m))


def time_mean_delta(series: ImpactSeries, *, t0: int, t1: int) -> float:
    if t1 <= t0:
        raise ValueError("Require t1 > t0")
    grid = np.unique(
        np.concatenate(
            ([t0], series.times[(series.times > t0) & (series.times < t1)], [t1])
        )
    )
    idx = np.searchsorted(series.times, grid[:-1], side="right") - 1
    if np.any(idx < 0) or not np.all(np.isfinite(series.delta[idx])):
        raise ValueError("Incomplete mid coverage in the impact window")
    return float(np.sum(series.delta[idx] * np.diff(grid)) / (t1 - t0))
