"""Fact estimators — versioned functions applied identically to real and simulated data.

Each estimator takes a 1-D returns array and produces a FactResult.
The same code path is used for both empirical and model-generated data
(§3.3: same-module contract).
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import numpy.typing as npt
from scipy import optimize, stats

from prism.types import FactResult

ESTIMATOR_VERSION = "0.2.0"

FactEstimatorFn = Callable[[npt.NDArray[np.float64]], FactResult]


def volatility_clustering(returns: npt.NDArray[np.float64]) -> FactResult:
    """GARCH(1,1) persistence parameter (alpha + beta).

    Fits a GARCH(1,1) model: sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2
    and returns alpha + beta as the persistence measure.  Values close to 1
    indicate strong volatility clustering.

    Uses quasi-maximum-likelihood with Gaussian innovations.
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="volatility_clustering",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    r = r - r.mean()
    variance = np.var(r)

    def neg_log_likelihood(params: npt.NDArray[np.float64]) -> float:
        omega, alpha, beta = params
        T = len(r)
        sigma2 = np.empty(T)
        sigma2[0] = variance
        for t in range(1, T):
            sigma2[t] = omega + alpha * r[t - 1] ** 2 + beta * sigma2[t - 1]
            if sigma2[t] < 1e-12:
                sigma2[t] = 1e-12
        ll = -0.5 * np.sum(np.log(sigma2) + r**2 / sigma2)
        return float(-ll)

    bounds = [(1e-10, 10 * variance), (1e-6, 0.7), (0.01, 0.9999)]
    constraints = {"type": "ineq", "fun": lambda p: 0.9999 - p[1] - p[2]}

    starting_points = [
        np.array([variance * 0.05, 0.05, 0.90]),
        np.array([variance * 0.10, 0.10, 0.85]),
        np.array([variance * 0.02, 0.03, 0.94]),
        np.array([variance * 0.20, 0.15, 0.70]),
        np.array([variance * 0.30, 0.25, 0.50]),
        np.array([variance * 0.50, 0.40, 0.30]),
    ]

    best_nll = np.inf
    best_params = starting_points[0]
    best_converged = False

    try:
        for x0 in starting_points:
            result = optimize.minimize(
                neg_log_likelihood,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000, "ftol": 1e-12},
            )
            if result.fun < best_nll:
                best_nll = result.fun
                best_params = result.x
                best_converged = result.success

        _, alpha_hat, beta_hat = best_params
        persistence = float(alpha_hat + beta_hat)
        meta: dict[str, object] = {
            "converged": best_converged,
            "omega": float(best_params[0]),
            "alpha": float(alpha_hat),
            "beta": float(beta_hat),
        }
    except Exception as e:
        persistence = float(np.nan)
        meta = {"error": str(e)}

    return FactResult(
        fact_id="volatility_clustering",
        value=persistence,
        estimator_version=ESTIMATOR_VERSION,
        metadata=meta,
    )


def leverage_effect(returns: npt.NDArray[np.float64]) -> FactResult:
    """Leverage effect: correlation between returns and future squared returns.

    Computes Corr(r_t, r_{t+1}^2) — a negative value indicates that negative
    returns are followed by higher volatility (the classic leverage/asymmetry
    effect).  Bootstrap CI is provided when sufficient data is available.
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="leverage_effect",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    r_t = r[:-1]
    r_t1_sq = r[1:] ** 2
    corr = float(np.corrcoef(r_t, r_t1_sq)[0, 1])

    ci95 = _bootstrap_ci(r, _leverage_corr_statistic, n_boot=1000)

    return FactResult(
        fact_id="leverage_effect",
        value=corr,
        ci95=ci95,
        estimator_version=ESTIMATOR_VERSION,
        metadata={"n": len(r), "lag": 1},
    )


def _leverage_corr_statistic(r: npt.NDArray[np.float64]) -> float:
    return float(np.corrcoef(r[:-1], r[1:] ** 2)[0, 1])


def gain_loss_asymmetry(returns: npt.NDArray[np.float64]) -> FactResult:
    """Gain/loss asymmetry via adjusted Fisher-Pearson skewness.

    Negative skewness indicates heavier left tail (losses are more extreme
    than gains).  Uses scipy.stats.skew with bias=False for the adjusted
    estimator.
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="gain_loss_asymmetry",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    skew_val = float(stats.skew(r, bias=False))

    ci95 = _bootstrap_ci(r, lambda x: float(stats.skew(x, bias=False)), n_boot=1000)

    return FactResult(
        fact_id="gain_loss_asymmetry",
        value=skew_val,
        ci95=ci95,
        estimator_version=ESTIMATOR_VERSION,
        metadata={"n": len(r)},
    )


