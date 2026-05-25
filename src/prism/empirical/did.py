"""Difference-in-Differences estimation using PRISM's own fact estimators.

Applies the SAME estimator functions to real market data that are used on
simulated data, ensuring apple-to-apple comparison.  The DiD structure:

    delta_F = (F_treatment_post - F_treatment_pre)
            - (F_control_post   - F_control_pre)

Bootstrap CI95 is computed by resampling stock-level fact estimates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from prism.facts import compute_fact
from prism.types import FactResult, GroundTruthDelta


@dataclass(frozen=True)
class StockFactResult:
    """Fact estimate for a single stock in one period."""

    instrument_id: str
    fact_id: str
    value: float
    n_obs: int


@dataclass(frozen=True)
class EmpiricalDiDResult:
    """DiD estimate for one fact, derived from real data using PRISM estimators."""

    fact_id: str
    did_estimate: float
    ci95: tuple[float, float]
    treatment_pre_mean: float
    treatment_post_mean: float
    control_pre_mean: float
    control_post_mean: float
    n_treatment: int
    n_control: int
    treatment_stocks: list[StockFactResult] = field(default_factory=list)
    control_stocks: list[StockFactResult] = field(default_factory=list)

    def to_ground_truth_delta(
        self,
        causal_method: str = "did_firm_fe",
        causal_assumptions: list[str] | None = None,
        references: list[str] | None = None,
    ) -> GroundTruthDelta:
        if causal_assumptions is None:
            causal_assumptions = [
                "parallel_trends",
                "no_anticipation",
                "no_spillover",
            ]
        if references is None:
            references = ["empirical_prism_estimator"]
        return GroundTruthDelta(
            fact_id=self.fact_id,
            delta_hat=self.did_estimate,
            ci95=self.ci95,
            causal_method=causal_method,
            causal_assumptions=causal_assumptions,
            unit="relative",
            references=references,
        )


def _compute_stock_facts(
    returns_matrix: npt.NDArray[np.float64],
    instrument_ids: list[str],
    fact_id: str,
) -> list[StockFactResult]:
    """Compute a fact for each stock column in the returns matrix."""
    results = []
    n_instruments = returns_matrix.shape[1] if returns_matrix.ndim > 1 else 1

    for i in range(n_instruments):
        col = returns_matrix[:, i] if returns_matrix.ndim > 1 else returns_matrix.ravel()
        valid = col[~np.isnan(col)]
        if len(valid) < 30:
            continue
        fact: FactResult = compute_fact(fact_id, valid)
        if np.isnan(fact.value):
            continue
        iid = instrument_ids[i] if i < len(instrument_ids) else f"stock_{i}"
        results.append(
            StockFactResult(
                instrument_id=iid,
                fact_id=fact_id,
                value=fact.value,
                n_obs=len(valid),
            )
        )
    return results


def _bootstrap_did_ci(
    treatment_pre_vals: npt.NDArray[np.float64],
    treatment_post_vals: npt.NDArray[np.float64],
    control_pre_vals: npt.NDArray[np.float64],
    control_post_vals: npt.NDArray[np.float64],
    n_boot: int = 2000,
    alpha: float = 0.05,
    rng_seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap CI95 for the DiD estimate by resampling stock-level values."""
    rng = np.random.default_rng(rng_seed)
    boot_dids = np.empty(n_boot)

    n_treat = len(treatment_pre_vals)
    n_ctrl = len(control_pre_vals)

    for b in range(n_boot):
        t_idx = rng.integers(0, n_treat, size=n_treat)
        c_idx = rng.integers(0, n_ctrl, size=n_ctrl)

        t_diff = np.mean(treatment_post_vals[t_idx]) - np.mean(treatment_pre_vals[t_idx])
        c_diff = np.mean(control_post_vals[c_idx]) - np.mean(control_pre_vals[c_idx])
        boot_dids[b] = t_diff - c_diff

    lo = float(np.percentile(boot_dids, 100 * alpha / 2))
    hi = float(np.percentile(boot_dids, 100 * (1 - alpha / 2)))
    return (lo, hi)


def did_facts(
    treatment_pre: npt.NDArray[np.float64],
    treatment_post: npt.NDArray[np.float64],
    control_pre: npt.NDArray[np.float64],
    control_post: npt.NDArray[np.float64],
    fact_ids: list[str],
    treatment_ids: list[str] | None = None,
    control_ids: list[str] | None = None,
    n_boot: int = 2000,
) -> list[EmpiricalDiDResult]:
    """Compute DiD estimates for each fact using PRISM's own estimators.

    Args:
        treatment_pre: Returns matrix (T, N_treat) for treatment group pre-intervention.
        treatment_post: Returns matrix (T, N_treat) for treatment group post-intervention.
        control_pre: Returns matrix (T, N_ctrl) for control group pre-intervention.
        control_post: Returns matrix (T, N_ctrl) for control group post-intervention.
        fact_ids: Which PRISM facts to estimate.
        treatment_ids: Instrument IDs for treatment stocks.
        control_ids: Instrument IDs for control stocks.
        n_boot: Number of bootstrap resamples for CI.

    Returns:
        List of EmpiricalDiDResult, one per fact_id.
    """
    n_treat = treatment_pre.shape[1] if treatment_pre.ndim > 1 else 1
    n_ctrl = control_pre.shape[1] if control_pre.ndim > 1 else 1

    if treatment_ids is None:
        treatment_ids = [f"treat_{i}" for i in range(n_treat)]
    if control_ids is None:
        control_ids = [f"ctrl_{i}" for i in range(n_ctrl)]

    results: list[EmpiricalDiDResult] = []

    for fact_id in fact_ids:
        tp_facts = _compute_stock_facts(treatment_pre, treatment_ids, fact_id)
        tq_facts = _compute_stock_facts(treatment_post, treatment_ids, fact_id)
        cp_facts = _compute_stock_facts(control_pre, control_ids, fact_id)
        cq_facts = _compute_stock_facts(control_post, control_ids, fact_id)

        if not (tp_facts and tq_facts and cp_facts and cq_facts):
            continue

        tp_vals = np.array([f.value for f in tp_facts])
        tq_vals = np.array([f.value for f in tq_facts])
        cp_vals = np.array([f.value for f in cp_facts])
        cq_vals = np.array([f.value for f in cq_facts])

        tp_mean = float(np.mean(tp_vals))
        tq_mean = float(np.mean(tq_vals))
        cp_mean = float(np.mean(cp_vals))
        cq_mean = float(np.mean(cq_vals))

        did = (tq_mean - tp_mean) - (cq_mean - cp_mean)

        ci95 = _bootstrap_did_ci(tp_vals, tq_vals, cp_vals, cq_vals, n_boot=n_boot)

        results.append(
            EmpiricalDiDResult(
                fact_id=fact_id,
                did_estimate=did,
                ci95=ci95,
                treatment_pre_mean=tp_mean,
                treatment_post_mean=tq_mean,
                control_pre_mean=cp_mean,
                control_post_mean=cq_mean,
                n_treatment=len(tp_facts),
                n_control=len(cp_facts),
                treatment_stocks=tp_facts + tq_facts,
                control_stocks=cp_facts + cq_facts,
            )
        )

    return results
