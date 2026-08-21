"""Summary-statistic vector for the AI-trader-share inverse problem.

Two blocks, both computed from returns alone:

* ``SIEVE_METRICS`` -- sieve's prespecified stylized-fact battery, resolved
  through ``sieve.metrics.registry`` so the ids, versions and *declared blind
  spots* travel with the numbers. Every one of them is declared
  ``scale_invariant=True``, which is exactly what this problem needs: the
  model is scale-equivariant under (rho*k, lam, gam) -> (c*rho*k, lam/c,
  gam/c), so any statistic that moves with the return scale would be reading
  the arbitrary units of rho*k rather than the trader mix.

* ``shape_features`` -- a few extra scale-free shape statistics of the |r|
  dynamics, added because the model's volatility recursion is linear in
  ``|u|`` rather than ``u^2`` (see specs/YH011_identification.md) and sieve's
  battery is squared-return oriented.

`GARCH_AUX` is deliberately *not* in either block: it is the auxiliary model
of the indirect-inference baseline, kept separate so the GARCH-free estimator
can be scored without it.
"""

from __future__ import annotations

import numpy as np

from sieve.metrics.registry import all_specs, compute

# sieve's prespecified battery, minus `drift`: the model's conditional mean is
# mechanically tied to its conditional sd (sigma_t = k|rho + f_t|), so drift is
# informative here -- but it is the one metric that is NOT scale-free in the
# units sense we need, so it is carried separately and reported, not fitted.
SIEVE_METRICS = [s.metric_id for s in all_specs() if s.metric_id != "drift"]
BLIND_SPOTS = {s.metric_id: s.known_blind_spots for s in all_specs()}


def shape_features(r: np.ndarray) -> dict[str, float]:
    """Scale-free features of the |r| process (absolute-value volatility)."""
    a = np.abs(r - r.mean())
    out: dict[str, float] = {}
    # coefficient of variation of |r| -- the natural scale-free amplitude of
    # an absolute-value volatility recursion
    out["cv_abs"] = float(a.std() / a.mean()) if a.mean() > 0 else float("nan")
    # ACF of |r| (not r^2): matches the model's own recursion order
    ac = a - a.mean()
    den = float((ac ** 2).sum())
    for lag in (1, 5, 20):
        out[f"acf_absr_{lag}"] = (
            float((ac[:-lag] * ac[lag:]).sum() / den) if den > 0 else float("nan"))
    # quantile-based tail and asymmetry: bounded, so they survive the model's
    # very heavy tails without a single outlier dominating the summary
    q = np.percentile(r, [1, 5, 25, 50, 75, 95, 99])
    iqr = q[3 + 1] - q[2]
    if iqr > 0:
        out["q_tail_ratio"] = float((q[5] - q[1]) / iqr)      # 95-5 over IQR
        out["q_xtail_ratio"] = float((q[6] - q[0]) / iqr)     # 99-1 over IQR
        out["q_skew"] = float((q[5] + q[1] - 2 * q[3]) / (q[5] - q[1]))
    else:
        out |= {"q_tail_ratio": np.nan, "q_xtail_ratio": np.nan, "q_skew": np.nan}
    return out


def summary_vector(r: np.ndarray) -> dict[str, float]:
    """Full GARCH-free summary vector for one run of returns."""
    out = {m: compute(m, r) for m in SIEVE_METRICS}
    out |= shape_features(r)
    return out


FEATURE_NAMES = SIEVE_METRICS + [
    "cv_abs", "acf_absr_1", "acf_absr_5", "acf_absr_20",
    "q_tail_ratio", "q_xtail_ratio", "q_skew"]


def summary_matrix(runs: np.ndarray) -> np.ndarray:
    """(n_runs, n_steps) returns -> (n_runs, n_features) summary matrix."""
    return np.array([[summary_vector(r)[k] for k in FEATURE_NAMES] for r in runs])


def garch_aux(r: np.ndarray) -> dict[str, float]:
    """Auxiliary GARCH(1,1) QMLE fit -- the indirect-inference baseline only."""
    import warnings
    from arch import arch_model
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = arch_model(r, mean="Constant", vol="GARCH", p=1, q=1,
                         rescale=False).fit(disp="off", show_warning=False)
    return {"omega": float(res.params["omega"]),
            "alpha": float(res.params["alpha[1]"]),
            "beta": float(res.params["beta[1]"])}
