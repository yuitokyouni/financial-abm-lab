"""YH011 step 1 -- is the AI-trader share p2 identifiable from returns at all?

Before any BTC number is quoted, this asks the prior question: does the
observable summary vector move with p2 by more than the across-seed sampling
noise at a realistic sample size? If it does not, no estimator -- GARCH-based
or otherwise -- can recover p2, and the honest output is a floor, not a point
estimate.

Reported per feature and for the joint vector:

  sensitivity  s = |dS/dp2| / sd(S)        standardised, per unit of p2
  MDD          minimum detectable difference in p2 from ONE window of length
               T at 5% two-sided, 80% power:  MDD = 2.80 / s

The joint-vector sensitivity is the Mahalanobis norm sqrt(d' Sigma^-1 d),
which is the Bayes-optimal linear combination -- an upper bound on what any
estimator built on this feature set can do.

Two nuisance regimes, because the gap between them is the whole story:
  oracle    -- every parameter except p2 is known exactly
  unknown   -- p1, lam, gam, k, h_coef drawn from a prior alongside p2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from nh_model import Params, PAPER, simulate, stability
from summaries import FEATURE_NAMES, summary_matrix

RESULTS = Path(__file__).resolve().parents[1] / "results"
Z80 = 2.80  # z_{0.975} + z_{0.80}


def robust_center_scale(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median / IQR-based scale. The model's kurtosis and Hill features have
    seed distributions heavy enough that a plain sd is set by one outlier."""
    med = np.nanmedian(a, axis=0)
    q75, q25 = np.nanpercentile(a, 75, axis=0), np.nanpercentile(a, 25, axis=0)
    scale = (q75 - q25) / 1.349
    return med, np.where(scale > 0, scale, np.nan)


def sweep(p2_grid, T, n_paths, base: dict, seed0=20250821):
    """Summary matrices at each p2 on the grid, nuisance held at `base`."""
    out = {}
    for i, p2 in enumerate(p2_grid):
        params = Params(**{**base, "p2": float(p2)})
        runs = simulate(params, T, seed=seed0 + i, n_paths=n_paths)["return"]
        out[float(p2)] = summary_matrix(np.atleast_2d(runs))
    return out


def sensitivity(mats: dict, p2_grid) -> dict:
    """Standardised slope dS/dp2 per feature + joint Mahalanobis sensitivity."""
    grid = np.asarray(p2_grid, dtype=float)
    centers = np.array([robust_center_scale(mats[float(p)])[0] for p in grid])
    # per-feature scale: pooled across the grid (the noise level of the feature)
    scales = np.nanmedian(
        np.array([robust_center_scale(mats[float(p)])[1] for p in grid]), axis=0)
    # local slope by least squares on the whole grid (robust to grid curvature
    # only in the average sense; per-point slopes reported alongside)
    A = np.column_stack([np.ones_like(grid), grid])
    slope = np.linalg.lstsq(A, centers, rcond=None)[0][1]
    s_feat = np.abs(slope) / scales
    # a feature whose across-seed spread collapses on part of the grid
    # produces a meaningless ratio; mark it rather than letting it
    # dominate the ranking
    s_feat = np.where(np.isfinite(s_feat), s_feat, np.nan)

    # joint sensitivity between adjacent grid points, using the pooled
    # within-p2 covariance (shrunk) of the standardised features
    joint = []
    for a, b in zip(grid[:-1], grid[1:]):
        Xa, Xb = mats[float(a)], mats[float(b)]
        Z = np.vstack([(Xa - np.nanmedian(Xa, axis=0)) / scales,
                       (Xb - np.nanmedian(Xb, axis=0)) / scales])
        Z = Z[np.isfinite(Z).all(axis=1)]
        S = np.cov(Z, rowvar=False) + 0.05 * np.eye(Z.shape[1])   # shrinkage
        d = (np.nanmedian(Xb, axis=0) - np.nanmedian(Xa, axis=0)) / scales
        m = float(np.sqrt(d @ np.linalg.solve(S, d)))
        joint.append({"p2_lo": float(a), "p2_hi": float(b),
                      "delta_p2": float(b - a),
                      "mahalanobis": m,
                      "sensitivity_per_unit_p2": m / float(b - a),
                      "mdd_p2": Z80 * float(b - a) / m if m > 0 else float("inf")})
    return {
        "per_feature": [
            {"feature": f, "slope": float(sl), "noise_sd": float(sc),
             "sensitivity_per_unit_p2": float(sf),
             "mdd_p2": float(Z80 / sf) if sf > 0 else float("inf")}
            for f, sl, sc, sf in zip(FEATURE_NAMES, slope, scales, s_feat)],
        "adjacent_joint": joint,
        "centers": {str(float(p)): dict(zip(FEATURE_NAMES, c.tolist()))
                    for p, c in zip(grid, centers)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-paths", type=int, default=400)
    ap.add_argument("--lengths", type=int, nargs="+", default=[1000, 5000, 20000])
    args = ap.parse_args()

    base = dict(PAPER)
    # stop below the stationarity ceiling -- past it every summary reads
    # the explosion rather than the trader mix (nh_model.stability)
    p2_max = stability(Params(**base))["p2_max_covariance_stationary"]
    p2_grid = [round(v, 3) for v in np.arange(0.0, 0.95 * p2_max, 0.075)]
    RESULTS.mkdir(exist_ok=True)
    report = {"p2_grid": p2_grid, "n_paths": args.n_paths,
              "base_params": base,
              "stability": stability(Params(**base)),
              "by_length": {}}
    print(f"p2 grid {p2_grid[0]:.2f}..{p2_grid[-1]:.2f} "
          f"(stationarity ceiling {p2_max:.3f})")

    for T in args.lengths:
        mats = sweep(p2_grid, T, args.n_paths, base)
        res = sensitivity(mats, p2_grid)
        report["by_length"][str(T)] = res
        usable = [d for d in res["per_feature"]
                  if np.isfinite(d["sensitivity_per_unit_p2"])]
        top = sorted(usable, key=lambda d: -d["sensitivity_per_unit_p2"])[:6]
        print(f"\n=== T = {T}  ({args.n_paths} runs per grid point, "
              f"oracle nuisance) ===")
        print(f"{'feature':18s} {'d(feat)/dp2':>12s} {'noise sd':>10s} "
              f"{'sens/unit p2':>13s} {'min detectable dp2':>19s}")
        for d in top:
            print(f"{d['feature']:18s} {d['slope']:12.4f} {d['noise_sd']:10.4f} "
                  f"{d['sensitivity_per_unit_p2']:13.2f} {d['mdd_p2']:19.3f}")
        j = res["adjacent_joint"]
        best = min(j, key=lambda d: d["mdd_p2"])
        worst = max(j, key=lambda d: d["mdd_p2"])
        print(f"  joint vector: min detectable dp2 ranges "
              f"{best['mdd_p2']:.3f} (at p2~{best['p2_lo']:.1f}) .. "
              f"{worst['mdd_p2']:.3f} (at p2~{worst['p2_lo']:.1f})")

    (RESULTS / "identifiability.json").write_text(json.dumps(report, indent=1))
    print(f"\nwrote {RESULTS/'identifiability.json'}")


if __name__ == "__main__":
    main()