def abs_autocorrelation(returns: npt.NDArray[np.float64]) -> FactResult:
    """Autocorrelation of absolute returns at lag 1.

    Financial returns are approximately uncorrelated, but their absolute
    values exhibit significant positive autocorrelation that decays
    slowly (long memory in volatility).  This is distinct from
    volatility_clustering (GARCH persistence) — it measures serial
    dependence directly.

    Typical lag-1 values for daily equity: 0.05–0.4 (Cont 2001).
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="abs_autocorrelation",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    abs_r = np.abs(r)
    abs_r = abs_r - abs_r.mean()
    var = np.sum(abs_r**2)
    if var < 1e-15:
        acf1 = 0.0
    else:
        acf1 = float(np.sum(abs_r[:-1] * abs_r[1:]) / var)

    ci95 = _bootstrap_ci(r, _abs_acf1_statistic, n_boot=1000)

    return FactResult(
        fact_id="abs_autocorrelation",
        value=acf1,
        ci95=ci95,
        estimator_version=ESTIMATOR_VERSION,
        metadata={"n": len(r), "lag": 1},
    )


def _abs_acf1_statistic(r: npt.NDArray[np.float64]) -> float:
    abs_r = np.abs(r) - np.abs(r).mean()
    var = np.sum(abs_r**2)
    if var < 1e-15:
        return 0.0
    return float(np.sum(abs_r[:-1] * abs_r[1:]) / var)


def squared_return_acf(returns: npt.NDArray[np.float64]) -> FactResult:
    """Lag-1 autocorrelation of squared returns.

    A simpler, optimization-free measure of volatility clustering that is
    more sensitive to regime changes than GARCH(1,1) persistence.
    Positive values indicate that large (small) squared returns tend to
    follow large (small) squared returns.

    Typical daily equity values: 0.05–0.40 (Cont 2001).
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="squared_return_acf",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    r2 = r**2
    r2 = r2 - r2.mean()
    var = np.sum(r2**2)
    if var < 1e-15:
        acf1 = 0.0
    else:
        acf1 = float(np.sum(r2[:-1] * r2[1:]) / var)

    ci95 = _bootstrap_ci(r, _sq_acf1_statistic, n_boot=1000)

    return FactResult(
        fact_id="squared_return_acf",
        value=acf1,
        ci95=ci95,
        estimator_version=ESTIMATOR_VERSION,
        metadata={"n": len(r), "lag": 1},
    )


def _sq_acf1_statistic(r: npt.NDArray[np.float64]) -> float:
    r2 = r**2
    r2 = r2 - r2.mean()
    var = np.sum(r2**2)
    if var < 1e-15:
        return 0.0
    return float(np.sum(r2[:-1] * r2[1:]) / var)


def fat_tails(returns: npt.NDArray[np.float64]) -> FactResult:
    """Fat tails via excess kurtosis (Fisher's definition).

    Financial returns are leptokurtic: the distribution has heavier tails
    than a Gaussian.  Excess kurtosis > 0 indicates fat tails;  typical
    values for daily equity returns are 3-50 (Cont 2001).

    Uses scipy.stats.kurtosis with Fisher=True (excess kurtosis = kurt - 3).
    """
    r = np.asarray(returns, dtype=np.float64).ravel()
    if len(r) < 30:
        return FactResult(
            fact_id="fat_tails",
            value=np.nan,
            estimator_version=ESTIMATOR_VERSION,
            metadata={"error": "insufficient data", "n": len(r)},
        )

    kurt_val = float(stats.kurtosis(r, fisher=True, bias=False))

    ci95 = _bootstrap_ci(
        r, lambda x: float(stats.kurtosis(x, fisher=True, bias=False)), n_boot=1000
    )

    return FactResult(
        fact_id="fat_tails",
        value=kurt_val,
        ci95=ci95,
        estimator_version=ESTIMATOR_VERSION,
        metadata={"n": len(r)},
    )


def _bootstrap_ci(
    data: npt.NDArray[np.float64],
    stat_fn: Callable[[npt.NDArray[np.float64]], float],
    n_boot: int = 1000,
    alpha: float = 0.05,
    rng_seed: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(rng_seed)
    n = len(data)
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        sample = data[rng.integers(0, n, size=n)]
        boot_stats[i] = stat_fn(sample)
    lo = float(np.percentile(boot_stats, 100 * alpha / 2))
    hi = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))
    return (lo, hi)


def compute_fact(fact_id: str, returns: npt.NDArray[np.float64]) -> FactResult:
    if fact_id not in FACT_REGISTRY:
        raise ValueError(f"Unknown fact_id: {fact_id}. Available: {list(FACT_REGISTRY.keys())}")
    return FACT_REGISTRY[fact_id](returns)


def compute_facts(fact_ids: list[str], returns: npt.NDArray[np.float64]) -> dict[str, FactResult]:
    return {fid: compute_fact(fid, returns) for fid in fact_ids}


FACT_REGISTRY: dict[str, FactEstimatorFn] = {
    "volatility_clustering": volatility_clustering,
    "leverage_effect": leverage_effect,
    "gain_loss_asymmetry": gain_loss_asymmetry,
    "fat_tails": fat_tails,
    "abs_autocorrelation": abs_autocorrelation,
    "squared_return_acf": squared_return_acf,
}
