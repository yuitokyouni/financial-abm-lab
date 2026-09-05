"""Seed-level uncertainty for paired, stepwise counterfactual trajectories."""

from __future__ import annotations

import numpy as np

from .impact import ImpactSeries


def sample_delta(series: ImpactSeries, times: np.ndarray) -> np.ndarray:
    """Previous observation only; retain missing quotes instead of zero filling."""
    if not len(series.times) or np.any(np.diff(series.times) <= 0):
        raise ValueError("Require nonempty, strictly increasing observation times")
    if len(times) and times[-1] > series.times[-1]:
        raise ValueError("Requested grid exceeds the observed horizon")
    indices = np.searchsorted(series.times, times, side="right") - 1
    values = np.full(len(times), np.nan)
    valid = indices >= 0
    values[valid] = series.delta[indices[valid]]
    return values


def bootstrap_weights(n_seeds: int, *, replicates: int, seed: int) -> np.ndarray:
    if n_seeds < 2 or replicates < 2:
        raise ValueError("Require at least two seeds and bootstrap replicates")
    # One row resamples whole seed trajectories. Reuse these rows for every
    # timestamp and for window means; time points are never independent draws.
    rng = np.random.default_rng(seed)
    return (
        rng.multinomial(n_seeds, np.full(n_seeds, 1 / n_seeds), size=replicates)
        / n_seeds
    )


def seed_statistics(values: np.ndarray, weights: np.ndarray) -> dict:
    """Sample SD and percentile 95% CI of the mean, with a fixed seed population.

    Missing data in any seed makes that column unreported, avoiding a changing
    or selectively filtered ensemble. CIs are pointwise, not simultaneous bands.
    """
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError("Expected [seed, observation] with at least two seeds")
    if weights.ndim != 2 or weights.shape[1] != len(values):
        raise ValueError("Bootstrap weights must resample the full seed population")
    mean = values.mean(axis=0)
    sd = values.std(axis=0, ddof=1)
    low, high = np.full_like(mean, np.nan), np.full_like(mean, np.nan)
    valid = np.flatnonzero(np.isfinite(values).all(axis=0))
    # Bound temporary storage to 4000 x 512 doubles for the default ensemble.
    for start in range(0, len(valid), 512):
        columns = valid[start : start + 512]
        draws = weights @ values[:, columns]
        low[columns], high[columns] = np.quantile(draws, [0.025, 0.975], axis=0)
    return {
        "mean": mean,
        "sd": sd,
        "se": sd / np.sqrt(len(values)),
        "ci_low": low,
        "ci_high": high,
        "n_finite": np.isfinite(values).sum(axis=0),
    }


def window_statistics(times, delta, weights, *, start, end):
    """Exact time integral on the integer grid; the endpoint has zero duration."""
    times = np.asarray(times)
    if (
        np.any(np.diff(times) != 1)
        or start not in times
        or end not in times
        or end <= start
    ):
        raise ValueError("Window requires a unit-spaced grid covering both endpoints")
    visible = (times >= start) & (times < end)
    if not np.isfinite(delta[:, visible]).all():
        raise ValueError("Incomplete seed coverage in window")
    seed_means = delta[:, visible].mean(axis=1)
    stats = seed_statistics(seed_means[:, None], weights)
    return {
        "start": int(start),
        "end": int(end),
        "per_seed_time_mean": seed_means.tolist(),
        **{
            name: float(value[0]) for name, value in stats.items() if name != "n_finite"
        },
        "n_seeds": len(delta),
    }
