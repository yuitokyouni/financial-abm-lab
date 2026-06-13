"""Bootstrap / Mann-Whitney U の骨格実装.

S1 (tentative) では使わない。S3+ (100 trial ensemble) で trial-level の値配列に
対して呼ばれる。Brief §5.1 / §5.2 のレシピを忠実に実装。
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from scipy import stats


def bootstrap_ci(
    values: np.ndarray,
    n_resample: int = 10_000,
    ci: float = 0.95,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[float, float, float]:
    """Percentile bootstrap CI for mean(values). Returns (mean, lo, hi)."""
    if rng is None:
        rng = np.random.default_rng(0)
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    boot = rng.choice(arr, size=(n_resample, arr.size), replace=True).mean(axis=1)
    alpha = (1.0 - ci) / 2.0
    lo, hi = np.quantile(boot, [alpha, 1.0 - alpha])
    return float(arr.mean()), float(lo), float(hi)


def bootstrap_interaction_ci(
    rho_C3: np.ndarray,
    rho_C2: np.ndarray,
    rho_C0p: np.ndarray,
    rho_C0u: np.ndarray,
    n_resample: int = 10_000,
    ci: float = 0.95,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[float, float, float]:
    """Bootstrap CI for interaction = [mean(C3) − mean(C2)] − [mean(C0p) − mean(C0u)].

    各条件で trial-level の ρ array (長さ = n_trials) を渡す。
    各 resample で 4 条件独立に resample → mean diff を計算。
    """
    if rng is None:
        rng = np.random.default_rng(0)
    rho_C3 = np.asarray(rho_C3, dtype=np.float64)
    rho_C2 = np.asarray(rho_C2, dtype=np.float64)
    rho_C0p = np.asarray(rho_C0p, dtype=np.float64)
    rho_C0u = np.asarray(rho_C0u, dtype=np.float64)
    boots = np.empty(n_resample, dtype=np.float64)
    for i in range(n_resample):
        b_C3 = rng.choice(rho_C3, size=rho_C3.size, replace=True).mean()
        b_C2 = rng.choice(rho_C2, size=rho_C2.size, replace=True).mean()
        b_C0p = rng.choice(rho_C0p, size=rho_C0p.size, replace=True).mean()
        b_C0u = rng.choice(rho_C0u, size=rho_C0u.size, replace=True).mean()
        boots[i] = (b_C3 - b_C2) - (b_C0p - b_C0u)
    alpha = (1.0 - ci) / 2.0
    lo, hi = np.quantile(boots, [alpha, 1.0 - alpha])
    return float(boots.mean()), float(lo), float(hi)


def mannwhitney_u(a: np.ndarray, b: np.ndarray) -> Tuple[float, float]:
    """Two-sided Mann-Whitney U test. Returns (statistic, p_value)."""
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    return float(res.statistic), float(res.pvalue)
