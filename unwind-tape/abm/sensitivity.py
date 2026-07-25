"""V <-> real ADV anchoring + scale sensitivity (research YH009, calibration D).

WHY THIS EXISTS
---------------
The empirical study measures **Q/ADV** per leg (sold shares / 20-day ADV). The
ABM consumes *exactly that ratio* as ``Qover_V``: ``Q = Qover_V * V``. So V is
**anchored to real ADV by construction** -- and, because every readout (s1, s2,
s3, sigma) is a log-price *ratio*, the absolute value of V (sim shares) cancels
out. Feeding the empirical Q/ADV distribution (``calibrate.QV_DIST``) is what
makes the model's size axis the same axis as the data's.

    interpretation: one *execution window* (W * exec_inter_steps sim-steps) is the
    ADV-averaging period, so Qover_V = Q/ADV and the model's impact-vs-size curve
    is directly comparable to the empirical implied_Y_s2 / sqrt-law test.

WHAT IS *NOT* ANCHORED, AND SO MUST BE STRESS-TESTED
----------------------------------------------------
The sim's internal **scale** is not observed: how many steps make a window (W,
``exec_inter_steps``), the tick grid (``tick_size``), and the seed-book depth.
If the size effect (delta) or the calibration moments (s1/s2/sigma) moved a lot
when these arbitrary choices change, the ABM's conclusions would be an artifact
of the scale rather than of the mechanism. This module sweeps each and reports
the movement, so we can state which conclusions are robust and which are not.

CLI:
    python -m abm.sensitivity              # sweep W, exec_inter_steps, tick, depth
    python -m abm.sensitivity --knob W --moment-seeds 40 --delta-seeds 20
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
from pathlib import Path

from .config import baseline
from .calibrate import run_moments, TARGETS
from . import experiments as X

OUT_DIR = Path(__file__).parent / "out"

# Scale knobs that are NOT pinned by data, and the grids we stress them over.
# The middle value of each grid is (near) the baseline, so the report reads as a
# perturbation around the default configuration.
SWEEPS = {
    "default_W": [30, 60, 120],          # execution window length (slices)
    "exec_inter_steps": [2, 4, 8],       # base steps between execution slices
    "tick_size": [0.02, 0.05, 0.10],     # price-grid resolution
    "seed_depth": [3, 6, 12],            # starter-book depth (scaffolding)
}

DELTA_GRID = [1, 2, 5, 10, 20, 50, 100]


def probe(cfg, n_moment=30, n_delta=15):
    """Measure the four scale-sensitive summaries for one configuration.

    Returns the announced no-buyback moments (s1_median, s2_std, sigma) plus the
    unannounced size-effect exponent (delta, r2). Same seeds each call, so the
    comparison across a sweep isolates the knob, not sampling noise.
    """
    mo = run_moments(cfg, n_moment)
    _r, _s, meta = X.exp1(list(range(n_delta)), grid=DELTA_GRID, cfg=cfg, verbose=False)
    return {
        "s1_median": mo["s1_median"],
        "s2_std": mo["s2_std"],
        "sigma": mo["sigma"],
        "delta": meta["delta"],
        "r2": meta["r2"],
    }


def _span(vals):
    """Peak-to-peak spread of a metric across a sweep, relative to its mean.

    A small relative span => the conclusion is robust to that (arbitrary) scale
    knob; a large span => it is scale-driven and must be reported as such.
    """
    lo, hi = min(vals), max(vals)
    mean = sum(vals) / len(vals) if vals else float("nan")
    return (hi - lo), (abs((hi - lo) / mean) if mean else float("nan"))


def sweep_knob(knob, values, n_moment, n_delta, history):
    """Run ``probe`` across one knob's grid; print a table and collect rows."""
    print(f"\n  sweep {knob} over {values}")
    print(f"    {'value':>10} {'s1_med':>9} {'s2_std':>9} {'sigma':>9} "
          f"{'delta':>7} {'r2':>6}")
    metrics = {k: [] for k in ("s1_median", "s2_std", "sigma", "delta")}
    for v in values:
        cfg = dataclasses.replace(baseline(), **{knob: v})
        p = probe(cfg, n_moment, n_delta)
        for k in metrics:
            metrics[k].append(p[k])
        print(f"    {str(v):>10} {p['s1_median']:>+9.4f} {p['s2_std']:>9.4f} "
              f"{p['sigma']:>9.4f} {p['delta']:>7.3f} {p['r2']:>6.2f}")
        history.append({"knob": knob, "value": v, **{k: round(p[k], 6) for k in p}})
    # robustness line: relative peak-to-peak span of each metric over the sweep
    spans = {k: _span(metrics[k])[1] for k in metrics}
    print(f"    rel.span:  s1={spans['s1_median']*100:4.0f}%  "
          f"s2std={spans['s2_std']*100:4.0f}%  sigma={spans['sigma']*100:4.0f}%  "
          f"delta={spans['delta']*100:4.0f}%   (small => robust to this scale knob)")
    return spans


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="abm.sensitivity",
        description="V<->ADV anchoring + scale sensitivity (calibration D)")
    p.add_argument("--knob", choices=list(SWEEPS), default=None,
                   help="sweep only this knob (default: all)")
    p.add_argument("--moment-seeds", type=int, default=30)
    p.add_argument("--delta-seeds", type=int, default=15)
    args = p.parse_args(argv)

    print("[sensitivity] V is anchored to ADV by construction (Qover_V = Q/ADV);")
    print("              this stress-tests the UN-anchored sim scale knobs.")
    print(f"              targets for reference: {TARGETS}")

    knobs = [args.knob] if args.knob else list(SWEEPS)
    history, spans = [], {}
    for knob in knobs:
        spans[knob] = sweep_knob(knob, SWEEPS[knob],
                                 args.moment_seeds, args.delta_seeds, history)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "sensitivity.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["knob", "value", "s1_median", "s2_std",
                                          "sigma", "delta", "r2"])
        w.writeheader()
        w.writerows(history)
    print(f"\n  wrote {out}  ({len(history)} rows)")

    print("\n  SUMMARY -- relative peak-to-peak span per knob (small = robust):")
    for knob in knobs:
        s = spans[knob]
        print(f"    {knob:<18} s1={s['s1_median']*100:4.0f}%  "
              f"s2std={s['s2_std']*100:4.0f}%  sigma={s['sigma']*100:4.0f}%  "
              f"delta={s['delta']*100:4.0f}%")


if __name__ == "__main__":
    main()
