"""fingerprint.py — the keystone (promoted verbatim from test/abmlab/fingerprint.py).

Turn one ABM run (a return series) into a fixed-length vector that captures its
*emergent* behaviour via financial stylized facts. Every downstream goal —
the ABM atlas, novelty search, and inverse-ABM ("which model is today's market
closest to?") — is just a nearest-neighbour / distance operation in this space.

Feature set follows the "stylized facts distance" used by the literature
(Gao et al., JASSS 27(2)8 / arXiv:2208.13654): Hill tail index, volatility,
return autocorrelation, squared-return autocorrelation — combined with
inverse-variance weighting so no single feature dominates the distance.
We add excess kurtosis and a leverage-effect term for separation power.
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "volatility",
    "kurtosis",
    "hill_tail_index",
    "acf_ret_l1",
    "acf_absret_mean",
    "leverage",
]


def _autocorr(x: np.ndarray, lag: int) -> float:
    if lag <= 0 or lag >= len(x):
        return 0.0
    a = x[:-lag] - x.mean()
    b = x[lag:] - x.mean()
    denom = np.sqrt((a @ a) * (b @ b))
    return float((a @ b) / denom) if denom > 0 else 0.0


def _autocorr_cross(x: np.ndarray, y: np.ndarray) -> float:
    a = x - x.mean()
    b = y - y.mean()
    denom = np.sqrt((a @ a) * (b @ b))
    return float((a @ b) / denom) if denom > 0 else 0.0


#: Cap the Hill estimator. Real equity returns sit ~3-4; anything above this
#: is a "thin tail" verdict. Without the cap, near-Gaussian / near-degenerate
#: series push alpha into the hundreds and dominate the L2 distance.
HILL_ALPHA_CAP = 20.0


def hill_tail_index(returns: np.ndarray, tail_frac: float = 0.05) -> float:
    """Hill estimator of the tail index on the largest |returns|.

    Returns alpha (tail exponent). Smaller alpha = fatter tails. Capped at
    `HILL_ALPHA_CAP` so a thin-tail / near-degenerate series saturates at the
    cap instead of producing an outlier (which would dominate inverse-variance
    weighting and destroy the geometry).
    """
    a = np.sort(np.abs(returns))[::-1]
    a = a[a > 0]
    k = max(5, int(len(a) * tail_frac))
    k = min(k, len(a) - 1)
    if k < 5:
        return float("nan")
    top = a[:k]
    xmin = a[k]
    if xmin <= 0:
        return float("nan")
    mean_log_ratio = float(np.mean(np.log(top / xmin)))
    if mean_log_ratio <= 0:
        return float("nan")
    alpha = 1.0 / mean_log_ratio
    return float(min(alpha, HILL_ALPHA_CAP))


def fingerprint(returns: np.ndarray, *, compute_hill: bool = True) -> np.ndarray:
    """Raw (unstandardized) stylized-facts fingerprint of a return series.

    Parameters
    ----------
    returns
        The series. For price ABMs this is log-returns. For priceless ABMs
        (MG/GCMG) it is the attendance excess `2A − N` — a discrete integer
        series for which a power-law tail index is meaningless.
    compute_hill
        If False, the Hill feature is filled with `HILL_ALPHA_CAP` (the
        "thin tail" verdict). Use False for discrete-integer series.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 50:
        return np.full(len(FEATURE_NAMES), np.nan)

    vol = float(np.std(r))
    rc = r - r.mean()
    m2 = np.mean(rc ** 2)
    kurt = float(np.mean(rc ** 4) / (m2 ** 2) - 3.0) if m2 > 0 else 0.0
    hill = hill_tail_index(r) if compute_hill else HILL_ALPHA_CAP
    acf_ret = _autocorr(r, 1)
    acf_abs = float(np.mean([_autocorr(np.abs(r), l) for l in range(1, 6)]))
    if len(r) > 2:
        lev = _autocorr_cross(r[:-1], r[1:] ** 2)
    else:
        lev = 0.0

    return np.array([vol, kurt, hill, acf_ret, acf_abs, lev], dtype=float)


def standardize(fps: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Z-score each feature across a population of fingerprints.

    Inverse-variance weighting from the stylized-facts-distance literature:
    after standardising, Euclidean distance weights each feature by 1/variance
    so no single stylized fact dominates the geometry.
    """
    fps = np.asarray(fps, dtype=float)
    mu = np.nanmean(fps, axis=0)
    sd = np.nanstd(fps, axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (fps - mu) / sd, mu, sd


def distance_matrix(fps_std: np.ndarray) -> np.ndarray:
    """Pairwise Euclidean distances in standardized fingerprint space."""
    diff = fps_std[:, None, :] - fps_std[None, :, :]
    return np.sqrt(np.nansum(diff ** 2, axis=-1))
