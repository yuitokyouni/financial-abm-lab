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
    "acf_absret_mean",          # short-range vol persistence (lag 1-5)
    "leverage",
    # v4: Cont-outside axes designed to break the GARCH(1,1) blind spot.
    # GARCH(1,1) clusters but decays exponentially; LM/SG cluster with
    # heavier long memory. These three should pull them apart.
    "acf_absret_long",          # mean |r| ACF over lag 20-50 (long memory)
    "acf_absret_decay",         # log-linear decay rate of |r| ACF lag 1-20
    "agg_kurt_decay",           # 1 - kurt(window=20) / kurt(window=1) ∈ ~[-2, +1]
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


def hill_tail_index_raw(returns: np.ndarray, tail_frac: float = 0.05) -> float:
    """Hill estimator α — uncapped. Useful as a diagnostic alongside the
    capped variant used inside `fingerprint()`. A raw α >> HILL_ALPHA_CAP
    is the honest signal "this series is essentially thin-tailed".
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
    return float(1.0 / mean_log_ratio)


def hill_tail_index(returns: np.ndarray, tail_frac: float = 0.05) -> float:
    """Capped Hill estimator α for use *in the fingerprint vector*.

    Without the cap a near-Gaussian / degenerate series produces α in the
    hundreds, which then dominates inverse-variance weighting and collapses
    the geometry. Cap at `HILL_ALPHA_CAP` keeps the vector well-behaved;
    callers wanting the uncapped reading should use `hill_tail_index_raw`.
    """
    raw = hill_tail_index_raw(returns, tail_frac=tail_frac)
    if not np.isfinite(raw):
        return raw
    return float(min(raw, HILL_ALPHA_CAP))


def _acf_decay_slope(absr: np.ndarray, lags=range(1, 21)) -> float:
    """Log-linear regression slope of |r| ACF vs lag (lags 1..20).

    Negative slope = decay; the *magnitude* of the slope distinguishes
    fast-decaying (exponential, e.g. GARCH(1,1)) from slow-decaying
    (power-law, long memory) clustering. Returns the slope of log|ACF| vs lag
    so values are negative-or-zero; magnitude near 0 means heavy long memory.
    """
    acfs = [max(1e-6, abs(_autocorr(absr, lag))) for lag in lags]
    lag_arr = np.array(list(lags), dtype=float)
    log_acf = np.log(np.asarray(acfs, dtype=float))
    # OLS slope of log_acf vs lag
    x = lag_arr - lag_arr.mean()
    y = log_acf - log_acf.mean()
    denom = float(x @ x)
    if denom <= 0:
        return 0.0
    return float((x @ y) / denom)


def _kurt_excess(x: np.ndarray) -> float:
    xc = x - x.mean()
    m2 = float(np.mean(xc ** 2))
    if m2 <= 0:
        return 0.0
    return float(np.mean(xc ** 4) / (m2 ** 2) - 3.0)


def _aggregational_kurt_decay(r: np.ndarray, window: int = 20) -> float:
    """1 − kurt(sum over window) / kurt(raw).

    Aggregational Gaussianity (Cont): for GARCH and most clustering ABMs, the
    sum-over-window returns approach Gaussian (excess kurt → 0). For α-stable
    Lévy, kurtosis is theoretically undefined / unchanged. So this number
    distinguishes "tails come from clustering" (→ +1) from "tails are
    structural" (→ ~0 or negative).
    """
    r = r[np.isfinite(r)]
    if len(r) < 4 * window:
        return float("nan")
    raw_k = _kurt_excess(r)
    if not np.isfinite(raw_k) or raw_k == 0:
        return float("nan")
    n_blocks = len(r) // window
    blocks = r[:n_blocks * window].reshape(n_blocks, window).sum(axis=1)
    agg_k = _kurt_excess(blocks)
    return float(1.0 - agg_k / raw_k)


def fingerprint(returns: np.ndarray, *, compute_hill: bool = True) -> np.ndarray:
    """Raw (unstandardized) stylized-facts fingerprint of a return series.

    Length = `len(FEATURE_NAMES)`. v4 adds three Cont-outside axes
    (acf_absret_long, acf_absret_decay, agg_kurt_decay) designed to break
    the GARCH(1,1) ↔ ABM blind spot identified in v3.
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
    absr = np.abs(r)
    acf_abs_short = float(np.mean([_autocorr(absr, l) for l in range(1, 6)]))
    if len(r) > 2:
        lev = _autocorr_cross(r[:-1], r[1:] ** 2)
    else:
        lev = 0.0
    # v4 additions
    if len(absr) > 50:
        acf_abs_long = float(np.mean([_autocorr(absr, l) for l in range(20, 51)]))
        acf_decay = _acf_decay_slope(absr)
    else:
        acf_abs_long = float("nan")
        acf_decay = float("nan")
    agg_kd = _aggregational_kurt_decay(r, window=20)

    return np.array([vol, kurt, hill, acf_ret, acf_abs_short, lev,
                     acf_abs_long, acf_decay, agg_kd], dtype=float)


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
