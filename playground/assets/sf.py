"""Shared analysis helpers for the browser playground (numpy-only).

These are NOT a re-implementation of any model — they are plotting/statistics
utilities so each page can derive figures from the *real* model output without
pulling matplotlib / scipy.stats / powerlaw into Pyodide. Kept faithful to the
estimators used in the repo (analysis/, experiments/YH005/analysis.py).
"""
from __future__ import annotations

import numpy as np


def excess_kurtosis(x):
    x = np.asarray(x, dtype=np.float64)
    x = x[~np.isnan(x)]
    if x.size < 4:
        return float("nan")
    s = x.std()
    if s == 0:
        return float("nan")
    z = (x - x.mean()) / s
    return float((z ** 4).mean() - 3.0)


def acf(series, max_lag):
    """Autocorrelation ACF[1..max_lag], NaN-aware (matches YH005 analysis._acf)."""
    x = np.asarray(series, dtype=np.float64)
    mask = ~np.isnan(x)
    if mask.sum() < 2:
        return [float("nan")] * max_lag
    var = ((x[mask] - x[mask].mean()) ** 2).mean()
    if var == 0:
        return [0.0] * max_lag
    xd = np.where(mask, x - x[mask].mean(), np.nan)
    out = []
    for lag in range(1, max_lag + 1):
        prod = xd[:-lag] * xd[lag:]
        out.append(float(np.nanmean(prod) / var))
    return out


def hill_alpha(values, k=None):
    """Hill MLE tail index alpha on |values| (matches YH005 analysis)."""
    x = np.asarray(values, dtype=np.float64)
    x = np.abs(x[~np.isnan(x)])
    x = x[x > 0]
    if x.size < 4:
        return float("nan")
    sd = np.sort(x)[::-1]
    if k is None:
        k = int(np.sqrt(sd.size))
    k = min(max(k, 2), sd.size - 1)
    lr = (np.log(sd[:k]) - np.log(sd[k])).mean()
    return float(1.0 / lr) if lr > 0 else float("nan")


def hill_alpha_p90(values, pct=90.0):
    """Hill alpha with xmin = pct-th percentile (matches YH005_1 wealth estimator).

    Returns (alpha, xmin, n_tail).
    """
    x = np.asarray(values, dtype=np.float64)
    x = x[~np.isnan(x)]
    x = x[x > 0]
    if x.size < 4:
        return float("nan"), float("nan"), 0
    xmin = float(np.percentile(x, pct))
    tail = x[x >= xmin]
    if tail.size < 2 or xmin <= 0:
        return float("nan"), xmin, int(tail.size)
    lr = np.log(tail / xmin).mean()
    a = float(1.0 / lr) if lr > 0 else float("nan")
    return a, xmin, int(tail.size)


def ccdf(values, scale_only=True):
    """Complementary CDF of |values|. Returns (x_sorted, ccdf)."""
    x = np.asarray(values, dtype=np.float64)
    x = np.abs(x[~np.isnan(x)])
    if scale_only:
        s = x.std()
        if s > 0:
            x = x / s
    x = np.sort(x)
    n = x.size
    return x, (1.0 - np.arange(n) / n)


def ccdf_raw(values):
    """CCDF P[X >= x] of positive values, no rescale (for wealth)."""
    x = np.asarray(values, dtype=np.float64)
    x = x[x > 0]
    x = np.sort(x)
    n = x.size
    return x, (1.0 - np.arange(n) / n)


def hist_density(x, lo, hi, bins=120):
    x = np.asarray(x, dtype=np.float64)
    x = x[~np.isnan(x)]
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(x, bins=edges, density=True)
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, counts


def loglog_hist(x, nbins=40):
    """Log-spaced histogram counts for positive integer-ish data (horizons etc.)."""
    x = np.asarray(x, dtype=np.float64)
    x = x[x > 0]
    if x.size == 0:
        return [], []
    lo = max(1.0, float(x.min()))
    hi = float(x.max())
    if hi <= lo:
        edges = np.array([lo, lo + 1.0])
    else:
        edges = np.logspace(np.log10(lo), np.log10(hi + 1), nbins)
    counts, _ = np.histogram(x, bins=edges)
    centers = 0.5 * (edges[:-1] + edges[1:])
    nz = counts > 0
    return centers[nz].tolist(), counts[nz].tolist()


def gaussian_pdf(grid, mu, sigma):
    grid = np.asarray(grid, dtype=np.float64)
    return (1.0 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((grid - mu) / sigma) ** 2)


def downsample(x, max_points=4000):
    """Stride-downsample a 1D series for plotting; returns (idx, vals)."""
    x = np.asarray(x)
    n = x.size
    if n <= max_points:
        return np.arange(n).tolist(), x.tolist()
    stride = int(np.ceil(n / max_points))
    idx = np.arange(0, n, stride)
    return idx.tolist(), x[idx].tolist()


def binom_cdf(k, n, p=0.5):
    """P[X <= k] for X~Bin(n,p), pure-python (for YH004 theory curve, small n)."""
    from math import comb
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    q = 1.0 - p
    total = 0.0
    for i in range(int(k) + 1):
        total += comb(n, i) * (p ** i) * (q ** (n - i))
    return total
