"""First-pass calibration of the unwind-tape ABM (research YH009).

Fits the ABM's information channels to the empirical *no-buyback* group moments
(n=10, cost convention: + = loss to the seller), matching **moments** (level +
dispersion), not paths. The vertical scale is arbitrary units.

WHAT IS CALIBRATED (and what is NOT)
------------------------------------
Only **s1** and **s2** (plus realised **sigma**) are ABM-calibrated here.
**s3 (the execution discount) is EXOGENOUS** -- it is the underwriter / placement
haircut (empirical median ~ -3.1%, size-independent), *not* an emergent ABM
quantity. NOTHING in this file scales s3 to a target; s3 stays whatever the
execution book-walk emergently produces. See config.py's NOTE on s3.

Knobs -> targets (each ~1:1 with its target; coordinate descent):
    announce_fundamental_drop  -> s1_median   (requires announce_impact_flow=True)
    frontrun_fraction          -> s2_std
    fcn_noise_sigma            -> sigma

Runs are done with ``announce_info=True`` (all real events are announced, so s1
and s2 both fire) over the empirical Q/V (sold-shares / ADV) distribution, with
buyback_ratio=0 and mkt_drift=0 (the no-buyback, no-backdrop cell).

HONEST FIRST-PASS LIMITS (measured, see the printed table + README):
  * s1 is *injected*: the passive, deep warmup book cannot reprice a fundamental
    step in 300 steps (measured s1 ~ 1 tick regardless of the drop), so s1 is
    transmitted as an informed sell flow that pins the mid to the announced
    level. Matching s1_median is therefore semi-trivial by construction.
  * s2_std saturates well below target: the front-run flow is one-sided (so the
    model's s2_median is > 0 while the empirical s2_median ~ 0), and the book
    walk is concave, which *compresses* the dispersion across Q/V. This s2
    absorption dynamic -- not the s1 level -- is the real modelling problem.
  * sigma has a hard architectural floor (~1e-4): per-order returns are tick-
    anchored and every knob (agent noise, fundamental noise, book thinning) is
    absorbed by the passive LOB. Matching a ~1.5% event vol needs genuinely
    informed / aggressive agents (next stage), not a parameter tweak.

Dependencies: numpy + Python standard library only. Self-contained.

CLI:
    python -m abm.calibrate            # calibrate, write out/calibration.csv, print table
    python -m abm.calibrate --seeds 80 # override seed count for run_moments
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
from pathlib import Path

import numpy as np

from .config import baseline
from .market import Market
from . import experiments as X

OUT_DIR = Path(__file__).parent / "out"

# --- empirical no-buyback moments (cost basis, + = loss) ------------------
TARGETS = {"s1_median": 0.038, "s2_std": 0.040, "sigma": 0.015}
WEIGHTS = {"s1_median": 1.0, "s2_std": 1.0, "sigma": 1.0}

# Empirical Q/V = sold-shares / ADV distribution (multiples of ADV) the events
# are run over. Dispersion of s2 across this distribution is the s2_std target.
QV_DIST = [1.578, 2.579, 2.974, 3.569, 7.172, 9.228, 13.263, 13.623, 14.127,
           14.999, 15.740, 18.057, 20.689, 25.837, 26.646, 33.744, 39.718,
           42.309, 49.213, 103.547]

# Coordinate-descent line-search grids (each knob against its own target).
GRIDS = {
    "announce_fundamental_drop": [0.02, 0.03, 0.038, 0.05, 0.07],
    "frontrun_fraction": [4.0, 12.0, 20.0, 30.0, 45.0],
    "fcn_noise_sigma": [0.002, 0.02, 0.05, 0.1],
}
# which target each knob is responsible for (used to report the mapping)
KNOB_TARGET = {
    "announce_fundamental_drop": "s1_median",
    "frontrun_fraction": "s2_std",
    "fcn_noise_sigma": "sigma",
}


# --------------------------------------------------------------------------
def run_moments(cfg, n_seeds=80):
    """Run the announced, no-buyback event over the empirical Q/V distribution.

    Pairs seed ``i`` with ``QV_DIST[i % len(QV_DIST)]`` so the empirical Q/V
    distribution is swept (``n_seeds // len(QV_DIST)`` reps each) with a fixed,
    reproducible seed per run. Returns the moments the calibration matches plus
    a couple of context moments (s1_std, s2_median) for the report table.
    """
    m = Market(cfg)
    s1s, s2s, s3s, sigs = [], [], [], []
    nqv = len(QV_DIST)
    for i in range(n_seeds):
        qv = QV_DIST[i % nqv]
        r = m.run_event(Qover_V=qv, W=cfg.default_W, announce_info=True,
                        buyback_ratio=0.0, mkt_drift=0.0, seed=i)
        s1s.append(r["s1"]); s2s.append(r["s2"]); s3s.append(r["s3"]); sigs.append(r["sigma"])
    s1s, s2s, s3s, sigs = map(np.asarray, (s1s, s2s, s3s, sigs))
    return {
        "s1_median": float(np.median(s1s)),
        "s2_std": float(np.std(s2s)),
        "sigma": float(np.mean(sigs)),
        # context (not calibration targets):
        "s1_std": float(np.std(s1s)),
        "s2_median": float(np.median(s2s)),
        "s3_median": float(np.median(s3s)),
        "n": int(n_seeds),
    }


def loss(moments):
    """Weighted sum of squared relative errors over the calibration targets."""
    return float(sum(
        WEIGHTS[k] * ((moments[k] - t) / t) ** 2 for k, t in TARGETS.items()
    ))


def _row(pass_i, knob, value, mo, is_best=False):
    r = {"pass": pass_i, "knob": knob, "value": value,
         "loss": round(loss(mo), 6), "is_best": int(is_best)}
    for k in ("s1_median", "s1_std", "s2_median", "s2_std", "sigma", "s3_median"):
        r[k] = round(mo[k], 6)
    return r


def _component(mo, target):
    """Squared relative error of one moment against its target (0 = perfect)."""
    return ((mo[target] - TARGETS[target]) / TARGETS[target]) ** 2


def line_search(cfg, knob, candidates, n_seeds, history, pass_i):
    """1-D search of one knob against ITS OWN target component.

    Each knob is (near-)independent of the other targets, so selecting on the
    knob's own component (announce_drop->s1_median, frontrun->s2_std,
    noise->sigma) is the intended separable coordinate descent and avoids picking
    a value on another target's sampling noise. The full loss is still logged.
    Ties keep the incumbent (strict <), so an inert knob stays at its start value.
    """
    target = KNOB_TARGET[knob]
    best_val, best_mo, best_comp = getattr(cfg, knob), None, float("inf")
    evals = []
    for v in candidates:
        c = dataclasses.replace(cfg, **{knob: v})
        mo = run_moments(c, n_seeds)
        comp = _component(mo, target)
        evals.append((v, mo))
        print(f"    {knob}={v:<8} {target}={mo[target]:+.5f}  "
              f"(rel.err {comp ** 0.5 * 100:+6.1f}%)  full_loss={loss(mo):7.4f}")
        if comp < best_comp:
            best_val, best_mo, best_comp = v, mo, comp
    for v, mo in evals:
        history.append(_row(pass_i, knob, v, mo, is_best=(v == best_val)))
    return dataclasses.replace(cfg, **{knob: best_val}), best_mo, loss(best_mo)


def calibrate(n_seeds=80, passes=2, verbose=True):
    """Coordinate descent over the three knobs; returns (best_cfg, history)."""
    # start from the baseline with the s1 transmission channel switched on
    cfg = dataclasses.replace(baseline(), announce_impact_flow=True)
    history = []
    if verbose:
        m0 = run_moments(cfg, n_seeds)
        print(f"  start loss={loss(m0):.4f}  "
              f"s1_med={m0['s1_median']:+.5f} s2_std={m0['s2_std']:.5f} sigma={m0['sigma']:.5f}")
    best_mo, best_loss = None, float("inf")
    for p in range(1, passes + 1):
        if verbose:
            print(f"  --- pass {p} ---")
        for knob, grid in GRIDS.items():
            if verbose:
                print(f"  line search: {knob} -> {KNOB_TARGET[knob]}")
            cfg, best_mo, best_loss = line_search(cfg, knob, grid, n_seeds, history, p)
        if verbose:
            print(f"  pass {p} best loss={best_loss:.4f}")
    return cfg, best_mo, history


# --------------------------------------------------------------------------
def delta_sensitivity(cfg, seeds, grid=None):
    """Fit the impact exponent delta for passive vs active FCN quoting.

    Uses the exp1 size sweep (announce_info OFF, so this is the pure execution
    size effect and is independent of the s1/s2 knobs). Passive and active
    quoting bracket delta -- the empirical size effect alone does not pin it.
    """
    grid = grid or [1, 2, 5, 10, 20, 50, 100]
    out = {}
    for passive in (True, False):
        c = dataclasses.replace(cfg, fcn_passive=passive)
        _rows, summary, meta = X.exp1(seeds, grid=grid, cfg=c, verbose=False)
        out["passive" if passive else "active"] = {
            "delta": meta["delta"], "r2": meta["r2"],
            "IS_min": summary[0]["IS_mean"], "IS_max": summary[-1]["IS_mean"],
        }
    return out


# --------------------------------------------------------------------------
def _pct(x, t):
    return f"{(x / t - 1.0) * 100:+.1f}%"


def print_report(before, after, best_cfg, delta):
    tgt = TARGETS
    print("\n" + "=" * 72)
    print("CALIBRATION RESULT -- moment agreement (no-buyback group, +=loss)")
    print("=" * 72)
    print(f"{'moment':<12}{'target':>11}{'before':>12}{'after':>12}{'after/tgt-1':>14}")
    for k in ("s1_median", "s2_std", "sigma"):
        print(f"{k:<12}{tgt[k]:>+11.5f}{before[k]:>+12.5f}{after[k]:>+12.5f}"
              f"{_pct(after[k], tgt[k]):>14}")
    print(f"  loss: before={loss(before):.4f}  after={loss(after):.4f}")
    print(f"  context (not targeted): s1_std after={after['s1_std']:.5f} "
          f"(emp ref ~0.053);  s2_median after={after['s2_median']:+.5f} "
          f"(emp ref ~0.000);  s3_median after={after['s3_median']:+.5f} "
          f"(EXOGENOUS, emp ~-0.031, not fitted)")

    print("\nBest parameters (calibrated Config overrides):")
    for knob in GRIDS:
        print(f"  {knob:<28}= {getattr(best_cfg, knob)}   -> {KNOB_TARGET[knob]}")
    print(f"  {'announce_impact_flow':<28}= {best_cfg.announce_impact_flow}   "
          f"(s1 transmission channel)")

    print("\ndelta sensitivity (impact exponent IS ~ (Q/V)^delta; 0.5 = sqrt-law):")
    print(f"  passive FCN (gradual absorption): delta={delta['passive']['delta']:.3f} "
          f"R2={delta['passive']['r2']:.3f}")
    print(f"  active  FCN (aggressive re-quote): delta={delta['active']['delta']:.3f} "
          f"R2={delta['active']['r2']:.3f}")
    print(f"  => passive delta ~ {delta['passive']['delta']:.2f} / "
          f"active delta ~ {delta['active']['delta']:.2f}: the data alone does NOT "
          f"pin delta to a single value\n     (the two quoting regimes bracket it) "
          f"-- this identification gap is the honest first-pass conclusion.")
    print("=" * 72)


def _write_history(path, history):
    if not history:
        return
    keys = ["pass", "knob", "value", "s1_median", "s1_std", "s2_median",
            "s2_std", "sigma", "s3_median", "loss", "is_best"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(history)
    print(f"  wrote {path}  ({len(history)} rows)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="abm.calibrate",
                                description="First-pass ABM calibration (s1, s2, sigma)")
    p.add_argument("--seeds", type=int, default=80,
                   help="seeds per run_moments evaluation (default 80)")
    p.add_argument("--passes", type=int, default=2,
                   help="coordinate-descent passes (default 2)")
    p.add_argument("--delta-seeds", type=int, default=25,
                   help="seeds for the delta sensitivity exp1 sweeps (default 25)")
    args = p.parse_args(argv)

    print(f"[calibrate] seeds={args.seeds} passes={args.passes}  "
          f"(targets: {TARGETS})")

    # BEFORE: the untouched baseline (s1 flow OFF), announced no-buyback cell.
    before = run_moments(baseline(), args.seeds)

    best_cfg, _best_mo, history = calibrate(args.seeds, args.passes)

    # AFTER: re-measure the calibrated config at the same seed count.
    after = run_moments(best_cfg, args.seeds)

    _write_history(OUT_DIR / "calibration.csv", history)

    delta = delta_sensitivity(best_cfg, list(range(args.delta_seeds)))
    print_report(before, after, best_cfg, delta)


if __name__ == "__main__":
    main()
